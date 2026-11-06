import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

st.set_page_config(page_title="Mini Data Center | Virtual Prototype", page_icon="🖥️", layout="wide")

st.title("🖥️ Mini Data Center — Virtual Prototype")
st.caption("Software simulation for hackathon demonstration | No physical Raspberry Pi / ESP32 connected")

# Train a small reproducible ML model on synthetic demonstration data.
@st.cache_resource
def train_cooling_model():
    rng = np.random.default_rng(42)
    n = 1200
    temp = rng.uniform(22, 50, n)
    cpu = rng.uniform(0, 100, n)
    ram = rng.uniform(10, 100, n)
    trend = rng.uniform(-1.5, 2.5, n)
    severity = 0.55 * (temp - 25) + 0.22 * cpu + 0.12 * ram + 5 * trend
    labels = np.where(severity < 35, "Low", np.where(severity < 55, "Medium", "High"))
    model = RandomForestClassifier(n_estimators=120, random_state=42, max_depth=8)
    model.fit(pd.DataFrame({"temperature": temp, "cpu": cpu, "ram": ram, "temp_trend": trend}), labels)
    return model

cooling_model = train_cooling_model()

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

st.sidebar.header("⚙️ Simulation controls")
st.sidebar.write("Change these values to test different server conditions. These are simulated readings.")
for i, name in enumerate(nodes):
    st.sidebar.subheader(name)
    nodes[name]["online"] = st.sidebar.toggle(f"{name} online", value=nodes[name]["online"], key=f"online_{i}")
    nodes[name]["temperature"] = st.sidebar.slider(f"{name} temperature (°C)", 20.0, 55.0, float(nodes[name]["temperature"]), 0.5, key=f"temp_{i}")
    nodes[name]["cpu"] = st.sidebar.slider(f"{name} CPU usage (%)", 0.0, 100.0, float(nodes[name]["cpu"]), 1.0, key=f"cpu_{i}")
    nodes[name]["ram"] = st.sidebar.slider(f"{name} RAM usage (%)", 0.0, 100.0, float(nodes[name]["ram"]), 1.0, key=f"ram_{i}")

if st.sidebar.button("↺ Reset demonstration"):
    st.session_state.nodes = {k: {**v, "apps": []} for k, v in DEFAULT_NODES.items()}
    st.session_state.logs = []
    st.session_state.last_decision = None
    st.rerun()

st.info("Demo mode: node metrics and cooling response are simulated. This app does not emulate Raspberry Pi hardware or physically cool equipment.")

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
    features = pd.DataFrame([{"temperature": d["temperature"], "cpu": d["cpu"], "ram": d["ram"], "temp_trend": 0.5}])
    pred = cooling_model.predict(features)[0]
    probs = cooling_model.predict_proba(features)[0]
    confidence = float(max(probs) * 100)
    fan = {"Low": 30, "Medium": 60, "High": 90}[pred]
    cool_rows.append({"Virtual zone": name, "Predicted cooling": pred, "Suggested virtual fan speed": f"{fan}%", "Model confidence": f"{confidence:.0f}%"})
st.dataframe(pd.DataFrame(cool_rows), use_container_width=True, hide_index=True)
st.caption("ML note: this Random Forest is trained on synthetic demonstration data. Its predictions illustrate the pipeline; they are not calibrated for real server thermal safety.")

st.subheader("4. Virtual cooling response")
fan_cols = st.columns(2)
for col, (name, d) in zip(fan_cols, nodes.items()):
    features = pd.DataFrame([{"temperature": d["temperature"], "cpu": d["cpu"], "ram": d["ram"], "temp_trend": 0.5}])
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
- **Cooling:** fan command and temperature reduction are simulated; no physical fan or ESP32 is connected.
""")
