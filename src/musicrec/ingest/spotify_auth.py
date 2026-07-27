"""Spotify OAuth: Authorization Code + PKCE flow.

PKCE means no client secret is needed (safe for a local script). First call
to get_access_token() opens a browser for one-time login and spins up a
short-lived local HTTP server to catch the redirect; the resulting tokens
are cached on disk and silently refreshed on subsequent calls.

Setup: create an app at https://developer.spotify.com/dashboard, add
`http://127.0.0.1:8080/callback` as a Redirect URI (must match exactly —
Spotify requires 127.0.0.1, not localhost), then set SPOTIFY_CLIENT_ID.
"""

import base64
import hashlib
import http.server
import json
import secrets
import time
import urllib.parse
import webbrowser

import requests

from musicrec.config import SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT_URI, SPOTIFY_TOKEN_CACHE_PATH

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = "user-read-recently-played user-library-read user-read-email"


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.auth_code = params.get("code", [None])[0]
        self.server.auth_error = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Spotify login complete, you can close this tab.")

    def log_message(self, *args):
        pass  # silence default request logging to stdout


def _run_authorization_flow() -> dict:
    if not SPOTIFY_CLIENT_ID:
        raise RuntimeError("SPOTIFY_CLIENT_ID is not set (see spotify_auth.py docstring for setup)")

    verifier, challenge = _generate_pkce_pair()

    redirect = urllib.parse.urlparse(SPOTIFY_REDIRECT_URI)
    server = http.server.HTTPServer((redirect.hostname, redirect.port), _CallbackHandler)
    server.auth_code = None
    server.auth_error = None

    query = urllib.parse.urlencode(
        {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    webbrowser.open(f"{AUTH_URL}?{query}")
    print("Opening browser for Spotify login... waiting for redirect callback.")
    server.handle_request()  # blocks until the OAuth redirect hits this server

    if server.auth_error:
        raise RuntimeError(f"Spotify authorization failed: {server.auth_error}")

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": server.auth_code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _refresh_tokens(refresh_token: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": SPOTIFY_CLIENT_ID,
        },
        timeout=30,
    )
    response.raise_for_status()
    tokens = response.json()
    tokens.setdefault("refresh_token", refresh_token)  # Spotify may omit it on refresh
    return tokens


def _load_cached_tokens() -> dict | None:
    if SPOTIFY_TOKEN_CACHE_PATH.exists():
        return json.loads(SPOTIFY_TOKEN_CACHE_PATH.read_text())
    return None


def _save_tokens(tokens: dict) -> None:
    tokens["obtained_at"] = time.time()
    SPOTIFY_TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPOTIFY_TOKEN_CACHE_PATH.write_text(json.dumps(tokens))


def get_access_token() -> str:
    tokens = _load_cached_tokens()

    if tokens is None:
        tokens = _run_authorization_flow()
        _save_tokens(tokens)
        return tokens["access_token"]

    expires_at = tokens["obtained_at"] + tokens["expires_in"]
    if time.time() < expires_at - 60:  # 60s safety margin
        return tokens["access_token"]

    tokens = _refresh_tokens(tokens["refresh_token"])
    _save_tokens(tokens)
    return tokens["access_token"]
