"""
gee_auth.py — GEE OAuth2 authorization using a local redirect server.

Opens a browser to Google's auth page. After the user authorizes, Google
redirects to http://localhost:8585/callback with an authorization code.
The script exchanges it for access + refresh tokens and caches them.

Run once:
    python scripts/gee_auth.py

After auth, the backend reads .tools/.secrets/gee_token.json automatically.
"""

import json
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

_SECRETS_DIR = Path(__file__).resolve().parents[3] / ".tools" / ".secrets"
_GEE_CREDS_FILE = _SECRETS_DIR / "gee.txt"
_TOKEN_CACHE = _SECRETS_DIR / "gee_token.json"

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_SCOPE = "https://www.googleapis.com/auth/earthengine.readonly"
_REDIRECT_URI = "http://localhost:8585/callback"
_PORT = 8585

_auth_code: str | None = None
_server_done = threading.Event()


def _load_credentials() -> tuple[str, str]:
    if not _GEE_CREDS_FILE.exists():
        print(f"[ERROR] Credentials file not found: {_GEE_CREDS_FILE}")
        sys.exit(1)
    lines = [l.strip() for l in _GEE_CREDS_FILE.read_text().splitlines() if l.strip()]
    if len(lines) < 2:
        print("[ERROR] gee.txt must have 2 lines: client_secret (line 1), client_id (line 2)")
        sys.exit(1)
    return lines[0], lines[1]  # client_secret, client_id


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            if "code" in params:
                _auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
<html><body style="font-family:monospace;background:#0d1117;color:#58a6ff;padding:40px">
<h2>GEE Authorization Complete</h2>
<p>You can close this window and return to the terminal.</p>
</body></html>""")
            else:
                error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Authorization failed: {error}".encode())
            _server_done.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return None


def _save_token(token_response: dict) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(seconds=token_response.get("expires_in", 3600))).isoformat()
    cache = {
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token", ""),
        "expires_at": expires,
    }
    _TOKEN_CACHE.write_text(json.dumps(cache, indent=2))
    print(f"\n[GEE AUTH] Token cached → {_TOKEN_CACHE}")


def _exchange_code(code: str, client_secret: str, client_id: str) -> dict:
    resp = httpx.post(_TOKEN_URL, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": _REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=15)
    if resp.status_code != 200:
        print(f"[ERROR] Token exchange failed: {resp.text}")
        sys.exit(1)
    return resp.json()


def _refresh_existing(client_secret: str, client_id: str) -> bool:
    """Try to refresh an existing cached token. Returns True on success."""
    if not _TOKEN_CACHE.exists():
        return False
    try:
        cached = json.loads(_TOKEN_CACHE.read_text())
        refresh_token = cached.get("refresh_token", "")
        if not refresh_token:
            return False
        print("[GEE AUTH] Trying to refresh existing token...")
        resp = httpx.post(_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            result["refresh_token"] = refresh_token  # preserve refresh token
            _save_token(result)
            print("[GEE AUTH] Existing token refreshed successfully.")
            return True
        print(f"[GEE AUTH] Refresh failed ({resp.status_code}), need new authorization.")
    except Exception as exc:
        print(f"[GEE AUTH] Refresh error: {exc}")
    return False


def main():
    client_secret, client_id = _load_credentials()
    print(f"[GEE AUTH] Client ID: {client_id[:46]}...")

    if _refresh_existing(client_secret, client_id):
        return

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{_AUTH_URL}?{urlencode(params)}"

    # Start local callback server
    server = HTTPServer(("localhost", _PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    print(f"\n[GEE AUTH] Opening browser to authorize GEE access...")
    print(f"  URL: {auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for callback (timeout 120s)
    got_code = _server_done.wait(timeout=120)
    server.server_close()

    if not got_code or _auth_code is None:
        print("[ERROR] Timed out waiting for authorization.")
        sys.exit(1)

    print("[GEE AUTH] Authorization code received. Exchanging for tokens...")
    token_response = _exchange_code(_auth_code, client_secret, client_id)
    _save_token(token_response)
    print("[GEE AUTH] Done. GEE provider is now active.\n")


if __name__ == "__main__":
    main()
