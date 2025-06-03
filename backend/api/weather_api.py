from dotenv import load_dotenv
import os
import requests
import json

class WeatherAPI:
    def __init__(self):
        """Initialize with OpenWeatherMap API credentials from .env file"""
        load_dotenv()
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        if not self.api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY not found in .env file")
        
        self.api_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather(self, city):
        """
        Fetch real-time weather data for a given city using OpenWeatherMap API.

        Args:
            city (str): City name (e.g., 'London,uk')

        Returns:
            dict: Formatted response with city, forecast, humidity, and wind
        """
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric"  # Celsius for temperature
        }

        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "city": data["name"],
                "forecast": f"{data['weather'][0]['description'].title()} with a high of {data['main']['temp_max']}°C ({int(data['main']['temp_max'] * 9/5 + 32)}°F).",
                "humidity": f"{data['main']['humidity']}%",
                "wind": f"{data['wind']['speed']} mph {self.deg_to_direction(data['wind']['deg'])}"
            }

        except Exception as e:
            print(f"Weather API Error: {str(e)}")
            return {
                "error": str(e),
                "city": city,
                "forecast": "Unable to fetch weather data.",
                "humidity": "N/A",
                "wind": "N/A"
            }

    def deg_to_direction(self, degrees):
        """Convert wind direction in degrees to cardinal direction."""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]