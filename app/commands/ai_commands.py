import json

import discord
from discord import app_commands
from discord.ext import commands

from app.ai.ollama import OllamaError, generate, healthcheck
from app.config import (
    CIRCLE_ROLE_NAME,
    MIST_DEFAULT_PERSONALITY,
    MIST_PERSONALITIES,
    OLLAMA_FAST_MODEL,
    OLLAMA_FAST_MODELS,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)
from app.lists.storage import ensure_user, recent_ai_interactions, record_ai_interaction


async def _get_member_roles_json(interaction: discord.Interaction) -> tuple:
    if interaction.guild is None:
        return interaction.user, json.dumps({"ids": [], "names": []})

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


async def _remember_user(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        return
    member, roles_json = await _get_member_roles_json(interaction)
    ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)


async def _has_log_access(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    member, roles_json = await _get_member_roles_json(interaction)
    role_names = json.loads(roles_json).get("names", [])
    permissions = getattr(member, "guild_permissions", None)
    can_manage = bool(
        getattr(permissions, "manage_guild", False)
        or getattr(permissions, "manage_messages", False)
        or getattr(permissions, "administrator", False)
    )
    return can_manage or CIRCLE_ROLE_NAME in role_names


async def _send_long(followup, text: str) -> None:
    chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)] or ["Sin respuesta."]
    await followup.send(chunks[0])
    for chunk in chunks[1:]:
        await followup.send(chunk)


def _safe_error(error: str | None) -> str:
    if not error:
        return "sin detalle"
    return error.replace(OLLAMA_URL, "[endpoint configurado]")


def _looks_like_prompt_leak(text: str) -> bool:
    lowered = text.lower()
    suspicious_terms = (
        "instrucciones internas",
        "describas tu personalidad",
        "describe tu personalidad",
        "responde como mist",
        "se trata de una clara",
    )
    return any(term in lowered for term in suspicious_terms)


def setup_ai_commands(bot: commands.Bot) -> None:
    async def model_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        del interaction
        models = OLLAMA_FAST_MODELS or [OLLAMA_FAST_MODEL]
        current_lower = current.lower()
        matches = [model for model in models if current_lower in model.lower()]
        return [app_commands.Choice(name=model, value=model) for model in matches[:25]]

    @bot.tree.command(name="mist_status", description="Revisa si Ollama está disponible para MIST")
    async def mist_status(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await healthcheck()

        if not status.available:
            await interaction.followup.send(
                "Ollama no está disponible.\n"
                f"Error: {_safe_error(status.error)}",
                ephemeral=True,
            )
            return

        models = ", ".join(status.models[:10]) if status.models else "sin modelos visibles"
        if len(status.models) > 10:
            models += f" ... y {len(status.models) - 10} más"

        await interaction.followup.send(
            "Ollama está disponible.\n"
            f"Modelo por defecto: {OLLAMA_FAST_MODEL}\n"
            f"Modelos: {models}",
            ephemeral=True,
        )

    @bot.tree.command(name="chat", description="Habla con MIST usando Ollama")
    @app_commands.describe(prompt="Qué querés decirle a MIST", modelo="Modelo opcional")
    @app_commands.autocomplete(modelo=model_autocomplete)
    async def chat(interaction: discord.Interaction, prompt: str, modelo: str | None = None):
        await interaction.response.defer()
        await _remember_user(interaction)

        prompt = prompt.strip()
        if not prompt:
            await interaction.followup.send("Escribime algo para poder responder.")
            return

        model_to_use = modelo or OLLAMA_FAST_MODEL
        if OLLAMA_FAST_MODELS and modelo and modelo not in OLLAMA_FAST_MODELS:
            await interaction.followup.send(f"Modelo desconocido. Modelos válidos: {', '.join(OLLAMA_FAST_MODELS)}")
            return

        system_prompt = MIST_PERSONALITIES.get(MIST_DEFAULT_PERSONALITY) or MIST_PERSONALITIES["mist"]

        try:
            response = await generate(
                prompt,
                model=model_to_use,
                timeout=OLLAMA_TIMEOUT,
                system=system_prompt,
            )
            if _looks_like_prompt_leak(response):
                response = await generate(
                    f"Contesta de forma natural y breve a este mensaje, sin explicar instrucciones: {prompt}",
                    model=model_to_use,
                    timeout=OLLAMA_TIMEOUT,
                )
        except OllamaError as exc:
            if interaction.guild is not None:
                record_ai_interaction(
                    interaction.guild.id,
                    interaction.channel_id,
                    interaction.user.id,
                    getattr(interaction.user, "display_name", interaction.user.name),
                    model_to_use,
                    prompt,
                    error=_safe_error(str(exc)),
                )
            await interaction.followup.send(
                "No pude consultar a Ollama.\n"
                f"Detalle: {_safe_error(str(exc))}\n"
                "La música y las listas siguen funcionando; mi cerebro opcional solo está fuera de línea."
            )
            return

        if interaction.guild is not None:
            record_ai_interaction(
                interaction.guild.id,
                interaction.channel_id,
                interaction.user.id,
                getattr(interaction.user, "display_name", interaction.user.name),
                model_to_use,
                prompt,
                response=response,
            )

        await _send_long(interaction.followup, f"MIST: {response}")

    @bot.tree.command(name="mist_logs", description="Muestra las últimas preguntas hechas a MIST")
    @app_commands.describe(cantidad="Cantidad de logs a mostrar (1-25)")
    async def mist_logs(interaction: discord.Interaction, cantidad: int = 10):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return

        if not await _has_log_access(interaction):
            await interaction.response.send_message("No tenés permiso para revisar los logs de MIST.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        rows = recent_ai_interactions(interaction.guild.id, cantidad)
        if not rows:
            await interaction.followup.send("Todavía no hay preguntas registradas.", ephemeral=True)
            return

        lines = ["Últimas preguntas a MIST:"]
        for row in rows:
            status = "error" if row.error else "ok"
            prompt = row.prompt.replace("\n", " ")[:140]
            author = row.display_name or str(row.user_id)
            lines.append(f"#{row.id} [{status}] {author} -> {prompt}")

        await interaction.followup.send("\n".join(lines), ephemeral=True)
