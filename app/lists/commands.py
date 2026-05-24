import discord
from discord import app_commands
from discord.ext import commands

from app.lists.storage import add_to_list, create_list, get_list, list_lists
from app.music import create_audio_source
from app.emojis import MIST_HELLO, MIST_MUSIC


def setup_lists_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="list_create", description="Crea una lista guardada")
    @app_commands.describe(name="Nombre de la lista", kind="Tipo de lista")
    async def list_create(interaction: discord.Interaction, name: str, kind: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        
        created = create_list(interaction.guild.id, name, kind)
        if not created:
            await interaction.response.send_message("Ya existe una lista con ese nombre.")
            return
        
        await interaction.response.send_message(f"{MIST_HELLO} Lista creada: {name} ({kind})")

    @bot.tree.command(name="list_add", description="Agrega un link a una lista guardada")
    @app_commands.describe(name="Nombre de la lista", url="Link de YouTube")
    async def list_add(interaction: discord.Interaction, name: str, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return
        
        added = add_to_list(interaction.guild.id, name, url)
        if not added:
            await interaction.response.send_message("No existe una lista con ese nombre.")
            return
        
        await interaction.response.send_message(f"{MIST_HELLO} Agregado a {name}.")

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
        
        await interaction.followup.send(f"{MIST_MUSIC} Reproduciendo {saved_list.name}: {title}")
