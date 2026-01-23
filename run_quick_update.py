#!/usr/bin/env python
r"""Quick Git Update Launcher - Run from Task Scheduler.

This script runs main.py with --push only (no AI summary).
Fast execution (~1-2 seconds) for frequent updates.

Usage:
    python run_quick_update.py          # Normal run
    pythonw.exe run_quick_update.py     # Silent run (no console window)

Task Scheduler setup:
    Program: C:\Users\user\PycharmProjects\enssanble\.venv\Scripts\pythonw.exe
    Arguments: C:\Users\user\PycharmProjects\enssanble\run_quick_update.py
    Start in: C:\Users\user\PycharmProjects\enssanble
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# Project paths - use absolute paths to avoid path issues
PROJECT_DIR = Path(r"C:\Users\user\PycharmProjects\enssanble")
VENV_PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
MAIN_SCRIPT = PROJECT_DIR / "main.py"
LOG_FILE = PROJECT_DIR / "data" / "run_quick_update.log"


def main():
    """Run main.py with --push using the virtual environment."""
    # Ensure we're in the project directory
    os.chdir(PROJECT_DIR)

    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Build command (--push only, no --ai for fast execution)
    cmd = [str(VENV_PYTHON), str(MAIN_SCRIPT), "--push"]

    # Run and capture output
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=120,  # 2 minute timeout (should be ~5 seconds)
        )

        # Log output
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] Quick update completed (exit code: {result.returncode})\n")
            f.write(f"{'='*60}\n")
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write(result.stderr)

        return result.returncode

    except subprocess.TimeoutExpired:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] [ERROR] Script timed out after 120 seconds\n")
        return 1

    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] [ERROR] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
