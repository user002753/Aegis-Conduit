"""Small smoke test for the optional local Ollama helper."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


MODEL_NAME = "qwen2.5-coder:7b"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"


def chat_with_local_agent(prompt: str, model_name: str = MODEL_NAME) -> str | None:
    payload = json.dumps(
        {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    print("Local agent is thinking...")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Unable to connect to Ollama: {exc}")
        print("Make sure Ollama is running and the model has been pulled.")
        return None

    answer = result.get("response", "")
    print("\nLocal agent response:\n")
    print(answer)
    return answer


if __name__ == "__main__":
    response = chat_with_local_agent("Write a quick Python function to verify file hashes.")
    raise SystemExit(0 if response else 1)
