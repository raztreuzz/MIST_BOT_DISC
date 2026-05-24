import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Role name that allows creating lists (override with env var if needed)
CIRCLE_ROLE_NAME = os.getenv("CIRCLE_ROLE_NAME", "Miembro del Circulo")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")