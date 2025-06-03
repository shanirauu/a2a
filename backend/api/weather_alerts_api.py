from dotenv import load_dotenv
import os
import requests
import json

class WeatherAlertsAPI:
    def __init__(self):
        """Initialize with OpenWeatherMap API credentials from .env file"""
        load_dotenv()
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        if not self.api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY not found in .env file")
        
        self.api_url = "https://api.openweathermap.org/data/3.0/onecall"

    def get_weather_alerts(self, city):
        """
        Fetch weather alerts for a given city using OpenWeatherMap One Call API.

        Args:
            city (str): City name (e.g., 'London,uk')

        Returns:
            dict: Formatted response with city and alerts
        """
        try:
            # Step 1: Get coordinates for the city
            geocoding_url = "http://api.openweathermap.org/geo/1.0/direct"
            geo_params = {
                "q": city,
                "appid": self.api_key,
                "limit": 1
            }
            geo_response = requests.get(geocoding_url, params=geo_params)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            if not geo_data:
                print(f"Weather Alerts API: No coordinates found for city='{city}'")
                return {
                    "city": city,
                    "alerts": "No weather alerts available for this city."
                }
            
            lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

            # Step 2: Fetch weather alerts
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "exclude": "current,minutely,hourly,daily"  # Only fetch alerts
            }
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"Weather Alerts API Response: {data}")  # Log for debugging

            alerts = data.get("alerts", [])
            if not alerts:
                return {
                    "city": city,
                    "alerts": "No active weather alerts for this city."
                }

            # Format the first alert (simplified for brevity)
            alert = alerts[0]
            return {
                "city": city,
                "alerts": f"Alert: {alert['event']} from {alert['sender_name']}. Description: {alert['description']}"
            }

        except requests.exceptions.HTTPError as http_err:
            print(f"Weather Alerts API HTTP Error: {http_err}, Response: {response.text}")
            return {
                "error": f"HTTP Error: {http_err}",
                "city": city,
                "alerts": "Unable to fetch weather alerts."
            }
        except Exception as e:
            print(f"Weather Alerts API General Error: {str(e)}")
            return {
                "error": str(e),
                "city": city,
                "alerts": "Unable to fetch weather alerts."
            }