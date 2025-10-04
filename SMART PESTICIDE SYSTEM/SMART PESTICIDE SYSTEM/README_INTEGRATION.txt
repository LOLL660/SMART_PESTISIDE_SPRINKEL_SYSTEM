SMART_PESTICIDE_SYSTEM - Integrated Project

- AI and Hardware code: kept inside ai/ (untouched).
- New wrapper: ai/interface.py (glue code).
- Backend: robot_server.py (Flask server).
- Dashboard: templates/index.html + static/ (replace with your frontend from GitHub repo).
- Logs: detections.log (stores pest detections).
- Runs fully offline on Raspberry Pi.

Run:
    pip install -r requirements.txt
    python3 robot_server.py

Access:
    http://<raspberry-pi-ip>:5000

Notes:
- Original AI/hardware code untouched.
- Wrapper ensures safe integration.
