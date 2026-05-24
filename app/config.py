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
# A default fast model name - override with env var if you have a specific fast model
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", os.getenv("OLLAMA_MODEL", "llama2-mini"))
# Optional comma-separated list of allowed fast models for the `/chat` command
_fast_models = os.getenv("OLLAMA_FAST_MODELS")
OLLAMA_FAST_MODELS = [m.strip() for m in _fast_models.split(",")] if _fast_models else []

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")
