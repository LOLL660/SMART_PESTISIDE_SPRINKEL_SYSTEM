# robot_server.py
"""
Robust Robot Server for SMART PESTICIDE SYSTEM
- Threaded subsystems (MotorController, Arm, Sprayer, BatteryMonitor, DBLogger)
- Flask API for control and reporting
- Simulation mode when RPi.GPIO is missing (so you can test on PC)
- Improved error handling, logging, and graceful shutdown
"""

import os
import time
import math
import json
import queue
import threading
import sqlite3
import logging
import signal
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Dict, Any, List

# Try to import RPi.GPIO; if not available, use a simple mock for desktop testing.
try:
    import RPi.GPIO as GPIO
    HW_AVAILABLE = True
except Exception:
    # Minimal mock for GPIO so code can run on non-RPi machines for testing.
    from unittest import mock
    GPIO = mock.MagicMock()
    HW_AVAILABLE = False
    print("⚠️ RPi.GPIO not available — running in SIMULATION mode (GPIO mocked).")

# Networking + server
from flask import Flask, request, jsonify

# requests used optionally for battery webhook
try:
    import requests
except Exception:
    requests = None

# -------------------------
# Logging setup
# -------------------------
LOG_PATH = os.path.join(os.getcwd(), "robot_errors.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

# -------------------------
# CONFIG (edit safely)
# -------------------------
class Config:
    GPIO_MODE = GPIO.BCM

    # Motor pins
    LEFT_FWD, LEFT_BWD = 17, 27
    RIGHT_FWD, RIGHT_BWD = 22, 23
    MOTOR_ENABLE = 24

    # Encoders
    USE_ENCODERS = True
    ENC_L_A, ENC_L_B = 5, 6
    ENC_R_A, ENC_R_B = 13, 19

    # Servos
    BASE_SERVO, SHOULDER_SERVO, ELBOW_SERVO = 12, 18, 16
    SERVO_FREQ = 50

    # Sprayer pin
    SPRAYER_PIN = 20
    PUMP_FLOW_ML_PER_S = 10.0
    DEFAULT_SPRAY_AREA_M2 = 0.5
    SPRAY_MAX_DURATION = 30.0

    # Ultrasonic
    US_TRIG, US_ECHO = 25, 8

    # Error indicator (LED or buzzer)
    ERROR_PIN = 21

    # Arm geometry (mm)
    L1, L2 = 120.0, 120.0

    # DB & status paths
    DB_PATH = os.path.join(os.getcwd(), "pesticide_log.db")
    STATUS_PATH = os.path.join(os.getcwd(), "robot_status.json")

    # Motor stall detection
    MOTOR_STALL_TIMEOUT = 2.0
    MOTOR_STALL_MIN_TICKS = 2

    # Battery monitoring
    BATTERY_POLL_INTERVAL_S = 30
    BATTERY_LOW_VOLTAGE = 11.0
    BATTERY_CRITICAL_VOLTAGE = 10.5
    BATTERY_WEBHOOK_URL = None  # e.g. "http://your-server/hook"

    # Webserver
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000

# -------------------------
# UTIL: Safe JSON write for status
# -------------------------
_status_lock = threading.Lock()
def write_status_file(status: Dict[str, Any]) -> None:
    try:
        with _status_lock:
            with open(Config.STATUS_PATH, "w") as f:
                json.dump(status, f, indent=2, default=str)
    except Exception as e:
        logging.exception("Failed to write status file: %s", e)

# -------------------------
# STATUS MANAGER
# -------------------------
class StatusManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.status: Dict[str, Any] = {
            "power": "OFF",
            "last_error": None,
            "components": {
                "motors": "UNKNOWN",
                "encoders": "UNKNOWN" if Config.USE_ENCODERS else "NOT_PRESENT",
                "servos": "UNKNOWN",
                "sprayer": "UNKNOWN",
                "ultrasonic": "UNKNOWN",
                "battery": "UNKNOWN"
            },
            "uptime_start": datetime.utcnow().isoformat(),
            "last_operation": None,
            "battery_v": None
        }
        try:
            GPIO.setup(Config.ERROR_PIN, GPIO.OUT)
            GPIO.output(Config.ERROR_PIN, GPIO.LOW)
        except Exception:
            # In simulation mode GPIO.setup may be mocked; ignore errors
            pass
        write_status_file(self.status)

    def set_error(self, component: str, message: str, causes: Optional[List[str]] = None) -> None:
        with self.lock:
            self.status["last_error"] = {"component": component, "message": message, "causes": causes or []}
            self.status["last_error_time"] = datetime.utcnow().isoformat()
            self.status["components"].setdefault(component, "ERROR")
            try:
                GPIO.output(Config.ERROR_PIN, GPIO.HIGH)
            except Exception:
                pass
            write_status_file(self.status)
            logging.error("Component ERROR: %s: %s (causes=%s)", component, message, causes)

    def clear_error(self, component: Optional[str] = None) -> None:
        with self.lock:
            self.status["last_error"] = None
            self.status["last_error_time"] = None
            if component:
                self.status["components"][component] = "OK"
            try:
                GPIO.output(Config.ERROR_PIN, GPIO.LOW)
            except Exception:
                pass
            write_status_file(self.status)

    def update_op(self, op: Any) -> None:
        with self.lock:
            self.status["last_operation"] = op
            write_status_file(self.status)

    def update_component(self, comp: str, val: Any) -> None:
        with self.lock:
            self.status["components"][comp] = val
            write_status_file(self.status)

    def update_battery(self, voltage: Optional[float]) -> None:
        with self.lock:
            self.status["battery_v"] = voltage
            self.status["components"]["battery"] = "OK" if voltage is not None else "UNKNOWN"
            write_status_file(self.status)

    def set_power(self, p: str) -> None:
        with self.lock:
            self.status["power"] = p
            write_status_file(self.status)

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.status)

# -------------------------
# DB Logger (thread-safe)
# -------------------------
class DBLogger(threading.Thread):
    def __init__(self, db_path: str):
        super().__init__(daemon=True)
        self.db_path = db_path
        self.queue: "queue.Queue[Tuple[float, float, Optional[float], Optional[float], Optional[float]]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._init_db()
        self.start()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS pesticide_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT,
                        ml_used REAL,
                        area_m2 REAL,
                        x REAL,
                        y REAL,
                        duration_s REAL
                    )""")
        conn.commit()
        conn.close()

    def run(self) -> None:
        # Use its own connection for the thread
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        c = conn.cursor()
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                ml, area, x, y, dur = item
                c.execute("INSERT INTO pesticide_log (ts, ml_used, area_m2, x, y, duration_s) VALUES (?, ?, ?, ?, ?, ?)",
                          (datetime.utcnow().isoformat(), ml, area, x, y, dur))
                conn.commit()
            except Exception:
                logging.exception("DBLogger failed to insert record: %s", item)
        conn.close()

    def log(self, ml: float, area: float, x: Optional[float] = None, y: Optional[float] = None, dur: Optional[float] = None) -> None:
        self.queue.put((ml, area, x, y, dur))

    def daily_report(self, day: Optional[date] = None) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if day is None:
            day = datetime.utcnow().date()
        start = datetime.combine(day, datetime.min.time()).isoformat()
        end = datetime.combine(day, datetime.max.time()).isoformat()
        c.execute("SELECT ts, ml_used, area_m2, x, y, duration_s FROM pesticide_log WHERE ts BETWEEN ? AND ? ORDER BY ts",
                  (start, end))
        rows = c.fetchall()
        conn.close()
        total_ml = sum(r[1] for r in rows)
        return {"date": str(day), "total_ml": total_ml, "entries": [
            {"ts": r[0], "ml_used": r[1], "area_m2": r[2], "x": r[3], "y": r[4], "duration_s": r[5]} for r in rows
        ]}

    def stop(self) -> None:
        self._stop_event.set()

# -------------------------
# Motor Controller
# -------------------------
class MotorController(threading.Thread):
    def __init__(self, status: StatusManager):
        super().__init__(daemon=True)
        self.status = status
        self.cmd_q: "queue.Queue[Any]" = queue.Queue()
        self._stop_event = threading.Event()
        self._init_gpio()
        self.enabled = False
        self.enc_counts = {"L": 0, "R": 0}
        self.enc_lock = threading.Lock()
        self.start()

    def _init_gpio(self) -> None:
        pins = [Config.LEFT_FWD, Config.LEFT_BWD, Config.RIGHT_FWD, Config.RIGHT_BWD, Config.MOTOR_ENABLE]
        for p in pins:
            try:
                GPIO.setup(p, GPIO.OUT)
                GPIO.output(p, GPIO.LOW)
            except Exception:
                pass
        if Config.USE_ENCODERS:
            try:
                GPIO.setup(Config.ENC_L_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(Config.ENC_L_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(Config.ENC_R_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(Config.ENC_R_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(Config.ENC_L_A, GPIO.RISING, callback=self._enc_l)
                GPIO.add_event_detect(Config.ENC_R_A, GPIO.RISING, callback=self._enc_r)
            except Exception:
                logging.warning("Encoder GPIO setup failed (maybe running in simulation)")

    def _enc_l(self, ch) -> None:
        b = GPIO.input(Config.ENC_L_B)
        with self.enc_lock:
            self.enc_counts["L"] += 1 if b else -1

    def _enc_r(self, ch) -> None:
        b = GPIO.input(Config.ENC_R_B)
        with self.enc_lock:
            self.enc_counts["R"] += 1 if b else -1

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                cmd = self.cmd_q.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                if cmd == "ENABLE":
                    try:
                        GPIO.output(Config.MOTOR_ENABLE, GPIO.HIGH)
                    except Exception:
                        pass
                    time.sleep(0.05)
                    self.enabled = True
                    self.status.set_power("ON")
                    # quick encoder test
                    if Config.USE_ENCODERS:
                        if self.check_stall(timeout=0.2):
                            self.enabled = False
                            self.status.set_error("motors", "enable failed: no encoder response")
                elif cmd == "DISABLE":
                    self.stop()
                    try:
                        GPIO.output(Config.MOTOR_ENABLE, GPIO.LOW)
                    except Exception:
                        pass
                    self.enabled = False
                    self.status.set_power("OFF")
                elif cmd == "FWD":
                    self._set(1, 0, 1, 0)
                elif cmd == "BWD":
                    self._set(0, 1, 0, 1)
                elif cmd == "LEFT":
                    self._set(0, 1, 1, 0)
                elif cmd == "RIGHT":
                    self._set(1, 0, 0, 1)
                elif cmd == "STOP":
                    self._set(0, 0, 0, 0)
                elif isinstance(cmd, tuple) and cmd[0] == "FWD_T":
                    self._set(1, 0, 1, 0)
                    time.sleep(cmd[1])
                    self._set(0, 0, 0, 0)
                # after movement, optionally check stall
                if Config.USE_ENCODERS:
                    if self.check_stall(timeout=Config.MOTOR_STALL_TIMEOUT):
                        # attempt stop and mark error
                        self._set(0, 0, 0, 0)
                        self.status.set_error("motors", "stall detected", ["mechanical jam", "driver", "battery low"])
            except Exception:
                logging.exception("MotorController command failed: %s", cmd)

    def _set(self, lf: int, lb: int, rf: int, rb: int) -> None:
        try:
            GPIO.output(Config.LEFT_FWD, GPIO.HIGH if lf else GPIO.LOW)
            GPIO.output(Config.LEFT_BWD, GPIO.HIGH if lb else GPIO.LOW)
            GPIO.output(Config.RIGHT_FWD, GPIO.HIGH if rf else GPIO.LOW)
            GPIO.output(Config.RIGHT_BWD, GPIO.HIGH if rb else GPIO.LOW)
            self.status.update_op(f"motors {lf}{lb}/{rf}{rb}")
        except Exception:
            logging.exception("Failed to set motor GPIO outputs")

    def enable(self) -> bool:
        # Put ENABLE command and wait a short time
        self.cmd_q.put("ENABLE")
        time.sleep(0.2)
        # Basic check
        if Config.USE_ENCODERS:
            start = self.get_encoders()
            time.sleep(0.2)
            end = self.get_encoders()
            if abs(end["L"] - start["L"]) < 1 and abs(end["R"] - start["R"]) < 1:
                self.enabled = False
                self.status.set_error("motors", "enable failed: no encoder increase")
                return False
        self.enabled = True
        return True

    def disable(self) -> None:
        self.cmd_q.put("DISABLE")

    def forward(self) -> None: self.cmd_q.put("FWD")
    def backward(self) -> None: self.cmd_q.put("BWD")
    def left(self) -> None: self.cmd_q.put("LEFT")
    def right(self) -> None: self.cmd_q.put("RIGHT")
    def stop(self) -> None: self.cmd_q.put("STOP")
    def forward_for(self, t: float) -> None: self.cmd_q.put(("FWD_T", t))

    def reset_encoders(self) -> None:
        with self.enc_lock:
            self.enc_counts = {"L": 0, "R": 0}

    def get_encoders(self) -> Dict[str, int]:
        with self.enc_lock:
            return dict(self.enc_counts)

    def check_stall(self, timeout: Optional[float] = None) -> bool:
        if not Config.USE_ENCODERS:
            return False
        start = self.get_encoders()
        time.sleep(timeout or Config.MOTOR_STALL_TIMEOUT)
        end = self.get_encoders()
        if (abs(end["L"] - start["L"]) < Config.MOTOR_STALL_MIN_TICKS and
                abs(end["R"] - start["R"]) < Config.MOTOR_STALL_MIN_TICKS):
            return True
        return False

    def stop_thread(self) -> None:
        self._stop_event.set()

# -------------------------
# Arm thread
# -------------------------
class Arm(threading.Thread):
    def __init__(self, status: StatusManager):
        super().__init__(daemon=True)
        self.status = status
        self.cmd_q: "queue.Queue[Tuple[float, float]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._init_gpio()
        self.start()

    def _init_gpio(self) -> None:
        for pin in (Config.BASE_SERVO, Config.SHOULDER_SERVO, Config.ELBOW_SERVO):
            try:
                GPIO.setup(pin, GPIO.OUT)
            except Exception:
                pass
        try:
            self.base_pwm = GPIO.PWM(Config.BASE_SERVO, Config.SERVO_FREQ)
            self.shoulder_pwm = GPIO.PWM(Config.SHOULDER_SERVO, Config.SERVO_FREQ)
            self.elbow_pwm = GPIO.PWM(Config.ELBOW_SERVO, Config.SERVO_FREQ)
            self.base_pwm.start(0); self.shoulder_pwm.start(0); self.elbow_pwm.start(0)
        except Exception:
            # In simulation mode, PWM might be mocked
            self.base_pwm = self.shoulder_pwm = self.elbow_pwm = None
            logging.warning("Servo PWM initialization failed (simulation?)")

    def _angle_to_duty(self, ang: float) -> float:
        # Typical mapping; adjust to your servos' calibration
        return 2.0 + (ang / 18.0)

    def _move_pwm(self, pwm, ang: float) -> None:
        if pwm is None:
            logging.info("Simulated servo move to %s degrees", ang)
            time.sleep(0.3)
            return
        pwm.ChangeDutyCycle(self._angle_to_duty(ang))
        time.sleep(0.30)
        pwm.ChangeDutyCycle(0)

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                x, y = self.cmd_q.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                shoulder_ang, elbow_ang = self.ik_2link(x, y)
                self._move_pwm(self.shoulder_pwm, shoulder_ang)
                self._move_pwm(self.elbow_pwm, elbow_ang)
                self.status.update_op({"arm_move": {"x": x, "y": y}})
            except Exception as e:
                self.status.set_error("arm", f"IK error: {e}")

    def move_to(self, x: float, y: float) -> None:
        try:
            self.cmd_q.put((x, y))
        except Exception as e:
            self.status.set_error("arm", f"arm move failed: {e}")

    def ik_2link(self, x: float, y: float) -> Tuple[float, float]:
        # Corrected inverse kinematics math (squared lengths)
        r = math.hypot(x, y)
        if r > (Config.L1 + Config.L2) or r < abs(Config.L1 - Config.L2):
            raise ValueError("target unreachable")
        cos_q2 = (x*x + y*y - Config.L1**2 - Config.L2**2) / (2 * Config.L1 * Config.L2)
        cos_q2 = max(-1.0, min(1.0, cos_q2))
        q2 = math.acos(cos_q2)
        k1 = Config.L1 + Config.L2 * math.cos(q2)
        k2 = Config.L2 * math.sin(q2)
        q1 = math.atan2(y, x) - math.atan2(k2, k1)
        shoulder_deg = math.degrees(q1)
        elbow_deg = math.degrees(q2)
        shoulder_servo_angle = 90 + shoulder_deg
        elbow_servo_angle = 90 + (elbow_deg - 90)
        return shoulder_servo_angle, elbow_servo_angle

    def cleanup(self) -> None:
        try:
            if self.base_pwm: self.base_pwm.stop()
            if self.shoulder_pwm: self.shoulder_pwm.stop()
            if self.elbow_pwm: self.elbow_pwm.stop()
        except Exception:
            pass

    def stop_thread(self) -> None:
        self._stop_event.set()

# -------------------------
# Sprayer thread
# -------------------------
class Sprayer(threading.Thread):
    def __init__(self, status: StatusManager, db_logger: DBLogger):
        super().__init__(daemon=True)
        self.status = status
        self.db = db_logger
        self.cmd_q: "queue.Queue[Tuple[float, Optional[float], Optional[float], Optional[float]]]" = queue.Queue()
        self._stop_event = threading.Event()
        try:
            GPIO.setup(Config.SPRAYER_PIN, GPIO.OUT)
            GPIO.output(Config.SPRAYER_PIN, GPIO.LOW)
        except Exception:
            pass
        self.start()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                dur, x, y, req_id = self.cmd_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if dur is None or dur <= 0:
                    continue
                if dur > Config.SPRAY_MAX_DURATION:
                    self.status.set_error("sprayer", "excessive duration clipped", ["bad command"])
                    dur = Config.SPRAY_MAX_DURATION
                # Activate pump (sprayer pin HIGH)
                try:
                    GPIO.output(Config.SPRAYER_PIN, GPIO.HIGH)
                except Exception:
                    logging.info("Simulated sprayer on for %s seconds", dur)
                t0 = time.time()
                while time.time() - t0 < dur:
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.05)
                try:
                    GPIO.output(Config.SPRAYER_PIN, GPIO.LOW)
                except Exception:
                    pass
                ml = dur * Config.PUMP_FLOW_ML_PER_S
                self.db.log(ml, Config.DEFAULT_SPRAY_AREA_M2, x, y, dur)
                self.status.update_op({"spray": {"ml": ml, "x": x, "y": y}})
            except Exception:
                logging.exception("Sprayer run error")

    def spray(self, duration_s: Optional[float] = None, volume_ml: Optional[float] = None, x: Optional[float] = None, y: Optional[float] = None, req_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if duration_s is None:
                if volume_ml is None:
                    duration_s = 1.0
                else:
                    duration_s = volume_ml / max(1e-6, Config.PUMP_FLOW_ML_PER_S)
            if duration_s <= 0:
                raise ValueError("duration must be positive")
            self.cmd_q.put((duration_s, x, y, req_id))
            return {"status": "queued", "duration_s": duration_s}
        except Exception as e:
            self.status.set_error("sprayer", f"spray failed: {e}")
            return {"status": "error", "message": str(e)}

    def stop_thread(self) -> None:
        self._stop_event.set()

# -------------------------
# Ultrasonic helper
# -------------------------
class Ultrasonic:
    def __init__(self, status: StatusManager):
        self.status = status
        try:
            GPIO.setup(Config.US_TRIG, GPIO.OUT)
            GPIO.setup(Config.US_ECHO, GPIO.IN)
            GPIO.output(Config.US_TRIG, False)
            time.sleep(0.1)
        except Exception:
            logging.warning("Ultrasonic init failed (simulation?)")

    def get_distance_cm(self, timeout: float = 0.02) -> Optional[float]:
        try:
            GPIO.output(Config.US_TRIG, True)
            time.sleep(0.00001)
            GPIO.output(Config.US_TRIG, False)
            pulse_start = time.time()
            timeout_at = pulse_start + timeout
            while GPIO.input(Config.US_ECHO) == 0 and time.time() < timeout_at:
                pulse_start = time.time()
            if time.time() >= timeout_at:
                self.status.set_error("ultrasonic", "no echo", ["wiring", "power"])
                return None
            pulse_end = time.time()
            while GPIO.input(Config.US_ECHO) == 1 and (time.time() - pulse_end) < timeout:
                pulse_end = time.time()
            duration = pulse_end - pulse_start
            dist_cm = (duration * 34300) / 2
            self.status.update_component("ultrasonic", "OK")
            return dist_cm
        except Exception as e:
            self.status.set_error("ultrasonic", f"exception: {e}")
            return None

# -------------------------
# Battery monitor
# -------------------------
class BatteryMonitor(threading.Thread):
    def __init__(self, status: StatusManager, read_adc_fn: Optional[callable] = None):
        super().__init__(daemon=True)
        self.status = status
        self.voltage = 12.0  # default initial
        self._stop_event = threading.Event()
        # read_adc_fn is an optional function to read real ADC voltage
        self.read_adc_fn = read_adc_fn
        self.start()

    def read_voltage(self) -> Optional[float]:
        try:
            if self.read_adc_fn:
                v = float(self.read_adc_fn())
                self.voltage = v
                return v
            # Simulation: return current stored value
            return self.voltage
        except Exception:
            logging.exception("Battery read failed")
            return None

    def run(self) -> None:
        while not self._stop_event.is_set():
            voltage = self.read_voltage()
            self.status.update_battery(voltage)
            if voltage is None:
                # cannot read battery
                self.status.set_error("battery", "read failed")
            else:
                if voltage < Config.BATTERY_CRITICAL_VOLTAGE:
                    self.status.set_error("battery", f"critical voltage {voltage}")
                    if Config.BATTERY_WEBHOOK_URL and requests:
                        try:
                            requests.post(Config.BATTERY_WEBHOOK_URL, json={"voltage": voltage})
                        except Exception:
                            pass
                elif voltage < Config.BATTERY_LOW_VOLTAGE:
                    self.status.set_error("battery", f"low voltage {voltage}")
                else:
                    # clear battery error
                    self.status.update_component("battery", "OK")
            time.sleep(Config.BATTERY_POLL_INTERVAL_S)

    def stop(self) -> None:
        self._stop_event.set()

# -------------------------
# Robot wrapper
# -------------------------
class Robot:
    def __init__(self, read_adc_fn: Optional[callable] = None):
        self.status = StatusManager()
        self.db = DBLogger(Config.DB_PATH)
        self.motors = MotorController(self.status)
        self.arm = Arm(self.status)
        self.sprayer = Sprayer(self.status, self.db)
        self.us = Ultrasonic(self.status)
        self.battery = BatteryMonitor(self.status, read_adc_fn)
        self._lock = threading.Lock()

    def start_robot(self) -> Dict[str, Any]:
        with self._lock:
            success = self.motors.enable()
            if not success:
                return {"ok": False, "error": "motors not responding; check connections"}
            try:
                # center arm servos to safe pose if possible
                if self.arm.base_pwm:
                    self.arm._move_pwm(self.arm.shoulder_pwm, 90)
                    self.arm._move_pwm(self.arm.elbow_pwm, 90)
            except Exception as e:
                self.status.set_error("arm", f"servo move failed: {e}")
                return {"ok": False, "error": "arm not responding"}
            self.status.set_power("ON")
            return {"ok": True, "message": "robot powered ON"}

    def stop_robot(self) -> Dict[str, Any]:
        with self._lock:
            try:
                self.motors.stop()
                # clear sprayer queue immediately
                try:
                    while not self.sprayer.cmd_q.empty():
                        self.sprayer.cmd_q.get_nowait()
                except Exception:
                    pass
                self.motors.disable()
                # if still enabled, it's an error
                if self.motors.enabled:
                    self.status.set_error("motors", "failed to disable")
                    return {"ok": False, "error": "motors did not stop"}
                self.status.set_power("OFF")
            except Exception as e:
                self.status.set_error("motors", f"stop failed: {e}")
                return {"ok": False, "error": str(e)}
            return {"ok": True, "message": "robot powered OFF"}

    def cleanup(self) -> None:
        logging.info("Robot cleanup initiated")
        try:
            # stop subsystems
            self.motors.stop_thread()
            self.arm.stop_thread()
            self.sprayer.stop_thread()
            self.battery.stop()
            self.db.stop()
            # join briefly to allow thread exit
            time.sleep(0.5)
        except Exception:
            logging.exception("Error during robot cleanup")

# -------------------------
# Flask API
# -------------------------
app = Flask(__name__)
robot = Robot()

@app.route("/start", methods=["POST"])
def api_start():
    res = robot.start_robot()
    if not res.get("ok"):
        return jsonify(res), 500
    return jsonify(res)

@app.route("/stop", methods=["POST"])
def api_stop():
    res = robot.stop_robot()
    if not res.get("ok"):
        return jsonify(res), 500
    return jsonify(res)

@app.route("/spray", methods=["POST"])
def api_spray():
    data = request.json or {}
    duration = data.get("duration_s")
    volume = data.get("volume_ml")
    x = data.get("x")
    y = data.get("y")
    try:
        res = robot.sprayer.spray(duration_s=duration, volume_ml=volume, x=x, y=y, req_id=data.get("req_id"))
        if res.get("status") == "error":
            return jsonify(res), 500
        return jsonify(res)
    except Exception as e:
        robot.status.set_error("sprayer", f"API spray failed: {e}")
        logging.exception("API spray exception")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def api_status():
    return jsonify(robot.status.get_snapshot())

@app.route("/report", methods=["GET"])
def api_report():
    date_str = request.args.get("date")
    try:
        date_obj = None
        if date_str:
            date_obj = datetime.fromisoformat(date_str).date()
        return jsonify(robot.db.daily_report(date_obj))
    except Exception:
        logging.exception("Failed to generate report")
        return jsonify({"status": "error", "message": "report generation failed"}), 500

@app.route("/motors/forward", methods=["POST"])
def api_motors_forward():
    if not robot.motors:
        return jsonify({"status": "error", "message": "motors not available"}), 500
    try:
        robot.motors.forward()
        return jsonify({"status": "ok"})
    except Exception as e:
        robot.status.set_error("motors", f"forward failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/motors/stop", methods=["POST"])
def api_motors_stop():
    try:
        robot.motors.stop()
        return jsonify({"status": "ok"})
    except Exception as e:
        robot.status.set_error("motors", f"stop failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Optional endpoint: trigger manual battery read
@app.route("/battery/read", methods=["GET"])
def api_battery_read():
    try:
        v = robot.battery.read_voltage()
        return jsonify({"status": "ok", "voltage": v})
    except Exception as e:
        robot.status.set_error("battery", f"read failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Manual shutdown endpoint (robot-level, not Pi OS shutdown)
@app.route("/manual_shutdown", methods=["POST"])
def api_manual_shutdown():
    try:
        res = robot.stop_robot()
        robot.cleanup()
        try:
            GPIO.cleanup()
        except Exception:
            pass
        return jsonify(res)
    except Exception as e:
        logging.exception("manual shutdown failed")
        return jsonify({"status": "error", "message": str(e)}), 500

# -------------------------
# Graceful process shutdown handler
# -------------------------
def _graceful_exit(signum, frame):
    logging.info("Received signal %s — shutting down gracefully", signum)
    try:
        robot.stop_robot()
        robot.cleanup()
        try:
            GPIO.cleanup()
        except Exception:
            pass
    except Exception:
        logging.exception("Error during graceful shutdown")
    # exit after giving threads a chance
    time.sleep(0.5)
    os._exit(0)

signal.signal(signal.SIGINT, _graceful_exit)
signal.signal(signal.SIGTERM, _graceful_exit)

# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    # Setup GPIO mode (if available)
    try:
        if HW_AVAILABLE:
            GPIO.setmode(Config.GPIO_MODE)
    except Exception:
        logging.warning("Failed to set GPIO mode (simulation?)")

    logging.info("Starting Robot Server on %s:%s", Config.WEB_HOST, Config.WEB_PORT)
    try:
        app.run(host=Config.WEB_HOST, port=Config.WEB_PORT)
    finally:
        logging.info("Shutting down Robot Server main")
        try:
            robot.cleanup()
            GPIO.cleanup()
        except Exception:
            pass
