"""FastAPI endpoints for Aegis Conduit agent ingestion and queries."""

from fastapi import FastAPI, HTTPException
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, List
import json
import asyncio
from fastapi.responses import StreamingResponse
from .state_store import StateStore
from .identity import IdentityManager


class ReportModel(BaseModel):
    source: str
    type: str | None = None
    timestamp: str | None = None
    event: dict[str, Any]


class HazardModel(BaseModel):
    event: dict[str, Any]


def create_app(agent) -> FastAPI:
    app = FastAPI(title="Aegis Conduit API")
    logger = logging.getLogger("aegis_conduit.api")
    logger.setLevel(logging.INFO)
    # CORS for local frontend dev (Vite) and production hosting
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # create or attach a broadcaster
    if not getattr(agent, "broadcaster", None):
        agent.broadcaster = None

    # ensure agent has a persistent state store
    if not getattr(agent, "state_store", None):
        try:
            agent.state_store = StateStore(path=getattr(agent, "state_store_path", None))
            agent.state_store.init_db()
        except Exception:
            agent.state_store = None

    # Ensure agent has an identity manager for signing decision trace logs.
    if not getattr(agent, "identity", None):
        try:
            agent.identity = IdentityManager()
        except Exception:
            agent.identity = None

    async def sse_generator(queue: asyncio.Queue):
        try:
            while True:
                payload = await queue.get()
                # SSE framing
                data = json.dumps(payload)
                yield f"data: {data}\n\n"
        finally:
            if agent.broadcaster:
                agent.broadcaster.unsubscribe(queue)

    @app.get("/routes")
    def get_routes():
        return agent.produce_recommendations()

    @app.get("/api/packets")
    def get_packets():
        # Try to return live in-memory recent packets from agent state, fall back to packaged sample data
        try:
            reports = agent.state.get("reports", None)
            if reports:
                return reports[-20:]
        except Exception:
            pass
        # fallback to bundled samples
        try:
            import pkgutil, json

            data = pkgutil.get_data(__name__, "../data/sample_packets.json")
            if data:
                return json.loads(data.decode("utf-8"))
        except Exception:
            pass
        return []

    @app.get("/state")
    def get_state():
        return agent.state

    @app.post("/report")
    def post_report(report: ReportModel):
        payload = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        try:
            # enqueue into mesh and process immediately
            agent.sync_engine.post_local_report(payload)
            incoming = agent.sync_engine.receive()
            if incoming is not None:
                agent.ingest_report(incoming)
            agent.run_cycle()
            # return the latest report validation record from agent state for visibility
            latest = None
            try:
                latest = agent.state.get("reports", [])[-1]
            except Exception:
                latest = None
            return {"status": "ok", "latest_report": latest}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/hazard")
    def post_hazard(hazard: HazardModel):
        try:
            payload = hazard.model_dump() if hasattr(hazard, "model_dump") else hazard.dict()
            agent.route_evaluator.ingest_hazard(payload["event"])
            agent.run_cycle()
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class CotModel(BaseModel):
        agent_id: str
        text: str
        time: str | None = None

    @app.post("/cot")
    def post_cot(entry: CotModel):
        try:
            etime = entry.time or __import__('datetime').datetime.utcnow().isoformat()
            record = {"agent_id": entry.agent_id, "time": etime, "text": entry.text}
            sig_hex = None
            try:
                if getattr(agent, "identity", None):
                    payload = json.dumps(record, sort_keys=True).encode("utf-8")
                    sig = agent.identity.sign(payload)
                    try:
                        sig_hex = sig.hex()
                    except Exception:
                        sig_hex = str(sig)
            except Exception:
                sig_hex = None

            # persist via state_store if available
            if getattr(agent, "state_store", None):
                try:
                    agent.state_store.append_cot(entry.agent_id, etime, entry.text, sig_hex)
                except Exception:
                    pass

            # also add to in-memory state for quick access
            try:
                agent.state.setdefault("cot_logs", []).append({**record, "signature": sig_hex})
            except Exception:
                pass

            # Optional: upload signed CoT backup to Azure Blob Storage if configured
            try:
                import os
                conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
                if conn_str:
                    try:
                        from azure.storage.blob import BlobServiceClient

                        bsc = BlobServiceClient.from_connection_string(conn_str)
                        container_name = os.environ.get("AZURE_COT_CONTAINER", "cot-backups")
                        try:
                            container_client = bsc.create_container(container_name)
                        except Exception:
                            container_client = bsc.get_container_client(container_name)

                        blob_name = f"cot_{entry.agent_id}_{etime.replace(':', '-')}.json"
                        blob_content = json.dumps({**record, "signature": sig_hex}, default=str)
                        blob_client = bsc.get_blob_client(container=container_name, blob=blob_name)
                        blob_client.upload_blob(blob_content, overwrite=True)
                    except Exception:
                        # do not fail the request if cloud upload fails; it's optional
                        pass
            except Exception:
                pass

            return {"status": "ok", "signature": sig_hex}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/cot")
    def get_cot(limit: int | None = None):
        try:
            if getattr(agent, "state_store", None):
                return agent.state_store.get_cot(limit)
            return agent.state.get("cot_logs", [])[-(limit or 100) :]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/stream")
    def stream_routes():
        # attach broadcaster if not present
        if not getattr(agent, "broadcaster", None):
            from .broadcast import RouteBroadcaster

            agent.broadcaster = RouteBroadcaster()

        queue = agent.broadcaster.subscribe()
        return StreamingResponse(sse_generator(queue), media_type="text/event-stream")

    @app.post("/foundry/ground")
    def mock_foundry_ground(payload: dict):
        event = payload.get("event", {})
        ref = event.get("reference_id")
        status = event.get("status")
        registry = {
            "warehouse_inventories": "verified",
            "evacuation_protocols": "active",
            "road_status_feed": "authenticated",
        }
        expected = registry.get(ref)
        trusted = bool(expected and expected == status)
        citations = [{"source": "mock_foundry_iq", "reference_id": ref, "status": expected}]
        reason = "grounded via mock foundry iq" if trusted else "grounding failed in mock foundry iq"
        return {"trusted": trusted, "reason": reason, "citations": citations}

    # If a built frontend exists, serve it at root. Also attach a startup
    # event that attempts to mount the static frontend if it is present when
    # the application starts (covers cases where build happened just before serve).
    try:
        import pathlib

        frontend_dist = pathlib.Path.cwd() / "frontend" / "dist"
        # Try to mount immediately if dist exists at app creation time.
        try:
            if frontend_dist.exists():
                try:
                    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
                    logger.info(f"Mounted frontend static files from {frontend_dist} at creation time")
                except Exception:
                    # mounting may fail if already mounted; ignore
                    logger.debug("StaticFiles mount at creation time failed or already mounted")
            else:
                logger.info(f"No frontend dist found at {frontend_dist} during app creation")
        except Exception as exc:
            logger.warning("Failed checking frontend dist: %s", exc)

        # Also attempt to mount on startup in case the build finished just before
        # the process started but after app object creation.
        def try_mount_frontend():
            try:
                if frontend_dist.exists():
                    try:
                        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
                        logger.info(f"Mounted frontend static files from {frontend_dist} on startup")
                    except Exception:
                        logger.debug("StaticFiles mount on startup failed or already mounted")
                else:
                    logger.info(f"No frontend dist found at {frontend_dist} on startup")
            except Exception as exc:
                logger.warning("Failed to mount frontend static files on startup: %s", exc)

        @app.on_event("startup")
        async def _startup_mount():
            try_mount_frontend()

        # Fallback index handler to serve index.html directly if present.
        try:
            index_path = frontend_dist / "index.html"
            if index_path.exists():
                from fastapi.responses import FileResponse

                @app.get("/")
                def _frontend_index():
                    return FileResponse(str(index_path), media_type="text/html")
        except Exception as exc:
            logger.debug("No fallback index handler installed: %s", exc)
    except Exception:
        logger = logging.getLogger("aegis_conduit.api")
        logger.debug("Skipping frontend static mount checks due to an exception")

    # Health endpoint
    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
