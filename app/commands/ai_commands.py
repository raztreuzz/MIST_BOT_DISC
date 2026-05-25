import discord
from discord import app_commands
from discord.ext import commands

from app.ai.ollama import generate
from app.config import OLLAMA_FAST_MODEL, OLLAMA_FAST_MODELS


def setup_ai_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="chat", description="Chat con un modelo Ollama rápido")
    @app_commands.describe(prompt="Prompt para el modelo", model="Modelo opcional (rápido por defecto)")
    async def chat(interaction: discord.Interaction, prompt: str, model: str | None = None):
        await interaction.response.defer()

        model_to_use = model or OLLAMA_FAST_MODEL

        # If a list of allowed fast models is configured, validate selection
        if OLLAMA_FAST_MODELS and model and model not in OLLAMA_FAST_MODELS:
            await interaction.followup.send(
                f"Modelo desconocido. Modelos válidos: {', '.join(OLLAMA_FAST_MODELS)}"
            )
            return

        result = await generate(prompt, model=model_to_use, timeout=60)

        # If the result is long, send as a followup message (discord limits apply)
        try:
            await interaction.followup.send(result)
        except Exception:
            # Fallback: chunk the response into multiple messages
            chunk_size = 1900
            for i in range(0, len(result), chunk_size):
                await interaction.followup.send(result[i : i + chunk_size])