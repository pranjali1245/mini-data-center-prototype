
import streamlit as st
import pandas as pd
import json
import threading
import uuid
from datetime import datetime
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh
import joblib
from pathlib import Path

# --------------------------------------------------
# 1. PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Mini Data Center | Virtual Prototype",
    page_icon="🖥️",
    layout="wide"
)

st.title("🖥️ Mini Data Center — Virtual Prototype")
st.caption(
    "Live Wokwi ESP32 telemetry through MQTT | "
    "Virtual Raspberry Pi nodes and workload management"
)

# --------------------------------------------------
# 2. MQTT CONFIGURATION
# --------------------------------------------------

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 8000

MQTT_TOPIC = "mini-dc-demo-7f3a91/telemetry"
MQTT_COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"


# --------------------------------------------------
# 3. MQTT SUBSCRIBER
# --------------------------------------------------

@st.cache_resource
def start_mqtt_subscriber():

    state = {
        "connected": False,
        "latest": None,
        "last_seen": None,
        "error": None,
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

            required = (
                "zone1_temp",
                "zone2_temp",
                "fan1_speed",
                "fan2_speed"
            )

            if not all(key in payload for key in required):
                raise ValueError("Missing MQTT fields")

            clean = {
                "zone1_temp": float(payload["zone1_temp"]),
                "zone2_temp": float(payload["zone2_temp"]),
                "fan1_speed": int(payload["fan1_speed"]),
                "fan2_speed": int(payload["fan2_speed"])
            }

            with state["lock"]:
                state["latest"] = clean
                state["last_seen"] = datetime.now().strftime(
                    "%H:%M:%S"
                )
                state["error"] = None

        except Exception as exc:

            with state["lock"]:
                state["error"] = str(exc)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"mini-dc-dashboard-{uuid.uuid4().hex[:8]}",
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
            "error": mqtt_state["error"]
        }


# --------------------------------------------------
# 4. LOAD ML MODEL
# --------------------------------------------------

@st.cache_resource
def load_cooling_model():

    model_path = Path(__file__).parent / "cooling_model.pkl"

    if not model_path.exists():
        raise FileNotFoundError(
            "cooling_model.pkl not found. "
            "Upload it in the same folder as app.py."
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


# --------------------------------------------------
# 5. VIRTUAL RASPBERRY PI NODES
# --------------------------------------------------

DEFAULT_NODES = {

    "Virtual Raspberry Pi 1": {
        "temperature": 42.0,
        "cpu": 85.0,
        "ram": 80.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    },

    "Virtual Raspberry Pi 2": {
        "temperature": 30.0,
        "cpu": 35.0,
        "ram": 40.0,
        "heat_load": 0.0,
        "online": True,
        "apps": []
    }
}


if "nodes" not in st.session_state:

    st.session_state.nodes = {
        k: {**v, "apps": []}
        for k, v in DEFAULT_NODES.items()
    }


if "logs" not in st.session_state:
    st.session_state.logs = []


if "last_decision" not in st.session_state:
    st.session_state.last_decision = None


# --------------------------------------------------
# 6. SIDEBAR AND LIVE REFRESH
# --------------------------------------------------

st.sidebar.header("⚙️ Simulation Controls")

live_mode = st.sidebar.toggle(
    "Use live Wokwi ESP32 temperatures",
    value=True,
    key="live_mode"
)

if live_mode:

    st_autorefresh(
        interval=2000,
        key="mqtt_dashboard_refresh"
    )

    st.sidebar.caption(
        "Dashboard automatically refreshes every 2 seconds."
    )

else:

    st.sidebar.caption(
        "Manual simulation mode is active."
    )


mqtt_snapshot = get_mqtt_snapshot()

nodes = st.session_state.nodes


# --------------------------------------------------
# 7. APPLY LIVE TEMPERATURES
# --------------------------------------------------

if live_mode and mqtt_snapshot["latest"]:

    nodes["Virtual Raspberry Pi 1"]["temperature"] = (
        mqtt_snapshot["latest"]["zone1_temp"]
    )

    nodes["Virtual Raspberry Pi 2"]["temperature"] = (
        mqtt_snapshot["latest"]["zone2_temp"]
    )


# --------------------------------------------------
# 8. SERVER CONTROLS
# --------------------------------------------------

for i, name in enumerate(nodes):

    st.sidebar.subheader(name)

    nodes[name]["online"] = st.sidebar.toggle(
        f"{name} online",
        value=nodes[name]["online"],
        key=f"online_{i}"
    )

    if not (live_mode and mqtt_snapshot["latest"]):

        nodes[name]["temperature"] = st.sidebar.slider(
            f"{name} temperature (°C)",
            20.0,
            80.0,
            float(nodes[name]["temperature"]),
            0.5,
            key=f"temp_{i}"
        )

    else:

        st.sidebar.metric(
            f"{name} live temperature",
            f'{nodes[name]["temperature"]:.1f} °C'
        )

    nodes[name]["cpu"] = st.sidebar.slider(
        f"{name} CPU usage (%)",
        0.0,
        100.0,
        float(nodes[name]["cpu"]),
        1.0,
        key=f"cpu_{i}"
    )

    nodes[name]["ram"] = st.sidebar.slider(
        f"{name} RAM usage (%)",
        0.0,
        100.0,
        float(nodes[name]["ram"]),
        1.0,
        key=f"ram_{i}"
    )


# --------------------------------------------------
# 9. RESET DEMONSTRATION
# --------------------------------------------------

if st.sidebar.button("↺ Reset demonstration"):

    st.session_state.nodes = {
        k: {**v, "apps": []}
        for k, v in DEFAULT_NODES.items()
    }

    st.session_state.logs = []
    st.session_state.last_decision = None

    st.rerun()


# --------------------------------------------------
# 10. MQTT CONNECTION STATUS
# --------------------------------------------------

st.info(
    "Raspberry Pi nodes, CPU/RAM, and physical cooling "
    "are virtual simulations. Wokwi provides simulated "
    "ESP32 sensor and fan behavior."
)

st.subheader("0. ESP32 → MQTT Connection")

if mqtt_snapshot["connected"]:

    st.success(
        f"MQTT connected: {MQTT_HOST}:{MQTT_PORT}"
    )

else:

    st.warning(
        "Connecting to MQTT broker. "
        "Start Wokwi and wait for telemetry."
    )


if mqtt_snapshot["error"]:

    st.caption(
        f"MQTT detail: {mqtt_snapshot['error']}"
    )


if mqtt_snapshot["latest"]:

    live = mqtt_snapshot["latest"]

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Zone 1 Temperature",
        f'{live["zone1_temp"]:.1f} °C'
    )

    m2.metric(
        "Zone 2 Temperature",
        f'{live["zone2_temp"]:.1f} °C'
    )

    m3.metric(
        "Fan 1 Speed",
        f'{live["fan1_speed"]}%'
    )

    m4.metric(
        "Fan 2 Speed",
        f'{live["fan2_speed"]}%'
    )

    st.caption(
        f"Last ESP32 message: {mqtt_snapshot['last_seen']}"
    )

else:

    st.caption("Waiting for ESP32 telemetry...")


# --------------------------------------------------
# 11. VIRTUAL SERVER MONITORING
# --------------------------------------------------

st.subheader("1. Virtual Server Monitoring")

cols = st.columns(2)

for col, (name, data) in zip(cols, nodes.items()):

    with col:

        status = "Online" if data["online"] else "Offline"

        col.metric(name, status)

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
            int(data["cpu"]),
            text="CPU Utilization"
        )

        st.progress(
            int(data["ram"]),
            text="RAM Utilization"
        )

        st.write(
            "Running Applications:",
            ", ".join(data["apps"])
            if data["apps"]
            else "None"
        )


# --------------------------------------------------
# 12. APPLICATION CATALOG
# --------------------------------------------------

st.divider()

st.subheader("2. Submit a New Application")

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


left, right = st.columns([2, 1])

with left:

    selected_app = st.selectbox(
        "Choose Application",
        list(app_catalog.keys())
    )

    st.caption(
        app_catalog[selected_app]["description"]
    )


req = app_catalog[selected_app]

with right:

    st.metric(
        "Estimated CPU Requirement",
        f'{req["cpu"]}%'
    )

    st.metric(
        "Estimated RAM Requirement",
        f'{req["ram"]}%'
    )


# --------------------------------------------------
# 13. AUTOMATIC WORKLOAD SCHEDULER
# --------------------------------------------------

def choose_node(app_req):

    candidates = []
    rejected = []

    for name, d in nodes.items():

        reasons = []

        if not d["online"]:
            reasons.append("Server offline")

        if d["temperature"] >= 48:
            reasons.append("Temperature safety threshold reached")

        if d["cpu"] + app_req["cpu"] > 90:
            reasons.append("Insufficient CPU")

        if d["ram"] + app_req["ram"] > 90:
            reasons.append("Insufficient RAM")

        if reasons:

            rejected.append((name, reasons))
            continue

        score = (
            (d["temperature"] / 50) * 0.40
            + (d["cpu"] / 100) * 0.35
            + (d["ram"] / 100) * 0.25
        )

        candidates.append((score, name))

    if not candidates:
        return None, rejected

    candidates.sort()

    return candidates[0][1], rejected


# --------------------------------------------------
# 14. APPLICATION ASSIGNMENT
# --------------------------------------------------

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

        st.session_state.logs.insert(
            0,
            f"REJECTED: {selected_app}"
        )

    else:

        d = nodes[chosen]

        d["apps"].append(selected_app)

        d["cpu"] = min(
            100.0,
            d["cpu"] + req["cpu"]
        )

        d["ram"] = min(
            100.0,
            d["ram"] + req["ram"]
        )

        d["heat_load"] = min(
            2.0,
            d["heat_load"] + req["heat"]
        )

        st.session_state.last_decision = {
            "status": "Deployed",
            "app": selected_app,
            "node": chosen,
            "reason": "Best eligible server selected"
        }

        st.session_state.logs.insert(
            0,
            f"DEPLOYED: {selected_app} -> {chosen}"
        )


# --------------------------------------------------
# 15. DISPLAY SCHEDULER DECISION
# --------------------------------------------------

if st.session_state.last_decision:

    decision = st.session_state.last_decision

    if decision["status"] == "Deployed":

        st.success(
            f'Application "{decision["app"]}" assigned to '
            f'**{decision["node"]}**.'
        )

    else:

        st.error(
            f'Application "{decision["app"]}" rejected: '
            f'{decision["reason"]}'
        )


# --------------------------------------------------
# 16. ML COOLING PREDICTION
# --------------------------------------------------

st.divider()

st.subheader("3. ML-Based Cooling Prediction")

cool_rows = []

for name, d in nodes.items():

    features = make_cooling_features(d)

    prediction = cooling_model.predict(features)[0]

    probabilities = cooling_model.predict_proba(features)[0]

    confidence = float(max(probabilities) * 100)

    fan = {
        "Low": 30,
        "Medium": 60,
        "High": 90
    }[prediction]

    cool_rows.append({

        "Virtual Zone": name,
        "Predicted Cooling": prediction,
        "Suggested Fan Speed": f"{fan}%",
        "Model Confidence": f"{confidence:.0f}%"

    })


st.dataframe(
    pd.DataFrame(cool_rows),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Random Forest uses synthetic demonstration data. "
    "Predictions are illustrative, not real-world calibrated."
)


# --------------------------------------------------
# 17. PUBLISH FAN COMMANDS AND WORKLOAD HEAT
# --------------------------------------------------

fan_commands = {}

for name, d in nodes.items():

    features = make_cooling_features(d)

    prediction = cooling_model.predict(features)[0]

    fan_commands[name] = {
        "Low": 30,
        "Medium": 60,
        "High": 90
    }[prediction]


command_payload = {

    "fan1_speed": int(
        fan_commands["Virtual Raspberry Pi 1"]
    ),

    "fan2_speed": int(
        fan_commands["Virtual Raspberry Pi 2"]
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
            json.dumps(command_payload),
            qos=0,
            retain=False
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            command_status = "ML commands published successfully"

        else:

            command_status = (
                f"MQTT publish error: {result.rc}"
            )

    except Exception as exc:

        command_status = str(exc)


st.info(
    f"{command_status} | "
    f"Fan 1: {command_payload['fan1_speed']}% | "
    f"Fan 2: {command_payload['fan2_speed']}%"
)

st.caption(
    f"MQTT command topic: {MQTT_COMMAND_TOPIC}"
)


# --------------------------------------------------
# 18. VIRTUAL COOLING RESPONSE
# --------------------------------------------------

st.divider()

st.subheader("4. Virtual Cooling Response")

fan_cols = st.columns(2)

for col, (name, d) in zip(fan_cols, nodes.items()):

    features = make_cooling_features(d)

    prediction = cooling_model.predict(features)[0]

    fan = {
        "Low": 30,
        "Medium": 60,
        "High": 90
    }[prediction]

    with col:

        st.write(f"**{name} — Virtual Fan**")

        st.progress(
            fan,
            text=f"Suggested fan speed: {fan}%"
        )

        st.write(
            f"Cooling prediction: {prediction}"
        )


# --------------------------------------------------
# 19. EVENT LOG
# --------------------------------------------------

st.divider()

st.subheader("5. Execution and System Event Log")

if st.session_state.logs:

    for item in st.session_state.logs[:12]:

        st.write("•", item)

else:

    st.write("No application submissions yet.")


# --------------------------------------------------
# 20. PROTOTYPE ARCHITECTURE
# --------------------------------------------------

st.divider()

st.subheader("6. Prototype Architecture and Limitations")

st.markdown("""
- **Laptop / Cloud Dashboard:** Central dashboard and Python scheduler.
- **Virtual Raspberry Pi 1 and 2:** Simulated server nodes.
- **Workload Scheduler:** Selects an eligible virtual server.
- **ML Model:** Random Forest predicts cooling requirements.
- **ESP32:** Receives fan commands and workload heat through MQTT.
- **Wokwi:** Simulates temperature inputs and fan indicators.
- **Physical Hardware:** Raspberry Pi servers, real sensors and physical fans are not connected in this online prototype.
""")
