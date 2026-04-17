"""
Tool: check_weather
Uses OpenWeatherMap API to check weather forecast for a location and date.
Returns: weather condition (Rain/Clear/Clouds), temperature, humidity.

API: https://api.openweathermap.org/data/2.5/forecast
Free tier: 1,000 calls/day
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


def check_weather(location: str, date: str) -> str:
    """
    Check weather forecast for a specific location and date.
    
    Args:
        location: City name (e.g., "Da Lat", "Hanoi", "Ho Chi Minh City")
        date: Date string in format "YYYY-MM-DD" (must be within 5 days from now)
    
    Returns:
        String with weather info: condition, temperature (°C), humidity (%), wind speed, and description.
        Example: "Weather in Da Lat on 2026-04-12: Clear sky, Temperature: 22°C, Humidity: 65%, Wind: 3.5 m/s"
    """
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "your_openweather_api_key_here":
        return _fallback_weather(location, date)
    
    try:
        # Call OpenWeatherMap Forecast API
        params = {
            "q": location,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",  # Celsius
            "cnt": 40  # Max forecast entries (5 days, every 3 hours)
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Find the forecast closest to the requested date
        target_date = datetime.strptime(date, "%Y-%m-%d")
        target_noon = target_date.replace(hour=12, minute=0, second=0)
        
        best_forecast = None
        min_diff = float("inf")
        
        for entry in data["list"]:
            forecast_time = datetime.fromtimestamp(entry["dt"])
            diff = abs((forecast_time - target_noon).total_seconds())
            if diff < min_diff:
                min_diff = diff
                best_forecast = entry
        
        if best_forecast is None:
            return f"No forecast data available for {location} on {date}. The forecast API covers only 5 days ahead."
        
        # Extract weather info
        condition = best_forecast["weather"][0]["main"]  # Rain, Clear, Clouds, etc.
        description = best_forecast["weather"][0]["description"]
        temp = best_forecast["main"]["temp"]
        humidity = best_forecast["main"]["humidity"]
        wind_speed = best_forecast["wind"]["speed"]
        
        result = (
            f"Weather in {location} on {date}: {condition} ({description}), "
            f"Temperature: {temp}°C, Humidity: {humidity}%, Wind: {wind_speed} m/s"
        )
        
        # Add rain warning if applicable
        if condition.lower() in ["rain", "drizzle", "thunderstorm"]:
            rain_amount = best_forecast.get("rain", {}).get("3h", 0)
            result += f", Rainfall: {rain_amount}mm/3h. It WILL rain — recommend indoor activities."
        else:
            result += ". No rain expected — great for outdoor activities!"
        
        return result
        
    except requests.exceptions.RequestException as e:
        return f"API Error: Could not fetch weather for {location}. Error: {str(e)}. Using fallback data."
    except (KeyError, ValueError) as e:
        return f"Parse Error: Could not parse weather data. Error: {str(e)}. Using fallback data."


def _fallback_weather(location: str, date: str) -> str:
    """
    Fallback weather data when API key is not available.
    Uses realistic simulated data for Vietnamese cities.
    """
    # Simulated weather data for common Vietnamese destinations
    weather_data = {
        "da lat": {
            "condition": "Clear",
            "description": "clear sky", 
            "temp": 22,
            "humidity": 65,
            "wind": 3.2,
            "rain": False
        },
        "dalat": {
            "condition": "Clear",
            "description": "clear sky",
            "temp": 22,
            "humidity": 65,
            "wind": 3.2,
            "rain": False
        },
        "hanoi": {
            "condition": "Clouds",
            "description": "overcast clouds",
            "temp": 28,
            "humidity": 75,
            "wind": 4.1,
            "rain": False
        },
        "ho chi minh": {
            "condition": "Rain",
            "description": "light rain",
            "temp": 32,
            "humidity": 85,
            "wind": 5.0,
            "rain": True
        },
        "hcm": {
            "condition": "Rain",
            "description": "light rain",
            "temp": 32,
            "humidity": 85,
            "wind": 5.0,
            "rain": True
        },
        "nha trang": {
            "condition": "Clear",
            "description": "sunny",
            "temp": 30,
            "humidity": 70,
            "wind": 6.0,
            "rain": False
        },
        "phu quoc": {
            "condition": "Clear",
            "description": "sunny",
            "temp": 31,
            "humidity": 72,
            "wind": 5.5,
            "rain": False
        },
        "hue": {
            "condition": "Rain",
            "description": "moderate rain",
            "temp": 26,
            "humidity": 88,
            "wind": 7.0,
            "rain": True
        },
        "sapa": {
            "condition": "Clouds",
            "description": "misty clouds",
            "temp": 15,
            "humidity": 90,
            "wind": 2.5,
            "rain": False
        }
    }
    
    location_key = location.lower().strip()
    # Try partial match
    matched = None
    for key in weather_data:
        if key in location_key or location_key in key:
            matched = weather_data[key]
            break
    
    if matched is None:
        # Default to nice weather
        matched = {
            "condition": "Clear",
            "description": "partly cloudy",
            "temp": 27,
            "humidity": 70,
            "wind": 3.0,
            "rain": False
        }
    
    result = (
        f"[SIMULATED] Weather in {location} on {date}: {matched['condition']} ({matched['description']}), "
        f"Temperature: {matched['temp']}°C, Humidity: {matched['humidity']}%, Wind: {matched['wind']} m/s"
    )
    
    if matched["rain"]:
        result += ". It WILL rain — recommend indoor activities."
    else:
        result += ". No rain expected — great for outdoor activities!"
    
    return result
