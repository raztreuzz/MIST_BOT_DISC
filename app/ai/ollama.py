import json
import asyncio
import aiohttp

from app.config import (
    OLLAMA_FAST_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)


async def generate(prompt: str, model: str | None = None, timeout: int = OLLAMA_TIMEOUT, system: str | None = None) -> str:
    """Call Ollama HTTP API to generate a response asynchronously.
    Uses aiohttp for non-blocking async I/O.
    """
    model = model or OLLAMA_FAST_MODEL
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
        },
    }
    if system:
        payload["system"] = system
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                
                full_response = ""
                async for line in resp.content:
                    if line:
                        try:
                            line_str = line.decode('utf-8').strip()
                            if line_str:
                                chunk = json.loads(line_str)
                                if "response" in chunk:
                                    full_response += chunk["response"]
                        except Exception:
                            pass
                
                return full_response.strip() if full_response else "[sin respuesta]"
    except asyncio.TimeoutError:
        return "[error] Timeout"
    except Exception as e:
        return f"[error] {str(e)[:50]}"


async def generate_streaming(prompt: str, model: str | None = None, timeout: int = OLLAMA_TIMEOUT, system: str | None = None):
    """Generate response in streaming mode - yields chunks as they arrive.
    Useful for Discord real-time message updates.
    """
    model = model or OLLAMA_FAST_MODEL
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
        },
    }
    if system:
        payload["system"] = system

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()

                async for line in resp.content:
                    if line:
                        try:
                            line_str = line.decode('utf-8').strip()
                            if line_str:
                                chunk = json.loads(line_str)
                                if "response" in chunk:
                                    yield chunk["response"]
                        except Exception:
                            pass
    except Exception as e:
        yield f"[error] {str(e)[:50]}"
