import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from app.ai.mist_voice import mist_command_reply
from app.music import search_youtube
from app.playback import playback_manager


def _repeat_label(mode: str) -> str:
    return {
        "off": "desactivado",
        "cancion": "repetir canción",
        "lista": "repetir lista",
    }.get(mode, mode)


def setup_music_commands(bot: commands.Bot) -> None:
    async def _mist(action: str, fallback: str, details: dict | None = None) -> str:
        return await mist_command_reply(action, fallback, details)

    async def _connect_voice_for_playback(interaction: discord.Interaction):
        if interaction.user.voice is None:
            await interaction.followup.send("Tenés que estar en un canal de voz.")
            return None

        voice_client = interaction.guild.voice_client
        if voice_client is not None:
            return voice_client

        try:
            return await interaction.user.voice.channel.connect()
        except Exception as exc:
            await interaction.followup.send(
                f"No pude conectarme al canal de voz: {exc}. Revisá permisos de conectar/hablar o intentá `/join` primero."
            )
            return None

    @bot.tree.command(name="voice_mist", description="Activa o desactiva la voz corta de MIST entre canciones")
    @app_commands.describe(activar="true para activar la voz, false para desactivarla")
    async def voice_mist(interaction: discord.Interaction, activar: bool):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        playback_manager.set_voice_enabled(interaction.guild.id, activar)
        if activar:
            await interaction.response.send_message("Voz de MIST activada. Hablaré solo con frases cortas entre canciones.")
        else:
            await interaction.response.send_message("Voz de MIST desactivada.")

    @bot.tree.command(name="join", description="Mist entra a tu canal de voz")
    async def join(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        if interaction.user.voice is None:
            await interaction.response.send_message("Tenés que estar en un canal de voz.")
            return

        await interaction.response.defer()
        channel = interaction.user.voice.channel

        if interaction.guild.voice_client is not None:
            try:
                await interaction.guild.voice_client.move_to(channel)
            except Exception as exc:
                await interaction.followup.send(f"No pude moverme al canal de voz: {exc}")
                return
            await interaction.followup.send(await _mist("join", "MIST se movió a tu canal de voz.", {"canal": channel.name}))
            await playback_manager.speak(
                interaction.guild.id,
                interaction.guild.voice_client,
                "join_voice",
                "Hola, ya estoy aquí.",
                {"canal": channel.name},
            )
            return

        try:
            voice_client = await channel.connect()
        except Exception as exc:
            await interaction.followup.send(
                f"No pude conectarme al canal de voz: {exc}. Revisá permisos de conectar/hablar o intentá de nuevo."
            )
            return
        await interaction.followup.send(await _mist("join", "Entré al canal de voz.", {"canal": channel.name}))
        await playback_manager.speak(
            interaction.guild.id,
            voice_client,
            "join_voice",
            "Hola, ya estoy aquí.",
            {"canal": channel.name},
        )

    @bot.tree.command(name="leave", description="Mist sale del canal de voz")
    async def leave(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        voice_client = interaction.guild.voice_client

        if voice_client is None:
            await interaction.response.send_message("MIST no está en un canal de voz.")
            return

        await interaction.response.defer()
        await voice_client.disconnect()
        await interaction.followup.send(await _mist("leave", "Salí del canal de voz."))

    @bot.tree.command(name="play", description="Reproduce audio desde un link de YouTube")
    @app_commands.describe(url="Link de YouTube")
    async def play(interaction: discord.Interaction, url: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()

        voice_client = await _connect_voice_for_playback(interaction)
        if voice_client is None:
            return

        if voice_client.is_playing() or voice_client.is_paused():
            playback_manager.stop(interaction.guild.id, voice_client)

        try:
            title = await playback_manager.play(interaction.guild.id, voice_client, url)
        except Exception as exc:
            await interaction.followup.send(f"No pude iniciar la reproducción: {exc}")
            return

        fallback = f"Secuencia musical iniciada: {title}"
        await interaction.followup.send(await _mist("play", fallback, {"titulo": title}))

    @bot.tree.command(name="search", description="Busca canciones en YouTube")
    @app_commands.describe(cancion="Nombre de la canción o artista")
    async def search(interaction: discord.Interaction, cancion: str):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()

        try:
            results = await asyncio.to_thread(search_youtube, cancion, 5)
        except Exception as exc:
            await interaction.followup.send(f"No pude buscar en YouTube: {exc}")
            return

        if not results:
            await interaction.followup.send("No encontré resultados.")
            return

        playback_manager.set_search_results(interaction.guild.id, results)
        lines = [f"Resultados para: {cancion}"]
        for idx, result in enumerate(results, start=1):
            lines.append(f"{idx}. {result['title']}\n   {result['url']}")
        lines.append("Usá `/play_result numero:<número>` para reproducir uno.")
        await interaction.followup.send("\n".join(lines))

    @bot.tree.command(name="play_result", description="Reproduce un resultado de la última búsqueda")
    @app_commands.describe(numero="Número del resultado de /search")
    async def play_result(interaction: discord.Interaction, numero: int):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        result = playback_manager.get_search_result(interaction.guild.id, numero)
        if result is None:
            await interaction.response.send_message("No existe ese resultado. Usá `/search` primero.")
            return

        await interaction.response.defer()

        voice_client = await _connect_voice_for_playback(interaction)
        if voice_client is None:
            return

        if voice_client.is_playing() or voice_client.is_paused():
            playback_manager.stop(interaction.guild.id, voice_client)

        try:
            title = await playback_manager.play(interaction.guild.id, voice_client, result["url"])
        except Exception as exc:
            await interaction.followup.send(f"No pude reproducir el resultado: {exc}")
            return

        fallback = f"Resultado {numero} seleccionado: {title}"
        await interaction.followup.send(await _mist("play_result", fallback, {"numero": numero, "titulo": title}))

    @bot.tree.command(name="pause", description="Pausa la canción actual")
    async def pause(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.followup.send(await _mist("pause", "Pausado."))
            return

        await interaction.followup.send("No hay música reproduciéndose.")

    @bot.tree.command(name="resume", description="Continúa la canción pausada")
    async def resume(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.followup.send(await _mist("resume", "Reanudado."))
            return

        await interaction.followup.send("No hay música pausada.")

    @bot.tree.command(name="stop", description="Detiene la canción actual")
    async def stop(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()
        voice_client = interaction.guild.voice_client

        if voice_client:
            playback_manager.stop(interaction.guild.id, voice_client)
            await interaction.followup.send(await _mist("stop", "Música detenida. La cola ha sido despejada."))
            return

        await interaction.followup.send("MIST no está en un canal de voz.")

    @bot.tree.command(name="skip", description="Salta la canción actual")
    async def skip(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()
        voice_client = interaction.guild.voice_client
        skipped, next_number, next_url = playback_manager.skip(interaction.guild.id, voice_client)
        if skipped:
            if next_number and next_url:
                fallback = f"Saltando a la canción {next_number}: {next_url}"
                await interaction.followup.send(await _mist("skip", fallback, {"siguiente": next_number, "url": next_url}))
            else:
                await interaction.followup.send(await _mist("skip", "Saltando canción. No quedan más canciones en cola."))
            return

        await interaction.followup.send("No hay canción reproduciéndose.")

    @bot.tree.command(name="nowplaying", description="Muestra la canción actual")
    async def nowplaying(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        info = playback_manager.nowplaying_info(interaction.guild.id)
        if not info["title"] and not info["url"]:
            await interaction.response.send_message("No hay música reproduciéndose.")
            return

        title = info["title"] or info["url"]
        lines = [f"Ahora suena: {title}"]
        if info["source_name"] and info["position"] and info["total"]:
            lines.append(f"Lista: {info['source_name']} ({info['position']}/{info['total']})")
        elif info["position"] and info["total"]:
            lines.append(f"Posición: {info['position']}/{info['total']}")
        lines.append(f"Repeat: {_repeat_label(info['repeat_mode'])}")
        lines.append(f"En cola: {info['queued']} canciones")
        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="shuffle", description="Mezcla las canciones pendientes de la cola")
    async def shuffle(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        await interaction.response.defer()
        shuffled = playback_manager.shuffle_queue(interaction.guild.id)
        if shuffled <= 1:
            await interaction.followup.send("No hay suficientes canciones pendientes para mezclar.")
            return

        fallback = f"Cola mezclada. {shuffled} canciones pendientes cambiaron de orden."
        await interaction.followup.send(await _mist("shuffle", fallback, {"canciones": shuffled}))

    @bot.tree.command(name="queue", description="Muestra la canción actual y las siguientes en cola")
    async def queue(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        current, upcoming, remaining = playback_manager.queue_summary(interaction.guild.id)
        info = playback_manager.nowplaying_info(interaction.guild.id)
        if not current and not upcoming:
            await interaction.response.send_message("No hay canciones en cola.")
            return

        lines = []
        repeat_mode = info["repeat_mode"]
        if repeat_mode != "off":
            lines.append(f"Repeat: {_repeat_label(repeat_mode)}")
        if current:
            if info["source_name"] and info["position"] and info["total"]:
                lines.append(f"Ahora ({info['position']}/{info['total']} de {info['source_name']}): {current}")
            else:
                lines.append(f"Ahora: {current}")
        if upcoming:
            lines.append("Siguientes:")
            lines.extend(f"{idx}. {url}" for idx, url in enumerate(upcoming, start=1))
        if remaining:
            lines.append(f"... y {remaining} más")

        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="repeat", description="Configura la repetición de música")
    @app_commands.describe(modo="Elige cómo repetir la música")
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="Desactivado", value="off"),
            app_commands.Choice(name="Repetir canción", value="cancion"),
            app_commands.Choice(name="Repetir lista", value="lista"),
        ]
    )
    async def repeat(interaction: discord.Interaction, modo: str = "off"):
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en un servidor.")
            return

        guild_id = interaction.guild.id
        modo = modo.lower().strip()
        if modo not in ("off", "cancion", "lista"):
            await interaction.response.send_message("Modo inválido. Elegí una opción de la lista.")
            return

        await interaction.response.defer()
        playback_manager.set_repeat_mode(guild_id, modo)
        if modo == "off":
            await interaction.followup.send(await _mist("repeat", "Repetición desactivada.", {"modo": _repeat_label(modo)}))
        elif modo == "cancion":
            await interaction.followup.send(
                await _mist("repeat", "Repetición activada para la canción actual.", {"modo": _repeat_label(modo)})
            )
        else:
            await interaction.followup.send(
                await _mist("repeat", "Repetición activada para toda la lista.", {"modo": _repeat_label(modo)})
            )
