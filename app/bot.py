import discord
from discord.ext import commands

from app.config import DISCORD_TOKEN
from app.lists import setup_lists_commands
from app.commands.music_commands import setup_music_commands
from app.commands.moderation_commands import setup_moderation_commands
from app.commands.ai_commands import setup_ai_commands

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"MIST online as {bot.user}")


setup_music_commands(bot)
setup_lists_commands(bot)
setup_moderation_commands(bot)
setup_ai_commands(bot)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)