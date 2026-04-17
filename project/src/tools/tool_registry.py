"""
Tool Registry: Central registry for all available tools.
The agent uses this to know what tools are available and how to call them.
"""

from src.tools.check_weather import check_weather
from src.tools.search_hotels import search_hotels
from src.tools.search_activities import search_activities


def get_tools():
    """
    Returns a list of tool definitions for the ReAct agent.
    Each tool has: name, description, function, parameters.
    
    The 'description' is CRITICAL — it's how the LLM understands what the tool does.
    """
    return [
        {
            "name": "check_weather",
            "description": (
                "Check weather forecast for a specific location and date. "
                "Takes two arguments: location (city name, e.g. 'Da Lat', 'Hanoi') "
                "and date (YYYY-MM-DD format, within 5 days from now). "
                "Returns weather condition (Clear/Rain/Clouds), temperature (°C), humidity, wind speed. "
                "IMPORTANT: The returned condition indicates if it will rain or not — "
                "use this to decide between outdoor vs indoor activities."
            ),
            "function": check_weather,
            "parameters": {
                "location": {"type": "string", "description": "City name (e.g., 'Da Lat', 'Hanoi')"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            }
        },
        {
            "name": "search_hotels",
            "description": (
                "Search for hotels in a location under a maximum price per night (in VND). "
                "Takes two arguments: location (city name, e.g. 'Da Lat') "
                "and max_price (number in VND, e.g. 500000 for 500k VND). "
                "Returns a list of hotels with name, price per night, and rating. "
                "Note: prices are in Vietnamese Dong (VND). 500k = 500000, 1 triệu = 1000000."
            ),
            "function": search_hotels,
            "parameters": {
                "location": {"type": "string", "description": "City name"},
                "max_price": {"type": "number", "description": "Max price in VND (e.g. 500000)"}
            }
        },
        {
            "name": "search_activities",
            "description": (
                "Search for recommended activities/places in a location based on weather condition. "
                "Takes two arguments: location (city name, e.g. 'Da Lat') "
                "and weather_condition (one of: 'Clear', 'Clouds', 'Rain', 'Drizzle', 'Thunderstorm'). "
                "If weather is Clear/Clouds → returns outdoor activities (hiking, parks, sightseeing). "
                "If weather is Rain/Drizzle/Thunderstorm → returns indoor activities (cafes, museums). "
                "IMPORTANT: Use the weather condition from check_weather tool as input."
            ),
            "function": search_activities,
            "parameters": {
                "location": {"type": "string", "description": "City name"},
                "weather_condition": {"type": "string", "description": "Weather condition from check_weather"}
            }
        }
    ]
