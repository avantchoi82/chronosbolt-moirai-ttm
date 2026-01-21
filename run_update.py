#!/usr/bin/env python
r"""Git Update Launcher - Run from Task Scheduler.

This script activates the virtual environment and runs main.py with --ai --push.
Can be scheduled with Windows Task Scheduler using pythonw.exe for silent execution.

Usage:
    python run_update.py          # Normal run
    pythonw.exe run_update.py     # Silent run (no console window)

Task Scheduler setup:
    Program: C:\Users\user\PycharmProjects\enssanble\.venv\Scripts\pythonw.exe
    Arguments: C:\Users\user\PycharmProjects\enssanble\run_update.py
    Start in: C:\Users\user\PycharmProjects\enssanble
"""

import subprocess
import sys
import os
from pathlib import Path

# Project paths
PROJECT_DIR = Path(__file__).parent
VENV_PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
MAIN_SCRIPT = PROJECT_DIR / "main.py"
LOG_FILE = PROJECT_DIR / "data" / "run_update.log"


def main():
    """Run main.py with --ai --push using the virtual environment."""
    # Ensure we're in the project directory
    os.chdir(PROJECT_DIR)

    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [str(VENV_PYTHON), str(MAIN_SCRIPT), "--ai", "--push"]

    # Run and capture output
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=600,  # 10 minute timeout
        )

        # Log output
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] Run completed (exit code: {result.returncode})\n")
            f.write(f"{'='*60}\n")
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write(result.stderr)

        return result.returncode

    except subprocess.TimeoutExpired:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[ERROR] Script timed out after 600 seconds\n")
        return 1

    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[ERROR] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
