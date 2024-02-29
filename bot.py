import discord 
from discord import option
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import datetime
import sqlite3
from typing import Union
from table2ascii import table2ascii as t2a, PresetStyle

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


# Setup SQLite database
def setup_db():
    conn = sqlite3.connect('servers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel INTEGER NOT NULL,
            message_id INTEGER
        )
    ''')
    conn.commit()
    return conn

conn = setup_db()  # Initialize the database

def store_message_id(conn, channel_id, message_id):
    cursor = conn.cursor()
    cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel_id))
    conn.commit()

def get_channels_to_update(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT channel, message_id FROM servers')
    return cursor.fetchall()
def add_server(conn, channel, message_id=None):
    cursor = conn.cursor()
    if message_id:
        # Update the existing record
        cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel))
    else:
        # Insert a new record
        cursor.execute('INSERT INTO servers (channel) VALUES (?)', (channel,))
    conn.commit()



@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


@tasks.loop(seconds=60)
async def update_hell_divers_info():
    await bot.wait_until_ready()
    # Fetch the latest Hell Divers data
    data = requests.get('http://127.0.0.1:5000/scrape').json()

    # Get the channels to update
    channels_to_update = get_channels_to_update(conn)  # Pass the connection object

    for channel_id, message_id in channels_to_update:
        channel = bot.get_channel(int(channel_id))
        if message_id:
            # Edit the existing message
            message = await channel.fetch_message(message_id)
            embed = create_embed(data)
            await message.edit(embed=embed)
        else:
            # Send a new message and store its ID
            embed = create_embed(data)
            message = await channel.send(embed=embed)
            # Store the new message ID for future updates
            store_message_id(conn, channel_id, message.id)  # Pass the connection object



def store_message_id(conn, channel_id, message_id):
    cursor = conn.cursor()
    cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel_id))
    conn.commit()

from table2ascii import table2ascii as t2a, PresetStyle

from discord import Embed, Colour

def create_embed(data):
    # Create a new Discord embed
    embed = Embed(title="Hell Divers Data", description="Current status", color=Colour.green())
    now = datetime.datetime.now()
    embed.set_footer(text=f'Last updated • Today at {now.strftime("%H:%M")} (UTC+00)')

    # Add each item from the data as a field in the embed
    for item in data:
        # Format the field name and value
        field_name = f"{item['defending']} - {item['percentage']}"
        field_value = f"Players: {item['count']}\nStatus: {item['status']}"

        # Add the field to the embed
        embed.add_field(name=field_name, value=field_value, inline=False)
        now = datetime.datetime.now() # Gets your current time as a datetime object


    return embed


@bot.slash_command()
async def send_data(ctx):
    response = requests.get('http://127.0.0.1:5000/scrape')
    data = response.json()

    embed = discord.Embed(title="Hell Divers Data", description="Current status", color=0x00ff00)
    for item in data:
        embed.add_field(name=item['defending'], value=f"Liberation: {item['percentage']}\nPlayers: {item['count']}\nStatus: {item['status']}", inline=False)

    await ctx.respond(embed=embed)

update_hell_divers_info.start()

@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    add_server(conn, channel.id)
    await ctx.defer()
    await ctx.followup.send(f"Added Galactic War Status to channel {channel.mention}", ephemeral=True)


bot.run('TOKEN')