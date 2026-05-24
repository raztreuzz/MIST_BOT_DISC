import os
import json
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")


def generate(prompt: str, model: str | None = None, timeout: int = 30) -> str:
    """Call Ollama HTTP API to generate a response.
    This assumes Ollama is reachable at OLLAMA_URL and exposes /api/generate.
    The exact API shape may vary by Ollama version; this is a best-effort wrapper.
    Ollama returns streaming NDJSON (newline-delimited JSON).
    """
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": model, "prompt": prompt}
    try:
        resp = requests.post(url, json=payload, timeout=timeout, stream=True)
        resp.raise_for_status()
        # Ollama returns streaming NDJSON; concatenate all response chunks
        full_response = ""
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        full_response += chunk["response"]
                except Exception:
                    pass
        return full_response.strip() if full_response else "[no response]"
    except Exception as e:
        return f"[ollama error] {e}"
