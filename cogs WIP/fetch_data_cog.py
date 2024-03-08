from discord.ext import commands, tasks
import requests
import datetime

class FetchDataCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    latest_data = None
    net_force_cleaned = None

    @tasks.loop(seconds=30)
    async def fetch_hell_divers_info():
        global latest_data
        
        latest_data = requests.get('http://82.165.212.88:3000/activePlanets').json()
        await bot.wait_until_ready()
        #delete_old_data(conn)
        for item in latest_data:
            if item['liberation'] is not None:
                global net_force_cleaned
                net_force_cleaned = item['liberation'].replace('%', '')
                cursor = conn.cursor()
                cursor.execute('INSERT INTO historical_data (planet, net_force) VALUES (?, ?)', (item['planet'], net_force_cleaned))
                conn.commit()
            else:
                print(f"Skipping insertion for planet {item['planet']} due to missing 'net_force' value.")
            # Determine the color and emoji based on the status
        
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


def setup(bot):
    bot.add_cog(FetchDataCog(bot))
