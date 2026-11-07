
# --------------------------------------------------
# 18. VIRTUAL COOLING RESPONSE - MANUAL + AUTOMATIC
# --------------------------------------------------

st.divider()
st.subheader("4. Virtual Cooling Response")

if "manual_fan" not in st.session_state:
    st.session_state.manual_fan = {
        "Virtual Raspberry Pi 1": 90,
        "Virtual Raspberry Pi 2": 90
    }

manual_mode = st.toggle(
    "Enable manual fan control",
    value=False,
    key="manual_cooling_mode"
)

fan_cols = st.columns(2)

for col, name in zip(fan_cols, nodes.keys()):

    with col:
        st.write(f"**{name} — Cooling Control**")

        if manual_mode:
            speed = st.slider(
                f"{name} fan speed (%)",
                0, 100,
                st.session_state.manual_fan[name],
                5,
                key=f"manual_fan_{name}"
            )

            st.session_state.manual_fan[name] = speed

            st.progress(
                speed,
                text=f"Manual fan speed: {speed}%"
            )

        else:
            speed = fan_commands[name]

            st.progress(
                speed,
                text=f"ML fan speed: {speed}%"
            )

        st.caption(
            "Manual control" if manual_mode
            else "Automatic ML control"
        )

# Publish selected manual or automatic fan speeds.
final_fan1 = (
    st.session_state.manual_fan["Virtual Raspberry Pi 1"]
    if manual_mode
    else fan_commands["Virtual Raspberry Pi 1"]
)

final_fan2 = (
    st.session_state.manual_fan["Virtual Raspberry Pi 2"]
    if manual_mode
    else fan_commands["Virtual Raspberry Pi 2"]
)

final_payload = {
    "fan1_speed": int(final_fan1),
    "fan2_speed": int(final_fan2),
    "zone1_heat": float(nodes["Virtual Raspberry Pi 1"]["heat_load"]),
    "zone2_heat": float(nodes["Virtual Raspberry Pi 2"]["heat_load"])
}

if mqtt_snapshot["connected"]:
    result = mqtt_connection["client"].publish(
        MQTT_COMMAND_TOPIC,
        json.dumps(final_payload),
        qos=0,
        retain=False
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        st.success("Cooling commands sent to ESP32.")
    else:
        st.warning(f"MQTT publish error: {result.rc}")
else:
    st.warning("Waiting for MQTT connection.")
