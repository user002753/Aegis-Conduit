FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements.txt README.md /app/
COPY aegis_conduit /app/aegis_conduit
COPY tests /app/tests

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "-m", "aegis_conduit.cli", "--serve"]
