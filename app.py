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
        Virtual Prototype | ESP32 • MQTT • Machine Learning • Smart Scheduling
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
# 8. DEFAULT VIRTUAL SERVERS
# =========================================================

DEFAULT_NODES = {

    "Virtual Raspberry Pi 1": {
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

    "Virtual Raspberry Pi 2": {
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

    nodes["Virtual Raspberry Pi 1"]["temperature"] = (
        mqtt_snapshot["latest"]["zone1_temp"]
    )

    nodes["Virtual Raspberry Pi 2"]["temperature"] = (
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
    "Hydro-Trace is a virtual data center prototype. "
    "ESP32 telemetry is received through MQTT. Raspberry Pi nodes, "
    "CPU/RAM/GPU values, cooling response, water flow and power "
    "calculations are virtual simulations."
)
