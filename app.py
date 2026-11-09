
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

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Mini Data Center | Virtual Prototype",
    page_icon="🖥️",
    layout="wide"
)

st.title("🖥️ Mini Data Center — Virtual Prototype")

st.caption(
    "Wokwi ESP32 + DHT22 simulator sends live temperature/humidity telemetry through MQTT | "
    "Raspberry Pi nodes and CPU/RAM remain virtual"
)


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
        "lock": threading.Lock(),
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
                raise ValueError(
                    "Message is missing expected fields"
                )

            humidity_value = payload.get("humidity")
            humidity_value = (
                float(humidity_value)
                if humidity_value is not None
                else None
            )

            if humidity_value is not None and not 0.0 <= humidity_value <= 100.0:
                raise ValueError("Humidity must be between 0 and 100 percent")

            clean = {
                "zone1_temp": float(payload["zone1_temp"]),
                "zone2_temp": float(payload["zone2_temp"]),
                "humidity": humidity_value,
                "fan1_speed": int(payload["fan1_speed"]),
                "fan2_speed": int(payload["fan2_speed"]),
            }

            with state["lock"]:

                state["latest"] = clean

                state["last_seen"] = (
                    datetime.now().strftime("%H:%M:%S")
                )

                state["error"] = None

        except Exception as exc:

            with state["lock"]:
                state["error"] = str(exc)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=f"mini-dc-dashboard-{uuid.uuid4().hex[:8]}",
        transport="websockets",
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
    },
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
    },
}


# =========================================================
# 7. SESSION STATE INITIALIZATION
# =========================================================

if "nodes" not in st.session_state:

    st.session_state.nodes = {
        name: {**data, "apps": []}
        for name, data in DEFAULT_NODES.items()
    }


if "deployments" not in st.session_state:
    st.session_state.deployments = []


if "logs" not in st.session_state:
    st.session_state.logs = []


if "last_decision" not in st.session_state:
    st.session_state.last_decision = None


# Recover missing fields if an older dashboard session exists.
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

    # Convert any old application-name records to deployment records.
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


# Rebuild deployment records from server records.
all_deployments = []

for name, node in st.session_state.nodes.items():

    for app in node["apps"]:

        app["node"] = name
        all_deployments.append(app)


st.session_state.deployments = all_deployments


# Recalculate actual resource usage.
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

st.sidebar.header("⚙️ Simulation controls")

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
        "Temperature and DHT22 humidity values come from Wokwi MQTT when messages arrive."
    )

else:

    st.sidebar.caption(
        "Manual demo mode: all displayed readings are simulated."
    )


# Apply live ESP32 temperature readings.
if live_mode and mqtt_snapshot["latest"]:

    nodes["Virtual Raspberry Pi 1"]["temperature"] = (
        mqtt_snapshot["latest"]["zone1_temp"]
    )

    nodes["Virtual Raspberry Pi 2"]["temperature"] = (
        mqtt_snapshot["latest"]["zone2_temp"]
    )


# Sidebar server controls.
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


# Recalculate after sidebar changes.
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

    st.rerun()


# =========================================================
# 10. PROJECT INFORMATION
# =========================================================

st.info(
    "Wokwi ESP32 temperatures can arrive live through the public MQTT broker. "
    "Raspberry Pi nodes, CPU/RAM values, ML training data, and physical cooling "
    "remain virtual simulations."
)


# =========================================================
# 11. ESP32 MQTT CONNECTION DISPLAY
# =========================================================

st.subheader("0. ESP32 → MQTT connection")

if mqtt_snapshot["connected"]:

    st.success(
        f"MQTT subscriber connected to "
        f"{MQTT_HOST}:{MQTT_PORT} and listening on `{MQTT_TOPIC}`."
    )

else:

    st.warning(
        "Connecting to MQTT broker. "
        "Start Wokwi simulation and wait for the first message."
    )


if mqtt_snapshot["error"]:

    st.caption(
        f"Connection/message detail: {mqtt_snapshot['error']}"
    )


if mqtt_snapshot["latest"]:

    live = mqtt_snapshot["latest"]

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric(
        "Zone 1 temperature",
        f'{live["zone1_temp"]:.1f} °C'
    )

    m2.metric(
        "Zone 2 temperature",
        f'{live["zone2_temp"]:.1f} °C'
    )

    humidity = live.get("humidity")
    m3.metric(
        "Live humidity (DHT22)",
        f"{humidity:.1f}%" if humidity is not None else "Not available"
    )

    m4.metric(
        "Fan 1 command",
        f'{live["fan1_speed"]}%'
    )

    m5.metric(
        "Fan 2 command",
        f'{live["fan2_speed"]}%'
    )

    st.caption(
        f"Last ESP32 message received at {mqtt_snapshot['last_seen']}."
    )

else:

    st.caption(
        "No ESP32 telemetry received yet. "
        "Confirm Wokwi shows MQTT Connected and publishes to the same topic."
    )


# =========================================================
# 12. VIRTUAL SERVER MONITORING
# =========================================================

st.subheader("1. Virtual server monitoring")

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
            "CPU usage",
            f'{data["cpu"]:.0f}%'
        )

        m3.metric(
            "RAM usage",
            f'{data["ram"]:.0f}%'
        )

        st.metric(
            "Workload heat load",
            f'{data["heat_load"]:.2f}'
        )

        st.progress(
            int(min(100, data["cpu"])),
            text="CPU utilization"
        )

        st.progress(
            int(min(100, data["ram"])),
            text="RAM utilization"
        )

        st.write(
            "Running applications:",
            ", ".join(
                app["app"] for app in data["apps"]
            ) if data["apps"] else "None"
        )


# =========================================================
# 13. APPLICATION SUBMISSION
# =========================================================

st.divider()

st.subheader("2. Submit a new application")

left, right = st.columns([2, 1])

with left:

    selected_app = st.selectbox(
        "Choose application",
        list(app_catalog.keys())
    )

    st.caption(
        app_catalog[selected_app]["description"]
    )

with right:

    req = app_catalog[selected_app]

    st.metric(
        "Estimated CPU requirement",
        f'{req["cpu"]}%'
    )

    st.metric(
        "Estimated RAM requirement",
        f'{req["ram"]}%'
    )

    st.metric(
        "Estimated heat load",
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
    "🚀 Submit application — automatic placement",
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
            "Check whether the servers are online and have sufficient "
            "CPU, RAM and temperature capacity."
        )


# =========================================================
# 17. RUNNING APPLICATIONS
# =========================================================

st.divider()

st.subheader("3. Running applications")

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

st.subheader("4. Remove a running application")

if st.session_state.deployments:

    deployment_options = {

        f'{d["app"]} | {d["node"]} | ID: {d["id"]}': d["id"]

        for d in st.session_state.deployments
    }

    selected_deployment = st.selectbox(
        "Select application to remove",
        list(deployment_options.keys()),
        key="remove_application_select"
    )

    if st.button(
        "🗑️ Remove selected application",
        type="secondary"
    ):

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

            # Remove only the selected application.
            server["apps"] = [
                app for app in server["apps"]
                if app["id"] != deployment_id
            ]

            # Recalculate CPU, RAM and heat from remaining apps.
            recalculate_server_resources()

            # Remove deployment record.
            st.session_state.deployments = [
                d for d in st.session_state.deployments
                if d["id"] != deployment_id
            ]

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

            st.rerun()

else:

    st.info("There are no running applications to remove.")


# =========================================================
# 19. ML-BASED COOLING PREDICTION
# =========================================================

st.divider()

st.subheader("5. ML-based cooling prediction")

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

        "Virtual zone": name,

        "Predicted cooling": prediction,

        "Suggested virtual fan speed": f"{fan}%",

        "Model confidence": f"{confidence:.0f}%"
    })


st.dataframe(
    pd.DataFrame(cool_rows),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "ML note: this Random Forest is trained on synthetic demonstration data. "
    "Its predictions illustrate the pipeline and are not calibrated "
    "for real server thermal safety."
)


# =========================================================
# 20. VIRTUAL COOLING RESPONSE
# =========================================================

st.divider()

st.subheader("6. Virtual cooling response")

manual_mode = st.toggle(
    "Enable manual fan control",
    value=False,
    key="manual_fan_control"
)


# Manual fan mode.
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


# Automatic ML fan mode.
else:

    final_fan_commands = fan_commands

    st.success(
        "Automatic ML cooling control is active."
    )


# Display virtual fan controls.
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

        st.write(f"**{name} — virtual fan**")

        st.progress(
            fan,
            text=f"Simulated fan command: {fan}% ({prediction})"
        )

        if st.button(
            f"Apply simulated cooling to {name}",
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

            command_status = (
                f"MQTT publish error: {result.rc}"
            )

    except Exception as exc:

        command_status = (
            f"Could not publish fan commands: {exc}"
        )

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

st.subheader("7. Execution and system event log")

if st.session_state.logs:

    for item in st.session_state.logs[:15]:

        st.write("•", item)

else:

    st.write("No application submissions yet.")


# =========================================================
# 23. PROTOTYPE ARCHITECTURE AND LIMITATIONS
# =========================================================

st.divider()

st.subheader("8. Prototype architecture and limitations")

st.markdown("""
- **Laptop/cloud app:** central dashboard and Python scheduler.
- **Virtual Node 1 and Node 2:** simulated server records inside this app.
- **Workload placement:** Python scheduler selects an eligible virtual node.
- **Application assignment:** CPU, RAM and workload heat are updated.
- **Application removal:** only the selected application's resources are released.
- **ML:** Random Forest trained on synthetic sample data predicts cooling class.
- **ESP32:** receives fan commands and publishes simulated temperature telemetry.
- **Cooling:** Wokwi LEDs represent fan speed; they do not create physical airflow.
- **Hardware limitation:** virtual Raspberry Pi nodes do not execute real Linux processes or Docker containers.
""")
