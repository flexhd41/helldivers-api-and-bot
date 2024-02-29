from flask import Flask, jsonify
import requests
import threading
import time
from flask_apscheduler import APScheduler
import math

api = Flask(__name__)
scheduler = APScheduler()
scheduler.init_app(api)
scheduler.start()

# Global variable to store the planet liberation percentages and previous percentages
planet_liberation_percentages = []

from datetime import datetime

# Update the global variables to store the timestamps
previous_percentages = {}
previous_timestamps = {}

def update_liberation_percentages():
    global planet_liberation_percentages, previous_percentages, previous_timestamps
    # Fetch the data from the provided API
    response = requests.get('https://helldivers-2.fly.dev/api/801/status')
        
    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
            
        # Extract the planet status information
        planet_statuses = data.get('planet_status', [])
            
        # Initialize an empty list to store the planet names and their liberation percentages
        updated_percentages = []
            
        # Iterate through the planet statuses and extract the names and liberation percentages
        for status in planet_statuses:
            planet_name = status['planet']['name']
            # Skip planets with no name
            if not planet_name:
                continue
                
            # Calculate liberation percentage based on health
            current_health = status['health']
            initial_health = status['planet']['max_health']
            corrected_percentage = 100 - ((current_health / initial_health) * 100)
                
            # Skip planets with a liberation percentage of 0
            if corrected_percentage == 0:
               continue
                
            # Calculate the percentage change per hour
            now = datetime.now()
            if planet_name in previous_percentages:
                time_diff = now - previous_timestamps[planet_name]
                hours_passed = time_diff.total_seconds() / 3600
                percentage_change_per_hour = (corrected_percentage - previous_percentages[planet_name]) / hours_passed
            else:
                percentage_change_per_hour = "N/A"
                
            # Update the previous percentage and timestamp for the current planet
            previous_percentages[planet_name] = corrected_percentage
            previous_timestamps[planet_name] = now
                
            # Get the number of players and the regeneration rate
            players = status['players']
            regen_per_second = status['regen_per_second']
                
            updated_percentages.append({
                'planet': planet_name,
                'liberation_percentage': corrected_percentage,
                'percentage_change_per_hour': percentage_change_per_hour,
                'players': players,
                'regen_per_second': regen_per_second
            })
                
        # Update the global variable with the new percentages
        planet_liberation_percentages = updated_percentages


        

@api.route('/liberation', methods=['GET'])
def get_liberation_percentage():
    return jsonify({'planets_liberation_percentages': planet_liberation_percentages})

if __name__ == '__main__':
    # Start the background thread to update the liberation percentages
    scheduler.add_job(id='update_liberation_percentages', func=update_liberation_percentages, trigger='interval', seconds=35)

    api.run(debug=True)
