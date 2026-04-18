import os
import sys
import httpx

def test_wms():
    # BBOX for Rondonia: -10.05, -63.05, -9.95, -62.95 (S, W, N, E) for EPSG:4326
    s, w, n, e = -10.05, -63.05, -9.95, -62.95
    url = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "LAYERS": "MODIS_Terra_CorrectedReflectance_TrueColor",
        "VERSION": "1.3.0",
        "FORMAT": "image/jpeg",
        "CRS": "EPSG:4326",
        "BBOX": f"{s},{w},{n},{e}",
        "WIDTH": 640,
        "HEIGHT": 480,
        "TIME": "2023-08-01"
    }

    print("Fetching from NASA GIBS WMS...")
    resp = httpx.get(url, params=params, timeout=20.0, follow_redirects=True)
    if resp.status_code == 200 and "image/jpeg" in resp.headers.get("content-type", ""):
        print(f"Success! Fetched {len(resp.content)} bytes.")
    else:
        print(f"Fail! Status {resp.status_code}. Output: {resp.text[:100]}")

if __name__ == "__main__":
    test_wms()
