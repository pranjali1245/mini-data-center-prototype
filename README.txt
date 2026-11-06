MINI DATA CENTER - MQTT DASHBOARD UPDATE

1. Extract this ZIP.
2. In your existing GitHub repository, replace app.py with this app.py.
3. Replace requirements.txt with this requirements.txt.
4. Commit the changes to GitHub.
5. Streamlit Community Cloud should redeploy automatically. If not, use Manage app > Reboot.

The app subscribes to broker.hivemq.com over WebSockets (port 8000, path /mqtt)
and topic mini-dc-demo-7f3a91/telemetry. These must match the Wokwi ESP32 sketch.
The ESP32 publishes over MQTT TCP to the same public broker. The public broker is shared;
do not publish private information. Wokwi sensor values and fan outputs are simulated.
