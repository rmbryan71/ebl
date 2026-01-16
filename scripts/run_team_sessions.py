import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "open_team_sessions.py"


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:5000")
    env = os.environ.copy()
    env["BASE_URL"] = base_url
    subprocess.run([sys.executable, str(SCRIPT_PATH)], check=True, env=env)


if __name__ == "__main__":
    main()
