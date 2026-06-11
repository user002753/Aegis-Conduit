"""CLI wrapper to start the Streamlit app with the recommended `streamlit run` command.

Usage:
    python run.py          # launches Streamlit using the current Python interpreter
    python run.py --port 8501
"""
import subprocess
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run Aegis Conduit Streamlit app")
    parser.add_argument("--port", type=int, default=8501, help="Port for Streamlit server")
    parser.add_argument("--host", default="localhost", help="Host for Streamlit server")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    app_path = repo_root / "app.py"
    if not app_path.exists():
        print(f"Could not find {app_path}")
        sys.exit(2)

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(args.port), "--server.address", args.host, "--server.headless", "true"]
    print("Launching Streamlit with:", " ".join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print("Streamlit exited with code", e.returncode)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
