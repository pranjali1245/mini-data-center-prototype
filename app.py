
import streamlit as st
import pandas as pd
import json
import threading
import uuid
import math
from datetime import datetime
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh
import joblib
from pathlib import Path


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Hydro-Trace | AI Water-Saving Engine",
    page_icon="🖥️",
    layout="wide"
)

st.markdown("""
<style>
/* Hydro-Trace dashboard theme */
:root { --ht-bg: #0b1220; --ht-panel: #111c2e; --ht-border: #24344d; --ht-cyan: #42d6d0; }
.stApp { background: radial-gradient(ellipse at 12% 0%, #142b42 0%, #0b1220 48%, #08101b 100%); }
.block-container { max-width: 1500px; padding-top: 1.6rem; padding-bottom: 3rem; }
[data-testid="stHeader"] { background: rgba(8,16,27,.75); }
[data-testid="stMetric"] { background: linear-gradient(145deg, rgba(23,39,60,.96), rgba(15,27,43,.96)); border: 1px solid #2a405b; padding: 15px 17px; border-radius: 14px; box-shadow: 0 8px 24px rgba(0,0,0,.16); }
[data-testid="stMetricLabel"] { color: #9fb4ca; }
[data-testid="stMetricValue"] { color: #f2f7fc; }
[data-testid="stMetricDelta"] { color: #42d6a4; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; border: 1px solid #2b7180; background: linear-gradient(100deg,#167b87,#1760a0); color: white; font-weight: 650; min-height: 2.6rem; transition: .18s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #55e4dc; color: white; transform: translateY(-1px); }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea { background: #101d2e; border-radius: 9px; }
[data-testid="stVerticalBlockBorderWrapper"] { background: rgba(17,28,46,.68); border: 1px solid #263a54; border-radius: 15px; }
hr { border-color: #263a54; }
h1, h2, h3 { letter-spacing: -.025em; }
h2, h3 { color: #e5f2ff; }
[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg,#19a6a6,#55dfbd); }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stDataFrame"] { border: 1px solid #263a54; border-radius: 12px; overflow: hidden; }
footer { visibility: hidden; }

/* Readability and contrast refinements */
html, body, [class*="css"], .stApp { color: #e8f0f8 !important; }
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
.stText, p, li, label, legend { color: #dce7f2; }
.stMarkdown strong, strong, b { color: #ffffff !important; font-weight: 700; }
h1 { color: #f7fbff !important; font-size: clamp(2rem, 3vw, 2.7rem) !important; }
h2 { color: #eaf5ff !important; font-size: 1.55rem !important; margin-top: .45rem; }
h3 { color: #d8f4f4 !important; font-size: 1.18rem !important; }
[data-testid="stMetricLabel"] p { color: #b8c9da !important; font-size: .88rem !important; }
[data-testid="stMetricValue"] div { color: #ffffff !important; font-weight: 750 !important; }
[data-testid="stMetricDelta"] { color: #70e0b8 !important; }
[data-testid="stCaptionContainer"] p { color: #aebfd0 !important; font-size: .82rem !important; }
.stTextInput label, .stNumberInput label, .stSelectbox label,
.stSlider label, .stToggle label, .stCheckbox label,
.stRadio label, .stMultiSelect label, .stTextArea label { color: #dceaf7 !important; font-weight: 600; }
.stTextInput input, .stNumberInput input, .stTextArea textarea,
[data-baseweb="select"] > div { color: #f4f8fc !important; background-color: #101d2e !important; border-color: #3a526d !important; }
[data-baseweb="select"] * { color: #f4f8fc !important; }
[data-testid="stDataFrame"] *, [data-testid="stTable"] * { color: #eaf2fa !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] li { color: #f1f6fb !important; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] details { color: #eaf2fa !important; }
.stTabs [data-baseweb="tab"] { color: #c5d6e7 !important; font-weight: 650; }
.stTabs [aria-selected="true"] { color: #62e0d7 !important; }
.stButton button, .stDownloadButton button { color: #ffffff !important; font-size: .94rem; }
[data-testid="stProgressBar"] { background: #26384d; border-radius: 99px; }
hr { margin-top: 1.3rem; margin-bottom: 1.3rem; }
@media (max-width: 700px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
  [data-testid="stMetric"] { padding: 11px 12px; }
}

</style>
<div style="padding:24px 26px 22px; margin:0 0 22px; border:1px solid #2a526b; border-radius:20px; background:linear-gradient(115deg,rgba(16,53,72,.96),rgba(17,30,51,.96) 58%,rgba(24,49,69,.94)); box-shadow:0 16px 38px rgba(0,0,0,.22);">
  <div style="display:flex; align-items:center; gap:10px; color:#62e0d7; font-size:12px; font-weight:750; letter-spacing:2px; text-transform:uppercase;">● LIVE PROTOTYPE <span style="color:#7793a9;">|</span> SMART DATA CENTER</div>
  <div style="font-size:clamp(28px,4vw,42px); font-weight:800; color:#f4f9ff; line-height:1.15; margin-top:9px;">HYDRO-TRACE <span style="color:#55d9d0;">//</span> AI Water-Saving Engine</div>
  <div style="color:#b4c8d9; font-size:15px; margin-top:10px;">Intelligent workload scheduling · Thermal monitoring · ML-based virtual cooling</div>
  <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:17px;">
    <span style="background:#153e4c;color:#8cebe2;padding:6px 11px;border-radius:20px;font-size:12px;">ESP32 Telemetry</span>
    <span style="background:#203650;color:#a9d6ff;padding:6px 11px;border-radius:20px;font-size:12px;">MQTT Connected</span>
    <span style="background:#26334c;color:#c9caff;padding:6px 11px;border-radius:20px;font-size:12px;">Random Forest ML</span>
    <span style="background:#234236;color:#a8edc8;padding:6px 11px;border-radius:20px;font-size:12px;">2 Virtual Nodes</span>
  </div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# 2. MQTT SETTINGS
# =========================================================

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

            # Humidity - optional for older ESP32 messages
            humidity = payload.get("humidity")

            if humidity is not None:
                humidity = float(humidity)

                if not math.isfinite(humidity) or not 0 <= humidity <= 100:
                    raise ValueError(
                        "Humidity must be between 0 and 100%."
                    )

            # Water flow - optional for backward compatibility
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
                raise ValueError("Fan speed must be between 0 and 100.")

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

                # Keep the latest 300 ESP32 readings for live graphs.
                state["history"].append({
                    "Time": now,
                    "Zone 1 Temperature": zone1_temp,
                    "Zone 2 Temperature": zone2_temp,
                    "Fan 1 Speed": fan1_speed,
                    "Fan 2 Speed": fan2_speed
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
# 7. SHARED DEMO STATE (SURVIVES BROWSER REFRESH)
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

# Reattach each browser session to the same in-memory demo state.
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
        "Temperature, humidity and water-flow readings "
        "arrive through Wokwi MQTT."
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
    "Workload assignments are kept in shared in-memory state, so they survive browser refreshes while this Streamlit app process remains running. "
    "ESP32 telemetry is received through MQTT. "
    "Temperature and humidity are simulated/read through Wokwi "
    "components. Water flow is simulated using a potentiometer. "
    "Raspberry Pi nodes, CPU/RAM values and cooling model "
    "remain virtual simulations."
)


# =========================================================
# 11. ESP32 MQTT CONNECTION DISPLAY
# =========================================================

st.subheader("🔌  Live Sensor & Connectivity")

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
        "Water flow is a virtual 0–20 L/min value generated "
        "from the Wokwi potentiometer, not a physical flow measurement."
    )

else:

    st.caption(
        "No ESP32 telemetry received yet. "
        "Check Wokwi MQTT connection and topic."
    )


# =========================================================
# 12. LIVE TEMPERATURE AND FAN SPEED GRAPHS
# =========================================================

st.divider()
st.subheader("📈  Live Thermal & Cooling Analytics")

history = mqtt_snapshot.get("history", [])

if history:

    history_df = pd.DataFrame(history)
    history_df["Time"] = pd.to_datetime(history_df["Time"])
    history_df = history_df.set_index("Time")

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

    st.caption(
        "Graphs display ESP32 telemetry received through MQTT. "
        "The latest 300 readings are kept in memory; history resets "
        "when the Streamlit app process restarts."
    )

else:

    st.info(
        "Waiting for ESP32 telemetry. Start the Wokwi simulation "
        "to display live temperature and fan-speed graphs."
    )


# =========================================================
# 13. VIRTUAL SERVER MONITORING
# =========================================================

st.subheader("🖥️  Virtual Server Command Center")

cols = st.columns(2)

for col, (name, data) in zip(cols, nodes.items()):

    with col:

        status = "Online" if data["online"] else "Offline"

        st.metric(name, status)

        m1, m2, m3 = st.columns(3)

        m1.metric(
            "Temperature",
            f'{data["temperature"]:.1f} °C'
        )

        m2.metric(
            "CPU Usage",
            f'{data["cpu"]:.0f}%'
        )

        m3.metric(
            "RAM Usage",
            f'{data["ram"]:.0f}%'
        )

        st.metric(
            "Workload Heat Load",
            f'{data["heat_load"]:.2f}'
        )

        st.progress(
            int(min(100, data["cpu"])),
            text="CPU Utilization"
        )

        st.progress(
            int(min(100, data["ram"])),
            text="RAM Utilization"
        )

        st.write(
            "Running Applications:",
            ", ".join(
                app["app"] for app in data["apps"]
            ) if data["apps"] else "None"
        )


# =========================================================
# 13. APPLICATION SUBMISSION
# =========================================================

st.divider()
st.subheader("🚀  Workload Deployment")

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
# 14. AUTOMATIC WORKLOAD SCHEDULER
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
# 15. ASSIGN APPLICATION
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
        shared_demo_state["last_decision"] = st.session_state.last_decision

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
        shared_demo_state["last_decision"] = st.session_state.last_decision

        st.session_state.logs.insert(
            0,
            f"DEPLOYED: {selected_app} -> {chosen}"
        )

    st.rerun()


# =========================================================
# 16. LAST DEPLOYMENT DECISION
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
# 17. RUNNING APPLICATIONS
# =========================================================

st.divider()
st.subheader("📦  Active Workloads")

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
# 18. REMOVE APPLICATION
# =========================================================

st.divider()
st.subheader("🧹  Workload Management")

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
            shared_demo_state["deployments"] = st.session_state.deployments

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
            shared_demo_state["last_decision"] = st.session_state.last_decision

            st.rerun()

else:

    st.info("There are no running applications to remove.")


# =========================================================
# 19. ML-BASED COOLING PREDICTION
# =========================================================

st.divider()
st.subheader("🧠  ML Cooling Intelligence")

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
# 20. VIRTUAL COOLING RESPONSE
# =========================================================

st.divider()
st.subheader("❄️  Smart Cooling Control")

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
# 21. SINGLE MQTT COMMAND PUBLISH BLOCK
# =========================================================

# Only this section publishes fan commands.
# Manual mode sends slider values.
# Automatic mode sends ML predicted values.

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
# 22. EVENT LOG
# =========================================================

st.divider()
st.subheader("🧾  System Activity & Event Log")

if st.session_state.logs:

    for item in st.session_state.logs[:15]:
        st.write("•", item)

else:

    st.write("No application submissions yet.")


# =========================================================
# 23. PROTOTYPE ARCHITECTURE AND LIMITATIONS
# =========================================================

st.divider()
st.subheader("🏗️  Architecture & Demo Scope")

st.markdown("""
- **Laptop/cloud app:** Central dashboard and Python scheduler.
- **Virtual Node 1 and Node 2:** Simulated Raspberry Pi server records.
- **Workload placement:** Python scheduler selects an eligible virtual node.
- **Application assignment:** CPU, RAM and workload heat are updated.
- **Application removal:** Selected application's resources are released.
- **ML:** Random Forest trained on synthetic sample data predicts cooling class.
- **ESP32:** Receives fan commands and publishes telemetry through MQTT.
- **Temperature:** Wokwi potentiometers simulate temperature inputs.
- **Humidity:** Wokwi DHT22 provides simulated humidity readings.
- **Water flow:** Wokwi potentiometer on GPIO 32 simulates a 0–20 L/min value.
- **Cooling:** Wokwi LEDs represent fan speed; they do not create physical airflow.
- **Hardware limitation:** Virtual Raspberry Pi nodes do not execute real Linux
  processes or Docker containers.
- **Physical limitation:** No actual water flow, cooling or power measurement
  is performed in this virtual prototype.
""")
