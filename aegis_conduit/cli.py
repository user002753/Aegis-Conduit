"""Command-line entry point for Aegis Conduit."""

import argparse

from .agent import CrisisAgent
from .mesh_sync import MeshSyncEngine
from .data_veracity import VeracityEngine
from .routing import RouteEvaluator
from .scenario import ScenarioRunner
from .api import create_app

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aegis Conduit decentralized crisis agent.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--simulate", action="store_true", help="Run a local scenario simulation")
    parser.add_argument("--serve", action="store_true", help="Run HTTP API server for ingestion and queries")
    args = parser.parse_args()

    veracity = VeracityEngine()
    sync = MeshSyncEngine()
    routing = RouteEvaluator()
    agent = CrisisAgent(sync_engine=sync, veracity_engine=veracity, route_evaluator=routing)

    if args.simulate:
        runner = ScenarioRunner(agent)
        runner.run()
        return
    if args.serve:
        app = create_app(agent)
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    agent.bootstrap()
    agent.run_loop()

import argparse
import threading
import subprocess
import signal
import sys
import time
import os
import pickle
import json

from .agent import CrisisAgent
from .mesh_sync import MeshSyncEngine
from .data_veracity import VeracityEngine
from .routing import RouteEvaluator
from .scenario import ScenarioRunner
from .api import create_app
from .anomaly import AnomalyDetector

import uvicorn


def _start_uvicorn_in_thread(app, host: str = "0.0.0.0", port: int = 8000):
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aegis Conduit decentralized crisis agent.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--simulate", action="store_true", help="Run a local scenario simulation")
    parser.add_argument("--serve", action="store_true", help="Run HTTP API server for ingestion and queries")
    parser.add_argument(
        "--serve-all",
        action="store_true",
        help="Run API server (uvicorn) and Streamlit UI together for local demos",
    )
    parser.add_argument("--export-slides", action="store_true", help="Export slide CSV/PNG from anomaly history and exit")

    parser.add_argument("--seed-model", action="store_true", help="Seed anomaly detector from sample packets and persist model")
    args = parser.parse_args()

    # handle seeding anomaly model
    if getattr(args, "seed_model", False):
        detector = AnomalyDetector()
        sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_packets.json")
        try:
            with open(sample_path, "r", encoding="utf-8") as fh:
                samples = json.load(fh)
        except Exception:
            samples = []

        detector.partial_fit(samples)
        model_path = os.path.join(os.getcwd(), ".cache")
        os.makedirs(model_path, exist_ok=True)
        model_file = os.path.join(model_path, "anomaly_model.pkl")
        try:
            with open(model_file, "wb") as mf:
                pickle.dump(getattr(detector, "model", None), mf)
            print(f"Anomaly model seeded and saved to {model_file}")
        except Exception:
            print("Warning: model persistence failed (sklearn may be missing). Seed completed in-memory.")
        return

    # handle export slides request
    if getattr(args, "export_slides", False):
        # run the exporter script (uses defaults: .cache/anomaly_history.json -> .cache/)
        try:
            proc = subprocess.run([sys.executable, os.path.join(os.getcwd(), "export_slide_assets.py")], check=False)
            if proc.returncode == 0:
                print("Export completed.")
            else:
                print("Export script exited with code:", proc.returncode)
        except Exception as exc:
            print("Failed to run exporter:", exc)
        return

    veracity = VeracityEngine()
    sync = MeshSyncEngine()
    routing = RouteEvaluator()
    agent = CrisisAgent(sync_engine=sync, veracity_engine=veracity, route_evaluator=routing)

    if args.simulate:
        runner = ScenarioRunner(agent)
        runner.run()
        return

    if args.serve:
        app = create_app(agent)
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    if args.serve_all:
        # Build frontend static assets (if missing) and start FastAPI to serve API + frontend
        frontend_dir = os.path.join(os.getcwd(), "frontend")
        dist_dir = os.path.join(frontend_dir, "dist")
        # Ensure we are running from the repository root so npm runs in the
        # expected directory. The package lives under ./aegis_conduit, so the
        # repo root is the parent of that directory.
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        try:
            os.chdir(repo_root)
        except Exception:
            pass

        frontend_dir = os.path.join(os.getcwd(), "frontend")
        dist_dir = os.path.join(frontend_dir, "dist")

        # If dist doesn't exist, try to build the frontend first so create_app
        # will mount the static files when the FastAPI app is created.
        if not os.path.exists(dist_dir):
            print("Building React frontend (this may take a moment)...")
            try:
                subprocess.check_call(["npm", "install", "--no-audit", "--no-fund"], cwd=frontend_dir)
                subprocess.check_call(["npm", "run", "build"], cwd=frontend_dir)
                print("Frontend build complete.")
            except Exception as e:
                print("Frontend build failed:", e)
                print("Proceeding to serve API only. You can build frontend manually under ./frontend and re-run with --serve-all.")

        # Create the FastAPI app after attempting the build so static files
        # (frontend/dist) are detected and mounted if present.
        app = create_app(agent)

        # Log current working directory and whether frontend/dist exists
        try:
            print(f"Serving from cwd: {os.getcwd()}")
            print(f"Frontend dist exists: {os.path.exists(dist_dir)} -> {dist_dir}")
        except Exception:
            pass

        # Start FastAPI app in background thread (serves static frontend if present)
        server, thread = _start_uvicorn_in_thread(app, host="0.0.0.0", port=8000)

        try:
            print("Started uvicorn and serving API + frontend (if built). Press Ctrl+C to stop.")
            # open browser to root
            try:
                import webbrowser

                webbrowser.open("http://localhost:8000")
            except Exception:
                pass

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Interrupt received; terminating services...")
        finally:
            try:
                server.should_exit = True
            except Exception:
                pass

        return

    agent.bootstrap()
    agent.run_loop()


if __name__ == "__main__":
    main()
