import subprocess
import json
import os
from pathlib import Path

# 1. Define the root directory of your project (SMART_PESTISIDE_SPRINKEL_SYSTEM)
# Path(__file__).resolve().parent is WEB_INTERFERNCE
# .parent.parent is the root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. Define the paths for the venv Python interpreter
# Windows Path: venv/Scripts/python.exe
VENV_PYTHON_WIN = PROJECT_ROOT / 'venv' / 'Scripts' / 'python.exe'
# Linux/macOS Path: venv/bin/python
VENV_PYTHON_UNIX = PROJECT_ROOT / 'venv' / 'bin' / 'python'

# 3. Construct the absolute path to the main program
MAIN_PROGRAM = PROJECT_ROOT / 'basic_main_program.py'

# 4. Determine the correct VENV_PYTHON path
if VENV_PYTHON_WIN.exists():
    VENV_PYTHON = VENV_PYTHON_WIN
elif VENV_PYTHON_UNIX.exists():
    VENV_PYTHON = VENV_PYTHON_UNIX
else:
    # If neither path exists, set VENV_PYTHON to None to trigger an error message
    VENV_PYTHON = None

# 5. Execute the program if the interpreter is found
if VENV_PYTHON is None:
    response = {"success": False, "message": f"Error: Virtual environment Python interpreter not found in 'venv/Scripts' or 'venv/bin' directory."}
else:
    try:
        # CRITICAL FIX: Set cwd (Current Working Directory) to PROJECT_ROOT.
        # This allows basic_main_program.py to find files (like ai.pt) using 
        # paths relative to the project root.
        process = subprocess.Popen(
            [str(VENV_PYTHON), str(MAIN_PROGRAM)],
            cwd=str(PROJECT_ROOT)  # <-- The key to fixing file path errors
        )

        response = {
            "success": True,
            "message": "AI program started successfully using VENV interpreter.",
            "pid": process.pid 
        }
    except Exception as e:
        # This catches errors if subprocess.Popen itself fails (e.g., permission denied)
        response = {"success": False, "message": f"Error starting AI program subprocess: {str(e)}"}

# Print the final JSON response
print(json.dumps(response))