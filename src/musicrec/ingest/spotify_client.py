"""Thin wrapper over the Spotify Web API endpoints this project uses.

Deliberately narrow — only what's needed to pull a user's identity, recent
plays, and saved tracks. Audio features/analysis/recommendations endpoints
are not included: Spotify restricted those to apps with pre-existing
extended-quota access as of Nov 2024, so new apps can't rely on them.
"""

import time

import requests

from musicrec.ingest.spotify_auth import get_access_token

API_BASE = "https://api.spotify.com/v1"


class SpotifyClient:
    def _get(self, path: str, params: dict | None = None) -> dict:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        response = requests.get(
            url, headers={"Authorization": f"Bearer {get_access_token()}"}, params=params, timeout=30
        )
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After", 1)))
            return self._get(path, params)
        response.raise_for_status()
        return response.json()

    def current_user(self) -> dict:
        return self._get("/me")

    def recently_played(self, limit: int = 50) -> list[dict]:
        """Spotify caps this at the last 50 plays total — a snapshot, not
        full history. Run ingestion periodically to accumulate more over
        time (listening_events dedupes on (user, track, ts, action))."""
        return self._get("/me/player/recently-played", {"limit": limit})["items"]

    def saved_tracks(self, limit: int = 50) -> list[dict]:
        """Paginates through the user's full saved-tracks library."""
        items = []
        path, params = "/me/tracks", {"limit": limit}
        while path:
            data = self._get(path, params)
            items.extend(data["items"])
            path, params = data.get("next"), None
        return items
