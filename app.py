import streamlit as st
import pandas as pd
import json
import threading
import uuid
import math
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh
import joblib


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Hydro-Trace | AI Water-Saving Engine",
    page_icon="💧",
    layout="wide"
)


# =========================================================
# 2. PROFESSIONAL BLUE & WHITE THEME
# =========================================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(135deg, #f4f8ff 0%, #edf4ff 100%);
    color: #17365d;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.hero {
    background: linear-gradient(120deg, #073b75, #0878c9, #20a4e8);
    padding: 30px 35px;
    border-radius: 18px;
    color: white;
    margin-bottom: 25px;
    box-shadow: 0 8px 25px rgba(0, 73, 145, 0.18);
}

.hero h1 {
    color: white !important;
    font-size: 34px !important;
    font-weight: 800 !important;
    margin-bottom: 8px;
}

.hero p {
    color: #e4f3ff !important;
    font-size: 15px;
    margin-bottom: 0;
}

h2, h3 {
    color: #07549a !important;
    font-weight: 750 !important;
}

h4 {
    color: #1477bd !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #e5f1ff, #f7fbff);
    border-right: 1px solid #c9ddf4;
}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #064b89 !important;
}

[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #d8e8f8;
    border-radius: 13px;
    padding: 15px 17px;
    box-shadow: 0 3px 12px rgba(30, 90, 150, 0.07);
}

[data-testid="stMetricLabel"] {
    color: #52718f !important;
    font-weight: 600;
}

[data-testid="stMetricValue"] {
    color: #07549a !important;
    font-weight: 800;
}

.stButton > button {
    background: linear-gradient(110deg, #07549a, #168bd4);
    color: white;
    border: none;
    border-radius: 9px;
    padding: 9px 18px;
    font-weight: 650;
    transition: 0.2s ease;
}

.stButton > button:hover {
    background: linear-gradient(110deg, #043c73, #0875bd);
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 90, 160, 0.2);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(110deg, #034b91, #078de0);
}

[data-testid="stDataFrame"] {
    border: 1px solid #d6e6f5;
    border-radius: 12px;
    overflow: hidden;
    background: white;
}

.stProgress > div > div > div {
    background: linear-gradient(90deg, #0878c9, #35b6ed);
}

[data-testid="stAlert"] {
    border-radius: 11px;
}

.stSelectbox > div > div,
.stNumberInput input,
.stTextInput input {
    border-radius: 9px;
}

hr {
    border-color: #cbdff2 !important;
}

[data-testid="stCaptionContainer"] {
    color: #64809c;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. DASHBOARD HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <h1>💧 HYDRO-TRACE</h1>
    <p>
        AI-Powered Smart Data Center Cooling & Workload Management
        <br>
       ESP32 • MQTT • Machine Learning • Smart Scheduling
    </p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 4. MQTT SETTINGS
# =========================================================

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 8000

MQTT_TOPIC = "mini-dc-demo-7f3a91/telemetry"
MQTT_COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"


MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 8000

MQTT_TOPIC = "mini-dc-demo-7f3a91/telemetry"
MQTT_COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"


# =========================================================
# 3. MQTT SUBSCRIBER
# =========================================================

@st.cache_resource
def start_mqtt_subscriber():

    state = {
        "connected": False,
        "latest": None,
        "last_seen": None,
        "error": None,
        "history": [],
        "lock": threading.Lock()
    }

    def on_connect(client, userdata, flags, rc):

        with state["lock"]:
            state["connected"] = (rc == 0)
            state["error"] = (
                None if rc == 0
                else f"MQTT connection code: {rc}"
            )

        if rc == 0:
            client.subscribe(MQTT_TOPIC, qos=0)

    def on_disconnect(client, userdata, rc):

        with state["lock"]:
            state["connected"] = False

            if rc != 0:
                state["error"] = (
                    f"MQTT disconnected (code {rc}); reconnecting..."
                )

    def on_message(client, userdata, msg):

        try:

            payload = json.loads(
                msg.payload.decode("utf-8")
            )

            required = [
                "zone1_temp",
                "zone2_temp",
                "fan1_speed",
                "fan2_speed"
            ]

            if not all(key in payload for key in required):
                raise ValueError(
                    "MQTT message is missing required fields."
                )

            # Temperature
            zone1_temp = float(payload["zone1_temp"])
            zone2_temp = float(payload["zone2_temp"])

            if not all(
                math.isfinite(x) and 0 <= x <= 100
                for x in [zone1_temp, zone2_temp]
            ):
                raise ValueError("Invalid temperature reading.")

            # Humidity
            humidity = payload.get("humidity")

            if humidity is not None:
                humidity = float(humidity)

                if not math.isfinite(humidity) or not 0 <= humidity <= 100:
                    raise ValueError(
                        "Humidity must be between 0 and 100%."
                    )

            # Water flow
            water_flow = payload.get("water_flow")

            if water_flow is not None:
                water_flow = float(water_flow)

                if (
                    not math.isfinite(water_flow)
                    or not 0 <= water_flow <= 20
                ):
                    raise ValueError(
                        "Water flow must be between 0 and 20 L/min."
                    )

            # Fan speeds
            fan1_speed = int(payload["fan1_speed"])
            fan2_speed = int(payload["fan2_speed"])

            if not (
                0 <= fan1_speed <= 100
                and 0 <= fan2_speed <= 100
            ):
                raise ValueError(
                    "Fan speed must be between 0 and 100."
                )

            clean = {
                "zone1_temp": zone1_temp,
                "zone2_temp": zone2_temp,
                "humidity": humidity,
                "water_flow": water_flow,
                "fan1_speed": fan1_speed,
                "fan2_speed": fan2_speed
            }

            with state["lock"]:

                state["latest"] = clean

                now = datetime.now()
                state["last_seen"] = now.strftime("%H:%M:%S")

                # Save telemetry for live graphs.
                # Water flow is included in history.
                state["history"].append({
                    "Time": now,
                    "Zone 1 Temperature": zone1_temp,
                    "Zone 2 Temperature": zone2_temp,
                    "Fan 1 Speed": fan1_speed,
                    "Fan 2 Speed": fan2_speed,
                    "Water Flow (L/min)": water_flow
                })

                if len(state["history"]) > 300:
                    state["history"] = state["history"][-300:]

                state["error"] = None

        except Exception as exc:

            with state["lock"]:
                state["error"] = str(exc)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"hydro-trace-dashboard-{uuid.uuid4().hex[:8]}",
        transport="websockets"
    )

    client.ws_set_options(path="/mqtt")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    client.reconnect_delay_set(
        min_delay=2,
        max_delay=30
    )

    try:

        client.connect_async(
            MQTT_HOST,
            MQTT_PORT,
            keepalive=45
        )

        client.loop_start()

    except Exception as exc:

        state["error"] = str(exc)

    return {
        "state": state,
        "client": client
    }


mqtt_connection = start_mqtt_subscriber()
mqtt_state = mqtt_connection["state"]


def get_mqtt_snapshot():

    with mqtt_state["lock"]:

        return {
            "connected": mqtt_state["connected"],
            "latest": (
                dict(mqtt_state["latest"])
                if mqtt_state["latest"]
                else None
            ),
            "last_seen": mqtt_state["last_seen"],
            "error": mqtt_state["error"],
            "history": list(mqtt_state["history"])
        }


# =========================================================
# 4. LOAD ML COOLING MODEL
# =========================================================

@st.cache_resource
def load_cooling_model():

    model_path = Path(__file__).parent / "cooling_model.pkl"

    if not model_path.exists():

        raise FileNotFoundError(
            "cooling_model.pkl not found. "
            "Upload it to the same GitHub folder as app.py."
        )

    return joblib.load(model_path)


cooling_model = load_cooling_model()


def make_cooling_features(node_data):

    return pd.DataFrame(
        [{
            "temperature": node_data["temperature"],
            "cpu_usage": node_data["cpu"],
            "ram_usage": node_data["ram"],
            "temp_trend": 0.5
        }],
        columns=[
            "temperature",
            "cpu_usage",
            "ram_usage",
            "temp_trend"
        ]
    )


# =========================================================
# 5. APPLICATION CATALOG
# =========================================================

app_catalog = {

    "Web application": {
        "cpu": 15,
        "ram": 15,
        "heat": 0.15,
        "description": "Small web service demo"
    },

    "Data processing": {
        "cpu": 35,
        "ram": 25,
        "heat": 0.35,
        "description": "Batch data-processing demo"
    },

    "ML inference": {
        "cpu": 30,
        "ram": 30,
        "heat": 0.30,
        "description": "Machine-learning inference demo"
    },

    "Heavy Analytics": {
        "cpu": 60,
        "ram": 50,
        "heat": 0.60,
        "description": "High workload demo"
    }
}


# =========================================================
# 6. DEFAULT VIRTUAL SERVERS
# =========================================================

DEFAULT_NODES = {

    "Virtual Raspberry Pi 1": {
        "temperature": 35.0,
        "base_cpu": 20.0,
        "base_ram": 20.0,
        "cpu": 20.0,
        "ram": 20.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    },

    "Virtual Raspberry Pi 2": {
        "temperature": 32.0,
        "base_cpu": 20.0,
        "base_ram": 20.0,
        "cpu": 20.0,
        "ram": 20.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    }
}


# =========================================================
# 7. SHARED DEMO STATE
# =========================================================

@st.cache_resource
def get_shared_demo_state():

    return {
        "nodes": {
            name: {**data, "apps": []}
            for name, data in DEFAULT_NODES.items()
        },
        "deployments": [],
        "logs": [],
        "last_decision": None
    }


shared_demo_state = get_shared_demo_state()

st.session_state.nodes = shared_demo_state["nodes"]
st.session_state.deployments = shared_demo_state["deployments"]
st.session_state.logs = shared_demo_state["logs"]
st.session_state.last_decision = shared_demo_state["last_decision"]


# Recover missing fields from older sessions
for name, default_data in DEFAULT_NODES.items():

    if name not in st.session_state.nodes:
        st.session_state.nodes[name] = {
            **default_data,
            "apps": []
        }

    node = st.session_state.nodes[name]

    node.setdefault("base_cpu", 20.0)
    node.setdefault("base_ram", 20.0)
    node.setdefault("heat_load", 0.0)
    node.setdefault("online", True)
    node.setdefault("apps", [])

    converted_apps = []

    for app in node["apps"]:

        if isinstance(app, dict) and "id" in app:
            converted_apps.append(app)

        elif isinstance(app, str) and app in app_catalog:

            requirements = app_catalog[app]

            converted_apps.append({
                "id": str(uuid.uuid4())[:8],
                "app": app,
                "node": name,
                "cpu": requirements["cpu"],
                "ram": requirements["ram"],
                "heat": requirements["heat"],
                "time": "Previous deployment"
            })

    node["apps"] = converted_apps


# Rebuild deployment records
all_deployments = []

for name, node in st.session_state.nodes.items():

    for app in node["apps"]:
        app["node"] = name
        all_deployments.append(app)

st.session_state.deployments = all_deployments
shared_demo_state["deployments"] = st.session_state.deployments


def recalculate_server_resources():

    for name, node in st.session_state.nodes.items():

        node["cpu"] = node["base_cpu"] + sum(
            app["cpu"] for app in node["apps"]
        )

        node["ram"] = node["base_ram"] + sum(
            app["ram"] for app in node["apps"]
        )

        node["heat_load"] = min(
            2.0,
            sum(app["heat"] for app in node["apps"])
        )


recalculate_server_resources()

nodes = st.session_state.nodes
mqtt_snapshot = get_mqtt_snapshot()


# =========================================================
# 8. SIMULATION CONTROLS
# =========================================================

st.sidebar.header("⚙️ Simulation Controls")

live_mode = st.sidebar.toggle(
    "Use live Wokwi ESP32 readings",
    value=True,
    key="live_mode"
)

if live_mode:

    st_autorefresh(
        interval=2000,
        key="mqtt_dashboard_refresh"
    )
    st.sidebar.caption(
    "Temperature and humidity arrive through Wokwi MQTT. "
    "Virtual water flow is calculated by ESP32 using fan speed."
    )


else:

    st.sidebar.caption(
        "Manual demo mode: readings are simulated."
    )


# Apply ESP32 temperatures to virtual nodes
if live_mode and mqtt_snapshot["latest"]:

    nodes["Virtual Raspberry Pi 1"]["temperature"] = (
        mqtt_snapshot["latest"]["zone1_temp"]
    )

    nodes["Virtual Raspberry Pi 2"]["temperature"] = (
        mqtt_snapshot["latest"]["zone2_temp"]
    )


# Sidebar node controls
for i, name in enumerate(nodes):

    node = nodes[name]

    st.sidebar.subheader(name)

    node["online"] = st.sidebar.toggle(
        f"{name} online",
        value=node["online"],
        key=f"online_{i}"
    )

    if not (live_mode and mqtt_snapshot["latest"]):

        node["temperature"] = st.sidebar.slider(
            f"{name} temperature (°C)",
            20.0,
            80.0,
            float(
                min(
                    80.0,
                    max(20.0, node["temperature"])
                )
            ),
            0.5,
            key=f"temp_{i}"
        )

    else:

        st.sidebar.metric(
            f"{name} live temperature",
            f'{node["temperature"]:.1f} °C'
        )

    node["base_cpu"] = st.sidebar.slider(
        f"{name} Base CPU usage (%)",
        0.0,
        100.0,
        float(node["base_cpu"]),
        1.0,
        key=f"cpu_{i}"
    )

    node["base_ram"] = st.sidebar.slider(
        f"{name} Base RAM usage (%)",
        0.0,
        100.0,
        float(node["base_ram"]),
        1.0,
        key=f"ram_{i}"
    )


recalculate_server_resources()


# =========================================================
# 9. RESET DEMONSTRATION
# =========================================================

if st.sidebar.button("↺ Reset demonstration"):

    st.session_state.nodes = {
        name: {**data, "apps": []}
        for name, data in DEFAULT_NODES.items()
    }

    st.session_state.deployments = []
    st.session_state.logs = []
    st.session_state.last_decision = None

    shared_demo_state["nodes"] = st.session_state.nodes
    shared_demo_state["deployments"] = st.session_state.deployments
    shared_demo_state["logs"] = st.session_state.logs
    shared_demo_state["last_decision"] = st.session_state.last_decision

    st.rerun()


# =========================================================
# 10. PROJECT INFORMATION
# =========================================================

st.info(
    "Workload assignments are kept in shared in-memory state, "
    "so they survive browser refreshes while this Streamlit app "
    "process remains running. ESP32 telemetry is received through MQTT. "
    "Temperature and humidity are simulated/read through Wokwi components. "
    "Water flow is calculated virtually by ESP32 from average fan speed. "
    "Raspberry Pi nodes, CPU/RAM values and cooling model remain virtual simulations."
)

# =========================================================
# 11. ESP32 MQTT CONNECTION DISPLAY
# =========================================================

st.subheader("0. ESP32 → MQTT Live Sensor Data")

if mqtt_snapshot["connected"]:

    st.success(
        f"MQTT connected to {MQTT_HOST}:{MQTT_PORT} "
        f"and listening on {MQTT_TOPIC}."
    )

else:

    st.warning(
        "Connecting to MQTT broker. "
        "Start Wokwi simulation and wait for telemetry."
    )


if mqtt_snapshot["error"]:

    st.caption(
        f"Connection/message detail: {mqtt_snapshot['error']}"
    )


if mqtt_snapshot["latest"]:

    live = mqtt_snapshot["latest"]

    m1, m2, m3 = st.columns(3)
    m4, m5, m6 = st.columns(3)

    m1.metric(
        "Zone 1 Temperature",
        f'{live["zone1_temp"]:.1f} °C'
    )

    m2.metric(
        "Zone 2 Temperature",
        f'{live["zone2_temp"]:.1f} °C'
    )

    humidity = live.get("humidity")

    m3.metric(
        "Live Humidity (DHT22)",
        f"{humidity:.1f}%" if humidity is not None
        else "Not available"
    )

    water_flow = live.get("water_flow")

    m4.metric(
        "Simulated Water Flow",
        f"{water_flow:.2f} L/min"
        if water_flow is not None
        else "Not available"
    )

    m5.metric(
        "Fan 1 Command",
        f'{live["fan1_speed"]}%'
    )

    m6.metric(
        "Fan 2 Command",
        f'{live["fan2_speed"]}%'
    )

    st.caption(
        f"Last ESP32 message received at "
        f"{mqtt_snapshot['last_seen']}."
    )
    st.caption(
    "Virtual water flow is automatically calculated by ESP32 "
    "from average fan speed (0–100%), with a simulated range "
    "of 0–20 L/min. It is not a physical water-flow measurement."
    )

  

else:

    st.caption(
        "No ESP32 telemetry received yet. "
        "Check Wokwi MQTT connection and topic."
    )

# =========================================================
# 12. LIVE TEMPERATURE, FAN AND WATER FLOW GRAPHS
# =========================================================

st.divider()
st.subheader("📈 Live Temperature and Cooling Analytics")

history = mqtt_snapshot.get("history", [])

if history:

    history_df = pd.DataFrame(history)

    history_df["Time"] = pd.to_datetime(
        history_df["Time"]
    )

    history_df = history_df.set_index("Time")

    # -------------------------------------
    # TEMPERATURE GRAPH
    # -------------------------------------

    st.markdown("### 🌡️ Temperature vs Time")

    temperature_df = history_df[[
        "Zone 1 Temperature",
        "Zone 2 Temperature"
    ]]

    st.line_chart(
        temperature_df,
        y_label="Temperature (°C)",
        x_label="Time",
        height=300
    )

    # -------------------------------------
    # FAN SPEED GRAPH
    # -------------------------------------

    st.markdown("### 🌀 Fan Speed vs Time")

    fan_df = history_df[[
        "Fan 1 Speed",
        "Fan 2 Speed"
    ]]

    st.line_chart(
        fan_df,
        y_label="Fan Speed (%)",
        x_label="Time",
        height=300
    )

    # -------------------------------------
    # WATER FLOW VS TIME
    # -------------------------------------

    st.markdown("### 💧 Water Flow Rate vs Time")

    if (
        "Water Flow (L/min)" in history_df.columns
        and history_df["Water Flow (L/min)"].notna().any()
    ):

        water_flow_df = history_df[
            ["Water Flow (L/min)"]
        ].dropna()

        st.line_chart(
            water_flow_df,
            y_label="Virtual Water Flow (L/min)",
            x_label="Time",
            height=300
        )

    else:

        st.info(
            "Waiting for calculated water-flow values "
            "from ESP32 MQTT telemetry."
        )

    # -------------------------------------
    # WATER FLOW VS AVERAGE FAN SPEED
    # -------------------------------------

    st.markdown(
        "### 💧🌀 Water Flow vs Average Fan Speed"
    )

    relationship_df = history_df[
        [
            "Water Flow (L/min)",
            "Fan 1 Speed",
            "Fan 2 Speed"
        ]
    ].dropna(
        subset=["Water Flow (L/min)"]
    ).copy()

    if not relationship_df.empty:

        relationship_df["Average Fan Speed (%)"] = (
            relationship_df["Fan 1 Speed"]
            + relationship_df["Fan 2 Speed"]
        ) / 2

        st.scatter_chart(
            relationship_df,
            x="Average Fan Speed (%)",
            y="Water Flow (L/min)",
            x_label="Average Fan Speed (%)",
            y_label="Virtual Water Flow (L/min)",
            height=350
        )

    else:

        st.info(
            "Waiting for fan-speed and water-flow readings."
        )

    st.caption(
        "All graphs display ESP32 telemetry received through MQTT. "
        "The latest 300 readings are kept in memory; history resets "
        "when the Streamlit app process restarts. "
        "Water flow is a simulated value calculated from average fan speed, "
        "not a physical water-flow measurement."
    )

else:

    st.info(
        "Waiting for ESP32 telemetry. Start the Wokwi simulation "
        "to display live temperature, fan-speed and virtual water-flow graphs."
    )

# =========================================================
# COOLING PERFORMANCE ANALYTICS
# =========================================================

st.markdown("---")
st.subheader("❄️ Cooling Performance Analytics")

analytics_history = mqtt_snapshot.get("history", [])

if analytics_history:

    analytics_df = pd.DataFrame(analytics_history)

    latest = analytics_df.iloc[-1]

    # Current readings
    temp1 = float(latest.get("Zone 1 Temperature", 20))
    temp2 = float(latest.get("Zone 2 Temperature", 20))

    fan1 = float(latest.get("Fan 1 Speed", 0))
    fan2 = float(latest.get("Fan 2 Speed", 0))

    water_flow = float(latest.get("Water Flow (L/min)", 0))

    avg_fan_speed = (fan1 + fan2) / 2
    avg_temperature = (temp1 + temp2) / 2
    max_temperature = max(temp1, temp2)

    # Temperature trend from previous reading
    if len(analytics_df) >= 2:
        previous = analytics_df.iloc[-2]

        previous_avg_temp = (
            float(previous.get("Zone 1 Temperature", temp1)) +
            float(previous.get("Zone 2 Temperature", temp2))
        ) / 2

        temperature_change = avg_temperature - previous_avg_temp
    else:
        temperature_change = 0.0

    # Demo cooling status
    if max_temperature < 40:
        cooling_status = "Normal"
    elif max_temperature < 48:
        cooling_status = "Monitor"
    else:
        cooling_status = "High Temperature"

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Average Temperature",
        f"{avg_temperature:.1f} °C",
        f"{temperature_change:+.2f} °C"
    )

    c2.metric(
        "Average Fan Speed",
        f"{avg_fan_speed:.0f}%"
    )

    c3.metric(
        "Virtual Water Flow",
        f"{water_flow:.2f} L/min"
    )

    c4.metric(
        "Cooling Status",
        cooling_status
    )

    st.markdown("### Zone-wise Cooling Response")

    zone1_status = (
        "Normal" if temp1 < 40
        else "Monitor" if temp1 < 48
        else "High Temperature"
    )

    zone2_status = (
        "Normal" if temp2 < 40
        else "Monitor" if temp2 < 48
        else "High Temperature"
    )

    zone_data = pd.DataFrame({
        "Zone": ["Zone 1", "Zone 2"],
        "Temperature (°C)": [temp1, temp2],
        "Fan Speed (%)": [fan1, fan2],
        "Cooling Status": [zone1_status, zone2_status]
    })

    st.dataframe(
        zone_data,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Temperature change shows the difference from the previous "
        "telemetry reading. Water flow is simulated from average fan speed. "
        "Cooling status uses demo thresholds, not real hardware safety limits."
    )

else:
    st.info(
        "Waiting for ESP32 telemetry. Cooling analytics will appear "
        "when live readings are received."
    )

# =========================================================
# VIRTUAL POWER CONSUMPTION ANALYTICS
# =========================================================

st.divider()
st.subheader("⚡ Power Consumption Analytics")

# Calculate estimated power for each virtual server
def calculate_virtual_power(node, fan_speed):

    power = (
        2.5
        + (node["cpu"] * 0.035)
        + (node["ram"] * 0.015)
        + (fan_speed * 0.005)
    )

    return round(power, 2)


power_rows = []
total_power = 0.0

for name, node in nodes.items():

    fan_speed = final_fan_commands[name]

    estimated_power = calculate_virtual_power(
        node,
        fan_speed
    )

    total_power += estimated_power

    power_rows.append({
        "Virtual Server": name,
        "CPU Usage": f'{node["cpu"]:.0f}%',
        "RAM Usage": f'{node["ram"]:.0f}%',
        "Fan Speed": f"{fan_speed}%",
        "Estimated Power (W)": f"{estimated_power:.2f} W"
    })


# Display server-wise power consumption
st.markdown("#### Server-wise Power Usage")

st.dataframe(
    pd.DataFrame(power_rows),
    use_container_width=True,
    hide_index=True
)


# Display total power and energy
st.markdown("#### Overall Energy Summary")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Estimated Power",
    f"{total_power:.2f} W"
)

col2.metric(
    "Hourly Energy",
    f"{total_power / 1000:.4f} kWh"
)

col3.metric(
    "Daily Energy",
    f"{(total_power * 24) / 1000:.3f} kWh"
)


# Power consumption chart
st.markdown("#### Power Usage by Server")

power_chart_df = pd.DataFrame(power_rows)

power_chart_df["Power (W)"] = [
    float(row["Estimated Power (W)"].replace(" W", ""))
    for row in power_rows
]

st.bar_chart(
    power_chart_df.set_index("Virtual Server")[["Power (W)"]],
    height=250
)

st.caption(
    "Power consumption values are virtual estimates "
    "calculated using CPU, RAM and fan speed. "
    "They are not measured using physical power sensors."
)

# =========================================================
# 14. APPLICATION SUBMISSION
# =========================================================

st.divider()
st.subheader("2. Submit a New Application")

left, right = st.columns([2, 1])

with left:

    selected_app = st.selectbox(
        "Choose Application",
        list(app_catalog.keys())
    )

    st.caption(
        app_catalog[selected_app]["description"]
    )

with right:

    req = app_catalog[selected_app]

    st.metric(
        "Estimated CPU Requirement",
        f'{req["cpu"]}%'
    )

    st.metric(
        "Estimated RAM Requirement",
        f'{req["ram"]}%'
    )

    st.metric(
        "Estimated Heat Load",
        f'{req["heat"]:.2f}'
    )


# =========================================================
# 15. AUTOMATIC WORKLOAD SCHEDULER
# =========================================================

def choose_node(app_req):

    candidates = []
    rejected = []

    for name, node in nodes.items():

        reasons = []

        if not node["online"]:
            reasons.append("Server offline")

        if node["temperature"] >= 48:
            reasons.append("Temperature safety threshold reached")

        if node["cpu"] + app_req["cpu"] > 90:
            reasons.append("Insufficient CPU headroom")

        if node["ram"] + app_req["ram"] > 90:
            reasons.append("Insufficient RAM headroom")

        if reasons:

            rejected.append({
                "server": name,
                "reasons": reasons
            })

            continue

        score = (
            (node["temperature"] / 50) * 0.40
            + (node["cpu"] / 100) * 0.35
            + (node["ram"] / 100) * 0.25
        )

        candidates.append((score, name))

    if not candidates:
        return None, rejected

    candidates.sort()

    return candidates[0][1], rejected


# =========================================================
# 16. ASSIGN APPLICATION
# =========================================================

if st.button(
    "🚀 Submit Application — Automatic Placement",
    type="primary"
):

    chosen, rejected = choose_node(req)

    if chosen is None:

        st.session_state.last_decision = {
            "status": "Rejected",
            "app": selected_app,
            "node": None,
            "reason": "No suitable server available"
        }

        shared_demo_state["last_decision"] = (
            st.session_state.last_decision
        )

        st.session_state.logs.insert(
            0,
            f"REJECTED: {selected_app} — no suitable server available"
        )

    else:

        node = nodes[chosen]

        deployment = {

            "id": str(uuid.uuid4())[:8],
            "app": selected_app,
            "node": chosen,
            "cpu": req["cpu"],
            "ram": req["ram"],
            "heat": req["heat"],
            "time": datetime.now().strftime("%H:%M:%S")
        }

        node["apps"].append(deployment)

        st.session_state.deployments.append(deployment)

        recalculate_server_resources()

        st.session_state.last_decision = {

            "status": "Deployed",
            "app": selected_app,
            "node": chosen,

            "reason": (
                "Best eligible server selected after "
                "temperature, CPU and RAM checks."
            )
        }

        shared_demo_state["last_decision"] = (
            st.session_state.last_decision
        )

        st.session_state.logs.insert(
            0,
            f"DEPLOYED: {selected_app} -> {chosen}"
        )

    st.rerun()


# =========================================================
# 17. LAST DEPLOYMENT DECISION
# =========================================================

if st.session_state.last_decision:

    decision = st.session_state.last_decision

    if decision["status"] == "Deployed":

        st.success(
            f'Application "{decision["app"]}" deployed to '
            f'**{decision["node"]}**.'
        )

        st.caption(decision["reason"])

    else:

        st.error(
            f'Application "{decision["app"]}" was not deployed: '
            f'{decision["reason"]}.'
        )

        st.caption(
            "Check server status, CPU, RAM and temperature capacity."
        )


# =========================================================
# 18. RUNNING APPLICATIONS
# =========================================================

st.divider()
st.subheader("3. Running Applications")

if st.session_state.deployments:

    deployment_rows = []

    for deployment in st.session_state.deployments:

        deployment_rows.append({

            "Application": deployment["app"],
            "Server": deployment["node"],
            "CPU": f'{deployment["cpu"]}%',
            "RAM": f'{deployment["ram"]}%',
            "Heat": f'{deployment["heat"]:.2f}',
            "Deployment ID": deployment["id"],
            "Time": deployment["time"]
        })

    st.dataframe(
        pd.DataFrame(deployment_rows),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("No applications are currently deployed.")


# =========================================================
# 19. REMOVE APPLICATION
# =========================================================

st.divider()
st.subheader("4. Remove a Running Application")

if st.session_state.deployments:

    deployment_options = {

        f'{d["app"]} | {d["node"]} | ID: {d["id"]}': d["id"]

        for d in st.session_state.deployments
    }

    selected_deployment = st.selectbox(
        "Select Application to Remove",
        list(deployment_options.keys()),
        key="remove_application_select"
    )

    if st.button("🗑️ Remove Selected Application"):

        deployment_id = deployment_options[selected_deployment]

        deployment_to_remove = next(
            (
                d for d in st.session_state.deployments
                if d["id"] == deployment_id
            ),
            None
        )

        if deployment_to_remove:

            server_name = deployment_to_remove["node"]
            server = nodes[server_name]

            server["apps"] = [
                app for app in server["apps"]
                if app["id"] != deployment_id
            ]

            recalculate_server_resources()

            st.session_state.deployments = [
                d for d in st.session_state.deployments
                if d["id"] != deployment_id
            ]

            shared_demo_state["deployments"] = (
                st.session_state.deployments
            )

            st.session_state.logs.insert(
                0,
                f'REMOVED: {deployment_to_remove["app"]} '
                f'from {server_name}'
            )

            st.session_state.last_decision = {

                "status": "Removed",
                "app": deployment_to_remove["app"],
                "node": server_name,
                "reason": "Application resources released successfully"
            }

            shared_demo_state["last_decision"] = (
                st.session_state.last_decision
            )

            st.rerun()

else:

    st.info("There are no running applications to remove.")


# =========================================================
# 20. ML-BASED COOLING PREDICTION
# =========================================================

st.divider()
st.subheader("5. ML-Based Cooling Prediction")

cool_rows = []
fan_commands = {}

for name, node in nodes.items():

    features = make_cooling_features(node)

    prediction = cooling_model.predict(features)[0]

    probabilities = cooling_model.predict_proba(features)[0]

    confidence = float(max(probabilities) * 100)

    fan = {
        "Low": 30,
        "Medium": 60,
        "High": 90
    }[prediction]

    fan_commands[name] = fan

    cool_rows.append({

        "Virtual Zone": name,
        "Predicted Cooling": prediction,
        "Suggested Virtual Fan Speed": f"{fan}%",
        "Model Confidence": f"{confidence:.0f}%"
    })


st.dataframe(
    pd.DataFrame(cool_rows),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "ML note: Random Forest is trained on synthetic demonstration data. "
    "Its predictions demonstrate the ML pipeline and are not calibrated "
    "for real server thermal safety."
)


# =========================================================
# 21. VIRTUAL COOLING RESPONSE
# =========================================================

st.divider()
st.subheader("6. Virtual Cooling Response")

manual_mode = st.toggle(
    "Enable Manual Fan Control",
    value=False,
    key="manual_fan_control"
)


if manual_mode:

    manual_cols = st.columns(2)

    manual_fan1 = manual_cols[0].slider(
        "Pi 1 Manual Fan Speed",
        0,
        100,
        60,
        key="manual_fan1"
    )

    manual_fan2 = manual_cols[1].slider(
        "Pi 2 Manual Fan Speed",
        0,
        100,
        60,
        key="manual_fan2"
    )

    final_fan_commands = {

        "Virtual Raspberry Pi 1": manual_fan1,
        "Virtual Raspberry Pi 2": manual_fan2
    }

    st.info(
        "Manual mode active. Slider values control fan commands."
    )

else:

    final_fan_commands = fan_commands

    st.success(
        "Automatic ML Cooling Control is Active."
    )


fan_cols = st.columns(2)

for col, (name, node) in zip(fan_cols, nodes.items()):

    fan = final_fan_commands[name]

    if manual_mode:
        prediction = "Manual"

    else:
        prediction = cooling_model.predict(
            make_cooling_features(node)
        )[0]

    with col:

        st.write(f"**{name} — Virtual Fan**")

        st.progress(
            fan,
            text=f"Simulated Fan Command: {fan}% ({prediction})"
        )

        if st.button(
            f"Apply Simulated Cooling to {name}",
            key=f"cool_{name}"
        ):

            if live_mode and mqtt_snapshot["latest"]:

                st.warning(
                    "Live temperature is controlled by ESP32 telemetry. "
                    "Use fan control to change the live fan command."
                )

            else:

                node["temperature"] = max(
                    22.0,
                    node["temperature"] - fan * 0.035
                )

                st.session_state.logs.insert(
                    0,
                    f"SIMULATED COOLING: {name}, fan {fan}%"
                )

                st.rerun()


# =========================================================
# 22. SINGLE MQTT COMMAND PUBLISH BLOCK
# =========================================================

final_payload = {

    "fan1_speed": int(
        final_fan_commands["Virtual Raspberry Pi 1"]
    ),

    "fan2_speed": int(
        final_fan_commands["Virtual Raspberry Pi 2"]
    ),

    "zone1_heat": float(
        nodes["Virtual Raspberry Pi 1"]["heat_load"]
    ),

    "zone2_heat": float(
        nodes["Virtual Raspberry Pi 2"]["heat_load"]
    )
}


command_status = "Waiting for MQTT connection"

if mqtt_snapshot["connected"]:

    try:

        result = mqtt_connection["client"].publish(
            MQTT_COMMAND_TOPIC,
            json.dumps(final_payload),
            qos=0,
            retain=False
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            command_status = "Cooling commands sent to ESP32."

        else:

            command_status = f"MQTT publish error: {result.rc}"

    except Exception as exc:

        command_status = f"Could not publish fan commands: {exc}"

else:

    command_status = "Waiting for MQTT connection."


st.info(
    f"{command_status} | "
    f"Fan 1: {final_payload['fan1_speed']}% | "
    f"Fan 2: {final_payload['fan2_speed']}%"
)

st.caption(
    f"Command topic: {MQTT_COMMAND_TOPIC}. "
    "Keep Wokwi ESP32 simulation running."
)


# =========================================================
# 23. EVENT LOG
# =========================================================

st.divider()
st.subheader("7. Execution and System Event Log")

if st.session_state.logs:

    for item in st.session_state.logs[:15]:
        st.write("•", item)

else:

    st.write("No application submissions yet.")




    unsafe_allow_html=True



