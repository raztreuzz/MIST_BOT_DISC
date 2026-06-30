import asyncio
import json

import discord
from discord import app_commands
from discord.ext import commands

from app.ai.mist_voice import mist_command_reply
from app.config import CIRCLE_ROLE_NAME
from app.lists.storage import (
    add_to_list,
    create_list,
    delete_list,
    ensure_user,
    get_list,
    list_lists,
    remove_list_item,
    rename_list,
    storage_stats,
    update_list_item,
)
from app.music import extract_playlist_urls, is_youtube_playlist_url, is_youtube_url
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
    async def _mist(action: str, fallback: str, details: dict | None = None) -> str:
        return await mist_command_reply(action, fallback, details)

    def _chunk_lines(header: str, lines: list[str], limit: int = 1900) -> list[str]:
        chunks = []
        current = header
        for line in lines:
            next_text = f"{current}\n{line}" if current else line
            if len(next_text) > limit:
                chunks.append(current)
                current = line
            else:
                current = next_text
        if current:
            chunks.append(current)
        return chunks

    async def _has_list_access(interaction: discord.Interaction) -> bool:
        member, roles_json = await _get_member_roles_json(interaction)
        role_names = json.loads(roles_json).get("names", [])
        permissions = getattr(member, "guild_permissions", None)
        can_manage = bool(
            getattr(permissions, "manage_guild", False)
            or getattr(permissions, "manage_messages", False)
            or getattr(permissions, "administrator", False)
        )
        return can_manage or CIRCLE_ROLE_NAME in role_names

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
        await interaction.response.defer()
        fallback = (
            f"Lista creada: {nombre}.\n"
            f"Ahora agregá links con `/list_add nombre:{nombre} url:<link de YouTube>`."
        )
        await interaction.followup.send(await _mist("list_create", fallback, {"lista": nombre}))

    @bot.tree.command(name="list_add", description="Agrega un link de YouTube a una lista")
    @app_commands.describe(nombre="Nombre de la lista", url="Link de YouTube")
    async def list_add(interaction: discord.Interaction, nombre: str, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        if not is_youtube_url(url):
            await interaction.response.send_message("Necesito un link de YouTube. Para buscar por nombre usá `/search`.")
            return

        if is_youtube_playlist_url(url):
            await interaction.response.send_message("Ese link es una playlist. Usá `/list_add_playlist` para importarla completa.")
            return

        added = add_to_list(interaction.guild.id, nombre, url)
        if not added:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return

        await interaction.response.defer()
        await interaction.followup.send(await _mist("list_add", f"Agregado a {nombre}.", {"lista": nombre}))

    @bot.tree.command(name="list_add_current", description="Agrega la canción actual a una lista")
    @app_commands.describe(nombre="Nombre de la lista")
    async def list_add_current(interaction: discord.Interaction, nombre: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        current_url = playback_manager.get_current(interaction.guild.id)
        if not current_url:
            await interaction.response.send_message("No hay una canción actual para guardar.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        added = add_to_list(interaction.guild.id, nombre, current_url)
        if not added:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return

        current_title = playback_manager.get_current_title(interaction.guild.id) or current_url
        await interaction.response.defer()
        fallback = f"Guardé en {nombre}: {current_title}"
        await interaction.followup.send(await _mist("list_add_current", fallback, {"lista": nombre, "titulo": current_title}))

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
            urls, playlist_title = await asyncio.to_thread(extract_playlist_urls, playlist_url)
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

        fallback = (
            f"Importé {added} canciones de '{playlist_title}' a {nombre}.\n"
            f"Si querés sumar un link suelto, usá `/list_add`."
        )
        await interaction.followup.send(
            await _mist(
                "list_add_playlist",
                fallback,
                {"lista": nombre, "playlist": playlist_title, "canciones": added},
            )
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

    @bot.tree.command(name="list_view", description="Muestra una lista completa con posiciones")
    @app_commands.describe(nombre="Nombre de la lista")
    async def list_view(interaction: discord.Interaction, nombre: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        saved_list = get_list(interaction.guild.id, nombre)
        if saved_list is None:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return
        if not saved_list.items:
            await interaction.response.send_message(f"La lista {saved_list.name} está vacía.")
            return

        header = f"{saved_list.name}: {len(saved_list.items)} canciones"
        lines = [f"{index}. {url}" for index, url in enumerate(saved_list.items, start=1)]
        chunks = _chunk_lines(header, lines)

        await interaction.response.send_message(chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    @bot.tree.command(name="list_delete", description="Borra una lista guardada")
    @app_commands.describe(nombre="Nombre de la lista", confirmar="Debe ser true para borrar")
    async def list_delete(interaction: discord.Interaction, nombre: str, confirmar: bool = False):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        if not await _has_list_access(interaction):
            await interaction.response.send_message(f"No tenés permiso para borrar listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        saved_list = get_list(interaction.guild.id, nombre)
        if saved_list is None:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return

        if not confirmar:
            await interaction.response.send_message(
                f"La lista {nombre} tiene {len(saved_list.items)} canciones. "
                f"Para borrarla usá `/list_delete nombre:{nombre} confirmar:true`."
            )
            return

        await interaction.response.defer()
        deleted_items = delete_list(interaction.guild.id, nombre)
        if deleted_items is None:
            await interaction.followup.send("No existe una lista con ese nombre.")
            return

        fallback = f"Lista {nombre} borrada. Se eliminaron {deleted_items} canciones guardadas."
        await interaction.followup.send(await _mist("list_delete", fallback, {"lista": nombre, "canciones": deleted_items}))

    @bot.tree.command(name="list_rename", description="Cambia el nombre de una lista guardada")
    @app_commands.describe(nombre="Nombre actual de la lista", nuevo_nombre="Nuevo nombre de la lista")
    async def list_rename(interaction: discord.Interaction, nombre: str, nuevo_nombre: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        if not await _has_list_access(interaction):
            await interaction.response.send_message(f"No tenés permiso para editar listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        nuevo_nombre = nuevo_nombre.strip()
        if not nuevo_nombre:
            await interaction.response.send_message("El nuevo nombre no puede estar vacío.")
            return

        await interaction.response.defer()
        renamed = rename_list(interaction.guild.id, nombre, nuevo_nombre)
        if renamed is None:
            await interaction.followup.send("No existe una lista con ese nombre.")
            return
        if not renamed:
            await interaction.followup.send("Ya existe una lista con ese nuevo nombre.")
            return

        fallback = f"Lista renombrada: {nombre} -> {nuevo_nombre}."
        await interaction.followup.send(
            await _mist("list_rename", fallback, {"lista": nombre, "nuevo_nombre": nuevo_nombre})
        )

    @bot.tree.command(name="list_remove", description="Quita una canción de una lista por posición")
    @app_commands.describe(nombre="Nombre de la lista", posicion="Número de la canción dentro de la lista")
    async def list_remove(interaction: discord.Interaction, nombre: str, posicion: int):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        if not await _has_list_access(interaction):
            await interaction.response.send_message(f"No tenés permiso para editar listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        if posicion < 1:
            await interaction.response.send_message("La posición debe ser 1 o mayor.")
            return

        await interaction.response.defer()
        removed_url = remove_list_item(interaction.guild.id, nombre, posicion)
        if removed_url is None:
            await interaction.followup.send("No existe una lista con ese nombre.")
            return
        if not removed_url:
            await interaction.followup.send("No hay una canción en esa posición.")
            return

        fallback = f"Quité la canción #{posicion} de {nombre}."
        await interaction.followup.send(
            await _mist("list_remove", fallback, {"lista": nombre, "posicion": posicion, "url": removed_url})
        )

    @bot.tree.command(name="list_edit", description="Reemplaza una canción de una lista por posición")
    @app_commands.describe(nombre="Nombre de la lista", posicion="Número de la canción a reemplazar", url="Nuevo link de YouTube")
    async def list_edit(interaction: discord.Interaction, nombre: str, posicion: int, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        if not await _has_list_access(interaction):
            await interaction.response.send_message(f"No tenés permiso para editar listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        if posicion < 1:
            await interaction.response.send_message("La posición debe ser 1 o mayor.")
            return
        if not is_youtube_url(url):
            await interaction.response.send_message("Necesito un link de YouTube. Para buscar por nombre usá `/search`.")
            return
        if is_youtube_playlist_url(url):
            await interaction.response.send_message("Ese link es una playlist. Usá `/list_add_playlist` para importarla completa.")
            return

        await interaction.response.defer()
        updated = update_list_item(interaction.guild.id, nombre, posicion, url)
        if updated is None:
            await interaction.followup.send("No existe una lista con ese nombre.")
            return
        if not updated:
            await interaction.followup.send("No hay una canción en esa posición.")
            return

        fallback = f"Actualicé la canción #{posicion} de {nombre}."
        await interaction.followup.send(
            await _mist("list_edit", fallback, {"lista": nombre, "posicion": posicion, "url": url})
        )

    @bot.tree.command(name="persist_status", description="Revisa conteos guardados en la base de datos")
    async def persist_status(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.", ephemeral=True)
            return

        if not await _has_list_access(interaction):
            await interaction.response.send_message("No tenés permiso para revisar persistencia.", ephemeral=True)
            return

        stats = storage_stats(interaction.guild.id)
        await interaction.response.send_message(
            "Persistencia activa.\n"
            f"Listas: {stats.lists}\n"
            f"Canciones guardadas: {stats.items}\n"
            f"Usuarios registrados: {stats.users}\n"
            f"Preguntas registradas: {stats.ai_logs}",
            ephemeral=True,
        )

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
            fallback = (
                f"Lista {saved_list.name} iniciada: {title}\n"
                f"Posición: 1/{len(saved_list.items)}. En cola: {remaining} canciones."
            )
        else:
            fallback = f"Lista {saved_list.name} iniciada: {title}"
        await interaction.followup.send(
            await _mist(
                "list_play",
                fallback,
                {"lista": saved_list.name, "titulo": title, "total": len(saved_list.items), "pendientes": remaining},
            )
        )

    @bot.tree.command(name="list_add_bulk", description="Agrega varios links de YouTube a una lista")
    @app_commands.describe(nombre="Nombre de la lista", links="Pega varios links separados por comas o saltos de línea")
    async def list_add_bulk(interaction: discord.Interaction, nombre: str, links: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member, roles_json = await _get_member_roles_json(interaction)
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, "display_name", None), roles_json)

        parts = [p.strip() for p in links.replace('\r', '\n').replace(',', '\n').split('\n') if p.strip()]
        invalid = [u for u in parts if not is_youtube_url(u) or is_youtube_playlist_url(u)]
        if invalid:
            await interaction.response.send_message(
                "Encontré links inválidos o playlists. Para playlists usá `/list_add_playlist`."
            )
            return
        if not parts:
            await interaction.response.send_message("No se detectaron URLs en la entrada.")
            return

        added = 0
        for u in parts:
            if add_to_list(interaction.guild.id, nombre, u):
                added += 1

        await interaction.response.defer()
        fallback = f"Agregados {added} links a {nombre}."
        await interaction.followup.send(await _mist("list_add_bulk", fallback, {"lista": nombre, "links": added}))
