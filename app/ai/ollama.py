import os
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")


def generate(prompt: str, model: str | None = None, timeout: int = 30) -> str:
    """Call Ollama HTTP API to generate a response.
    This assumes Ollama is reachable at OLLAMA_URL and exposes /api/generate.
    The exact API shape may vary by Ollama version; this is a best-effort wrapper.
    """
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": model, "prompt": prompt}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # response structure may vary; try common fields
        if isinstance(data, dict):
            if "text" in data:
                return data["text"]
            if "result" in data and isinstance(data["result"], dict) and "content" in data["result"]:
                return data["result"]["content"]
        return str(data)
    except Exception as e:
        return f"[ollama error] {e}"
