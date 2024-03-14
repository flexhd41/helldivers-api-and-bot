# cogs/command_handler.py

import discord
from discord.ext import commands
from discord import option
from typing import Union
import cogs.data_fetcher
from cogs.data_fetcher import *

class CommandHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.slash_command()
    @option(
        "channel",
        Union[discord.TextChannel],
        description="Select a channel",
    )
    async def galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel], conn):
        add_server(conn, channel.id)
        await ctx.respond(f"Added Galactic War Status to channel {channel.mention}", ephemeral=True)
    @commands.slash_command()
    @option(
        "channel",
        Union[discord.TextChannel],
        description="Select a channel",
    )
    async def remove_galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel], conn):
        # Remove the channel ID from the database
        cursor = conn.cursor()
        cursor.execute('DELETE FROM servers WHERE channel_id = ?', (channel.id,))
        conn.commit()
        await ctx.respond(f"Removed Galactic War Status from channel {channel.mention}", ephemeral=True)

    @commands.slash_command()
    @option(
        "channel",
        Union[discord.TextChannel],
        description="Select a channel",
    )
    async def set_announcement_channel(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel], conn):
        # Store the channel ID in the database
        cursor = conn.cursor()
        cursor.execute('INSERT INTO announcement_channels (channel_id) VALUES (?)', (channel.id,))
        conn.commit()
        await ctx.respond(f"Set {channel.mention} as the announcement channel", ephemeral=True)
    @commands.slash_command()
    @option(
        "channel",
        Union[discord.TextChannel],
        description="Select a channel",
    )
    async def remove_announcement_channel(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel], conn):
        # Remove the channel ID from the database
        cursor = conn.cursor()
        cursor.execute('DELETE FROM announcement_channels WHERE channel_id = ?', (channel.id,))
        conn.commit()
        await ctx.respond(f"Removed {channel.mention} from the announcement channels", ephemeral=True)

def setup(bot):
    bot.add_cog(CommandHandler(bot))