import os
import sys
import httpx

sys.path.insert(0, os.path.abspath('.'))
from core.config import resolve_nasa_credentials

def fetch_image():
    creds = resolve_nasa_credentials()
    if not creds.available:
        print("No NASA API key found.")
        return
        
    url = "https://api.nasa.gov/planetary/earth/imagery"
    params = {
        "lon": -60.025,
        "lat": -3.119,
        "date": "2024-01-01",
        "dim": 0.05,
        "api_key": creds.api_key
    }
    print(f"Fetching from {url}...")
    try:
        resp = httpx.get(url, params=params, timeout=30.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Success! Fetched {len(resp.content)} bytes.")
        else:
            print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_image()
