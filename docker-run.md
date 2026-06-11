# Docker: build & run (Streamlit UI)

This project includes `Dockerfile.streamlit` to build a small image that serves the Streamlit UI.

Build the image:

```powershell
docker build -t aegis-conduit-streamlit -f Dockerfile.streamlit .
```

Run the container (port 8501 forwarded):

```powershell
docker run --rm -p 8501:8501 aegis-conduit-streamlit
```

If you prefer to run Streamlit with the included Python wrapper inside the container, pass a custom command to `docker run`:

```powershell
docker run --rm -p 8501:8501 aegis-conduit-streamlit python run.py --port 8501 --host 0.0.0.0
```

Note: the image exposes port 8501 by default; map it to your host as shown above.
