import os
import json
import asyncio
import aiohttp

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi")


async def generate(prompt: str, model: str | None = None, timeout: int = 60) -> str:
    """Call Ollama HTTP API to generate a response asynchronously.
    This assumes Ollama is reachable at OLLAMA_URL and exposes /api/generate.
    Ollama returns streaming NDJSON (newline-delimited JSON).
    Uses aiohttp for non-blocking async I/O.
    """
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": model, "prompt": prompt}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                
                # Ollama returns streaming NDJSON; concatenate all response chunks
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
                
                return full_response.strip() if full_response else "[no response]"
    except asyncio.TimeoutError:
        return "[error] Request to Ollama timed out"
    except Exception as e:
        return f"[ollama error] {e}"
