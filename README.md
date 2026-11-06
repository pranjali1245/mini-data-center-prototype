# Mini Data Center Virtual Prototype

This is a browser-deployable software simulation for a hackathon demonstration.

## Files
- `app.py`: Streamlit dashboard, two virtual nodes, automatic workload placement, synthetic ML cooling classifier, simulated fan response.
- `requirements.txt`: Python dependencies.

## Run locally
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free using Streamlit Community Cloud
1. Create a GitHub repository and upload `app.py` and `requirements.txt`.
2. Open https://share.streamlit.io/ and sign in.
3. Choose Create app, select the repository and `app.py`, then deploy.

## Honest demo scope
The two Raspberry Pi nodes, temperature/CPU/RAM readings, and fan response are simulated in software. The Python scheduler really executes its selection logic, but this starter version does not deploy Linux containers to separate physical Raspberry Pis. The Random Forest model is trained on synthetic demonstration data and is not a calibrated thermal-safety model.

## Suggested next integration
Build a separate ESP32 + two temperature-sensor simulation in Wokwi. For a real end-to-end bridge between Wokwi and this hosted dashboard, use an MQTT broker or HTTP endpoint and configure credentials securely. Do not expose broker passwords or API keys in public source code.
