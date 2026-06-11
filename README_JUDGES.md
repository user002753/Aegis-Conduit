Judge quickstart
================

This project is prepared to run locally or inside Docker so judges can view
the demo with a single command.

Quick run (recommended)

1. Build and run the services:

```bash
docker compose up --build
```

2. Open the UI in your browser:

- Frontend: http://localhost:5173/
- Backend API (Swagger): http://localhost:8000/docs

Security & external integrations

- The Foundry connector is disabled by default. To enable it, set:

```bash
export ENABLE_FOUNDRY=true
export FOUNDRY_API_URL="https://your-foundry.example"
export FOUNDRY_API_KEY="<your-key>"
```

Leave those unset to keep the demo fully local and self-contained.

- Azure Blob backup (optional) is also opt-in. To enable, provide
  `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_COT_CONTAINER`.

Auto-start demo

- When running `docker compose up --build`, a lightweight `demo` service
  automatically posts a small set of spoofed reports to the API so the UI
  surfaces signed decision-trace activity immediately. The demo is conservative
  and local-only by default.

Notes for judges

- No secrets are stored in the repository.
- The demo defaults to local-only behavior; enabling external services is
  opt-in and clearly documented above.
