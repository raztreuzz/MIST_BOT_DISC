import json
import discord
from discord import app_commands
from discord.ext import commands

from app.ai.ollama import generate_streaming
from app.config import (
    OLLAMA_FAST_MODEL,
    OLLAMA_FAST_MODELS,
    OLLAMA_TIMEOUT,
    MIST_PERSONALITIES,
    MIST_DEFAULT_PERSONALITY,
)
from app.lists.storage import ensure_user


async def _get_member_roles_json(interaction: discord.Interaction) -> tuple:
    """Helper to fetch member and return (member, roles_json) tuple."""
    member = interaction.guild.get_member(interaction.user.id)
    try:
        if not member:
            member = await interaction.guild.fetch_member(interaction.user.id)
    except Exception:
        member = interaction.user

    role_objs = getattr(member, "roles", [])
    role_names = [r.name for r in role_objs if getattr(r, "name", "") != "@everyone"]
    role_ids = [r.id for r in role_objs if getattr(r, "id", None) is not None and getattr(r, "name", "") != "@everyone"]
    roles_json = json.dumps({"ids": role_ids, "names": role_names})
    return member, roles_json


def setup_ai_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="chat", description="Chat con MIST (streaming en vivo). Personalidades definidas en config.py")
    @app_commands.describe(
        prompt="Prompt para el modelo",
        model="Modelo opcional (rápido por defecto)"
    )
    async def chat(interaction: discord.Interaction, prompt: str, model: str | None = None):
        await interaction.response.defer()

        try:
            # Register user in database
            member, roles_json = await _get_member_roles_json(interaction)
            ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

            model_to_use = model or OLLAMA_FAST_MODEL

            # If a list of allowed fast models is configured, validate selection
            if OLLAMA_FAST_MODELS and model and model not in OLLAMA_FAST_MODELS:
                await interaction.followup.send(
                    f"❌ Modelo desconocido. Usa: {', '.join(OLLAMA_FAST_MODELS)}"
                )
                return

            # Use personality defined in configuration (edit `app/config.py` to change)
            personality = MIST_DEFAULT_PERSONALITY
            system_prompt = MIST_PERSONALITIES.get(personality, "")

            # Generate response with streaming
            full_response = ""
            message = None

            async for chunk in generate_streaming(
                prompt,
                model=model_to_use,
                timeout=OLLAMA_TIMEOUT,
                system=system_prompt,
            ):
                full_response += chunk

                # Send/update message for immediate feedback
                if message is None and full_response:
                    # Send first message immediately
                    message = await interaction.followup.send(f"🤖 {full_response[:1900]}")
                elif message and len(full_response) % 100 < len(chunk):
                    # Update every ~100 chars
                    try:
                        await message.edit(content=f"🤖 {full_response[:1900]}")
                    except Exception:
                        pass

            # Final update with complete response
            if message and full_response:
                total_len = len(full_response)
                if total_len > 1900:
                    # Split into multiple messages
                    chunks = [full_response[i:i+1900] for i in range(0, total_len, 1900)]
                    await message.edit(content=f"🤖 {chunks[0]}")
                    for chunk_text in chunks[1:]:
                        await interaction.followup.send(f"🤖 {chunk_text}")
                else:
                    await message.edit(content=f"🤖 {full_response}")
            elif not full_response:
                await interaction.followup.send("❌ Sin respuesta de Ollama.")

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)[:100]}")
