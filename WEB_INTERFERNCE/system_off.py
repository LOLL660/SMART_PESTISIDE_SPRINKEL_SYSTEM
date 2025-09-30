import json
import sys
import os
import signal
import psutil
from pathlib import Path

# 1. Define the root directory of your project (SMART_PESTISIDE_SPRINKEL_SYSTEM)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. Construct the absolute path to the main program
MAIN_PROGRAM = str(PROJECT_ROOT / 'basic_main_program.py')

# 3. Find and terminate all running instances of basic_main_program.py
terminated = False
error_message = None
try:
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(MAIN_PROGRAM in str(arg) for arg in cmdline):
                proc.terminate()  # Send SIGTERM
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()  # Force kill if not terminated
                terminated = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if terminated:
        response = {"success": True, "message": "AI program stopped successfully."}
    else:
        response = {"success": False, "message": "No running AI program found to stop."}
except Exception as e:
    response = {"success": False, "message": f"Error stopping AI program: {str(e)}"}

print(json.dumps(response))
