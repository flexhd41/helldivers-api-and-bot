# cogs/database_manager.py

import sqlite3
from discord.ext import commands

class DatabaseManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = self.setup_db()

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

    def cleanup(conn, bot):
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

    def delete_old_data(conn):
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM historical_data
            WHERE timestamp < datetime('now', '-1 hour')
        ''')
        conn.commit()

def setup(bot):
    bot.add_cog(DatabaseManager(bot))