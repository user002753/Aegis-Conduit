"""Download the local Ollama model used by the optional helper demos."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


MODEL_NAME = "qwen2.5-coder:7b"
OLLAMA_PULL_URL = "http://localhost:11434/api/pull"


def pull_missing_model(model_name: str = MODEL_NAME) -> bool:
    """Ask Ollama to pull the configured model.

    Returns True when Ollama reports success. The hackathon demo remains fully
    usable without this helper; it is only for optional local LLM experiments.
    """
    payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_PULL_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    print(f"Requesting Ollama to download {model_name}...")
    print("This can take several minutes, depending on your connection.")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Unable to trigger model pull: {exc}")
        print("Make sure Ollama is running at http://localhost:11434.")
        return False

    if result.get("status") == "success":
        print("Model download complete. The local helper is ready.")
        return True

    print(f"Ollama returned: {result}")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if pull_missing_model() else 1)
