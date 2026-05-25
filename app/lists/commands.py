import json

import discord
from discord import app_commands
from discord.ext import commands

from app.config import CIRCLE_ROLE_NAME
from app.lists.storage import add_to_list, create_list, ensure_user, get_list, list_lists
from app.music import extract_playlist_urls
from app.playback import playback_manager


async def _get_member_roles_json(interaction: discord.Interaction) -> tuple:
    """Helper to fetch member and return (member, roles_json) tuple."""
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        try:
            member = await interaction.guild.fetch_member(interaction.user.id)
        except Exception:
            member = interaction.user

    role_objs = getattr(member, "roles", [])
    role_names = [r.name for r in role_objs if getattr(r, "name", "") != "@everyone"]
    role_ids = [r.id for r in role_objs if getattr(r, "id", None) is not None and getattr(r, "name", "") != "@everyone"]
    roles_json = json.dumps({"ids": role_ids, "names": role_names})
    return member, roles_json


def setup_lists_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="list_create", description="Crea una lista de canciones")
    @app_commands.describe(nombre="Nombre de la lista")
    async def list_create_command(interaction: discord.Interaction, nombre: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        role_names = json.loads(roles_json).get("names", [])

        if CIRCLE_ROLE_NAME not in role_names:
            await interaction.response.send_message(f"No tenés permiso para crear listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        created = create_list(interaction.guild.id, nombre, "musica", creator_id=interaction.user.id)
        if not created:
            await interaction.response.send_message("Ya existe una lista con ese nombre.")
            return
        await interaction.response.send_message(
            f"Lista creada: {nombre}.\n"
            f"Ahora agregá links con `/list_add nombre:{nombre} url:<link de YouTube>`."
        )

    @bot.tree.command(name="list_add", description="Agrega un link de YouTube a una lista")
    @app_commands.describe(nombre="Nombre de la lista", url="Link de YouTube")
    async def list_add(interaction: discord.Interaction, nombre: str, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        added = add_to_list(interaction.guild.id, nombre, url)
        if not added:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return

        await interaction.response.send_message(f"Agregado a {nombre}.")

    @bot.tree.command(name="list_add_playlist", description="Importa una playlist de YouTube completa a una lista guardada")
    @app_commands.describe(nombre="Nombre de la lista", playlist_url="Link de la playlist de YouTube")
    async def list_add_playlist(interaction: discord.Interaction, nombre: str, playlist_url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        await interaction.response.defer()

        try:
            urls, playlist_title = extract_playlist_urls(playlist_url)
        except Exception as exc:
            await interaction.followup.send(f"No pude leer la playlist: {exc}")
            return

        if not urls:
            await interaction.followup.send("La playlist no tiene pistas visibles para importar.")
            return

        added = 0
        for url in urls:
            if add_to_list(interaction.guild.id, nombre, url):
                added += 1

        if added == 0:
            await interaction.followup.send(f"No pude agregar canciones a {nombre}.")
            return

        await interaction.followup.send(
            f"Importé {added} canciones de '{playlist_title}' a {nombre}.\n"
            f"Si querés sumar un link suelto, usá `/list_add`."
        )

    @bot.tree.command(name="list_show", description="Muestra las listas guardadas")
    async def list_show(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        lists = list_lists(interaction.guild.id)
        if not lists:
            await interaction.response.send_message("No hay listas guardadas todavía.")
            return

        lines = [f"{sl.name}: {len(sl.items)} canciones" for sl in lists]
        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="list_play", description="Reproduce una lista guardada")
    @app_commands.describe(nombre="Nombre de la lista")
    async def list_play(interaction: discord.Interaction, nombre: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        saved_list = get_list(interaction.guild.id, nombre)
        if saved_list is None:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return

        if not saved_list.items:
            await interaction.response.send_message("La lista está vacía.")
            return

        await interaction.response.defer()

        if interaction.user.voice is None:
            await interaction.followup.send("Tenés que estar en un canal de voz.")
            return

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except Exception as exc:
                await interaction.followup.send(
                    f"No pude conectarme al canal de voz: {exc}. Revisá permisos de conectar/hablar o intentá `/join` primero."
                )
                return

        if voice_client.is_playing() or voice_client.is_paused():
            playback_manager.stop(interaction.guild.id, voice_client)

        try:
            title = await playback_manager.play_queue(interaction.guild.id, voice_client, saved_list.items, source_name=saved_list.name)
        except Exception as exc:
            await interaction.followup.send(f"No pude reproducir la lista: {exc}")
            return

        remaining = len(saved_list.items) - 1
        if remaining:
            await interaction.followup.send(
                f"Lista {saved_list.name} iniciada: {title}\n"
                f"Posición: 1/{len(saved_list.items)}. En cola: {remaining} canciones."
            )
        else:
            await interaction.followup.send(f"Lista {saved_list.name} iniciada: {title}")

    @bot.tree.command(name="list_add_bulk", description="Agrega varios links de YouTube a una lista")
    @app_commands.describe(nombre="Nombre de la lista", links="Pega varios links separados por comas o saltos de línea")
    async def list_add_bulk(interaction: discord.Interaction, nombre: str, links: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        parts = [p.strip() for p in links.replace('\r', '\n').replace(',', '\n').split('\n') if p.strip()]
        if not parts:
            await interaction.response.send_message("No se detectaron URLs en la entrada.")
            return

        added = 0
        for u in parts:
            if add_to_list(interaction.guild.id, nombre, u):
                added += 1

        await interaction.response.send_message(f"Agregados {added} links a {nombre}.")
