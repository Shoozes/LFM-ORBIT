import os
import sys

# Add the project root to python path so we can import core modules
sys.path.insert(0, os.path.abspath('.'))

from core.config import resolve_nasa_credentials

def get_key():
    creds = resolve_nasa_credentials()
    if creds.available:
        print(f"Key found: {creds.api_key[:5]}...")
    else:
        print("No NASA API key found.")

if __name__ == "__main__":
    get_key()
