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
import json
from discord.errors import DiscordServerError
import asyncio

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
    cursor.execute('CREATE TABLE IF NOT EXISTS announcement_channels (channel_id INTEGER PRIMARY KEY)')
    conn.commit()
    return conn

conn = setup_db()  # Initialize the database

def store_message_id(conn, channel_id, message_id):
    cursor = conn.cursor()
    cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel_id))
    conn.commit()

def cleanup():
    cursor = conn.cursor()
    servers = cursor.fetchall()
    for channel_id in servers:
        channel_id = channel_id[0]  # fetchall() returns a list of tuples
        try:
            channel = bot.get_channel(int(channel_id))
            if channel is None:
                raise Exception('403 Forbidden')
        except Exception as e:
            if '403 Forbidden' in str(e):
                cursor.execute("DELETE FROM servers WHERE channel_id = ?", (channel_id,))
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
def estimate_time_remaining(current_liberation, liberation_per_hour, regen_per_hour):
    remaining_liberation = 100 - current_liberation
    net_liberation_per_hour = liberation_per_hour - regen_per_hour
    if net_liberation_per_hour <= 0:
        return "Infinite"
    else:
        hours_remaining = remaining_liberation / net_liberation_per_hour
        return f"{hours_remaining} hours remaining"
from datetime import datetime

def calculate_liberation_per_hour(conn, planet):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT net_force, timestamp
        FROM historical_data
        WHERE planet = ?
        ORDER BY timestamp DESC
        LIMIT 2
    ''', (planet,))
    data = cursor.fetchall()
    if len(data) < 2:
        return None  # Not enough data to calculate liberation per hour
    else:
        recent_liberation, recent_timestamp_str = data[0]
        previous_liberation, previous_timestamp_str = data[1]
        # Convert timestamp strings to datetime objects
        datetime_format = "%Y-%m-%d %H:%M:%S"  # Adjust this to match the format of your timestamps
        recent_timestamp = datetime.strptime(recent_timestamp_str, datetime_format)
        previous_timestamp = datetime.strptime(previous_timestamp_str, datetime_format)
        liberation_diff = recent_liberation - previous_liberation
        time_diff = (recent_timestamp - previous_timestamp).total_seconds() / 3600  # Convert time difference to hours
        liberation_per_hour = liberation_diff / time_diff
        return liberation_per_hour
    
async def cleanup_message_ids(channels_to_update):
    cursor = conn.cursor()
    for channel_id, message_id in channels_to_update:
        channel = bot.get_channel(int(channel_id))
        if channel is not None:
            try:
                await channel.fetch_message(message_id)
            except discord.NotFound:
                # If the message is not found, remove its ID from the database
                cursor.execute("DELETE FROM servers WHERE channel_id = ?", (channel_id,))  # Assuming remove_message_id is a function that removes a message ID from the database




@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')


latest_data = None
net_force_cleaned = None

@tasks.loop(seconds=30)
async def fetch_hell_divers_info():
    global latest_data
    
    latest_data = requests.get('http://dev.nexusrealms.de:25567/api/planet-data').json()
    await bot.wait_until_ready()
    cleanup()
    # Get the channels to update
    channels_to_update = get_channels_to_update(conn)  # Pass the connection object

    # Cleanup message IDs
    await cleanup_message_ids(channels_to_update)
    for item in latest_data:
        if item['liberation'] is not None:
            global net_force_cleaned
            net_force_cleaned = item['liberation'].replace('%', '')
            cursor = conn.cursor()
            # Get the current timestamp in the desired format
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO historical_data (planet, net_force, timestamp) VALUES (?, ?, ?)', (item['name'], net_force_cleaned, timestamp))
            conn.commit()
        else:
            print(f"Skipping insertion for planet {item['name']} due to missing 'liberation' value.")

@tasks.loop(seconds=60)
async def update_announcements():
    await bot.wait_until_ready()
    
    # Fetch the latest Hell Divers data
    data = latest_data  # Use the data directly

    # Get the announcement channels
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id FROM announcement_channels')
    announcement_channels = [row[0] for row in cursor.fetchall()]

    # Get the list of planets from the database
    cursor.execute('SELECT DISTINCT planet FROM historical_data')
    db_planets = [row[0] for row in cursor.fetchall()]

    # Get the list of planets from the latest data
    latest_planets = [item['name'] for item in data]

    # Find the planets that have been liberated
    liberated_planets = [planet for planet in db_planets if planet not in latest_planets]

    # Find the planets that are under attack
    attacked_planets = [planet for planet in latest_planets if planet not in db_planets]

    # Announce the status changes
    for channel_id in announcement_channels:
        channel = bot.get_channel(int(channel_id))
        for planet in liberated_planets:
            await channel.send(f'{planet} has been liberated!')
        for planet in attacked_planets:
            await channel.send(f'{planet} is under attack!')


@tasks.loop(seconds=60)
async def update_hell_divers_info():
    cleanup()
    await bot.wait_until_ready()
    
    # Fetch the latest Hell Divers data
    data = latest_data  # Use the data directly

    # Get the channels to update
    channels_to_update = get_channels_to_update(conn)  # Pass the connection object

    for channel_id, message_id in channels_to_update:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            print(f"Channel with ID {channel_id} not found.")
            continue  # Skip to the next iteration
        if message_id:
            # Edit the existing message
            for _ in range(3):  # retry up to 3 times
                try:
                    message = await channel.fetch_message(message_id)
                    break  # if successful, break out of the loop
                except DiscordServerError as e:
                    if e.status == 503:
                        await asyncio.sleep(10)  # wait for 10 seconds before retrying
                    else:
                        raise  # re-raise the exception if it's not a 503 error
            embed = create_embed(data)
            await message.edit(embed=embed)
        else:
            # Send a new message and store its ID
            embed = create_embed(data)
            try:
                message = await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send message to channel {channel_id}: {e}")
                continue  # Skip to the next iteration
            # Store the new message ID for future updates
            store_message_id(conn, channel_id, message.id)

def store_message_id(conn, channel_id, message_id):
    cursor = conn.cursor()
    cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel_id))
    conn.commit()
def create_embed(data):
    embed = discord.Embed(title="Galactic War Status", description="Current status of planets", color=0x00ff00)
    embed.timestamp = datetime.utcnow()

    for item in data:
        value = ""
        planet_name = "⚔️" + item['name']
        liberation_percentage = round(float(item['liberation'].replace('%', '')))  # Remove the '%' and convert to float, then round to int
        liberation_percentage = round(float(item['liberation'].replace('%', '')))  # Remove the '%' and convert to float, then round to int
        liberation_per_hour = calculate_liberation_per_hour(conn, item['name'])
        if liberation_per_hour is not None:
            regen_per_hour = float(item['regen_per_hour_percent'].replace('%/hr', ''))
            estimated_time = estimate_time_remaining(liberation_percentage, liberation_per_hour, regen_per_hour)
            value += f"{estimated_time}"
        if liberation_percentage < 50:
            color = '🟥'  # red
        elif 50 <= liberation_percentage < 75:
            color = '🟧'  # orange
        elif 75 <= liberation_percentage < 90:
            color = '🟨'  # yellow
        else:
            color = '🟩'  # green
        filled_length = round(liberation_percentage / 10)  # Calculate filled part of the bar
        filled = color * filled_length
        empty = '⬛' * (10 - filled_length)  # Calculate empty part of the bar
        liberation = f"{filled}{empty} {liberation_percentage}%/100%"  # Add the percentage to the health bar
        value = f"Liberation: {liberation}\nPlayers: {item['players']}\nInitial Owner: {item['initialOwner']}\nRegen per hour percent: {item['regen_per_hour_percent']}\nEstimated Time: {value}"#\nEstimated Outcome: {item.get('estimatedOutcome', 'N/A')}\nEstimated Time: {item.get('estimatedTime', 'N/A')}
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
update_announcements.start()


import matplotlib.dates as mdates
from scipy.interpolate import interp1d
from Levenshtein import ratio

@bot.slash_command()
@option(
    "planet",
    description="Select a planet"
)
@option(
    "time_range",
    description="Select a time range",
    choices=["1h", "12h", "1d", "all"]
)
async def send_graph(ctx, planet: str, time_range: str):
    # Determine the time range
    if time_range == "1h":
        time_limit = "1 hour"
        x_axis_format = '%H:%M'  # minutes and seconds
        interval = 10  # 10 minutes
    elif time_range == "12h":
        time_limit = "12 hours"
        x_axis_format = '%H:%M'  # hours and minutes
        interval = 60  # 1 hour
    elif time_range == "1d":
        time_limit = "1 day"
        x_axis_format = '%H:%M'  # hours and minutes
        interval = 120  # 2 hours
    else:
        time_limit = None
        x_axis_format = '%Y-%m-%d %H:%M'  # date, hours and minutes
        interval = 24*60  # 1 day

    # Fetch historical data for the selected planet
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT planet
        FROM historical_data
    ''')
    planets = [row[0] for row in cursor.fetchall()]

    # Find the planet that most closely matches the selected planet
    closest_match = max(planets, key=lambda x: ratio(x.lower(), planet.lower()))
    print(closest_match)

    # If the match is not close enough, reject the selection
    if ratio(closest_match.lower(), planet.lower()) < 0.8:
        await ctx.respond(f"Invalid planet. Did you mean {closest_match}?", ephemeral=True)
        return
    
    if time_limit:
        cursor.execute('''
            SELECT timestamp, net_force
            FROM historical_data
            WHERE planet = ? AND timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
        ''', (closest_match, '-' + time_limit))  # Use closest_match instead of planet
    else:
        cursor.execute('''
            SELECT timestamp, net_force
            FROM historical_data
            WHERE planet = ? 
            ORDER BY timestamp DESC
        ''', (closest_match,))  # Use closest_match instead of planet
    rows = cursor.fetchall()

    if len(rows) < 2:
        await ctx.respond("Not enough historical data available.")
        return
    timestamps = [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in rows]
    net_forces = [float(row[1]) for row in rows]
    # Convert timestamps and net_forces to numpy arrays
    timestamps = np.array(timestamps)
    net_forces = np.array(net_forces)

    # Find the indices of unique timestamps
    unique_indices = np.unique(timestamps, return_index=True)[1]

    # Create new arrays of unique timestamps and corresponding net_forces
    timestamps_unique = timestamps[unique_indices]
    net_forces_unique = net_forces[unique_indices]

    # Convert unique timestamps to numbers
    timestamps_num_unique = mdates.date2num(timestamps_unique)

    # Create a cubic interpolation function
    f = interp1d(timestamps_num_unique, net_forces_unique, kind='cubic')

    # Create new timestamps for interpolation
    timestamps_interp = np.linspace(timestamps_num_unique.min(), timestamps_num_unique.max(), 500)

    # Apply the interpolation function to the new timestamps
    net_forces_interp = f(timestamps_interp)
    # Create a figure and a set of subplots
    fig, ax = plt.subplots()

    # Plot the interpolated net force over time
    ax.plot_date(timestamps_interp, net_forces_interp, marker='o', linestyle='-', label='Net Force')

    # Set labels and titles
    ax.set_xlabel('Time')
    ax.set_ylabel('Liberation (%)')
    ax.set_title(f'Liberation Trend for {planet} Per {time_range}')
    ax.legend()

    # Format x-axis to display every 5 minutes
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=interval))  # to get a tick every 5 minutes
    ax.xaxis.set_major_formatter(mdates.DateFormatter(x_axis_format))  # hours and minutes

    # Save the figure as an image file
    plt.savefig('net_force_graph.png')

    # Send the image with your bot
    with open('net_force_graph.png', 'rb') as f:
        picture = discord.File(f, filename='net_force_graph.png')
    await ctx.respond(file=picture)
import requests
import matplotlib.pyplot as plt
from adjustText import adjust_text

import matplotlib.pyplot as plt



def create_map(info):
    fig, ax = plt.subplots(figsize=(12, 10))  # Increase figure width
    for planet_info in info:
        if planet_info['initial_owner'] != 'Humans' and planet_info['name'] != "":
            x = planet_info['position']['x']
            y = planet_info['position']['y']
            name = planet_info['name']
            ax.scatter(x, y, s=300, label=name)  # Add label for the legend
            ax.text(x, y, name[0], color='black', ha='center', va='center')  # Add the first letter of the name to the center of the circle

    # Add a legend outside of the plot
    ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.5))  # Move the legend to the right

    # Adjust layout to make sure everything fits
    plt.tight_layout(rect=[0, 0, 0.99, 1])  # Adjust this as needed

    plt.savefig('map.png', dpi=600)

@bot.slash_command()
async def gen_map_wip(ctx):
    await ctx.response.defer()

    # Senden Sie eine GET-Anfrage an die URL
    response = requests.get('http://api.nexusrealms.de:4000/api/801/planets')

    # Überprüfen Sie, ob die Anfrage erfolgreich war
    if response.status_code == 200:
        # Verarbeiten Sie die Antwort
        info = response.json()

        # Überprüfen Sie, ob die Antwort eine Liste ist
        if isinstance(info, list):
            # Erstellen Sie eine Karte für jeden Planeten
            create_map(info)

    with open('map.png', 'rb') as f:
        picture = discord.File(f, filename='map.png')
    await ctx.followup.send(file=picture)

@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    add_server(conn, channel.id)
    await ctx.respond(f"Added Galactic War Status to channel {channel.mention}", ephemeral=True)
@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def remove_galactic_war_info(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    # Remove the channel ID from the database
    cursor = conn.cursor()
    cursor.execute('DELETE FROM servers WHERE channel_id = ?', (channel.id,))
    conn.commit()
    await ctx.respond(f"Removed Galactic War Status from channel {channel.mention}", ephemeral=True)

@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def set_announcement_channel(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    # Store the channel ID in the database
    cursor = conn.cursor()
    cursor.execute('INSERT INTO announcement_channels (channel_id) VALUES (?)', (channel.id,))
    conn.commit()
    await ctx.respond(f"Set {channel.mention} as the announcement channel", ephemeral=True)
@bot.slash_command()
@option(
    "channel",
    Union[discord.TextChannel],
    description="Select a channel",
)
async def remove_announcement_channel(ctx: discord.ApplicationContext, channel: Union[discord.TextChannel]):
    # Remove the channel ID from the database
    cursor = conn.cursor()
    cursor.execute('DELETE FROM announcement_channels WHERE channel_id = ?', (channel.id,))
    conn.commit()
    await ctx.respond(f"Removed {channel.mention} from the announcement channels", ephemeral=True)

bot.run(os.getenv('DISCORD_BOT_TOKEN'))
