from flask import Flask, render_template, jsonify, request
import threading, time, datetime
from ai import interface as ai_interface
from datetime import datetime

app = Flask(_name_)

system_status = {
    "running": False,
    "battery": 100,
    "last_detection": None,
    "detections_today": 0
}

log_file = "detections.log"

def log_detection(coords, pest):
    with open(log_file, "a") as f:
        f.write(f"{datetime.datetime.now()} - {pest} at {coords}\n")

def robot_loop():
    while True:
        if system_status["running"]:
            system_status["battery"] = ai_interface.read_battery()
            coords, pest = ai_interface.detect_pest()
            if pest:
                system_status["last_detection"] = {"coords": coords, "pest": pest}
                system_status["detections_today"] += 1
                ai_interface.move_to(coords)
                ai_interface.buzzer_alert()
                log_detection(coords, pest)
            if system_status["battery"] < 20:
                ai_interface.buzzer_alert()
        time.sleep(5)

@app.route("/")
def index():
    return render_template("index.html", status=system_status, datetime=datetime)

@app.route("/start", methods=["POST"])
def start():
    system_status["running"] = True
    return jsonify({"status": "started"})

@app.route("/stop", methods=["POST"])
def stop():
    system_status["running"] = False
    return jsonify({"status": "stopped"})

@app.route("/status")
def status():
    return jsonify(system_status)

@app.route("/report")
def report():
    try:
        with open(log_file, "r") as f:
            return "<pre>" + f.read() + "</pre>"
    except FileNotFoundError:
        return "No reports yet."

@app.route("/manual_shutdown", methods=["POST"])
def manual_shutdown():
    ai_interface.shutdown()
    system_status["running"] = False
    return jsonify({"status": "shutdown initiated"})

if _name_ == "_main_":
    t = threading.Thread(target=robot_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000 , debug = True)

