from discord.ext import commands
import sqlite3

class DatabaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('servers.db')

    def delete_old_data(conn):
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM historical_data
            WHERE timestamp < datetime('now', '-1 hour')
        ''')
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


def setup(bot):
    bot.add_cog(DatabaseCog(bot))
