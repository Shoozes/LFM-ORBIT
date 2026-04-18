import httpx
import sys

def test_nasa():
    try:
        url = "https://api.nasa.gov/planetary/earth/imagery"
        for date_str in ["2024-04-17", "2025-04-17", "2026-04-14"]:
            params = {
                "lon": -60.025,
                "lat": -3.119,
                "date": date_str,
                "dim": 0.025,
                "api_key": "DEMO_KEY"
            }
            print(f"Fetching from NASA API for {date_str}...")
            resp = httpx.get(url, params=params, follow_redirects=True, timeout=20.0)
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Image length: {len(resp.content)} bytes")
            else:
                print(f"Error text: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_nasa()
