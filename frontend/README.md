# Frontend (React)

This is a lightweight Vite + React frontend for the Aegis Conduit Tactical Console.

Quick start:

```powershell
cd frontend
npm install
npm run dev
```

By default Vite dev server runs on port 5173. The app will attempt to fetch `/api/packets` from a backend; if unavailable it falls back to packaged sample data.

Production build (static site with nginx):

```powershell
cd frontend
npm install
npm run build
docker build -t aegis-conduit-frontend -f Dockerfile .
docker run --rm -p 80:80 aegis-conduit-frontend
```

The container proxies `/api` and `/stream` to `host.docker.internal:8000` by default; run the backend API on port 8000 (`python -m aegis_conduit.cli --serve`) and the container will reach it.
