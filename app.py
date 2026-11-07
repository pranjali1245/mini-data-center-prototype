
import streamlit as st
import pandas as pd
import json
import threading
import uuid
import joblib
from pathlib import Path
from datetime import datetime
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Mini Data Center Smart Cooling",
    page_icon="❄️",
    layout="wide"
)

st.title("❄️ Mini Data Center - Smart Cooling Dashboard")
st.caption("IoT + ML Based Workload Management and Cooling Prototype")


# =========================================================
# 2. MQTT CONFIGURATION
# =========================================================

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 8000

MQTT_TOPIC = "mini-dc-demo-7f3a91/telemetry"
MQTT_COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"


# =========================================================
# 3. MQTT CALLBACKS AND CONNECTION
# =========================================================

mqtt_lock = threading.Lock()


@st.cache_resource
def create_mqtt_connection():

    state = {
        "connected": False,
        "error": None,
        "zone1_temp": None,
        "zone2_temp": None,
        "zone1_humidity": None,
        "zone2_humidity": None,
        "fan1_speed": 0,
        "fan2_speed": 0,
        "last_seen": None,
        "last_published": None
    }

    def on_connect(client, userdata, flags, rc):

        with mqtt_lock:
            state["connected"] = (rc == 0)
            state["error"] = None if rc == 0 else str(rc)
            state["last_published"] = None

        if rc == 0:
            client.subscribe(MQTT_TOPIC)

    def on_disconnect(client, userdata, rc):

        with mqtt_lock:
            state["connected"] = False

    def on_message(client, userdata, msg):

        try:
            data = json.loads(msg.payload.decode())

            with mqtt_lock:

                state["zone1_temp"] = data.get("zone1_temp")
                state["zone2_temp"] = data.get("zone2_temp")

                state["zone1_humidity"] = data.get("zone1_humidity")
                state["zone2_humidity"] = data.get("zone2_humidity")

                state["fan1_speed"] = data.get("fan1_speed", 0)
                state["fan2_speed"] = data.get("fan2_speed", 0)

                state["last_seen"] = datetime.now().strftime(
                    "%H:%M:%S"
                )

        except Exception as exc:
            with mqtt_lock:
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
        "client": client,
        "state": state
    }


mqtt_connection = create_mqtt_connection()


def get_mqtt_snapshot():

    with mqtt_lock:
        return dict(mqtt_connection["state"])


mqtt_snapshot = get_mqtt_snapshot()


# =========================================================
# 4. LIVE MONITORING MODE
# =========================================================

st.sidebar.header("Monitoring Settings")

live_mode = st.sidebar.toggle(
    "Enable Live ESP32 Monitoring",
    value=False
)

if live_mode:
    st_autorefresh(
        interval=2000,
        key="mqtt_dashboard_refresh"
    )

    if mqtt_snapshot["connected"]:
        st.sidebar.success("MQTT Connected")
    else:
        st.sidebar.warning("Waiting for MQTT connection...")


# =========================================================
# 5. DEFAULT VIRTUAL SERVERS
# =========================================================

DEFAULT_NODES = {

    "Virtual Raspberry Pi 1": {
        "temperature": 42.0,
        "humidity": 45.0,
        "cpu": 85.0,
        "ram": 80.0,
        "heat_load": 0.0,
        "online": True,
        "apps": [],
        "temp_trend": 0.5
    },

    "Virtual Raspberry Pi 2": {
        "temperature": 30.0,
        "humidity": 40.0,
        "cpu": 35.0,
        "ram": 40.0,
        "heat_load": 0.0,
        "online": True,
        "apps": [],
        "temp_trend": 0.5
    }
}


if "nodes" not in st.session_state:
    st.session_state.nodes = {
        name: data.copy()
        for name, data in DEFAULT_NODES.items()
    }

if "logs" not in st.session_state:
    st.session_state.logs = []

if "last_decision" not in st.session_state:
    st.session_state.last_decision = "No application assigned yet."


nodes = st.session_state.nodes


# =========================================================
# 6. APPLY LIVE ESP32 TEMPERATURE
# =========================================================

if live_mode and mqtt_snapshot["connected"]:

    if mqtt_snapshot["zone1_temp"] is not None:
        nodes["Virtual Raspberry Pi 1"]["temperature"] = float(
            mqtt_snapshot["zone1_temp"]
        )

    if mqtt_snapshot["zone2_temp"] is not None:
        nodes["Virtual Raspberry Pi 2"]["temperature"] = float(
            mqtt_snapshot["zone2_temp"]
        )

    if mqtt_snapshot["zone1_humidity"] is not None:
        nodes["Virtual Raspberry Pi 1"]["humidity"] = float(
            mqtt_snapshot["zone1_humidity"]
        )

    if mqtt_snapshot["zone2_humidity"] is not None:
        nodes["Virtual Raspberry Pi 2"]["humidity"] = float(
            mqtt_snapshot["zone2_humidity"]
        )


# =========================================================
# 7. SIDEBAR SERVER CONTROLS
# =========================================================

st.sidebar.header("Virtual Server Controls")

for name, data in nodes.items():

    with st.sidebar.expander(name):

        data["online"] = st.checkbox(
            "Server Online",
            value=data["online"],
            key=f"online_{name}"
        )

        data["cpu"] = st.slider(
            f"{name} CPU Usage",
            0.0,
            100.0,
            float(data["cpu"]),
            key=f"cpu_{name}"
        )

        data["ram"] = st.slider(
            f"{name} RAM Usage",
            0.0,
            100.0,
            float(data["ram"]),
            key=f"ram_{name}"
        )

        if not live_mode:

            data["temperature"] = st.slider(
                f"{name} Temperature",
                20.0,
                80.0,
                float(data["temperature"]),
                key=f"temp_{name}"
            )


# =========================================================
# 8. COOLING ML MODEL
# =========================================================

@st.cache_resource
def load_cooling_model():

    model_path = Path(__file__).parent / "cooling_model.pkl"

    if model_path.exists():
        return joblib.load(model_path)

    return None


cooling_model = load_cooling_model()


def make_cooling_features(node_data):

    return pd.DataFrame([{
        "temperature": float(node_data["temperature"]),
        "cpu_usage": float(node_data["cpu"]),
        "ram_usage": float(node_data["ram"]),
        "temp_trend": float(node_data.get("temp_trend", 0.5))
    }])


def predict_cooling(node_data):

    if cooling_model is not None:

        features = make_cooling_features(node_data)
        prediction = cooling_model.predict(features)[0]

        return str(prediction)

    # Fallback if model file is unavailable
    if node_data["temperature"] >= 55 or node_data["cpu"] >= 85:
        return "High"

    elif node_data["temperature"] >= 40 or node_data["cpu"] >= 60:
        return "Medium"

    return "Low"


FAN_SPEEDS = {
    "Low": 30,
    "Medium": 60,
    "High": 90
}


# =========================================================
# 9. APPLICATION CATALOG
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
# 10. WORKLOAD SCHEDULER
# =========================================================

def select_best_server(app_name):

    req = app_catalog[app_name]

    eligible_nodes = []

    for name, data in nodes.items():

        if not data["online"]:
            continue

        if data["temperature"] >= 48:
            continue

        if data["cpu"] + req["cpu"] > 90:
            continue

        if data["ram"] + req["ram"] > 90:
            continue

        score = (
            0.40 * data["temperature"] +
            0.35 * data["cpu"] +
            0.25 * data["ram"]
        )

        eligible_nodes.append((score, name))

    if not eligible_nodes:
        return None

    eligible_nodes.sort(key=lambda x: x[0])

    return eligible_nodes[0][1]


# =========================================================
# 11. SERVER OVERVIEW
# =========================================================

st.header("1. Virtual Server Overview")

server_cols = st.columns(2)

for col, (name, data) in zip(server_cols, nodes.items()):

    with col:

        st.subheader(name)

        st.metric(
            "Temperature",
            f"{data['temperature']:.1f} °C"
        )

        st.metric(
            "Humidity",
            f"{data['humidity']:.1f} %"
        )

        st.metric(
            "CPU Usage",
            f"{data['cpu']:.1f} %"
        )

        st.metric(
            "RAM Usage",
            f"{data['ram']:.1f} %"
        )

        st.metric(
            "Workload Heat",
            f"{data['heat_load']:.2f}"
        )

        st.write(
            "Status:",
            "🟢 Online" if data["online"] else "🔴 Offline"
        )

        st.write("Assigned applications:", data["apps"])


# =========================================================
# 12. APPLICATION ASSIGNMENT
# =========================================================

st.divider()

st.header("2. Application Workload Assignment")

selected_app = st.selectbox(
    "Select Application",
    list(app_catalog.keys())
)

st.write(app_catalog[selected_app]["description"])

if st.button("Submit Application", type="primary"):

    chosen = select_best_server(selected_app)

    if chosen is None:

        st.error(
            "No suitable server available. "
            "Check temperature, CPU, RAM and server status."
        )

    else:

        req = app_catalog[selected_app]
        data = nodes[chosen]

        data["apps"].append(selected_app)

        data["cpu"] = min(
            100.0,
            data["cpu"] + req["cpu"]
        )

        data["ram"] = min(
            100.0,
            data["ram"] + req["ram"]
        )

        data["heat_load"] = min(
            2.0,
            data["heat_load"] + req["heat"]
        )

        st.session_state.last_decision = (
            f"{selected_app} assigned to {chosen}"
        )

        st.session_state.logs.insert(
            0,
            f"{datetime.now().strftime('%H:%M:%S')} - "
            f"{selected_app} assigned to {chosen}"
        )

        st.success(st.session_state.last_decision)


st.info(
    "Scheduler considers server temperature, CPU, RAM and online status."
)


# =========================================================
# 13. ML COOLING PREDICTION
# =========================================================

st.divider()

st.header("3. ML-Based Cooling Prediction")

fan_commands = {}

predictions = {}

cooling_cols = st.columns(2)

for col, (name, data) in zip(cooling_cols, nodes.items()):

    prediction = predict_cooling(data)

    fan_speed = FAN_SPEEDS[prediction]

    predictions[name] = prediction
    fan_commands[name] = fan_speed

    with col:

        st.subheader(name)

        st.write(f"ML Cooling Prediction: **{prediction}**")

        st.progress(
            fan_speed,
            text=f"Automatic fan command: {fan_speed}%"
        )


if cooling_model is None:
    st.warning(
        "cooling_model.pkl not found. "
        "Using fallback rule-based cooling prediction."
    )


# =========================================================
# 14. MANUAL FAN CONTROL
# =========================================================

st.divider()

st.header("4. Fan Control")

manual_mode = st.toggle(
    "Enable Manual Fan Control",
    value=False
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

    st.info("Manual mode active. Slider values will control fan commands.")

else:

    final_fan_commands = fan_commands

    st.success("Automatic ML fan control active.")


# =========================================================
# 15. VIRTUAL COOLING RESPONSE BUTTONS
# =========================================================

st.divider()

st.header("5. Virtual Cooling Response")

if live_mode:

    st.info(
        "Live mode is active. ESP32 telemetry controls displayed "
        "temperatures. Use fan sliders or ML mode for ESP32 fan commands."
    )

cooling_cols = st.columns(2)

for col, (name, data) in zip(cooling_cols, nodes.items()):

    fan = final_fan_commands[name]

    with col:

        st.subheader(name)

        st.progress(
            fan,
            text=f"Selected fan speed: {fan}%"
        )

        if not live_mode:

            if st.button(
                f"Apply simulated cooling to {name}",
                key=f"cool_{name}"
            ):

                data["temperature"] = max(
                    22.0,
                    data["temperature"] - fan * 0.035
                )

                st.session_state.logs.insert(
                    0,
                    f"SIMULATED COOLING: {name}, fan {fan}%"
                )

                st.success("Virtual temperature reduced.")

        else:

            st.caption(
                "This local simulation button is disabled during live telemetry."
            )


# =========================================================
# 16. FINAL MQTT COMMAND PAYLOAD
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


# =========================================================
# 17. SINGLE MQTT PUBLISH BLOCK
# =========================================================

if mqtt_snapshot["connected"]:

    payload_string = json.dumps(final_payload)

    with mqtt_lock:
        previous_payload = mqtt_connection["state"]["last_published"]

    if payload_string != previous_payload:

        result = mqtt_connection["client"].publish(
            MQTT_COMMAND_TOPIC,
            payload_string,
            qos=0,
            retain=False
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            with mqtt_lock:
                mqtt_connection["state"]["last_published"] = payload_string

            st.success("Cooling commands sent to ESP32.")

        else:

            st.warning(
                f"MQTT publish error: {result.rc}"
            )

    else:

        st.caption("No change in cooling commands.")

else:

    st.warning("Waiting for MQTT connection.")


# =========================================================
# 18. LIVE ESP32 TELEMETRY
# =========================================================

st.divider()

st.header("6. ESP32 Live Telemetry")

if mqtt_snapshot["connected"]:

    telemetry_cols = st.columns(4)

    telemetry_cols[0].metric(
        "Zone 1 Temperature",
        (
            f"{mqtt_snapshot['zone1_temp']:.1f} °C"
            if mqtt_snapshot["zone1_temp"] is not None
            else "Waiting"
        )
    )

    telemetry_cols[1].metric(
        "Zone 2 Temperature",
        (
            f"{mqtt_snapshot['zone2_temp']:.1f} °C"
            if mqtt_snapshot["zone2_temp"] is not None
            else "Waiting"
        )
    )

    telemetry_cols[2].metric(
        "Fan 1 Speed",
        f"{mqtt_snapshot['fan1_speed']}%"
    )

    telemetry_cols[3].metric(
        "Fan 2 Speed",
        f"{mqtt_snapshot['fan2_speed']}%"
    )

    st.caption(
        f"Last telemetry received: {mqtt_snapshot['last_seen']}"
    )

    st.write(
        "Humidity fields are displayed only when ESP32 sends "
        "zone1_humidity and zone2_humidity."
    )

else:

    st.warning(
        "ESP32 is not connected. Enable Live Monitoring and "
        "check the Wokwi MQTT connection."
    )


# =========================================================
# 19. WORKLOAD AND COOLING LOGS
# =========================================================

st.divider()

st.header("7. Activity Logs")

if st.session_state.logs:

    for entry in st.session_state.logs[:20]:
        st.write("•", entry)

else:

    st.info("No activity recorded yet.")


st.write("Latest Scheduler Decision:")
st.info(st.session_state.last_decision)


# =========================================================
# 20. RESET DEMONSTRATION
# =========================================================

st.divider()

if st.button("Reset Demonstration"):

    st.session_state.nodes = {
        name: data.copy()
        for name, data in DEFAULT_NODES.items()
    }

    st.session_state.logs = []

    st.session_state.last_decision = (
        "No application assigned yet."
    )

    st.success("Virtual demonstration reset successfully.")

    st.rerun()
