# cogs/data_fetcher.py

import discord
from discord import option
from discord.ext import commands, tasks
import requests
import datetime
import sqlite3
from typing import Union
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from cogs.database_manager import *
import matplotlib.dates as mdates
from scipy.interpolate import interp1d
from Levenshtein import ratio

load_dotenv()

class DataFetcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.latest_data = None
        self.net_force_cleaned = None
    def store_message_id(conn, channel_id, message_id):
        cursor = conn.cursor()
        cursor.execute('UPDATE servers SET message_id = ? WHERE channel = ?', (message_id, channel_id))
        conn.commit()
    def create_embed1(data):
        embed = discord.Embed(title="Galactic War Status", description="Current status of planets", color=0x00ff00)
        embed.timestamp = datetime.utcnow()

        for item in data:
            planet_name = "⚔️" + item['name']
            liberation_percentage = round(float(item['liberation'].replace('%', '')))  # Remove the '%' and convert to float, then round to int
            reds = '🟥' * (liberation_percentage // 10 if liberation_percentage < 50 else 5)
            oranges = '🟧' * ((liberation_percentage - 50) // 10 if 50 <= liberation_percentage < 75 else 0)
            yellows = '🟨' * ((liberation_percentage - 75) // 10 if 75 <= liberation_percentage < 90 else 0)
            greens = '🟩' * ((liberation_percentage - 90) // 10 if liberation_percentage >= 90 else 0)
            blacks = '⬛' * (10 - len(reds + oranges + yellows + greens))  # Add black squares for the empty percentages
            liberation = f"{reds}{oranges}{yellows}{greens}{blacks}{liberation_percentage}%/100%"  # Add the percentage to the health bar
            value = f"Liberation: {liberation}\nPlayers: {item['players']}\nInitial Owner: {item['initialOwner']}\nRegen per hour percent: {item['regen_per_hour_percent']}\nRegen per hour HP: {item['regen_per_hour_hp']}"#\nEstimated Outcome: {item.get('estimatedOutcome', 'N/A')}\nEstimated Time: {item.get('estimatedTime', 'N/A')}
            embed.add_field(name=planet_name, value=value, inline=False)

        return embed

    @tasks.loop(seconds=30)
    async def fetch_hell_divers_info(bot, conn):
        global latest_data
        
        latest_data = requests.get('http://dev.nexusrealms.de:25567/api/planet-data').json()
        await bot.wait_until_ready()
        cleanup()
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
    async def update_announcements(bot, conn):
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
    async def update_hell_divers_info(bot, conn, self):
        cleanup()
        await bot.wait_until_ready()
        
        # Fetch the latest Hell Divers data
        data = latest_data  # Use the data directly

        # Get the channels to update
        channels_to_update = get_channels_to_update(conn)  # Pass the connection object

        for channel_id, message_id in channels_to_update:
            channel = bot.get_channel(int(channel_id))
            if message_id:
                # Edit the existing message
                message = await channel.fetch_message(message_id)
                embed = self.create_embed1(data)
                await message.edit(embed=embed)
            else:
                # Send a new message and store its ID
                embed = self.create_embed1(data)
                message = await channel.send(embed=embed)
                # Store the new message ID for future updates
                self.store_message_id(conn, channel_id, message.id)  # Pass the connection object

    

    @commands.slash_command()
    async def send_data(ctx):
        response = requests.get('http://82.165.212.88:3000/activePlanets')
        data = response.json()

        embed = discord.Embed(title="Hell Divers Data", description="Current status", color=0x00ff00)
        for item in data:
            embed.add_field(name=item['defending'], value=f"Liberation: {item['percentage']}\nPlayers: {item['count']}\nStatus: {item['status']}", inline=False)

        await ctx.respond(embed=embed)

    @commands.slash_command()
    @option(
        "planet",
        description="Select a planet"
    )
    @option(
        "time_range",
        description="Select a time range",
        choices=["1h", "12h", "1d", "all"]
    )
    async def send_graph(ctx, planet: str, time_range: str, conn):
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

def setup(bot):
    bot.add_cog(DataFetcher(bot))