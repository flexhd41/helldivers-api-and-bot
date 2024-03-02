import discord 
from discord import option
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import datetime
import sqlite3
from typing import Union
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

def delete_old_data(conn):
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM historical_data
        WHERE timestamp < datetime('now', '-1 hour')
    ''')
    conn.commit()
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planet TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            net_force REAL NOT NULL
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


latest_data = None

@tasks.loop(seconds=30)
async def fetch_hell_divers_info():
    global latest_data
    latest_data = requests.get('http://82.165.212.88:3000/activePlanets').json()
    await bot.wait_until_ready()
    delete_old_data(conn)
    
    # Fetch the latest Hell Divers data
    

@tasks.loop(seconds=60)
async def update_hell_divers_info():
    await bot.wait_until_ready()
    # Fetch the latest Hell Divers data
    data = latest_data

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

import discord


def create_embed(data):
    # Create a new embed object
    embed = discord.Embed(title="Galactic War Status", description="Current status of planets", color=0x00ff00)
    
    # Set the timestamp for the last update
    embed.timestamp = datetime.utcnow()
    
    # Iterate over each item in the data
    for item in data:
        if item['forces']['net'] is not None:
            net_force_cleaned = item['forces']['net'].replace('%/hr', '')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO historical_data (planet, net_force) VALUES (?, ?)', (item['planet'], net_force_cleaned))
            conn.commit()
        else:
            print(f"Skipping insertion for planet {item['planet']} due to missing 'net_force' value.")
        # Determine the color and emoji based on the status
        if "LOSING GROUND" in item['status']:
            embed.color = discord.Color.red()
        elif "LIBERATING" in item['status']:
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.blue()
        if "(" in item['planet']:
            planet_name = "🛡️" + item['planet']
        else:
            planet_name = "⚔️" + item['planet']
            
        
        # Combine all relevant information into a single field
        value = f"Liberation: {item['liberation']}\nPlayers: {item['players']}\nStatus: {item['status']}\nSuper Earth Forces: {item['forces']['super_earth_forces']}\nEnemy Forces: {item['forces']['enemy_forces']}\nNet: {item['forces']['net']}"
        
        # Add a field for each planet with the combined information
        embed.add_field(name=planet_name, value=value, inline=False)
    
    return embed









@bot.slash_command()
async def send_data(ctx):
    response = requests.get('http://82.165.212.88:3000/activePlanets')
    data = response.json()

    embed = discord.Embed(title="Hell Divers Data", description="Current status", color=0x00ff00)
    for item in data:
        embed.add_field(name=item['defending'], value=f"Liberation: {item['percentage']}\nPlayers: {item['count']}\nStatus: {item['status']}", inline=False)

    await ctx.respond(embed=embed)

update_hell_divers_info.start()
fetch_hell_divers_info.start()


import matplotlib.dates as mdates

@bot.slash_command()
@option(
    "planet",
    description="Select a planet",
    choices=["PÖPLI IX", "VELD", "INGMAR", "DRAUPNIR", "MALEVELON CREEK", "Other Planets**"]
)
async def send_graph(ctx, planet: str):
    # Fetch historical data for the selected planet
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, net_force FROM historical_data WHERE planet = ? ORDER BY timestamp DESC LIMIT 100', (planet,))
    rows = cursor.fetchall()

    if len(rows) < 2:
        await ctx.respond("Not enough historical data available.")
        return

    # Convert the strings to datetime objects and net_force to float
    timestamps = [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in rows]
    net_forces = [float(row[1]) for row in rows]

    # Create a figure and a set of subplots
    fig, ax = plt.subplots()

    # Plot the net force over time
    ax.plot(timestamps, net_forces, marker='o', label='Net Force')

    # Set labels and title
    ax.set_xlabel('Time')
    ax.set_ylabel('Net Force (%/Hr)')
    ax.set_title(f'Net Force Trend for {planet} Per hour')
    ax.legend()

    # Format x-axis to display every 5 minutes
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))  # to get a tick every 5 minutes
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))  # hours and minutes

    # Save the figure as an image file
    plt.savefig('net_force_graph.png')

    # Send the image with your bot
    with open('net_force_graph.png', 'rb') as f:
        picture = discord.File(f, filename='net_force_graph.png')
    await ctx.respond(file=picture)


@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    add_server(conn, channel.id)
    await ctx.respond(f"Added Galactic War Status to channel {channel.mention}", ephemeral=True)


bot.run(os.getenv('DISCORD_BOT_TOKEN'))
