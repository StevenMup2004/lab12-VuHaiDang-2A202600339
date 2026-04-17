"""
Tool: search_activities
Uses SerpAPI Google Local Results to find activities based on weather.
If sunny → outdoor activities (hiking, sightseeing, parks)
If rainy → indoor activities (cafes, museums, galleries)

API: https://serpapi.com/google-local-api
Free tier: 100 searches/month
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"


def search_activities(location: str, weather_condition: str) -> str:
    """
    Search for activities in a location based on current weather conditions.
    
    Args:
        location: City name (e.g., "Da Lat", "Hanoi")
        weather_condition: Current weather — must be one of: "Clear", "Clouds", "Rain", "Drizzle", "Thunderstorm".
                          Use the condition returned by check_weather tool.
    
    Returns:
        String listing recommended activities based on weather.
        If weather is Clear/Clouds → outdoor activities (hiking, sightseeing, parks).
        If weather is Rain/Drizzle/Thunderstorm → indoor activities (cafes, museums, shopping).
    """
    is_rainy = weather_condition.lower() in ["rain", "drizzle", "thunderstorm", "mưa"]
    
    if is_rainy:
        query_type = "quán cafe đẹp, quán cà phê view đẹp, bảo tàng"
        activity_label = "indoor (rainy weather)"
    else:
        query_type = "địa điểm tham quan ngoài trời, hiking, công viên, điểm ngắm cảnh"
        activity_label = "outdoor (good weather)"
    
    if not SERPAPI_API_KEY or SERPAPI_API_KEY == "your_serpapi_api_key_here":
        return _fallback_activities(location, is_rainy)
    
    try:
        params = {
            "engine": "google_local",
            "q": f"{query_type} {location}",
            "api_key": SERPAPI_API_KEY,
            "hl": "vi",
            "gl": "vn",
            "num": 5
        }
        
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        places = data.get("local_results", [])
        
        if not places:
            return _fallback_activities(location, is_rainy)
        
        result = f"Recommended {activity_label} activities in {location}:\n"
        for i, place in enumerate(places[:5], 1):
            name = place.get("title", "Unknown")
            rating = place.get("rating", "N/A")
            address = place.get("address", "")
            place_type = place.get("type", "")
            
            result += f"  {i}. {name}"
            if rating != "N/A":
                result += f" — Rating: {rating}/5"
            if place_type:
                result += f" — Type: {place_type}"
            if address:
                result += f"\n     📍 {address}"
            result += "\n"
        
        return result.strip()
        
    except requests.exceptions.RequestException as e:
        return f"API Error: {str(e)}.\n" + _fallback_activities(location, is_rainy)
    except (KeyError, ValueError) as e:
        return f"Parse Error: {str(e)}.\n" + _fallback_activities(location, is_rainy)


def _fallback_activities(location: str, is_rainy: bool) -> str:
    """Fallback activity data when SerpAPI key is unavailable."""
    
    activities_db = {
        "da lat": {
            "outdoor": [
                {"name": "Đồi Chè Cầu Đất (Cau Dat Tea Hill)", "rating": 4.6, "type": "Scenic viewpoint", "desc": "Beautiful tea plantations with panoramic views"},
                {"name": "Thung Lũng Tình Yêu (Valley of Love)", "rating": 4.3, "type": "Park & Garden", "desc": "Iconic park with flower gardens and lake"},
                {"name": "Hồ Tuyền Lâm (Tuyen Lam Lake)", "rating": 4.7, "type": "Lake & Nature", "desc": "Serene lake with hiking trails and boating"},
                {"name": "Núi Langbiang (Langbiang Mountain)", "rating": 4.5, "type": "Hiking", "desc": "1,929m peak with breathtaking views of Dalat"},
                {"name": "Vườn Hoa Dalat (Dalat Flower Garden)", "rating": 4.2, "type": "Garden", "desc": "Colorful flower gardens near Xuan Huong Lake"},
            ],
            "indoor": [
                {"name": "Là Việt Coffee (La Viet Coffee)", "rating": 4.8, "type": "Specialty Coffee", "desc": "Best craft coffee in Dalat, industrial-chic atmosphere"},
                {"name": "The Married Beans Coffee", "rating": 4.6, "type": "Cafe & Views", "desc": "Cozy cafe with stunning valley views"},
                {"name": "Cafe Túi Mơ To", "rating": 4.5, "type": "Vintage Cafe", "desc": "Retro-themed cafe with unique decor"},
                {"name": "Bảo tàng Lâm Đồng (Lam Dong Museum)", "rating": 4.1, "type": "Museum", "desc": "Local history and Central Highlands culture"},
                {"name": "Crazy House (Biệt thự Hằng Nga)", "rating": 4.4, "type": "Architecture", "desc": "Quirky treehouse architecture by Dang Viet Nga"},
            ]
        },
        "hanoi": {
            "outdoor": [
                {"name": "Hồ Hoàn Kiếm (Hoan Kiem Lake)", "rating": 4.7, "type": "Lake & Heritage", "desc": "Iconic lake in the heart of Old Quarter"},
                {"name": "Hoàng Thành Thăng Long (Imperial Citadel)", "rating": 4.5, "type": "Heritage Site", "desc": "UNESCO World Heritage site"},
                {"name": "Hồ Tây (West Lake)", "rating": 4.4, "type": "Lake & Walking", "desc": "Largest lake, great for cycling and walking"},
            ],
            "indoor": [
                {"name": "Cộng Cà Phê (Cong Caphe)", "rating": 4.5, "type": "Themed Cafe", "desc": "Iconic Vietnamese communist-themed cafe"},
                {"name": "Bảo tàng Mỹ thuật (Fine Arts Museum)", "rating": 4.3, "type": "Art Museum", "desc": "Vietnamese art across centuries"},
                {"name": "Egg Coffee at Giang Cafe", "rating": 4.7, "type": "Historic Cafe", "desc": "Birthplace of famous egg coffee"},
            ]
        },
        "ho chi minh": {
            "outdoor": [
                {"name": "Bến Nhà Rồng (Dragon Wharf)", "rating": 4.3, "type": "Historic Site", "desc": "Historical landmark by Saigon River"},
                {"name": "Công viên Tao Đàn (Tao Dan Park)", "rating": 4.2, "type": "Park", "desc": "Lush park in the city center"},
            ],
            "indoor": [
                {"name": "The Workshop Coffee", "rating": 4.6, "type": "Specialty Coffee", "desc": "Top-rated specialty coffee in Saigon"},
                {"name": "Bảo tàng Chứng tích Chiến tranh", "rating": 4.5, "type": "Museum", "desc": "War Remnants Museum"},
            ]
        }
    }
    
    location_key = location.lower().strip()
    matched = None
    for key in activities_db:
        if key in location_key or location_key in key or location_key.replace(" ", "") in key.replace(" ", ""):
            matched = activities_db[key]
            break
    
    if matched is None:
        if is_rainy:
            return (
                f"[SIMULATED] Recommended indoor activities in {location} (rainy weather):\n"
                f"  1. Local cafe with views — Rating: 4.3/5\n"
                f"  2. City museum — Rating: 4.0/5\n"
                f"  3. Indoor shopping mall — Rating: 4.1/5"
            )
        else:
            return (
                f"[SIMULATED] Recommended outdoor activities in {location} (good weather):\n"
                f"  1. City walking tour — Rating: 4.4/5\n"
                f"  2. Local park — Rating: 4.2/5\n"
                f"  3. Scenic viewpoint — Rating: 4.5/5"
            )
    
    category = "indoor" if is_rainy else "outdoor"
    activities = matched[category]
    weather_label = "rainy weather — indoor activities" if is_rainy else "good weather — outdoor activities"
    
    result = f"[SIMULATED] Recommended activities in {location} ({weather_label}):\n"
    for i, act in enumerate(activities, 1):
        result += f"  {i}. {act['name']} — Rating: {act['rating']}/5 — Type: {act['type']}\n"
        result += f"     📍 {act['desc']}\n"
    
    return result.strip()
