# Aegis Conduit (Updated Overview)

Aegis Conduit is an experimental, modular agent for decentralized crisis logistics and resilient edge coordination. It provides a FastAPI backend, a Streamlit tactical console, and a React frontend scaffold for demos and development.

Status: active development — core CLI, API endpoints, Streamlit UI, and frontend scaffold are present; many components are scaffolded and ready for integration.

Highlights
- CLI: `python -m aegis_conduit.cli` (serve, simulate, seed-model, export-slides)
- FastAPI endpoints for ingestion, hazards, route queries, and SSE (`/stream`)
- Streamlit tactical console: `app.py`
- React frontend scaffold: `frontend/` (Vite + React)
- Persistence: SQLite and `.cache/` artifacts for demo flows

Quickstart (development)

Prerequisites: Python 3.10+ (Windows: PowerShell examples) and Node.js for frontend development.

Backend (Python)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# serve the API
python -m aegis_conduit.cli --serve
# or run Streamlit UI
streamlit run app.py
# or convenience combined demo
python -m aegis_conduit.cli --serve-all
```

Frontend (optional)

```powershell
cd frontend
npm install
npm run dev
```

Testing

```powershell
pip install -r requirements.txt
pip install pytest
pytest -q
```

Docker (Streamlit demo)

```powershell
docker build -t aegis-conduit-streamlit -f Dockerfile.streamlit .
docker run --rm -p 8501:8501 aegis-conduit-streamlit
```

Project layout (short)
- `aegis_conduit/` — core modules: `agent.py`, `mesh_sync.py`, `routing.py`, `api.py`, `cli.py`, `anomaly.py`, `state_store.py`, etc.
- `app.py` — Streamlit tactical console
- `frontend/` — Vite + React UI scaffold
- `requirements.txt`, `pyproject.toml` — dependency metadata
- `scripts/` — demo helpers
- `tests/` — pytest tests

How I assessed the repo
- Verified presence of CLI, API, Streamlit UI, and frontend scaffold.
- Tests exist under `tests/`; run `pytest` to validate current behavior locally.
- The `--serve-all` convenience flow exists but may need readiness checks for robust start sequencing.

Next suggested steps
- Add a minimal CI (GitHub Actions) to run `pytest` and linting.
- Add a smoke test that runs `export_slide_assets.py` against bundled sample data.
- Harden the API with auth and readiness probes for production runs.

If you'd like, I can replace the original `README.md` with this updated overview, or add a CI workflow and a smoke test next. Which should I do?