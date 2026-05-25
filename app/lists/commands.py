import discord
from discord import app_commands
from discord.ext import commands
import json

from app.lists.storage import add_to_list, create_list, get_list, list_lists, ensure_user
from app.music import create_audio_source
from app.config import CIRCLE_ROLE_NAME


def setup_lists_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="list_create", description="Crea una lista guardada")
    @app_commands.describe(name="Nombre de la lista", kind="Tipo de lista")
    async def list_create(interaction: discord.Interaction, name: str, kind: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        # Fetch member reliably and capture roles as JSON
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                member = interaction.user

        role_objs = getattr(member, 'roles', [])
        role_names = [r.name for r in role_objs if getattr(r, 'name', '') != '@everyone']
        role_ids = [r.id for r in role_objs if getattr(r, 'id', None) is not None and getattr(r, 'name', '') != '@everyone']
        roles_json = json.dumps({'ids': role_ids, 'names': role_names})

        if CIRCLE_ROLE_NAME not in role_names:
            await interaction.response.send_message(f"No tenés permiso para crear listas. Se requiere el rol '{CIRCLE_ROLE_NAME}'.")
            return

        # Ensure user profile
        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, 'display_name', None), roles_json)

        created = create_list(interaction.guild.id, name, kind, creator_id=interaction.user.id)
        if not created:
            await interaction.response.send_message("Ya existe una lista con ese nombre.")
            return
        await interaction.response.send_message(f"Hola {interaction.user.display_name}, lista creada: {name} ({kind}).\nSi querés agregar varias canciones ahora, usá `/list_add_bulk` con una lista de URLs separadas por comas o saltos de línea.")

    @bot.tree.command(name="list_add", description="Agrega un link a una lista guardada")
    @app_commands.describe(name="Nombre de la lista", url="Link de YouTube")
    async def list_add(interaction: discord.Interaction, name: str, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        # ensure user recorded (fetch roles)
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                member = interaction.user

        role_objs = getattr(member, 'roles', [])
        role_names = [r.name for r in role_objs if getattr(r, 'name', '') != '@everyone']
        role_ids = [r.id for r in role_objs if getattr(r, 'id', None) is not None and getattr(r, 'name', '') != '@everyone']
        roles_json = json.dumps({'ids': role_ids, 'names': role_names})

        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, 'display_name', None), roles_json)

        added = add_to_list(interaction.guild.id, name, url)
        if not added:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return
        
        await interaction.response.send_message(f"Agregado a {name}.")

    @bot.tree.command(name="list_show", description="Muestra las listas guardadas")
    async def list_show(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        
        lists = list_lists(interaction.guild.id)
        if not lists:
            await interaction.response.send_message("No hay listas guardadas todavía.")
            return
        
        lines = [f"{sl.name} ({sl.kind}): {len(sl.items)} items" for sl in lists]
        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="list_play", description="Reproduce una lista guardada")
    @app_commands.describe(name="Nombre de la lista")
    async def list_play(interaction: discord.Interaction, name: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        
        saved_list = get_list(interaction.guild.id, name)
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
            voice_client = await interaction.user.voice.channel.connect()
        
        if voice_client.is_playing():
            voice_client.stop()
        
        first_url = saved_list.items[0]
        source, title = create_audio_source(first_url)
        voice_client.play(source)
        
        await interaction.followup.send(f"Reproduciendo {saved_list.name}: {title}")

    @bot.tree.command(name="list_add_bulk", description="Agrega varios links a una lista (separados por comas o saltos de línea)")
    @app_commands.describe(name="Nombre de la lista", urls="URLs separadas por comas o saltos de línea")
    async def list_add_bulk(interaction: discord.Interaction, name: str, urls: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                member = interaction.user

        role_objs = getattr(member, 'roles', [])
        role_names = [r.name for r in role_objs if getattr(r, 'name', '') != '@everyone']
        role_ids = [r.id for r in role_objs if getattr(r, 'id', None) is not None and getattr(r, 'name', '') != '@everyone']
        roles_json = json.dumps({'ids': role_ids, 'names': role_names})

        ensure_user(interaction.guild.id, interaction.user.id, getattr(member, 'display_name', None), roles_json)

        # split by newline or comma
        parts = [p.strip() for p in urls.replace('\r', '\n').replace(',', '\n').split('\n') if p.strip()]
        if not parts:
            await interaction.response.send_message("No se detectaron URLs en la entrada.")
            return

        added = 0
        for u in parts:
            if add_to_list(interaction.guild.id, name, u):
                added += 1

        await interaction.response.send_message(f"Agregados {added} items a {name}.")
