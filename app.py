import streamlit as st
import pandas as pd
import json
import threading
import time
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

st.title("💧 Hydro-Trace | AI Water-Saving Engine")
st.caption(
    "AI-assisted virtual data center monitoring, "
    "smart workload scheduling and simulated cooling"
)


# =========================================================
# 2. MQTT CONFIGURATION
# =========================================================

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 8000
MQTT_PATH = "/mqtt"

TELEMETRY_TOPIC = "mini-dc-demo-7f3a91/telemetry"
COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"


# =========================================================
# 3. SHARED MQTT STATE
# =========================================================

@st.cache_resource
def get_shared_state():

    return {
        "lock": threading.Lock(),

        "connected": False,

        "telemetry": {
            "zone1_temp": 20.0,
            "zone2_temp": 20.0,
            "humidity": 40.0,
            "water_flow": 0.0,
            "fan1_speed": 30,
            "fan2_speed": 30
        },

        "last_message_time": None,

        "mqtt_client": None,

        "mqtt_started": False
    }


shared = get_shared_state()


# =========================================================
# 4. MQTT CALLBACKS
# =========================================================

def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code == 0:

        with shared["lock"]:
            shared["connected"] = True

        client.subscribe(TELEMETRY_TOPIC)

    else:

        with shared["lock"]:
            shared["connected"] = False


def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties
):

    with shared["lock"]:
        shared["connected"] = False


def on_message(client, userdata, message):

    try:

        payload = json.loads(message.payload.decode("utf-8"))

        allowed_fields = [
            "zone1_temp",
            "zone2_temp",
            "humidity",
            "water_flow",
            "fan1_speed",
            "fan2_speed"
        ]

        with shared["lock"]:

            for key in allowed_fields:

                if key in payload:

                    value = float(payload[key])

                    if math.isfinite(value):

                        shared["telemetry"][key] = value

            shared["last_message_time"] = datetime.now()

    except Exception as e:

        print("MQTT message error:", e)


# =========================================================
# 5. START MQTT CLIENT
# =========================================================

def start_mqtt():

    if shared["mqtt_started"]:
        return

    try:

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="hydro-trace-dashboard",
            transport="websockets"
        )

        client.ws_set_options(path=MQTT_PATH)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )

        client.loop_start()

        shared["mqtt_client"] = client
        shared["mqtt_started"] = True

    except Exception as e:

        with shared["lock"]:
            shared["connected"] = False

        st.warning(f"MQTT connection issue: {e}")


start_mqtt()


# =========================================================
# 6. LOAD EXISTING ML MODEL
# =========================================================

MODEL_PATH = Path(__file__).parent / "cooling_model.pkl"

try:

    cooling_model = joblib.load(MODEL_PATH)

except Exception as e:

    st.error(
        "Cooling ML model could not be loaded. "
        "Please keep cooling_model.pkl in the same folder as app.py."
    )

    st.exception(e)
    st.stop()


# =========================================================
# 7. APPLICATION CATALOG
# =========================================================

APP_CATALOG = {

    "Web Application": {
        "cpu": 15,
        "ram": 15,
        "gpu": 0,
        "heat": 0.15
    },

    "Data Processing": {
        "cpu": 35,
        "ram": 25,
        "gpu": 5,
        "heat": 0.35
    },

    "ML Inference": {
        "cpu": 30,
        "ram": 30,
        "gpu": 35,
        "heat": 0.30
    },

    "Heavy Analytics": {
        "cpu": 60,
        "ram": 50,
        "gpu": 45,
        "heat": 0.60
    }
}


# =========================================================
# 8. VIRTUAL SERVER INITIALIZATION
# =========================================================

def create_default_nodes():

    return {

        "Raspberry Pi 1": {

            "temperature": 35.0,

            "base_cpu": 20,
            "base_ram": 20,
            "base_gpu": 10,

            "cpu": 20,
            "ram": 20,
            "gpu": 10,

            "heat": 0.0,

            "fan_speed": 30,

            "online": True,

            "apps": []
        },

        "Raspberry Pi 2": {

            "temperature": 32.0,

            "base_cpu": 20,
            "base_ram": 20,
            "base_gpu": 10,

            "cpu": 20,
            "ram": 20,
            "gpu": 10,

            "heat": 0.0,

            "fan_speed": 30,

            "online": True,

            "apps": []
        }
    }


# =========================================================
# 9. SESSION STATE INITIALIZATION
# =========================================================

if "nodes" not in st.session_state:

    st.session_state.nodes = create_default_nodes()


if "event_logs" not in st.session_state:

    st.session_state.event_logs = []


if "history" not in st.session_state:

    st.session_state.history = []


if "last_decision" not in st.session_state:

    st.session_state.last_decision = "No workload assigned yet"


if "auto_cooling" not in st.session_state:

    st.session_state.auto_cooling = True


if "manual_mode" not in st.session_state:

    st.session_state.manual_mode = False


if "last_command" not in st.session_state:

    st.session_state.last_command = None


# =========================================================
# 10. EVENT LOGGER
# =========================================================

def add_log(message):

    timestamp = datetime.now().strftime("%H:%M:%S")

    st.session_state.event_logs.insert(
        0,
        f"[{timestamp}] {message}"
    )

    st.session_state.event_logs = (
        st.session_state.event_logs[:50]
    )


# =========================================================
# 11. RECALCULATE SERVER RESOURCES
# =========================================================

# =========================================================
# 11. RECALCULATE SERVER RESOURCES
# =========================================================

def recalculate_node(node):

    cpu = node.get("base_cpu", 20)
    ram = node.get("base_ram", 20)
    gpu = node.get("base_gpu", 10)

    heat = 0.0

    applications = node.get("apps", [])

    # Handle old or unexpected application data formats
    if not isinstance(applications, list):
        applications = []

    for item in applications:

        # If old data contains a dictionary
        if isinstance(item, dict):

            app_name = (
                item.get("name")
                or item.get("app")
                or item.get("application")
            )

        # If old data contains a string
        elif isinstance(item, str):

            app_name = item

        else:
            continue

        if not isinstance(app_name, str):
            continue

        if app_name in APP_CATALOG:

            app = APP_CATALOG[app_name]

            cpu += app["cpu"]
            ram += app["ram"]
            gpu += app["gpu"]

            heat += app["heat"]

    node["apps"] = [
        item if isinstance(item, str)
        else (
            item.get("name")
            or item.get("app")
            or item.get("application")
        )
        for item in applications
        if (
            isinstance(item, str)
            or (
                isinstance(item, dict)
                and (
                    item.get("name")
                    or item.get("app")
                    or item.get("application")
                )
            )
        )
    ]

    node["cpu"] = min(cpu, 100)
    node["ram"] = min(ram, 100)
    node["gpu"] = min(gpu, 100)

    node["heat"] = min(heat, 2.0)
# =========================================================
# 12. VIRTUAL POWER ESTIMATION
# =========================================================

def estimate_power(node):

    cpu = node["cpu"]
    ram = node["ram"]
    gpu = node["gpu"]
    fan = node["fan_speed"]

    power = (
        8
        + cpu * 0.12
        + ram * 0.04
        + gpu * 0.10
        + fan * 0.03
    )

    return round(power, 2)


# =========================================================
# 13. HTES SCORE
# =========================================================

def calculate_htes(node):

    temperature = node["temperature"]
    cpu = node["cpu"]
    ram = node["ram"]
    gpu = node["gpu"]
    fan = node["fan_speed"]

    thermal_score = max(
        0,
        100 - max(0, temperature - 25) * 2
    )

    resource_score = max(
        0,
        100 - (
            cpu * 0.35
            + ram * 0.30
            + gpu * 0.35
        )
    )

    cooling_score = max(
        0,
        100 - fan * 0.25
    )

    htes = (
        thermal_score * 0.50
        + resource_score * 0.30
        + cooling_score * 0.20
    )

    return round(max(0, min(100, htes)), 1)


# HTES = Hydro-Trace Efficiency Score.
# This is a project-defined demo index, not an industry standard.


# =========================================================
# 14. SIDEBAR CONTROLS
# =========================================================

st.sidebar.title("⚙️ System Controls")

live_mode = st.sidebar.toggle(
    "ESP32 Live Telemetry",
    value=True
)

manual_mode = st.sidebar.toggle(
    "Manual Control Mode",
    value=False
)

st.session_state.manual_mode = manual_mode

st.sidebar.divider()

st.sidebar.subheader("Virtual Server Base Resources")

for node_name, node in st.session_state.nodes.items():

    with st.sidebar.expander(node_name):

        node["base_cpu"] = st.slider(
            f"{node_name} Base CPU",
            5,
            60,
            int(node["base_cpu"]),
            key=f"{node_name}_base_cpu"
        )

        node["base_ram"] = st.slider(
            f"{node_name} Base RAM",
            5,
            60,
            int(node["base_ram"]),
            key=f"{node_name}_base_ram"
        )

        node["base_gpu"] = st.slider(
            f"{node_name} Base GPU",
            0,
            60,
            int(node["base_gpu"]),
            key=f"{node_name}_base_gpu"
        )

        node["online"] = st.checkbox(
            f"{node_name} Online",
            value=node["online"],
            key=f"{node_name}_online"
        )

        recalculate_node(node)


if st.sidebar.button(
    "🔄 Reset Virtual System",
    use_container_width=True
):

    st.session_state.nodes = create_default_nodes()

    st.session_state.event_logs = []

    st.session_state.history = []

    st.session_state.last_decision = (
        "System reset completed"
    )

    st.rerun()


# =========================================================
# 15. READ ESP32 TELEMETRY
# =========================================================

with shared["lock"]:

    telemetry = shared["telemetry"].copy()

    mqtt_connected = shared["connected"]

    last_message_time = shared["last_message_time"]


if live_mode and mqtt_connected:

    st.session_state.nodes["Raspberry Pi 1"]["temperature"] = (
        telemetry["zone1_temp"]
    )

    st.session_state.nodes["Raspberry Pi 2"]["temperature"] = (
        telemetry["zone2_temp"]
    )


# =========================================================
# 16. SYSTEM STATUS
# =========================================================

st.subheader("📡 System Connectivity")

col1, col2, col3 = st.columns(3)

with col1:

    if mqtt_connected:

        st.success("MQTT Connected")

    else:

        st.error("MQTT Disconnected")


with col2:

    if live_mode:

        st.info("ESP32 Live Mode")

    else:

        st.info("Virtual Simulation Mode")


with col3:

    if last_message_time:

        st.caption(
            f"Last telemetry: "
            f"{last_message_time.strftime('%H:%M:%S')}"
        )

    else:

        st.caption("Waiting for ESP32 telemetry")


# =========================================================
# 17. LIVE SENSOR METRICS
# =========================================================

st.subheader("🌡️ Live Sensor Monitoring")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Zone 1 Temperature",
    f"{telemetry['zone1_temp']:.1f} °C"
)

c2.metric(
    "Zone 2 Temperature",
    f"{telemetry['zone2_temp']:.1f} °C"
)

c3.metric(
    "Humidity",
    f"{telemetry['humidity']:.1f} %"
)

c4.metric(
    "Virtual Water Flow",
    f"{telemetry['water_flow']:.2f} L/min"
)


# =========================================================
# 18. SERVER METRICS
# =========================================================

st.divider()

st.subheader("🖥️ Virtual Raspberry Pi Monitoring")

server_columns = st.columns(2)

for index, (node_name, node) in enumerate(
    st.session_state.nodes.items()
):

    with server_columns[index]:

        st.markdown(f"### {node_name}")

        status = (
            "🟢 Online"
            if node["online"]
            else "🔴 Offline"
        )

        st.write(status)

        st.metric(
            "Temperature",
            f"{node['temperature']:.1f} °C"
        )

        st.progress(
            min(node["cpu"], 100) / 100,
            text=f"CPU Usage: {node['cpu']}%"
        )

        st.progress(
            min(node["ram"], 100) / 100,
            text=f"RAM Usage: {node['ram']}%"
        )

        st.progress(
            min(node["gpu"], 100) / 100,
            text=f"Virtual GPU Usage: {node['gpu']}%"
        )

        st.metric(
            "Estimated Power",
            f"{estimate_power(node)} W"
        )

        st.metric(
            "HTES Efficiency Score",
            f"{calculate_htes(node)} / 100"
        )


# =========================================================
# PART 1 ENDS HERE
# PART 2 WILL CONTINUE IN THE SAME app.py FILE
# =========================================================
# =========================================================
# 19. TEMPERATURE HISTORY AND CHARTS
# =========================================================

st.divider()

st.subheader("📊 Live Performance Analytics")

node1 = st.session_state.nodes["Raspberry Pi 1"]
node2 = st.session_state.nodes["Raspberry Pi 2"]

history_record = {
    "time": datetime.now().strftime("%H:%M:%S"),

    "zone1_temp": node1["temperature"],
    "zone2_temp": node2["temperature"],

    "fan1_speed": telemetry["fan1_speed"],
    "fan2_speed": telemetry["fan2_speed"],

    "water_flow": telemetry["water_flow"],

    "avg_temperature": (
        node1["temperature"] + node2["temperature"]
    ) / 2
}

# Add history only when values change or 5 seconds pass
now = time.time()

if (
    "last_history_time" not in st.session_state
    or now - st.session_state.last_history_time >= 5
):

    st.session_state.history.append(history_record)

    st.session_state.history = (
        st.session_state.history[-100:]
    )

    st.session_state.last_history_time = now


history_df = pd.DataFrame(
    st.session_state.history
)


if not history_df.empty:

    chart1, chart2 = st.columns(2)

    with chart1:

        st.markdown("**Temperature Monitoring**")

        st.line_chart(
            history_df.set_index("time")[
                ["zone1_temp", "zone2_temp"]
            ]
        )

    with chart2:

        st.markdown("**Fan Speed Monitoring**")

        st.line_chart(
            history_df.set_index("time")[
                ["fan1_speed", "fan2_speed"]
            ]
        )

    chart3, chart4 = st.columns(2)

    with chart3:

        st.markdown("**Virtual Water Flow Over Time**")

        st.line_chart(
            history_df.set_index("time")[
                ["water_flow"]
            ]
        )

    with chart4:

        st.markdown("**Temperature Comparison**")

        st.line_chart(
            history_df.set_index("time")[
                ["avg_temperature"]
            ]
        )

else:

    st.info("Waiting for monitoring history...")


# =========================================================
# 20. APPLICATION SELECTION
# =========================================================

st.divider()

st.subheader("📦 Workload Management")

st.write(
    "Select an application. The scheduler will evaluate "
    "temperature, CPU, RAM and virtual GPU capacity "
    "before assigning the workload."
)

selected_app = st.selectbox(
    "Select Application",
    list(APP_CATALOG.keys())
)

app_requirement = APP_CATALOG[selected_app]

req1, req2, req3, req4 = st.columns(4)

req1.metric(
    "Required CPU",
    f"{app_requirement['cpu']}%"
)

req2.metric(
    "Required RAM",
    f"{app_requirement['ram']}%"
)

req3.metric(
    "Required GPU",
    f"{app_requirement['gpu']}%"
)

req4.metric(
    "Heat Load",
    f"{app_requirement['heat']:.2f}"
)


# =========================================================
# 21. SMART SCHEDULER
# =========================================================

def calculate_scheduler_score(node):

    temperature = node["temperature"]
    cpu = node["cpu"]
    ram = node["ram"]
    gpu = node["gpu"]

    # Lower score means a better candidate.
    score = (
        temperature * 0.35
        + cpu * 0.25
        + ram * 0.20
        + gpu * 0.20
    )

    return score


def select_best_server(app_name):

    requirements = APP_CATALOG[app_name]

    candidates = []

    for node_name, node in st.session_state.nodes.items():

        if not node["online"]:
            continue

        if node["temperature"] >= 48:
            continue

        if node["cpu"] + requirements["cpu"] > 90:
            continue

        if node["ram"] + requirements["ram"] > 90:
            continue

        if node["gpu"] + requirements["gpu"] > 90:
            continue

        score = calculate_scheduler_score(node)

        candidates.append(
            (score, node_name)
        )

    if not candidates:

        return None

    candidates.sort(key=lambda item: item[0])

    return candidates[0][1]


# =========================================================
# 22. ASSIGN WORKLOAD
# =========================================================

if st.button(
    "🚀 Assign Application Automatically",
    use_container_width=True
):

    selected_server = select_best_server(selected_app)

    if selected_server is None:

        st.error(
            "No suitable server available. "
            "Check temperature, CPU, RAM, GPU capacity "
            "or server online status."
        )

        add_log(
            f"Assignment failed for {selected_app}"
        )

    else:

        node = st.session_state.nodes[selected_server]

        node["apps"].append(selected_app)

        recalculate_node(node)

        st.session_state.last_decision = (
            f"{selected_app} assigned to {selected_server}"
        )

        add_log(
            f"{selected_app} assigned to {selected_server}"
        )

        st.success(
            f"{selected_app} successfully assigned "
            f"to {selected_server}"
        )

        st.rerun()


st.info(
    f"Last Scheduler Decision: "
    f"{st.session_state.last_decision}"
)


# =========================================================
# 23. RUNNING APPLICATIONS
# =========================================================

st.divider()

st.subheader("📋 Running Applications")

for node_name, node in st.session_state.nodes.items():

    with st.expander(
        f"{node_name} — {len(node['apps'])} Applications"
    ):

        if node["apps"]:

            for app_name in node["apps"]:

                st.write(f"• {app_name}")

        else:

            st.write("No applications running.")

        if node["apps"]:

            remove_app = st.selectbox(
                f"Select application to remove from {node_name}",
                node["apps"],
                key=f"remove_{node_name}"
            )

            if st.button(
                f"Remove from {node_name}",
                key=f"remove_button_{node_name}"
            ):

                node["apps"].remove(remove_app)

                recalculate_node(node)

                add_log(
                    f"{remove_app} removed from {node_name}"
                )

                st.success(
                    f"{remove_app} removed successfully"
                )

                st.rerun()


# =========================================================
# 24. ML COOLING PREDICTION
# =========================================================

st.divider()

st.subheader("🤖 AI-Based Cooling Prediction")

def get_temperature_trend(node_name):

    if len(st.session_state.history) < 2:
        return 0.5

    previous = st.session_state.history[-2]
    current = st.session_state.history[-1]

    if node_name == "Raspberry Pi 1":

        difference = (
            current["zone1_temp"] - previous["zone1_temp"]
        )

    else:

        difference = (
            current["zone2_temp"] - previous["zone2_temp"]
        )

    return round(difference, 2)


def predict_cooling(node_name, node):

    temperature = float(node["temperature"])
    cpu = float(node["cpu"])
    ram = float(node["ram"])

    temp_trend = get_temperature_trend(node_name)

    # IMPORTANT:
    # Existing cooling_model.pkl receives only these
    # four original features. GPU is not passed to it.

    input_data = pd.DataFrame(
        [[temperature, cpu, ram, temp_trend]],
        columns=[
            "temperature",
            "cpu_usage",
            "ram_usage",
            "temp_trend"
        ]
    )

    prediction = cooling_model.predict(input_data)[0]

    prediction = str(prediction).strip().lower()

    if "high" in prediction:

        cooling_level = "High"
        fan_speed = 90

    elif "medium" in prediction:

        cooling_level = "Medium"
        fan_speed = 60

    else:

        cooling_level = "Low"
        fan_speed = 30

    return cooling_level, fan_speed


cooling_results = {}

cooling_columns = st.columns(2)

for index, (node_name, node) in enumerate(
    st.session_state.nodes.items()
):

    level, predicted_fan = predict_cooling(
        node_name,
        node
    )

    cooling_results[node_name] = {
        "level": level,
        "fan": predicted_fan
    }

    with cooling_columns[index]:

        st.markdown(f"### {node_name}")

        st.metric(
            "AI Cooling Level",
            level
        )

        st.metric(
            "Recommended Fan Speed",
            f"{predicted_fan}%"
        )

        if level == "High":

            st.warning(
                "High cooling requirement detected"
            )

        elif level == "Medium":

            st.info(
                "Moderate cooling requirement detected"
            )

        else:

            st.success(
                "Low cooling requirement detected"
            )


# =========================================================
# 25. AUTOMATIC / MANUAL COOLING CONTROL
# =========================================================

st.divider()

st.subheader("❄️ Smart Cooling Control")

auto_cooling = st.toggle(
    "Enable AI Automatic Cooling",
    value=st.session_state.auto_cooling
)

st.session_state.auto_cooling = auto_cooling

if auto_cooling:

    for node_name, node in st.session_state.nodes.items():

        node["fan_speed"] = (
            cooling_results[node_name]["fan"]
        )

    st.success(
        "AI automatic cooling is enabled. "
        "Fan speed is selected from the ML prediction."
    )

else:

    st.info("Manual cooling mode is active.")

    manual1, manual2 = st.columns(2)

    with manual1:

        node1["fan_speed"] = st.slider(
            "Raspberry Pi 1 Fan Speed",
            0,
            100,
            int(node1["fan_speed"]),
            key="manual_fan1"
        )

    with manual2:

        node2["fan_speed"] = st.slider(
            "Raspberry Pi 2 Fan Speed",
            0,
            100,
            int(node2["fan_speed"]),
            key="manual_fan2"
        )


# =========================================================
# 26. SIMULATED COOLING FOR VIRTUAL MODE
# =========================================================

if not live_mode:

    st.caption(
        "Virtual mode: cooling changes the simulated "
        "server temperature in the dashboard."
    )

    if st.button(
        "Apply Simulated Cooling",
        use_container_width=True
    ):

        for node in st.session_state.nodes.values():

            cooling_effect = (
                node["fan_speed"] / 100
            ) * 2.0

            heat_effect = node["heat"] * 0.8

            node["temperature"] = max(
                20,
                node["temperature"]
                + heat_effect
                - cooling_effect
            )

        add_log(
            "Simulated cooling applied to virtual servers"
        )

        st.success(
            "Simulated cooling applied. "
            "Temperature values have been updated."
        )

        st.rerun()


else:

    st.caption(
        "Live mode: ESP32 thermal simulation controls "
        "the reported temperature. Dashboard sends fan "
        "and workload commands through MQTT."
    )


# =========================================================
# 27. PUBLISH COMMANDS TO ESP32
# =========================================================

def publish_esp32_commands():

    client = shared["mqtt_client"]

    if client is None:
        return

    if not mqtt_connected:
        return

    n1 = st.session_state.nodes["Raspberry Pi 1"]
    n2 = st.session_state.nodes["Raspberry Pi 2"]

    command = {

        "fan1_speed": int(n1["fan_speed"]),

        "fan2_speed": int(n2["fan_speed"]),

        "workload_heat1": round(
            min(n1["heat"], 2.0),
            2
        ),

        "workload_heat2": round(
            min(n2["heat"], 2.0),
            2
        )
    }

    command_text = json.dumps(command)

    # Publish only when the command changes.
    if command_text != st.session_state.last_command:

        try:

            result = client.publish(
                COMMAND_TOPIC,
                command_text,
                qos=0
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:

                st.session_state.last_command = command_text

                add_log(
                    "Fan and workload commands sent to ESP32"
                )

        except Exception as e:

            st.warning(
                f"Could not publish MQTT command: {e}"
            )


publish_esp32_commands()


# =========================================================
# 28. COOLING AND WATER FLOW SUMMARY
# =========================================================

st.divider()

st.subheader("💧 Cooling and Water Flow Summary")

average_fan = (
    node1["fan_speed"] + node2["fan_speed"]
) / 2

estimated_virtual_flow = (
    average_fan / 100
) * 20

summary1, summary2, summary3 = st.columns(3)

summary1.metric(
    "Average Fan Speed",
    f"{average_fan:.1f}%"
)

summary2.metric(
    "Virtual Water Flow Estimate",
    f"{estimated_virtual_flow:.2f} L/min"
)

summary3.metric(
    "Total Estimated Power",
    f"{estimate_power(node1) + estimate_power(node2):.2f} W"
)

st.caption(
    "Water flow is a virtual estimate derived from fan speed. "
    "It is not measured by a physical flow sensor."
)


# =========================================================
# 29. SYSTEM EVENT LOG
# =========================================================

st.divider()

st.subheader("📝 System Event Log")

if st.session_state.event_logs:

    for event in st.session_state.event_logs[:15]:

        st.text(event)

else:

    st.info("No events recorded yet.")


# =========================================================
# 30. PROJECT ARCHITECTURE AND LIMITATIONS
# =========================================================

st.divider()

st.subheader("🏗️ Project Architecture")

st.markdown(
    """
    **ESP32 Simulation (Wokwi)**

    Temperature, humidity and fan simulation

    ↓ MQTT Telemetry

    **Hydro-Trace Streamlit Dashboard**

    Live monitoring, virtual Raspberry Pi nodes,
    CPU/RAM/GPU resource tracking and workload scheduling

    ↓ Smart Scheduling

    **AI Cooling Model**

    Cooling level prediction and fan speed selection

    ↓ MQTT Commands

    **ESP32 Simulation**

    Simulated fan response and thermal behaviour
    """
)

with st.expander("ℹ️ Prototype Scope and Limitations"):

    st.write(
        """
        - Raspberry Pi nodes are virtual server representations.
        - GPU utilization is simulated.
        - Power consumption is an estimated project value.
        - HTES is a project-defined efficiency score.
        - Water flow is estimated from fan speed.
        - Cooling is simulated through the ESP32 thermal model.
        - The existing ML model uses temperature, CPU, RAM
          and temperature trend as its input features.
        - This prototype demonstrates scheduling and cooling
          logic; it is not a physical Kubernetes deployment.
        """
    )


# =========================================================
# 31. AUTO REFRESH
# =========================================================

st_autorefresh(
    interval=3000,
    key="hydro_trace_refresh"
)
