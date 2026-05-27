import tempfile
import uuid
from pathlib import Path

import discord

from app.ai.ollama import OllamaError, generate
from app.config import MIST_PERSONALITIES, MIST_VOICE, OLLAMA_FAST_MODEL

try:
    import edge_tts
except Exception:
    edge_tts = None


VOICE_SYSTEM = (
    MIST_PERSONALITIES["mist"]
    + " Vas a decir una frase corta en voz alta en un canal de Discord. "
    + "Una sola oracion, sin emojis, sin comillas y sin explicar instrucciones. "
    + "Habla en femenino cuando te refieras a MIST."
)


async def mist_voice_line(event: str, fallback: str, details: dict | None = None) -> str:
    detail_lines = "\n".join(f"- {key}: {value}" for key, value in (details or {}).items() if value is not None)
    prompt = (
        f"Evento: {event}\n"
        f"Frase base: {fallback}\n"
        f"Datos:\n{detail_lines or '- sin datos extra'}\n\n"
        "Genera una frase natural para decir en voz alta. Maximo 8 palabras."
    )

    try:
        response = await generate(prompt, model=OLLAMA_FAST_MODEL, timeout=8, system=VOICE_SYSTEM)
    except OllamaError:
        return fallback

    line = response.replace("\n", " ").strip()
    if not line or len(line) > 140:
        return fallback
    return line


async def create_tts_source(text: str) -> tuple[discord.FFmpegPCMAudio, Path] | None:
    if edge_tts is None:
        return None

    voice_dir = Path(tempfile.gettempdir()) / "mist_voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    output_path = voice_dir / f"{uuid.uuid4().hex}.mp3"

    communicate = edge_tts.Communicate(text=text, voice=MIST_VOICE)
    await communicate.save(str(output_path))
    return discord.FFmpegPCMAudio(str(output_path)), output_path


def cleanup_tts_file(path: Path | None) -> None:
    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
