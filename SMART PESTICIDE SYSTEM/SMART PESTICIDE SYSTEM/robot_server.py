from flask import Flask, render_template, jsonify, request
import threading
import time
import datetime
import os
from ai import interface as ai_interface

app = Flask(__name__)

system_status = {
    "running": False,
    "battery": 100,
    "last_detection": None,
    "detections_today": 0,
    "error": None
}

log_file = "detections.log"

def log_detection(coords, pest):
    try:
        with open(log_file, "a") as f:
            f.write(f"{datetime.datetime.now()} - {pest} at {coords}\n")
    except Exception as e:
        system_status["error"] = f"Log write error: {str(e)}"

# Function to clear log older than max_age_days (30 days here)
def clean_old_logs(log_path=log_file, max_age_days=30):
    if os.path.exists(log_path):
        file_age = time.time() - os.path.getmtime(log_path)
        max_age_seconds = max_age_days * 86400  # seconds in a day
        if file_age > max_age_seconds:
            try:
                with open(log_path, "w") as f:
                    f.write("")  # clear log file
                print(f"Cleared log file: {log_path}")
            except Exception as e:
                system_status["error"] = f"Log cleanup error: {str(e)}"

def robot_loop():
    while True:
        clean_old_logs()  # Clear logs older than 30 days

        if system_status["running"]:
            try:
                system_status["battery"] = ai_interface.read_battery()
                coords, pest = ai_interface.detect_pest()
                if pest:
                    system_status["last_detection"] = {"coords": coords, "pest": pest}
                    system_status["detections_today"] += 1
                    ai_interface.move_to(coords)
                    ai_interface.buzzer_alert()
                    log_detection(coords, pest)
            except Exception as e:
                system_status["error"] = str(e)
                try:
                    with open("errors.log", "a") as error_log:
                        error_log.write(f"{time.ctime()} - Error: {str(e)}\n")
                except:
                    pass  # avoid recursive errors

            if system_status["battery"] < 20:
                ai_interface.buzzer_alert()

        time.sleep(5)

@app.route("/")
def index():
    return render_template("index.html", status=system_status)

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

if __name__ == "__main__":
    t = threading.Thread(target=robot_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)

