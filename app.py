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


# =========================================================
# 5. MQTT SUBSCRIBER
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

            zone1_temp = float(payload["zone1_temp"])
            zone2_temp = float(payload["zone2_temp"])

            if not all(
                math.isfinite(x) and 0 <= x <= 100
                for x in [zone1_temp, zone2_temp]
            ):
                raise ValueError("Invalid temperature reading.")

            humidity = payload.get("humidity")

            if humidity is not None:
                humidity = float(humidity)

                if not math.isfinite(humidity) or not 0 <= humidity <= 100:
                    raise ValueError("Invalid humidity reading.")

            water_flow = payload.get("water_flow")

            if water_flow is not None:
                water_flow = float(water_flow)

                if (
                    not math.isfinite(water_flow)
                    or not 0 <= water_flow <= 20
                ):
                    raise ValueError("Invalid water-flow reading.")

            fan1_speed = int(payload["fan1_speed"])
            fan2_speed = int(payload["fan2_speed"])

            if not (
                0 <= fan1_speed <= 100
                and 0 <= fan2_speed <= 100
            ):
                raise ValueError("Invalid fan speed.")

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
# 6. LOAD ML COOLING MODEL
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
# 7. APPLICATION CATALOG
# =========================================================

app_catalog = {

    "Web application": {
        "cpu": 15,
        "ram": 15,
        "gpu": 5,
        "heat": 0.15,
        "description": "Small web service demo"
    },

    "Data processing": {
        "cpu": 35,
        "ram": 25,
        "gpu": 15,
        "heat": 0.35,
        "description": "Batch data-processing demo"
    },

    "ML inference": {
        "cpu": 30,
        "ram": 30,
        "gpu": 35,
        "heat": 0.30,
        "description": "Machine-learning inference demo"
    },

    "Heavy Analytics": {
        "cpu": 60,
        "ram": 50,
        "gpu": 50,
        "heat": 0.60,
        "description": "High workload demo"
    }
}


# =========================================================
# 8. DEFAULT  SERVERS
# =========================================================

DEFAULT_NODES = {

    " Raspberry Pi 1": {
        "temperature": 35.0,
        "base_cpu": 20.0,
        "base_ram": 20.0,
        "base_gpu": 10.0,
        "cpu": 20.0,
        "ram": 20.0,
        "gpu": 10.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    },

    " Raspberry Pi 2": {
        "temperature": 32.0,
        "base_cpu": 20.0,
        "base_ram": 20.0,
        "base_gpu": 10.0,
        "cpu": 20.0,
        "ram": 20.0,
        "gpu": 10.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    }
}


# =========================================================
# 9. SHARED DEMO STATE
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


for name, default_data in DEFAULT_NODES.items():

    if name not in st.session_state.nodes:

        st.session_state.nodes[name] = {
            **default_data,
            "apps": []
        }

    node = st.session_state.nodes[name]

    node.setdefault("base_cpu", 20.0)
    node.setdefault("base_ram", 20.0)
    node.setdefault("base_gpu", 10.0)
    node.setdefault("gpu", 10.0)
    node.setdefault("heat_load", 0.0)
    node.setdefault("online", True)
    node.setdefault("apps", [])

    converted_apps = []

    for app in node["apps"]:

        if isinstance(app, dict) and "id" in app:

            app.setdefault(
                "gpu",
                app_catalog.get(app.get("app"), {}).get("gpu", 0)
            )

            app.setdefault("cpu", 0)
            app.setdefault("ram", 0)
            app.setdefault("heat", 0)

            converted_apps.append(app)

        elif isinstance(app, str) and app in app_catalog:

            requirements = app_catalog[app]

            converted_apps.append({

                "id": str(uuid.uuid4())[:8],
                "app": app,
                "node": name,
                "cpu": requirements["cpu"],
                "ram": requirements["ram"],
                "gpu": requirements["gpu"],
                "heat": requirements["heat"],
                "time": "Previous deployment"
            })

    node["apps"] = converted_apps


all_deployments = []

for name, node in st.session_state.nodes.items():

    for app in node["apps"]:
        app["node"] = name
        all_deployments.append(app)

st.session_state.deployments = all_deployments
shared_demo_state["deployments"] = st.session_state.deployments


# =========================================================
# 10. RESOURCE CALCULATION
# =========================================================

def recalculate_server_resources():

    for name, node in st.session_state.nodes.items():

        node["cpu"] = node["base_cpu"] + sum(
            app["cpu"] for app in node["apps"]
        )

        node["ram"] = node["base_ram"] + sum(
            app["ram"] for app in node["apps"]
        )

        node["gpu"] = node["base_gpu"] + sum(
            app.get("gpu", 0) for app in node["apps"]
        )

        node["heat_load"] = min(
            2.0,
            sum(app["heat"] for app in node["apps"])
        )


recalculate_server_resources()

nodes = st.session_state.nodes
mqtt_snapshot = get_mqtt_snapshot()


# =========================================================
# 11. SIMULATION CONTROLS
# =========================================================

st.sidebar.title("⚙️ Control Center")
st.sidebar.caption("Hydro-Trace Simulation Settings")

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
        "Live temperature and humidity arrive through Wokwi MQTT."
    )

else:

    st.sidebar.caption(
        "Manual demo mode: readings are simulated."
    )


if live_mode and mqtt_snapshot["latest"]:

    nodes[" Raspberry Pi 1"]["temperature"] = (
        mqtt_snapshot["latest"]["zone1_temp"]
    )

    nodes[" Raspberry Pi 2"]["temperature"] = (
        mqtt_snapshot["latest"]["zone2_temp"]
    )


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
            float(min(80.0, max(20.0, node["temperature"]))),
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

    node["base_gpu"] = st.sidebar.slider(
        f"{name} Base GPU usage (%)",
        0.0,
        100.0,
        float(node["base_gpu"]),
        1.0,
        key=f"gpu_{i}"
    )


recalculate_server_resources()


# =========================================================
# 12. RESET DEMONSTRATION
# =========================================================

if st.sidebar.button("↺ Reset Demonstration"):

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
# 13. PROJECT INFORMATION
# =========================================================

st.info(
    "Intelligent Data Center. Smarter Cooling. Sustainable Computing."
    "AI-Driven Thermal Intelligence & Workload Orchestration"
)
# =========================================================
# 14. ESP32 MQTT LIVE SENSOR MONITORING
# =========================================================

st.divider()
st.subheader("📡 ESP32 → MQTT Live Sensor Monitoring")

if mqtt_snapshot["connected"]:

    st.success(
        f"MQTT Connected | {MQTT_HOST}:{MQTT_PORT}"
    )

else:

    st.warning(
        "Connecting to MQTT broker. Start Wokwi simulation."
    )

if mqtt_snapshot["error"]:

    st.caption(
        f"Connection detail: {mqtt_snapshot['error']}"
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
        "Live Humidity",
        f"{humidity:.1f}%" if humidity is not None
        else "Not available"
    )

    water_flow = live.get("water_flow")

    m4.metric(
        " Water Flow",
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
        f"Last ESP32 message: {mqtt_snapshot['last_seen']}"
    )

    st.caption(
        "Water flow is a  value calculated from fan speed. "
        "It is not a physical water-flow measurement."
    )

else:

    st.info(
        "Waiting for ESP32 telemetry. "
        "Check Wokwi MQTT connection and topic."
    )


# =========================================================
# 15. LIVE MONITORING GRAPHS - 2 X 2 LAYOUT
# =========================================================

st.divider()
st.subheader("📊 Live Monitoring & Cooling Analytics")

history = mqtt_snapshot.get("history", [])

if history:

    history_df = pd.DataFrame(history)

    history_df["Time"] = pd.to_datetime(
        history_df["Time"]
    )

    history_df = history_df.set_index("Time")

    # -----------------------------------------------------
    # FIRST ROW - TWO GRAPHS
    # -----------------------------------------------------

    graph_col1, graph_col2 = st.columns(2, gap="large")

    # GRAPH 1 - TEMPERATURE

    with graph_col1:

        st.markdown("#### 🌡️ Temperature Monitoring")

        temperature_df = history_df[[
            "Zone 1 Temperature",
            "Zone 2 Temperature"
        ]]

        st.line_chart(
            temperature_df,
            y_label="Temperature (°C)",
            height=240
        )

        st.caption(
            "Live temperature comparison between both zones."
        )

    # GRAPH 2 - FAN SPEED

    with graph_col2:

        st.markdown("#### 🌀 Fan Speed Monitoring")

        fan_df = history_df[[
            "Fan 1 Speed",
            "Fan 2 Speed"
        ]]

        st.line_chart(
            fan_df,
            y_label="Fan Speed (%)",
            height=240
        )

        st.caption(
            " cooling fan commands received from ESP32."
        )

    # -----------------------------------------------------
    # SECOND ROW - TWO GRAPHS
    # -----------------------------------------------------

    graph_col3, graph_col4 = st.columns(2, gap="large")

    # GRAPH 3 - WATER FLOW

    with graph_col3:

        st.markdown("#### 💧  Water Flow")

        if (
            "Water Flow (L/min)" in history_df.columns
            and history_df["Water Flow (L/min)"].notna().any()
        ):

            water_flow_df = history_df[
                ["Water Flow (L/min)"]
            ].dropna()

            st.line_chart(
                water_flow_df,
                y_label="Flow (L/min)",
                height=240
            )

            st.caption(
                "Estimated water-flow simulation based on fan speed."
            )

        else:

            st.info(
                "Waiting for water-flow readings."
            )

    # GRAPH 4 - FAN SPEED VS WATER FLOW

    with graph_col4:

        st.markdown("#### 🔄 Fan Speed vs Water Flow")

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
                y_label="Flow (L/min)",
                height=240
            )

            st.caption(
                "Relationship between average fan speed and  flow."
            )

        else:

            st.info(
                "Waiting for fan-speed and water-flow readings."
            )

    st.caption(
        "Live graphs use ESP32 telemetry received through MQTT. "
        "Latest 300 readings are retained in memory."
    )

else:

    st.info(
        "📡 Waiting for ESP32 telemetry. "
        "Start Wokwi simulation to populate the live graphs."
    )


# =========================================================
# 16. COOLING PERFORMANCE ANALYTICS
# =========================================================

st.divider()
st.subheader("❄️ Cooling Performance Analytics")

analytics_history = mqtt_snapshot.get("history", [])

if analytics_history:

    analytics_df = pd.DataFrame(analytics_history)

    latest = analytics_df.iloc[-1]

    temp1 = float(
        latest.get("Zone 1 Temperature", 20)
    )

    temp2 = float(
        latest.get("Zone 2 Temperature", 20)
    )

    fan1 = float(
        latest.get("Fan 1 Speed", 0)
    )

    fan2 = float(
        latest.get("Fan 2 Speed", 0)
    )

    water_value = latest.get(
        "Water Flow (L/min)", 0
    )

    water_flow = (
        float(water_value)
        if pd.notna(water_value)
        else 0.0
    )

    avg_fan_speed = (fan1 + fan2) / 2

    avg_temperature = (temp1 + temp2) / 2

    max_temperature = max(temp1, temp2)

    if len(analytics_df) >= 2:

        previous = analytics_df.iloc[-2]

        previous_avg_temp = (
            float(previous.get("Zone 1 Temperature", temp1))
            + float(previous.get("Zone 2 Temperature", temp2))
        ) / 2

        temperature_change = (
            avg_temperature - previous_avg_temp
        )

    else:

        temperature_change = 0.0

    if max_temperature < 40:
        cooling_status = "Normal"

    elif max_temperature < 48:
        cooling_status = "Monitor"

    else:
        cooling_status = "High Temperature"

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
        " Water Flow",
        f"{water_flow:.2f} L/min"
    )

    c4.metric(
        "Cooling Status",
        cooling_status
    )

    st.markdown("### Zone-wise Cooling Response")

    zone_data = pd.DataFrame({

        "Zone": ["Zone 1", "Zone 2"],

        "Temperature (°C)": [
            temp1,
            temp2
        ],

        "Fan Speed (%)": [
            fan1,
            fan2
        ],

        "Cooling Status": [
            "Normal" if temp1 < 40 else
            "Monitor" if temp1 < 48 else
            "High Temperature",

            "Normal" if temp2 < 40 else
            "Monitor" if temp2 < 48 else
            "High Temperature"
        ]
    })

    st.dataframe(
        zone_data,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Temperature thresholds are for demonstration only, "
        "not real hardware safety limits."
    )

else:

    st.info(
        "Waiting for ESP32 telemetry for cooling analytics."
    )


# =========================================================
# 17.  SERVER MONITORING
# =========================================================

st.divider()
st.subheader("🖥️  Data Center Server Monitoring")

cols = st.columns(2, gap="large")

for col, (name, data) in zip(cols, nodes.items()):

    with col:

        with st.container(border=True):

            status = (
                "🟢 Online"
                if data["online"]
                else "🔴 Offline"
            )

            st.markdown(f"### {name}")

            st.write(f"**Server Status:** {status}")

            m1, m2 = st.columns(2)

            m1.metric(
                "Temperature",
                f'{data["temperature"]:.1f} °C'
            )

            m2.metric(
                "Workload Heat",
                f'{data["heat_load"]:.2f}'
            )

            m3, m4 = st.columns(2)

            m3.metric(
                "CPU Usage",
                f'{data["cpu"]:.0f}%'
            )

            m4.metric(
                "RAM Usage",
                f'{data["ram"]:.0f}%'
            )

            m5, m6 = st.columns(2)

            m5.metric(
                "GPU Usage",
                f'{data["gpu"]:.0f}%'
            )

            m6.metric(
                "Running Apps",
                len(data["apps"])
            )

            st.progress(
                int(min(100, max(0, data["cpu"]))),
                text="CPU Utilization"
            )

            st.progress(
                int(min(100, max(0, data["ram"]))),
                text="RAM Utilization"
            )

            st.progress(
                int(min(100, max(0, data["gpu"]))),
                text="GPU Utilization"
            )

            st.markdown("**Running Applications**")

            if data["apps"]:

                for app in data["apps"]:

                    st.write(
                        f"• {app['app']}"
                    )

            else:

                st.caption("No applications assigned.")


# =========================================================
# 18. APPLICATION SUBMISSION
# =========================================================

st.divider()
st.subheader("🚀 Submit a New Application")

left, right = st.columns([2, 1], gap="large")

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
        "Estimated GPU Requirement",
        f'{req["gpu"]}%'
    )

    st.metric(
        "Estimated Heat Load",
        f'{req["heat"]:.2f}'
    )


# =========================================================
# 19. AUTOMATIC WORKLOAD SCHEDULER
# =========================================================

def choose_node(app_req):

    candidates = []
    rejected = []

    for name, node in nodes.items():

        reasons = []

        if not node["online"]:
            reasons.append("Server offline")

        if node["temperature"] >= 48:
            reasons.append(
                "Temperature safety threshold reached"
            )

        if node["cpu"] + app_req["cpu"] > 90:
            reasons.append(
                "Insufficient CPU headroom"
            )

        if node["ram"] + app_req["ram"] > 90:
            reasons.append(
                "Insufficient RAM headroom"
            )

        if node["gpu"] + app_req["gpu"] > 90:
            reasons.append(
                "Insufficient GPU headroom"
            )

        if reasons:

            rejected.append({
                "server": name,
                "reasons": reasons
            })

            continue

        score = (
            (node["temperature"] / 50) * 0.35
            + (node["cpu"] / 100) * 0.25
            + (node["ram"] / 100) * 0.20
            + (node["gpu"] / 100) * 0.20
        )

        candidates.append((score, name))

    if not candidates:

        return None, rejected

    candidates.sort()

    return candidates[0][1], rejected


# =========================================================
# 20. ASSIGN APPLICATION
# =========================================================

if st.button(
    "🚀 Submit Application — Automatic Placement",
    type="primary",
    use_container_width=True
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

            "gpu": req["gpu"],

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
                "temperature, CPU, RAM and GPU checks."
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
# 21. LAST DEPLOYMENT DECISION
# =========================================================

st.markdown("---")
st.subheader("21. Latest Workload Scheduling Decision")

last_decision = st.session_state.get("last_decision")

if last_decision:
    st.success(last_decision)
else:
    st.info("No workload scheduling decision has been made yet.")


# =========================================================
# 22. RUNNING APPLICATIONS
# =========================================================

st.markdown("---")
st.subheader("22. Running Applications")

deployment_records = st.session_state.get("deployments", [])

if deployment_records:
    deployment_df = pd.DataFrame(deployment_records)

    display_columns = [
        col for col in [
            "app",
            "server",
            "cpu",
            "ram",
            "gpu",
            "heat",
            "status",
            "time"
        ]
        if col in deployment_df.columns
    ]

    if display_columns:
        st.dataframe(
            deployment_df[display_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Deployment information is not available.")
else:
    st.info("No applications are currently deployed.")


# =========================================================
# 23. REMOVE APPLICATION
# =========================================================

st.markdown("---")
st.subheader("23. Application Management")

current_deployments = st.session_state.get("deployments", [])

if current_deployments:
    deployment_options = [
        f"{i + 1}. {item.get('app', 'Application')} - "
        f"{item.get('server', 'Unknown Server')}"
        for i, item in enumerate(current_deployments)
    ]

    selected_remove = st.selectbox(
        "Select an application to remove",
        options=deployment_options,
        key="remove_application_select"
    )

    if st.button(
        "Remove Selected Application",
        use_container_width=True
    ):
        remove_index = deployment_options.index(selected_remove)
        removed_app = current_deployments.pop(remove_index)

        server_name = removed_app.get("server")

        for node in st.session_state.nodes:
            if node.get("name") == server_name:
                app_name = removed_app.get("app")

                if app_name in node.get("apps", []):
                    node["apps"].remove(app_name)

                node["used_cpu"] = max(
                    0,
                    node.get("used_cpu", 0) - removed_app.get("cpu", 0)
                )

                node["used_ram"] = max(
                    0,
                    node.get("used_ram", 0) - removed_app.get("ram", 0)
                )

                node["used_gpu"] = max(
                    0,
                    node.get("used_gpu", 0) - removed_app.get("gpu", 0)
                )

                node["heat_load"] = max(
                    0,
                    node.get("heat_load", 0) - removed_app.get("heat", 0)
                )

        st.session_state.deployments = current_deployments

        st.session_state.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": f"Removed application: {removed_app.get('app')}"
        })

        st.success("Application removed successfully.")
        st.rerun()
else:
    st.info("There are no applications to remove.")


# =========================================================
# 24. AI-BASED COOLING PREDICTION
# =========================================================

st.markdown("---")
st.subheader("24. AI-Based Cooling Prediction")

fan_commands = {
    "fan1": 30,
    "fan2": 30
}

zone_temperatures = [
    float(mqtt_snapshot.get("zone1_temp", 30)),
    float(mqtt_snapshot.get("zone2_temp", 30))
]

# Safely read  server data

current_nodes = st.session_state.get("nodes", [])

# Ensure two  servers are available
if not isinstance(current_nodes, list):
    current_nodes = []

while len(current_nodes) < 2:
    current_nodes.append({
        "name": f" Raspberry Pi {len(current_nodes) + 1}",
        "temperature": 30,
        "base_cpu": 100,
        "base_ram": 100,
        "base_gpu": 100,
        "used_cpu": 0,
        "used_ram": 0,
        "used_gpu": 0,
        "heat_load": 0,
        "online": True,
        "apps": []
    })

st.session_state.nodes = current_nodes

zone_cpu_values = [
    float(current_nodes[0].get("used_cpu", 0)),
    float(current_nodes[1].get("used_cpu", 0))
]

zone_ram_values = [
    float(current_nodes[0].get("used_ram", 0)),
    float(current_nodes[1].get("used_ram", 0))
]

prediction_results = []

for index in range(2):
    temperature = zone_temperatures[index]
    cpu_usage = zone_cpu_values[index]
    ram_usage = zone_ram_values[index]

    if cooling_model is not None:
        try:
            trend = 0

            if len(mqtt_snapshot.get("history", [])) >= 2:
                history_data = mqtt_snapshot["history"]

                if index == 0:
                    previous_temp = history_data[-2].get(
                        "zone1_temp", temperature
                    )
                else:
                    previous_temp = history_data[-2].get(
                        "zone2_temp", temperature
                    )

                trend = temperature - float(previous_temp)

            prediction_input = create_features(
                temperature,
                cpu_usage,
                ram_usage,
                trend
            )

            prediction = cooling_model.predict(prediction_input)[0]

            prediction_text = str(prediction).strip().lower()

            if "high" in prediction_text:
                cooling_level = "High"
                fan_speed = 90
            elif "medium" in prediction_text:
                cooling_level = "Medium"
                fan_speed = 60
            else:
                cooling_level = "Low"
                fan_speed = 30

        except Exception as error:
            prediction_text = "Fallback rule-based prediction"

            if temperature >= 45 or cpu_usage >= 85:
                cooling_level = "High"
                fan_speed = 90
            elif temperature >= 35 or cpu_usage >= 65:
                cooling_level = "Medium"
                fan_speed = 60
            else:
                cooling_level = "Low"
                fan_speed = 30

    else:
        if temperature >= 45 or cpu_usage >= 85:
            cooling_level = "High"
            fan_speed = 90
        elif temperature >= 35 or cpu_usage >= 65:
            cooling_level = "Medium"
            fan_speed = 60
        else:
            cooling_level = "Low"
            fan_speed = 30

    prediction_results.append({
        "Zone": f"Zone {index + 1}",
        "Temperature (°C)": round(temperature, 1),
        "CPU Usage (%)": round(cpu_usage, 1),
        "RAM Usage (%)": round(ram_usage, 1),
        "Cooling Level": cooling_level,
        "Recommended Fan (%)": fan_speed
    })

    fan_commands[f"fan{index + 1}"] = fan_speed

prediction_df = pd.DataFrame(prediction_results)

st.dataframe(
    prediction_df,
    use_container_width=True,
    hide_index=True
)

if cooling_model is not None:
    st.caption("AI model loaded: cooling_model.pkl")
else:
    st.warning(
        "AI model file not found. Rule-based fallback prediction is active."
    )


# =========================================================
# 25.  COOLING CONTROL
# =========================================================

st.markdown("---")
st.subheader("25.  Cooling Control")

st.write(
    "Choose automatic AI-based cooling or manually control the fan speeds."
)

manual_mode = st.toggle(
    "Enable Manual Cooling Control",
    value=False,
    key="manual_cooling_mode"
)

if manual_mode:
    st.info("Manual mode is active. Adjust the fan speeds below.")

    manual_fan1 = st.slider(
        "Zone 1 Fan Speed (%)",
        min_value=0,
        max_value=100,
        value=int(st.session_state.get("manual_fan1", 30)),
        key="manual_fan1_slider"
    )

    manual_fan2 = st.slider(
        "Zone 2 Fan Speed (%)",
        min_value=0,
        max_value=100,
        value=int(st.session_state.get("manual_fan2", 30)),
        key="manual_fan2_slider"
    )

    st.session_state.manual_fan1 = manual_fan1
    st.session_state.manual_fan2 = manual_fan2

    final_fan_commands = {
        "fan1": manual_fan1,
        "fan2": manual_fan2
    }

else:
    st.success("Automatic AI-based cooling mode is active.")

    final_fan_commands = fan_commands

cooling_col1, cooling_col2 = st.columns(2)

with cooling_col1:
    st.metric(
        "Zone 1 Fan Speed",
        f"{final_fan_commands['fan1']}%"
    )

with cooling_col2:
    st.metric(
        "Zone 2 Fan Speed",
        f"{final_fan_commands['fan2']}%"
    )

st.markdown("####  Cooling Response")

st.caption(
    "This is a software simulation of cooling response, not a measurement "
    "from a physical cooling device."
)

if st.button(
    "Apply  Cooling",
    use_container_width=True
):
    for index, fan_key in enumerate(["fan1", "fan2"]):
        fan_speed = final_fan_commands[fan_key]

        node = st.session_state.nodes[index]

        # Simulated cooling response
        if fan_speed >= 80:
            cooling_effect = 2.0
        elif fan_speed >= 50:
            cooling_effect = 1.0
        elif fan_speed >= 20:
            cooling_effect = 0.4
        else:
            cooling_effect = 0.0

        current_temp = float(node.get("temperature", 30))

        node["temperature"] = max(
            20,
            round(current_temp - cooling_effect, 1)
        )

    st.session_state.logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "event": (
            " cooling applied: "
            f"Fan 1 = {final_fan_commands['fan1']}%, "
            f"Fan 2 = {final_fan_commands['fan2']}%"
        )
    })

    st.success(" cooling response applied successfully.")
    st.rerun()


# =========================================================
# 26. MQTT COMMAND PUBLISHING
# =========================================================

st.markdown("---")
st.subheader("26. ESP32 Cooling Command Communication")

final_payload = {
    "fan1_speed": int(final_fan_commands["fan1"]),
    "fan2_speed": int(final_fan_commands["fan2"]),
    "zone1_heat": round(zone_temperatures[0], 1),
    "zone2_heat": round(zone_temperatures[1], 1),
    "mode": "manual" if manual_mode else "automatic"
}

st.json(final_payload)

if st.button(
    "Send Cooling Commands to ESP32",
    use_container_width=True
):
    if mqtt_connection is not None:
        try:
            result = mqtt_connection.publish(
                COMMAND_TOPIC,
                json.dumps(final_payload)
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                st.success("Cooling commands published to MQTT broker.")
            else:
                st.error(
                    f"MQTT publish failed. Return code: {result.rc}"
                )

        except Exception as error:
            st.error(f"Unable to publish MQTT command: {error}")

    else:
        st.warning(
            "MQTT is not connected. Commands are displayed in simulation mode."
        )


# =========================================================
# 27.  POWER CONSUMPTION ANALYTICS
# =========================================================

st.markdown("---")
st.subheader("27.  Power Consumption Analytics")

# Illustrative power model:
# Base server power + fan power based on fan speed.

server_power = 0

for node in st.session_state.nodes:
    if node.get("online", True):
        server_power += (
            8
            + node.get("used_cpu", 0) * 0.08
            + node.get("used_ram", 0) * 0.03
        )

fan1_power = 2 + (final_fan_commands["fan1"] / 100) * 18
fan2_power = 2 + (final_fan_commands["fan2"] / 100) * 18

total_fan_power = fan1_power + fan2_power
total_power = server_power + total_fan_power

estimated_hourly_energy = total_power / 1000

power_col1, power_col2, power_col3 = st.columns(3)

with power_col1:
    st.metric(
        " Server Power",
        f"{server_power:.1f} W"
    )

with power_col2:
    st.metric(
        " Cooling Power",
        f"{total_fan_power:.1f} W"
    )

with power_col3:
    st.metric(
        "Estimated Total Power",
        f"{total_power:.1f} W"
    )

st.metric(
    "Estimated Energy Consumption",
    f"{estimated_hourly_energy:.4f} kWh",
    help="Estimated energy for one hour at the current  power level."
)

st.caption(
    "Power values are illustrative software estimates, not actual "
    "electrical measurements."
)


# =========================================================
# 28. HYDRO-TRACE THERMAL EFFICIENCY SCORE (HTES)
# =========================================================

st.markdown("---")
st.subheader("28. Hydro-Trace Thermal Efficiency Score (HTES)")

def calculate_thermal_score(temperature):
    if temperature <= 30:
        return 100
    elif temperature <= 35:
        return 90
    elif temperature <= 40:
        return 75
    elif temperature <= 45:
        return 60
    elif temperature <= 50:
        return 40
    else:
        return 20


def calculate_fan_efficiency(fan_speed):
    if fan_speed <= 30:
        return 100
    elif fan_speed <= 50:
        return 85
    elif fan_speed <= 70:
        return 70
    elif fan_speed <= 90:
        return 50
    else:
        return 35


htes_results = []

for index in range(2):
    temperature = zone_temperatures[index]
    fan_speed = final_fan_commands[f"fan{index + 1}"]

    temperature_score = calculate_thermal_score(temperature)
    fan_score = calculate_fan_efficiency(fan_speed)

    htes_score = (
        temperature_score * 0.70
        + fan_score * 0.30
    )

    if htes_score >= 85:
        status = "Excellent"
    elif htes_score >= 70:
        status = "Good"
    elif htes_score >= 50:
        status = "Moderate"
    else:
        status = "Needs Attention"

    htes_results.append({
        "Zone": f"Zone {index + 1}",
        "Temperature Score": temperature_score,
        "Fan Efficiency Score": fan_score,
        "HTES Score": round(htes_score, 1),
        "Status": status
    })

htes_df = pd.DataFrame(htes_results)

st.dataframe(
    htes_df,
    use_container_width=True,
    hide_index=True
)

overall_htes = round(
    sum(item["HTES Score"] for item in htes_results) / 2,
    1
)

st.metric(
    "Overall HTES",
    f"{overall_htes}/100"
)

if overall_htes >= 85:
    st.success("Excellent thermal efficiency.")
elif overall_htes >= 70:
    st.info("Good thermal efficiency.")
elif overall_htes >= 50:
    st.warning("Moderate thermal efficiency. Monitor the cooling system.")
else:
    st.error("Thermal efficiency needs attention.")


# =========================================================
# 29. SYSTEM EVENT LOG
# =========================================================

st.markdown("---")
st.subheader("29. System Event Log")

event_logs = st.session_state.get("logs", [])

if event_logs:
    logs_df = pd.DataFrame(event_logs)

    if "time" in logs_df.columns and "event" in logs_df.columns:
        st.dataframe(
            logs_df[["time", "event"]].iloc[::-1],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.dataframe(
            logs_df.iloc[::-1],
            use_container_width=True,
            hide_index=True
        )

    if st.button("Clear Event Log"):
        st.session_state.logs = []
        st.rerun()

else:
    st.info("No system events recorded yet.")


# =========================================================
# 30. PROJECT ARCHITECTURE AND DEMONSTRATION NOTES
# =========================================================
'''
st.markdown("---")
st.subheader("30. Hydro-Trace System Architecture")

st.markdown("""
### How the prototype works

1. **ESP32 Sensor Simulation**  
   temperature, humidity, and cooling-related sensor readings
   are generated using Wokwi.

2. **MQTT Communication**  
   Sensor data is transmitted through an MQTT broker to the Streamlit
   dashboard.

3. ** Data Center Monitoring**  
   Two  Raspberry Pi servers represent separate computing nodes.
   Their CPU, RAM, workload, and temperature are monitored.

4. **Intelligent Workload Scheduling**  
   The scheduling logic evaluates server availability, temperature,
   and resource capacity before assigning applications.

5. **AI-Based Cooling Prediction**  
   The cooling model predicts the required cooling level using the
   available temperature and workload features.

6. **Cooling Command Communication**  
   The dashboard can publish fan-speed commands through MQTT to the
   ESP32 simulation.

7. **Power and Thermal Analytics**  
   The dashboard estimates  power consumption and calculates
   the Hydro-Trace Thermal Efficiency Score (HTES).
""")

st.markdown("### Prototype Scope and Limitations")

st.info("""
This is a  proof-of-concept prototype.

- Raspberry Pi servers are represented by software-based  nodes.
- ESP32 and sensor behavior is demonstrated through Wokwi simulation.
- Cooling response and power consumption are software estimates.
- MQTT communication demonstrates the sensor-to-dashboard and
  dashboard-to-simulation communication flow.
- Actual hardware performance, energy consumption, and cooling efficiency
  would require validation using physical devices.
""")
'''
st.markdown("---")

st.markdown(
    """
    <div style="text-align:center; padding:18px 5px;">
        <h2 style="color:#1769AA; margin-bottom:5px;">
            HYDRO-TRACE
        </h2>
        <p style="color:#64748b; font-size:14px;">
            Intelligent Workload Management • AI-Based Cooling •
            Smart Data Center Monitoring
        </p>
        <p style="color:#94a3b8; font-size:12px;">
             Prototype Demonstration
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
