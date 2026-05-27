import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from app.ai.mist_voice import mist_command_reply
from app.config import CIRCLE_ROLE_NAME


def setup_moderation_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="purge", description="Borra mensajes del canal (máx 100).")
    @app_commands.describe(cantidad="Cantidad de mensajes a borrar (1-100)", usuario="Opcional: borrar solo mensajes de este usuario")
    async def purge(interaction: discord.Interaction, cantidad: int, usuario: Optional[discord.Member] = None):
        # Basic checks
        if interaction.guild is None:
            await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
            return

        # Check permissions: Manage Messages or role
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except Exception:
                member = interaction.user

        role_names = [r.name for r in getattr(member, 'roles', []) if getattr(r, 'name', '') != '@everyone']
        has_perm = interaction.user.guild_permissions.manage_messages or (CIRCLE_ROLE_NAME in role_names)
        if not has_perm:
            await interaction.response.send_message("No tenés permiso para borrar mensajes.", ephemeral=True)
            return

        if cantidad < 1 or cantidad > 100:
            await interaction.response.send_message("La cantidad debe estar entre 1 y 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Este comando solo funciona en canales de texto.", ephemeral=True)
            return

        def check(m: discord.Message) -> bool:
            if usuario is None:
                return True
            return m.author.id == usuario.id

        try:
            deleted = await channel.purge(limit=cantidad, check=check)
            fallback = f"Borrados {len(deleted)} mensajes."
            message = await mist_command_reply("purge", fallback, {"mensajes": len(deleted)})
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error al borrar mensajes: {e}", ephemeral=True)
