from discord.ext import commands, option
import matplotlib.pyplot as plt
from adjustText import adjust_text
import matplotlib.dates as mdates
from scipy.interpolate import interp1d
from Levenshtein import ratio
import sqlite3

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('servers.db')
        cursor = self.conn.cursor()


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
            ''', (planet, '-' + time_limit))
        else:
            cursor.execute('''
                SELECT timestamp, net_force
                FROM historical_data
                WHERE planet = ?
                ORDER BY timestamp DESC
            ''', (planet,))
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

    # Add other command-related functions here

def setup(bot):
    bot.add_cog(CommandsCog(bot))
