import json
from dataclasses import dataclass

import aiohttp

from app.config import (
    OLLAMA_FAST_MODEL,
    OLLAMA_HEALTH_TIMEOUT,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaStatus:
    available: bool
    url: str
    models: list[str]
    error: str | None = None


def _timeout(total: int | float | None = None) -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=total or OLLAMA_TIMEOUT)


def _endpoint(path: str) -> str:
    return f"{OLLAMA_URL}{path}"


def _generate_payload(prompt: str, model: str, system: str | None = None, stream: bool = False) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
        },
    }
    if system:
        payload["system"] = system
    return payload


def _chat_payload(prompt: str, model: str, system: str | None = None) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
        },
    }


async def list_models(timeout: int | float | None = OLLAMA_HEALTH_TIMEOUT) -> list[str]:
    try:
        async with aiohttp.ClientSession(timeout=_timeout(timeout)) as session:
            async with session.get(_endpoint("/api/tags")) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise OllamaError(f"Ollama respondió HTTP {resp.status}: {body[:200]}")
                data = await resp.json()
    except TimeoutError as exc:
        raise OllamaError(f"Ollama no respondió a tiempo en {OLLAMA_URL}") from exc
    except aiohttp.ClientConnectorError as exc:
        raise OllamaError(f"No pude conectar con Ollama en {OLLAMA_URL}") from exc
    except aiohttp.ClientError as exc:
        raise OllamaError(f"Error HTTP conectando con Ollama: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise OllamaError("Ollama devolvió una respuesta inválida al listar modelos") from exc

    models = []
    for item in data.get("models", []):
        name = item.get("name") or item.get("model")
        if name:
            models.append(name)
    return models


async def healthcheck() -> OllamaStatus:
    try:
        models = await list_models()
    except OllamaError as exc:
        return OllamaStatus(available=False, url=OLLAMA_URL, models=[], error=str(exc))
    return OllamaStatus(available=True, url=OLLAMA_URL, models=models)


async def generate(prompt: str, model: str | None = None, timeout: int = OLLAMA_TIMEOUT, system: str | None = None) -> str:
    model_to_use = model or OLLAMA_FAST_MODEL
    payload = _chat_payload(prompt, model_to_use, system=system)

    try:
        async with aiohttp.ClientSession(timeout=_timeout(timeout)) as session:
            async with session.post(_endpoint("/api/chat"), json=payload) as resp:
                body = await resp.text()
                if resp.status == 404:
                    raise OllamaError(f"Modelo no encontrado: {model_to_use}")
                if resp.status >= 400:
                    raise OllamaError(f"Ollama respondió HTTP {resp.status}: {body[:200]}")
    except TimeoutError as exc:
        raise OllamaError(f"Ollama tardó demasiado en responder ({timeout}s)") from exc
    except aiohttp.ClientConnectorError as exc:
        raise OllamaError(f"No pude conectar con Ollama en {OLLAMA_URL}") from exc
    except aiohttp.ClientError as exc:
        raise OllamaError(f"Error HTTP conectando con Ollama: {exc}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama devolvió una respuesta inválida") from exc

    message = data.get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise OllamaError("Ollama respondió vacío")
    return text


async def generate_streaming(prompt: str, model: str | None = None, timeout: int = OLLAMA_TIMEOUT, system: str | None = None):
    model_to_use = model or OLLAMA_FAST_MODEL
    payload = _generate_payload(prompt, model_to_use, system=system, stream=True)

    try:
        async with aiohttp.ClientSession(timeout=_timeout(timeout)) as session:
            async with session.post(_endpoint("/api/generate"), json=payload) as resp:
                if resp.status == 404:
                    raise OllamaError(f"Modelo no encontrado: {model_to_use}")
                if resp.status >= 400:
                    body = await resp.text()
                    raise OllamaError(f"Ollama respondió HTTP {resp.status}: {body[:200]}")

                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue
                    if "response" in chunk:
                        yield chunk["response"]
    except OllamaError as exc:
        yield f"[error] {exc}"
    except TimeoutError:
        yield f"[error] Ollama tardó demasiado en responder ({timeout}s)"
    except aiohttp.ClientConnectorError:
        yield f"[error] No pude conectar con Ollama en {OLLAMA_URL}"
    except aiohttp.ClientError as exc:
        yield f"[error] Error HTTP conectando con Ollama: {exc}"
