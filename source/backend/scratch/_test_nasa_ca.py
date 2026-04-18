import os
import sys
import httpx

sys.path.insert(0, os.path.abspath('.'))
from core.config import resolve_nasa_credentials

def fetch_cali():
    creds = resolve_nasa_credentials()
    url = "https://api.nasa.gov/planetary/earth/imagery"
    params = {
        "lon": -122.0,
        "lat": 37.0,
        "date": "2024-01-01",
        "dim": 0.015,
        "api_key": creds.api_key if creds.available else "DEMO_KEY"
    }
    print(f"Testing optimal conditions (CA, dim=0.015)")
    try:
        resp = httpx.get(url, params=params, timeout=30.0)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Success!")
    except Exception as e:
        print(f"Timeout/Error: {e}")

if __name__ == "__main__":
    fetch_cali()
