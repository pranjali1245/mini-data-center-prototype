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

st.set_page_config(page_title="Mini Data Center | Virtual Prototype", page_icon="🖥️", layout="wide")

st.title("🖥️ Mini Data Center — Virtual Prototype")
st.caption("Wokwi ESP32 simulator sends live telemetry through MQTT | Raspberry Pi nodes and CPU/RAM remain virtual")


# MQTT settings: must match the ESP32 sketch. HiveMQ public broker uses
# MQTT over WebSockets on port 8000 with the /mqtt path.
MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 8000
MQTT_TOPIC = "mini-dc-demo-7f3a91/telemetry"
MQTT_COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"

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
@st.cache_resource
def start_mqtt_subscriber():
    state = {
        "connected": False,
        "latest": None,
        "last_seen": None,
        "error": None,
        "lock": threading.Lock(),
    }

    def on_connect(client, userdata, flags, rc):
        with state["lock"]:
            state["connected"] = (rc == 0)
            state["error"] = None if rc == 0 else f"MQTT connection code: {rc}"
        if rc == 0:
            client.subscribe(MQTT_TOPIC, qos=0)

    def on_disconnect(client, userdata, rc):
        with state["lock"]:
            state["connected"] = False
            if rc != 0:
                state["error"] = f"MQTT disconnected (code {rc}); reconnecting..."

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            required = ("zone1_temp", "zone2_temp", "fan1_speed", "fan2_speed")
            if not all(key in payload for key in required):
                raise ValueError("Message is missing one or more expected fields")
            clean = {
                "zone1_temp": float(payload["zone1_temp"]),
                "zone2_temp": float(payload["zone2_temp"]),
                "fan1_speed": int(payload["fan1_speed"]),
                "fan2_speed": int(payload["fan2_speed"]),
            }
            with state["lock"]:
                state["latest"] = clean
                state["last_seen"] = datetime.now().strftime("%H:%M:%S")
                state["error"] = None
        except Exception as exc:
            with state["lock"]:
                state["error"] = f"Could not read MQTT message: {exc}"

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"mini-dc-dashboard-{uuid.uuid4().hex[:8]}",
        transport="websockets",
    )
    client.ws_set_options(path="/mqtt")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=2, max_delay=30)
    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=45)
        client.loop_start()
    except Exception as exc:
        state["error"] = str(exc)

    return {"state": state, "client": client}

mqtt_connection = start_mqtt_subscriber()
mqtt_state = mqtt_connection["state"]

def get_mqtt_snapshot():
    with mqtt_state["lock"]:
        return {
            "connected": mqtt_state["connected"],
            "latest": dict(mqtt_state["latest"]) if mqtt_state["latest"] else None,
            "last_seen": mqtt_state["last_seen"],
            "error": mqtt_state["error"],
        }

# Load the Random Forest model trained in Google Colab.
@st.cache_resource
def load_cooling_model():
    model_path = Path(__file__).parent / "cooling_model.pkl"
    if not model_path.exists():
        raise FileNotFoundError(
            "cooling_model.pkl not found. Upload it to the same GitHub folder as app.py."
        )
    return joblib.load(model_path)

cooling_model = load_cooling_model()


def make_cooling_features(node_data):
    # Column names and order must match the Colab training notebook.
    return pd.DataFrame([{
        "temperature": node_data["temperature"],
        "cpu_usage": node_data["cpu"],
        "ram_usage": node_data["ram"],
        "temp_trend": 0.5
    }], columns=["temperature", "cpu_usage", "ram_usage", "temp_trend"])

DEFAULT_NODES = {
    "Virtual Raspberry Pi 1": {"temperature": 42.0, "cpu": 85.0, "ram": 80.0, "online": True, "apps": []},
    "Virtual Raspberry Pi 2": {"temperature": 30.0, "cpu": 35.0, "ram": 40.0, "online": True, "apps": []},
}
if "nodes" not in st.session_state:
    st.session_state.nodes = {k: {**v, "apps": []} for k, v in DEFAULT_NODES.items()}
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last_decision" not in st.session_state:
    st.session_state.last_decision = None

nodes = st.session_state.nodes

mqtt_snapshot = get_mqtt_snapshot()

st.sidebar.header("⚙️ Simulation controls")
live_mode = st.sidebar.toggle("Use live Wokwi ESP32 temperatures", value=True, key="live_mode")
if live_mode:
    st_autorefresh(interval=2000, key="mqtt_dashboard_refresh")
    st.sidebar.caption("Temperature values come from Wokwi MQTT when messages arrive.")
else:
    st.sidebar.caption("Manual demo mode: all displayed readings are simulated.")

if live_mode and mqtt_snapshot["latest"]:
    nodes["Virtual Raspberry Pi 1"]["temperature"] = mqtt_snapshot["latest"]["zone1_temp"]
    nodes["Virtual Raspberry Pi 2"]["temperature"] = mqtt_snapshot["latest"]["zone2_temp"]

for i, name in enumerate(nodes):
    st.sidebar.subheader(name)
    nodes[name]["online"] = st.sidebar.toggle(f"{name} online", value=nodes[name]["online"], key=f"online_{i}")
    if not (live_mode and mqtt_snapshot["latest"]):
        nodes[name]["temperature"] = st.sidebar.slider(f"{name} temperature (°C)", 20.0, 80.0, float(min(80.0, max(20.0, nodes[name]["temperature"]))), 0.5, key=f"temp_{i}")
    else:
        st.sidebar.metric(f"{name} live temperature", f'{nodes[name]["temperature"]:.1f} °C')
    nodes[name]["cpu"] = st.sidebar.slider(f"{name} CPU usage (%)", 0.0, 100.0, float(nodes[name]["cpu"]), 1.0, key=f"cpu_{i}")
    nodes[name]["ram"] = st.sidebar.slider(f"{name} RAM usage (%)", 0.0, 100.0, float(nodes[name]["ram"]), 1.0, key=f"ram_{i}")

if st.sidebar.button("↺ Reset demonstration"):
    st.session_state.nodes = {k: {**v, "apps": []} for k, v in DEFAULT_NODES.items()}
    st.session_state.logs = []
    st.session_state.last_decision = None
    st.rerun()

st.info("Wokwi ESP32 temperatures can arrive live through the public MQTT broker. Raspberry Pi nodes, CPU/RAM values, ML training data, and physical cooling remain virtual simulations.")

st.subheader("0. ESP32 → MQTT connection")
if mqtt_snapshot["connected"]:
    st.success(f"MQTT subscriber connected to {MQTT_HOST}:{MQTT_PORT} and listening on `{MQTT_TOPIC}`.")
else:
    st.warning("Connecting to the MQTT broker. Start the Wokwi simulation and wait for the first message.")
if mqtt_snapshot["error"]:
    st.caption(f"Connection/message detail: {mqtt_snapshot['error']}")
if mqtt_snapshot["latest"]:
    live = mqtt_snapshot["latest"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Zone 1 temperature", f'{live["zone1_temp"]:.1f} °C')
    m2.metric("Zone 2 temperature", f'{live["zone2_temp"]:.1f} °C')
    m3.metric("Fan 1 command", f'{live["fan1_speed"]}%')
    m4.metric("Fan 2 command", f'{live["fan2_speed"]}%')
    st.caption(f"Last ESP32 message received at {mqtt_snapshot['last_seen']}.")
else:
    st.caption("No ESP32 telemetry received yet. Confirm Wokwi shows MQTT Connected and is publishing to the same topic.")

st.subheader("1. Virtual server monitoring")
cols = st.columns(2)
for col, (name, data) in zip(cols, nodes.items()):
    with col:
        status = "Online" if data["online"] else "Offline"
        col.metric(name, status)
        m1, m2, m3 = st.columns(3)
        m1.metric("Temperature", f'{data["temperature"]:.1f} °C')
        m2.metric("CPU usage", f'{data["cpu"]:.0f}%')
        m3.metric("RAM usage", f'{data["ram"]:.0f}%')
        st.progress(int(data["cpu"]), text="CPU utilization")
        st.progress(int(data["ram"]), text="RAM utilization")
        st.write("Running applications:", ", ".join(data["apps"]) if data["apps"] else "None")

st.divider()
st.subheader("2. Submit a new application")
app_catalog = {
    "Web application": {"cpu": 15, "ram": 15, "description": "Small web service demo"},
    "Data processing": {"cpu": 35, "ram": 25, "description": "Batch data-processing demo"},
    "ML inference": {"cpu": 30, "ram": 30, "description": "Machine-learning inference demo"},
}
left, right = st.columns([2, 1])
with left:
    selected_app = st.selectbox("Choose application", list(app_catalog.keys()))
    st.caption(app_catalog[selected_app]["description"])
with right:
    req = app_catalog[selected_app]
    st.metric("Estimated CPU requirement", f'{req["cpu"]}%')
    st.metric("Estimated RAM requirement", f'{req["ram"]}%')

def choose_node(app_req):
    candidates = []
    rejected = []
    for name, d in nodes.items():
        reasons = []
        if not d["online"]:
            reasons.append("server offline")
        if d["temperature"] >= 48:
            reasons.append("temperature safety threshold reached (≥48°C)")
        if d["cpu"] + app_req["cpu"] > 90:
            reasons.append("insufficient CPU headroom")
        if d["ram"] + app_req["ram"] > 90:
            reasons.append("insufficient RAM headroom")
        if reasons:
            rejected.append((name, reasons))
            continue
        # Lower score is better. Temperature, CPU and RAM pressure all matter.
        score = (d["temperature"] / 50) * 0.40 + (d["cpu"] / 100) * 0.35 + (d["ram"] / 100) * 0.25
        candidates.append((score, name))
    if not candidates:
        return None, rejected
    candidates.sort()
    return candidates[0][1], rejected

if st.button("🚀 Submit application — automatic placement", type="primary"):
    chosen, rejected = choose_node(req)
    if chosen is None:
        st.session_state.last_decision = {"status": "Rejected", "app": selected_app, "node": None, "reason": "No suitable server available"}
        st.session_state.logs.insert(0, f"REJECTED: {selected_app} — no suitable server available")
    else:
        d = nodes[chosen]
        d["apps"].append(selected_app)
        d["cpu"] = min(100.0, d["cpu"] + req["cpu"])
        d["ram"] = min(100.0, d["ram"] + req["ram"])
        # Synthetic workload-related heat increase for demonstration.
        d["temperature"] = min(55.0, d["temperature"] + req["cpu"] * 0.08)
        st.session_state.last_decision = {"status": "Deployed", "app": selected_app, "node": chosen, "reason": "Best eligible score after safety/resource checks"}
        st.session_state.logs.insert(0, f"DEPLOYED: {selected_app} -> {chosen}")
    st.rerun()

if st.session_state.last_decision:
    d = st.session_state.last_decision
    if d["status"] == "Deployed":
        st.success(f'Application "{d["app"]}" deployed to **{d["node"]}**. This is the selected virtual node in the simulation.')
        st.caption(d["reason"])
    else:
        st.error(f'Application "{d["app"]}" was not deployed: {d["reason"]}.')

st.divider()
st.subheader("3. ML-based cooling prediction")
cool_rows = []
for name, d in nodes.items():
    # Demonstration trend is zero; a future live sensor integration can replace it.
    features = make_cooling_features(d)
    pred = cooling_model.predict(features)[0]
    probs = cooling_model.predict_proba(features)[0]
    confidence = float(max(probs) * 100)
    fan = {"Low": 30, "Medium": 60, "High": 90}[pred]
    cool_rows.append({"Virtual zone": name, "Predicted cooling": pred, "Suggested virtual fan speed": f"{fan}%", "Model confidence": f"{confidence:.0f}%"})
st.dataframe(pd.DataFrame(cool_rows), use_container_width=True, hide_index=True)
st.caption("ML note: this Random Forest is trained on synthetic demonstration data. Its predictions illustrate the pipeline; they are not calibrated for real server thermal safety.")

# Send the two zone-specific ML fan commands to the ESP32 over MQTT.
# The ESP32 subscribes to MQTT_COMMAND_TOPIC and applies these PWM percentages.
fan_commands = {}
for name, d in nodes.items():
    features = make_cooling_features(d)
    prediction = cooling_model.predict(features)[0]
    fan_commands[name] = {"Low": 30, "Medium": 60, "High": 90}[prediction]

command_payload = {
    "fan1_speed": int(fan_commands["Virtual Raspberry Pi 1"]),
    "fan2_speed": int(fan_commands["Virtual Raspberry Pi 2"]),
}
command_status = "Waiting for MQTT connection"
if mqtt_snapshot["connected"]:
    try:
        result = mqtt_connection["client"].publish(
            MQTT_COMMAND_TOPIC,
            json.dumps(command_payload),
            qos=0,
            retain=False,
        )
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            command_status = "ML fan commands published to MQTT"
        else:
            command_status = f"MQTT publish returned code {result.rc}"
    except Exception as exc:
        command_status = f"Could not publish fan commands: {exc}"

st.info(f"{command_status} | Fan 1: {command_payload['fan1_speed']}% | Fan 2: {command_payload['fan2_speed']}%")
st.caption(f"Command topic: {MQTT_COMMAND_TOPIC}. Keep the Wokwi ESP32 simulation running to receive commands.")

st.subheader("4. Virtual cooling response")
fan_cols = st.columns(2)
for col, (name, d) in zip(fan_cols, nodes.items()):
    features = make_cooling_features(d)
    pred = cooling_model.predict(features)[0]
    fan = {"Low": 30, "Medium": 60, "High": 90}[pred]
    with col:
        st.write(f"**{name} — virtual fan**")
        st.progress(fan, text=f"Simulated fan command: {fan}% ({pred} cooling)")
        if st.button(f"Apply simulated cooling to {name}", key=f"cool_{name}"):
            # Simple illustrative thermal response, not a physical model.
            d["temperature"] = max(22.0, d["temperature"] - fan * 0.035)
            st.session_state.logs.insert(0, f"SIMULATED COOLING: {name}, fan {fan}%")
            st.rerun()

st.divider()
st.subheader("5. Execution and system event log")
if st.session_state.logs:
    for item in st.session_state.logs[:12]:
        st.write("•", item)
else:
    st.write("No application submissions yet.")

st.subheader("6. Prototype architecture and limitations")
st.markdown("""
- **Laptop/cloud app:** central dashboard and Python scheduler.
- **Virtual Node 1 and Node 2:** simulated server records inside this app.
- **Workload placement:** actual Python decision logic selects an eligible virtual node.
- **Application execution:** the demo records the application against that node; it does not start a separate Linux process/container on a real Raspberry Pi.
- **ML:** Random Forest trained on synthetic sample data predicts a cooling class.
- **Cooling:** ESP32 fan-speed values are received from the Wokwi simulation; physical fans and actual cooling are not connected. Dashboard cooling response remains simulated.
""")
