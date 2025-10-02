# Wrapper interface to avoid modifying original AI/hardware files.
# Exposes safe functions for robot_server.

try:
    from . import real_time_ai
except Exception:
    real_time_ai = None

try:
    from . import hardware as orig_hardware
except Exception:
    orig_hardware = None

def detect_pest():
    """Call AI detector and return (coords, pest)."""
    if real_time_ai is None:
        return None, None
    for name in ('detect_pest', 'run_detection', 'infer', 'detect'):
        fn = getattr(real_time_ai, name, None)
        if callable(fn):
            try:
                result = fn()
                if isinstance(result, tuple) and len(result) >= 2:
                    return result[0], result[1]
                if isinstance(result, dict):
                    coords = result.get('coords') or result.get('location')
                    pest = result.get('pest') or result.get('label')
                    return coords, pest
            except Exception:
                continue
    return None, None

def read_battery():
    if orig_hardware is None:
        return 0
    for name in ('read_battery', 'get_battery_percent', 'battery_level'):
        fn = getattr(orig_hardware, name, None)
        if callable(fn):
            try:
                return int(fn())
            except Exception:
                continue
    return 0

def move_to(coords):
    if orig_hardware is None: return
    for name in ('move_to', 'goto', 'move'):
        fn = getattr(orig_hardware, name, None)
        if callable(fn):
            try: fn(coords); return
            except Exception: continue

def buzzer_alert():
    if orig_hardware is None: return
    for name in ('buzzer_alert', 'buzzer_on', 'buzz'):
        fn = getattr(orig_hardware, name, None)
        if callable(fn):
            try: fn(); return
            except Exception: continue

def shutdown():
    if orig_hardware is None: return
    for name in ('shutdown', 'safe_shutdown', 'stop_all'):
        fn = getattr(orig_hardware, name, None)
        if callable(fn):
            try: fn(); return
            except Exception: continue
