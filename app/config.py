import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Role name that allows creating lists (override with env var if needed)
CIRCLE_ROLE_NAME = os.getenv("CIRCLE_ROLE_NAME", "Miembro del Circulo")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    # default to sqlite file in data/mist.sqlite3 for local/dev
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'mist.sqlite3'}"

# Ollama defaults: default to a fast model name and allow overriding
# `OLLAMA_FAST_MODEL` should be set to a fast, smaller model available locally.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# A default fast model name - ultra-rápido tinyllama, fallback a sara
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", os.getenv("OLLAMA_MODEL", "tinyllama"))
# Low-latency defaults for local GPUs with limited VRAM
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "20"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "1024"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "96"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
# Optional comma-separated list of allowed fast models for the `/chat` command
_fast_models = os.getenv("OLLAMA_FAST_MODELS")
OLLAMA_FAST_MODELS = [m.strip() for m in _fast_models.split(",")] if _fast_models else []

# Personalizaciones de MIST
MIST_PERSONALITIES = {
    "asistente": "Eres MIST, un asistente amable y profesional en Discord. Responde de manera clara y concisa.",
    "jugueton": "Eres MIST, un asistente divertido y bromista. Responde con humor y emojis ocasionales.",
    "tecnico": "Eres MIST, un experto técnico. Proporciona respuestas detalladas y precisas con explicaciones.",
    "formal": "Eres MIST, un asistente formal y profesional. Utiliza lenguaje corporativo y respuestas estructuradas.",
    "sara": "Eres SARA, una interfaz de inteligencia artificial avanzada. Mantén un tono sofisticado y analítico.",
}
MIST_DEFAULT_PERSONALITY = "asistente"

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")
