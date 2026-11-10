
import streamlit as st
import pandas as pd
import json
import time
import math
import uuid
import threading
from datetime import datetime
from collections import deque

import joblib
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh


# =====================================================
# HYDRO-TRACE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="HYDRO-TRACE",
    page_icon="🌐",
    layout="wide"
)

BROKER = "broker.hivemq.com"
PORT = 8000
WS_PATH = "/mqtt"

TELEMETRY_TOPIC = "mini-dc-demo-7f3a91/telemetry"
COMMAND_TOPIC = "mini-dc-demo-7f3a91/fan_command"

MODEL_PATH = "cooling_model.pkl"


# =====================================================
# SHARED MQTT DATA
# =====================================================

if "shared" not in st.session_state:

    st.session_state.shared = {
        "lock": threading.Lock(),

        "connected": False,

        "last_seen": None,

        "telemetry": {
            "zone1_temp": 28.0,
            "zone2_temp": 30.0,
            "humidity": 50.0,
            "water_flow": 0.0,
            "fan1_speed": 0.0,
            "fan2_speed": 0.0
        },

        "history": deque(maxlen=300),

        "client": None,

        "started": False,

        "error": "",

        "events": deque(maxlen=100)
    }


shared = st.session_state.shared


def add_event(message):

    with shared["lock"]:

        shared["events"].appendleft({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Event": message
        })


# =====================================================
# MQTT CALLBACKS
# =====================================================

def on_connect(client, userdata, flags, reason_code, properties=None):

    success = getattr(reason_code, "value", reason_code) == 0

    with shared["lock"]:

        shared["connected"] = success

    if success:

        client.subscribe(TELEMETRY_TOPIC)

        add_event("ESP32 connected successfully")

    else:

        add_event("MQTT connection failed")


def on_disconnect(client, userdata, *args):

    with shared["lock"]:

        shared["connected"] = False

    add_event("MQTT disconnected")


def on_message(client, userdata, message):

    try:

        data = json.loads(
            message.payload.decode()
        )

        defaults = {
            "zone1_temp": 28.0,
            "zone2_temp": 30.0,
            "humidity": 50.0,
            "water_flow": 0.0,
            "fan1_speed": 0.0,
            "fan2_speed": 0.0
        }

        telemetry = {}

        for key, default in defaults.items():

            try:

                telemetry[key] = float(
                    data.get(key, default)
                )

            except (ValueError, TypeError):

                telemetry[key] = default

        now = datetime.now()

        with shared["lock"]:

            shared["telemetry"].update(telemetry)

            shared["last_seen"] = now

            shared["history"].append({
                "Time": now,
                **telemetry
            })

    except Exception as e:

        add_event(f"Telemetry error: {e}")


# =====================================================
# MQTT CONNECTION
# =====================================================

def start_mqtt():

    if shared["started"]:
        return

    try:

        try:

            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="hydro-dashboard-" + uuid.uuid4().hex[:8],
                transport="websockets"
            )

        except (AttributeError, TypeError):

            client = mqtt.Client(
                client_id="hydro-dashboard-" + uuid.uuid4().hex[:8],
                transport="websockets"
            )

        client.ws_set_options(path=WS_PATH)

        client.on_connect = on_connect

        client.on_disconnect = on_disconnect

        client.on_message = on_message

        client.connect_async(
            BROKER,
            PORT,
            keepalive=45
        )

        client.loop_start()

        with shared["lock"]:

            shared["client"] = client

            shared["started"] = True

            shared["error"] = ""

    except Exception as e:

        with shared["lock"]:

            shared["error"] = str(e)


start_mqtt()

st_autorefresh(
    interval=2500,
    key="hydro_refresh"
)


# =====================================================
# ML MODEL
# =====================================================

@st.cache_resource
def load_model():

    try:

        return joblib.load(MODEL_PATH)

    except Exception:

        return None


model = load_model()


def cooling_prediction(temp, cpu, ram):

    # Try the trained ML model first.

    if model is not None:

        try:

            prediction = model.predict([[
                temp,
                cpu,
                ram
            ]])[0]

            if isinstance(prediction, str):

                level = prediction.lower()

                if level == "low":
                    return "Low", 30, "ML Model"

                if level == "medium":
                    return "Medium", 60, "ML Model"

                if level == "high":
                    return "High", 90, "ML Model"

            value = float(prediction)

            if value <= 1:
                value *= 100

            fan = int(max(0, min(100, value)))

            level = (
                "High" if fan >= 75
                else "Medium" if fan >= 45
                else "Low"
            )

            return level, fan, "ML Model"

        except Exception:

            pass

    # Fallback rules

    if temp >= 38 or cpu >= 85 or ram >= 90:

        return "High", 90, "Safety Rules"

    elif temp >= 33 or cpu >= 65 or ram >= 75:

        return "Medium", 60, "Safety Rules"

    else:

        return "Low", 30, "Safety Rules"


# =====================================================
# VIRTUAL RASPBERRY PI SERVERS
# =====================================================

if "servers" not in st.session_state:

    st.session_state.servers = {

        "Raspberry Pi 1": {
            "cpu": 35.0,
            "ram": 40.0,
            "apps": []
        },

        "Raspberry Pi 2": {
            "cpu": 25.0,
            "ram": 35.0,
            "apps": []
        }

    }


if "applications" not in st.session_state:

    st.session_state.applications = {}


if "app_counter" not in st.session_state:

    st.session_state.app_counter = 1


servers = st.session_state.servers


# =====================================================
# SERVER TEMPERATURE
# =====================================================

with shared["lock"]:

    telemetry = dict(shared["telemetry"])

    history = list(shared["history"])

    connected = shared["connected"]

    last_seen = shared["last_seen"]

    events = list(shared["events"])


servers["Raspberry Pi 1"]["temp"] = telemetry["zone1_temp"]

servers["Raspberry Pi 2"]["temp"] = telemetry["zone2_temp"]


# =====================================================
# WORKLOAD SCHEDULING
# =====================================================

APP_REQUIREMENTS = {

    "Web Application": (20, 15),

    "Database Service": (35, 30),

    "Analytics Engine": (40, 35),

    "IoT Monitoring": (15, 12),

    "AI Inference": (45, 40)

}


def select_server(cpu_required, ram_required):

    candidates = []

    for name, server in servers.items():

        available_cpu = 100 - server["cpu"]

        available_ram = 100 - server["ram"]

        if (
            available_cpu >= cpu_required
            and available_ram >= ram_required
        ):

            score = (
                0.45 * server["temp"]
                + 0.30 * server["cpu"]
                + 0.25 * server["ram"]
            )

            candidates.append((score, name))

    if not candidates:

        return None

    return min(candidates)[1]


# =====================================================
# FAN COMMAND
# =====================================================

def send_fan_command(fan1, fan2):

    with shared["lock"]:

        client = shared["client"]

        connected_now = shared["connected"]

    if client is None or not connected_now:

        return False

    payload = {

        "fan1_speed": int(fan1),

        "fan2_speed": int(fan2),

        "zone1_heat": telemetry["zone1_temp"],

        "zone2_heat": telemetry["zone2_temp"]

    }

    try:

        result = client.publish(
            COMMAND_TOPIC,
            json.dumps(payload)
        )

        return result.rc == mqtt.MQTT_ERR_SUCCESS

    except Exception:

        return False


# =====================================================
# PROFESSIONAL DESIGN
# =====================================================

st.markdown("""
<style>

.stApp {
    background-color: #F3F7FC;
}

[data-testid="stSidebar"] {
    background-color: #E8F0FA;
}

.hero {

    padding: 25px;

    border-radius: 16px;

    background: linear-gradient(
        110deg,
        #102B50,
        #1769AA,
        #21A6B7
    );

    color: white;

    margin-bottom: 22px;

}

.hero h1 {
    font-size: 34px;
    margin: 0;
}

.hero p {
    margin: 6px 0 0 0;
    font-size: 15px;
}

.metric-card {

    background: white;

    border: 1px solid #DFE8F2;

    border-radius: 13px;

    padding: 17px;

    min-height: 110px;

}

.metric-label {
    color: #65758B;
    font-size: 13px;
}

.metric-value {
    color: #163B63;
    font-size: 27px;
    font-weight: bold;
    margin-top: 7px;
}

.section-title {

    font-size: 22px;

    font-weight: bold;

    color: #15385F;

    margin-top: 15px;

    margin-bottom: 12px;

}

</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
# =====================================================

st.markdown("""
<div class="hero">

<h1>HYDRO-TRACE</h1>

<p>
AI-Assisted Smart Data Center Cooling
&
Intelligent Workload Management
</p>

</div>
""", unsafe_allow_html=True)


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("CONTROL CENTER")

    page = st.radio(

        "Navigation",

        [

            "Overview",

            "Workload Management",

            "Cooling Control",

            "Live Analytics",

            "System Events"

        ]

    )

    st.divider()

    if connected:

        st.success("ESP32 Connected")

    else:

        st.warning("Waiting for ESP32")

    if last_seen:

        st.caption(
            "Last data: " +
            last_seen.strftime("%H:%M:%S")
        )

    if shared["error"]:

        st.caption(shared["error"])

    st.divider()

    demo_mode = st.toggle(
        "Simulated Sensor Mode",
        value=False
    )


# =====================================================
# OPTIONAL DEMONSTRATION VALUES
# =====================================================

if demo_mode:

    tick = int(time.time() // 5)

    telemetry["zone1_temp"] = round(
        29 + 7 * (0.5 + 0.5 * math.sin(tick / 3)),
        1
    )

    telemetry["zone2_temp"] = round(
        30 + 9 * (0.5 + 0.5 * math.sin(tick / 4 + 1.2)),
        1
    )

    telemetry["humidity"] = round(
        45 + 12 * (0.5 + 0.5 * math.sin(tick / 5)),
        1
    )

    st.sidebar.info(
        "Demo sensor values are generated locally."
    )


# =====================================================
# OVERVIEW PAGE
# =====================================================

if page == "Overview":

    st.markdown(
        '<div class="section-title">SYSTEM OVERVIEW</div>',
        unsafe_allow_html=True
    )

    avg_temp = (
        telemetry["zone1_temp"]
        + telemetry["zone2_temp"]
    ) / 2

    avg_fan = (
        telemetry["fan1_speed"]
        + telemetry["fan2_speed"]
    ) / 2

    columns = st.columns(4)

    metrics = [

        ("AVERAGE TEMPERATURE", f"{avg_temp:.1f} °C"),

        ("HUMIDITY", f'{telemetry["humidity"]:.1f}%'),

        ("FAN SPEED", f"{avg_fan:.0f}%"),

        ("WATER FLOW", f'{telemetry["water_flow"]:.1f} L/min')

    ]

    for col, (label, value) in zip(columns, metrics):

        with col:

            st.markdown(f"""
            <div class="metric-card">

            <div class="metric-label">
            {label}
            </div>

            <div class="metric-value">
            {value}
            </div>

            </div>
            """, unsafe_allow_html=True)


    st.markdown("### VIRTUAL SERVER STATUS")

    c1, c2 = st.columns(2)

    for col, (name, server) in zip(
        [c1, c2],
        servers.items()
    ):

        with col:

            st.subheader(name)

            st.metric(
                "Temperature",
                f'{server["temp"]:.1f} °C'
            )

            st.progress(
                int(server["cpu"]),
                text=f'CPU Usage: {server["cpu"]:.0f}%'
            )

            st.progress(
                int(server["ram"]),
                text=f'RAM Usage: {server["ram"]:.0f}%'
            )

            st.caption(
                f'Running Applications: {len(server["apps"])}'
            )


    st.markdown("### SMART COOLING INTELLIGENCE")

    avg_cpu = (
        servers["Raspberry Pi 1"]["cpu"]
        + servers["Raspberry Pi 2"]["cpu"]
    ) / 2

    avg_ram = (
        servers["Raspberry Pi 1"]["ram"]
        + servers["Raspberry Pi 2"]["ram"]
    ) / 2

    level, fan, source = cooling_prediction(
        avg_temp,
        avg_cpu,
        avg_ram
    )

    a, b, c = st.columns(3)

    a.metric("Cooling Level", level)

    b.metric("Recommended Fan Speed", f"{fan}%")

    c.metric("Decision Source", source)

    if demo_mode:

        st.info(
            "Demonstration values are simulated, not physical measurements."
        )

    elif not connected:

        st.warning(
            "Start Wokwi ESP32 simulation to receive sensor telemetry."
        )


# =====================================================
# WORKLOAD MANAGEMENT
# =====================================================

elif page == "Workload Management":

    st.markdown(
        '<div class="section-title">INTELLIGENT WORKLOAD MANAGEMENT</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Applications are assigned according to server temperature, "
        "available CPU and available RAM."
    )

    with st.form("deployment_form"):

        app_name = st.selectbox(
            "Select Application",
            list(APP_REQUIREMENTS.keys())
        )

        cpu_required, ram_required = APP_REQUIREMENTS[app_name]

        st.info(
            f"CPU Requirement: {cpu_required}% | "
            f"RAM Requirement: {ram_required}%"
        )

        placement = st.radio(
            "Scheduling Strategy",
            ["Automatic", "Raspberry Pi 1", "Raspberry Pi 2"],
            horizontal=True
        )

        deploy = st.form_submit_button(
            "Deploy Application",
            type="primary"
        )


    if deploy:

        if placement == "Automatic":

            target = select_server(
                cpu_required,
                ram_required
            )

        else:

            target = placement

        if target is None:

            st.error(
                "No server has enough available CPU and RAM."
            )

        else:

            server = servers[target]

            if (
                100 - server["cpu"] < cpu_required
                or 100 - server["ram"] < ram_required
            ):

                st.error(
                    f"{target} does not have enough capacity."
                )

            else:

                app_id = (
                    "APP-" +
                    str(st.session_state.app_counter).zfill(3)
                )

                st.session_state.app_counter += 1

                record = {

                    "Application ID": app_id,

                    "Application": app_name,

                    "CPU": cpu_required,

                    "RAM": ram_required,

                    "Server": target,

                    "Time": datetime.now().strftime("%H:%M:%S")

                }

                st.session_state.applications[app_id] = record

                server["apps"].append(app_id)

                server["cpu"] += cpu_required

                server["ram"] += ram_required

                add_event(
                    f"{app_name} deployed on {target}"
                )

                st.success(
                    f"{app_name} successfully deployed on {target}."
                )


    st.markdown("### APPLICATION ALLOCATION")

    if st.session_state.applications:

        df = pd.DataFrame(
            list(st.session_state.applications.values())
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        remove_id = st.selectbox(
            "Select application to remove",
            list(st.session_state.applications.keys())
        )

        if st.button("Remove Application"):

            record = st.session_state.applications.pop(remove_id)

            server = servers[record["Server"]]

            server["apps"].remove(remove_id)

            server["cpu"] = max(
                0,
                server["cpu"] - record["CPU"]
            )

            server["ram"] = max(
                0,
                server["ram"] - record["RAM"]
            )

            add_event(
                f'{record["Application"]} removed'
            )

            st.success("Application removed.")

            st.rerun()

    else:

        st.info(
            "No applications deployed. Deploy an application to demonstrate scheduling."
        )


    st.markdown("### SERVER RESOURCE CAPACITY")

    for name, server in servers.items():

        st.write(f"**{name}**")

        st.progress(
            int(server["cpu"]),
            text=f'CPU: {server["cpu"]:.0f}%'
        )

        st.progress(
            int(server["ram"]),
            text=f'RAM: {server["ram"]:.0f}%'
        )


# =====================================================
# COOLING CONTROL
# =====================================================

elif page == "Cooling Control":

    st.markdown(
        '<div class="section-title">SMART COOLING CONTROL</div>',
        unsafe_allow_html=True
    )

    avg_temp = (
        telemetry["zone1_temp"]
        + telemetry["zone2_temp"]
    ) / 2

    avg_cpu = (
        servers["Raspberry Pi 1"]["cpu"]
        + servers["Raspberry Pi 2"]["cpu"]
    ) / 2

    avg_ram = (
        servers["Raspberry Pi 1"]["ram"]
        + servers["Raspberry Pi 2"]["ram"]
    ) / 2

    level, recommended, source = cooling_prediction(
        avg_temp,
        avg_cpu,
        avg_ram
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Zone 1 Temperature",
        f'{telemetry["zone1_temp"]:.1f} °C'
    )

    c2.metric(
        "Zone 2 Temperature",
        f'{telemetry["zone2_temp"]:.1f} °C'
    )

    c3.metric(
        "Cooling Recommendation",
        level
    )

    st.info(
        f"Recommended cooling: {recommended}% | Source: {source}"
    )

    mode = st.radio(
        "Cooling Mode",
        ["Automatic", "Manual"],
        horizontal=True
    )

    if mode == "Automatic":

        fan1 = (
            recommended
            if telemetry["zone1_temp"] >= 32
            else max(20, recommended - 15)
        )

        fan2 = (
            recommended
            if telemetry["zone2_temp"] >= 32
            else max(20, recommended - 15)
        )

        st.write(f"Zone 1 fan target: **{fan1}%**")

        st.write(f"Zone 2 fan target: **{fan2}%**")

    else:

        fan1 = st.slider(
            "Zone 1 Fan Speed",
            0,
            100,
            30
        )

        fan2 = st.slider(
            "Zone 2 Fan Speed",
            0,
            100,
            30
        )

    if st.button(
        "Send Fan Command to ESP32",
        type="primary"
    ):

        if send_fan_command(fan1, fan2):

            st.success("Fan command published successfully.")

        else:

            st.warning(
                "MQTT is not connected. Command was not sent."
            )

    st.caption(
        "The ESP32 must subscribe to the fan_command topic and implement the fan control."
    )


# =====================================================
# LIVE ANALYTICS
# =====================================================

elif page == "Live Analytics":

    st.markdown(
        '<div class="section-title">LIVE PERFORMANCE ANALYTICS</div>',
        unsafe_allow_html=True
    )

    if history:

        df = pd.DataFrame(history)

        df["Time"] = pd.to_datetime(df["Time"]).dt.strftime(
            "%H:%M:%S"
        )

        st.markdown("### Temperature Monitoring")

        st.line_chart(
            df.set_index("Time")[
                ["zone1_temp", "zone2_temp"]
            ]
        )

        st.markdown("### Cooling Response")

        st.line_chart(
            df.set_index("Time")[
                ["fan1_speed", "fan2_speed"]
            ]
        )

        st.markdown("### Humidity & Water Flow")

        st.line_chart(
            df.set_index("Time")[
                ["humidity", "water_flow"]
            ]
        )

    else:

        st.info(
            "Waiting for sensor readings. Start Wokwi ESP32."
        )


    st.markdown("### SERVER RESOURCE UTILIZATION")

    resource_df = pd.DataFrame(

        [

            {

                "Server": name,

                "CPU": server["cpu"],

                "RAM": server["ram"]

            }

            for name, server in servers.items()

        ]

    ).set_index("Server")

    st.bar_chart(resource_df)


# =====================================================
# SYSTEM EVENTS
# =====================================================

elif page == "System Events":

    st.markdown(
        '<div class="section-title">SYSTEM EVENT LOG</div>',
        unsafe_allow_html=True
    )

    if events:

        st.dataframe(
            pd.DataFrame(events),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No events recorded yet.")


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "HYDRO-TRACE | Smart Data Center Cooling & Workload Management"
)

st.caption(
    "ESP32 sensor telemetry is received through MQTT. "
    "Raspberry Pi CPU and RAM are virtual server metrics in this prototype."
)
