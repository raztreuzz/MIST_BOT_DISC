import discord
from discord import app_commands
from discord.ext import commands

from app.music import create_audio_source
from app.emojis import MIST_HELLO, MIST_BYE, MIST_MUSIC


def setup_music_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="join", description="Mist entra a tu canal de voz")
    async def join(interaction: discord.Interaction):
        if interaction.user.voice is None:
            await interaction.response.send_message("Tenés que estar en un canal de voz.")
            return

        channel = interaction.user.voice.channel

        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.move_to(channel)
            await interaction.response.send_message("MIST se movió a tu canal de voz.")
            return

        await channel.connect()
        await interaction.response.send_message(f"{MIST_HELLO} Entré al canal de voz.")

    @bot.tree.command(name="leave", description="Mist sale del canal de voz")
    async def leave(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if voice_client is None:
            await interaction.response.send_message("MIST no está en un canal de voz.")
            return

        await voice_client.disconnect()
        await interaction.response.send_message(f"{MIST_BYE} Salí del canal de voz.")

    @bot.tree.command(name="play", description="Reproduce audio desde un link de YouTube")
    @app_commands.describe(url="Link de YouTube")
    async def play(interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        if interaction.user.voice is None:
            await interaction.followup.send("Tenés que estar en un canal de voz.")
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None:
            voice_client = await interaction.user.voice.channel.connect()

        if voice_client.is_playing():
            voice_client.stop()

        source, title = create_audio_source(url)

        voice_client.play(source)
        await interaction.followup.send(f"{MIST_MUSIC} Reproduciendo: {title}")

    @bot.tree.command(name="pause", description="Pausa la canción actual")
    async def pause(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Pausado.")
            return

        await interaction.response.send_message("No hay música reproduciéndose.")

    @bot.tree.command(name="resume", description="Continúa la canción pausada")
    async def resume(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Reanudado.")
            return

        await interaction.response.send_message("No hay música pausada.")

    @bot.tree.command(name="stop", description="Detiene la canción actual")
    async def stop(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if voice_client:
            voice_client.stop()
            await interaction.response.send_message("Detenido.")
            return

        await interaction.response.send_message("MIST no está en un canal de voz.")
