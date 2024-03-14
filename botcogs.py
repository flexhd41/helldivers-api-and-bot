import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

bot.load_extension('cogs.data_fetcher')
bot.load_extension('cogs.database_manager')
bot.load_extension('cogs.command_handler')

bot.run(os.getenv('DISCORD_BOT_TOKEN'))