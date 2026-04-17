"""
Tool: search_hotels
Uses SerpAPI Google Hotels to find hotels under a specified price.
Returns: list of hotels with name, price, rating.

API: https://serpapi.com/google-hotels-api
Free tier: 100 searches/month
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_URL = "https://serpapi.com/search.json"


def search_hotels(location: str, max_price: float) -> str:
    """
    Search for hotels in a location under a maximum price per night.
    
    Args:
        location: City/area name (e.g., "Da Lat", "Hanoi")
        max_price: Maximum price per night in VND (e.g., 500000 for 500k VND).
                   Common values: 300000 (300k), 500000 (500k), 1000000 (1 triệu).

    Returns:
        String listing hotels with name, price per night, and rating.
        Example: "Found 3 hotels in Da Lat under 500,000 VND:\n1. Hotel ABC - 450,000 VND/night - Rating: 4.5/5\n..."
    """
    if not SERPAPI_API_KEY or SERPAPI_API_KEY == "your_serpapi_api_key_here":
        return _fallback_hotels(location, max_price)
    
    try:
        params = {
            "engine": "google_hotels",
            "q": f"hotels in {location}",
            "check_in_date": _get_next_saturday(),
            "check_out_date": _get_next_sunday(),
            "currency": "VND",
            "api_key": SERPAPI_API_KEY,
            "hl": "vi",  # Vietnamese language
            "gl": "vn"   # Vietnam region
        }
        
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        hotels = []
        properties = data.get("properties", [])
        
        for hotel in properties:
            price = hotel.get("total_rate", {}).get("lowest")
            if price is None:
                price = hotel.get("rate_per_night", {}).get("lowest")
            
            if price is None:
                continue
                
            # Extract numeric price
            price_str = str(price).replace(",", "").replace("₫", "").replace("VND", "").strip()
            try:
                price_num = float(price_str)
            except ValueError:
                continue
            
            if price_num <= max_price:
                name = hotel.get("name", "Unknown Hotel")
                rating = hotel.get("overall_rating", "N/A")
                hotels.append({
                    "name": name,
                    "price": price_num,
                    "rating": rating
                })
        
        if not hotels:
            return f"No hotels found in {location} under {max_price:,.0f} VND. Try increasing your budget."
        
        # Sort by price
        hotels.sort(key=lambda x: x["price"])
        
        result = f"Found {len(hotels)} hotel(s) in {location} under {max_price:,.0f} VND/night:\n"
        for i, h in enumerate(hotels[:5], 1):  # Top 5
            result += f"  {i}. {h['name']} — {h['price']:,.0f} VND/night — Rating: {h['rating']}/5\n"
        
        return result.strip()
        
    except requests.exceptions.RequestException as e:
        return f"API Error: {str(e)}. Using fallback data.\n" + _fallback_hotels(location, max_price)
    except (KeyError, ValueError) as e:
        return f"Parse Error: {str(e)}. Using fallback data.\n" + _fallback_hotels(location, max_price)


def _get_next_saturday():
    """Get next Saturday date string."""
    from datetime import datetime, timedelta
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    next_sat = today + timedelta(days=days_until_saturday)
    return next_sat.strftime("%Y-%m-%d")


def _get_next_sunday():
    """Get next Sunday date string."""
    from datetime import datetime, timedelta
    today = datetime.now()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sun = today + timedelta(days=days_until_sunday)
    return next_sun.strftime("%Y-%m-%d")


def _fallback_hotels(location: str, max_price: float) -> str:
    """Fallback hotel data when SerpAPI key is not available."""
    
    hotel_database = {
        "da lat": [
            {"name": "Dreams Hotel Dalat", "price": 350000, "rating": 4.5},
            {"name": "Dalat Cozy Nook Homestay", "price": 280000, "rating": 4.3},
            {"name": "Villa Vista Dalat", "price": 480000, "rating": 4.7},
            {"name": "Zen Valley Dalat Resort", "price": 650000, "rating": 4.8},
            {"name": "Dalat De Charme Hotel", "price": 420000, "rating": 4.4},
            {"name": "Ana Mandara Villas Dalat", "price": 1200000, "rating": 4.9},
            {"name": "Dalat Palace Heritage Hotel", "price": 900000, "rating": 4.6},
            {"name": "Tulip Hotel Dalat", "price": 300000, "rating": 4.2},
        ],
        "hanoi": [
            {"name": "Hanoi La Siesta Hotel", "price": 550000, "rating": 4.6},
            {"name": "Old Quarter View Hotel", "price": 380000, "rating": 4.2},
            {"name": "Hanoi Backpacker Hostel", "price": 150000, "rating": 4.0},
            {"name": "Silk Path Hotel Hanoi", "price": 750000, "rating": 4.5},
        ],
        "ho chi minh": [
            {"name": "Liberty Central Saigon", "price": 600000, "rating": 4.4},
            {"name": "Saigon Budget Inn", "price": 250000, "rating": 3.9},
            {"name": "A25 Hotel Saigon", "price": 350000, "rating": 4.1},
        ],
        "nha trang": [
            {"name": "Nha Trang Beach Hotel", "price": 450000, "rating": 4.3},
            {"name": "Seaside Homestay", "price": 300000, "rating": 4.1},
            {"name": "Galina Hotel Nha Trang", "price": 500000, "rating": 4.5},
        ]
    }
    
    location_key = location.lower().strip()
    matched_hotels = None
    for key in hotel_database:
        if key in location_key or location_key in key or location_key.replace(" ", "") in key.replace(" ", ""):
            matched_hotels = hotel_database[key]
            break
    
    if matched_hotels is None:
        matched_hotels = [
            {"name": f"{location} Central Hotel", "price": 400000, "rating": 4.2},
            {"name": f"{location} Budget Stay", "price": 250000, "rating": 3.8},
        ]
    
    # Filter by max_price
    filtered = [h for h in matched_hotels if h["price"] <= max_price]
    filtered.sort(key=lambda x: x["price"])
    
    if not filtered:
        return f"[SIMULATED] No hotels found in {location} under {max_price:,.0f} VND/night. Try increasing your budget."
    
    result = f"[SIMULATED] Found {len(filtered)} hotel(s) in {location} under {max_price:,.0f} VND/night:\n"
    for i, h in enumerate(filtered[:5], 1):
        result += f"  {i}. {h['name']} — {h['price']:,.0f} VND/night — Rating: {h['rating']}/5\n"
    
    return result.strip()
