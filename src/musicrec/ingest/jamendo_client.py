"""Thin wrapper over the Jamendo API (public, free-tier catalog + audio).

Get a free client_id at https://devportal.jamendo.com/ (instant, no OAuth
needed for these read-only catalog endpoints).
"""

import requests

from musicrec.config import JAMENDO_CLIENT_ID

API_BASE = "https://api.jamendo.com/v3.0"


class JamendoClient:
    def _get(self, path: str, params: dict) -> list[dict]:
        params = {**params, "client_id": JAMENDO_CLIENT_ID, "format": "json"}
        response = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()["results"]

    def tracks(self, limit: int = 50, offset: int = 0, tags: str | None = None) -> list[dict]:
        """Returns track metadata + a downloadable audio URL per track.
        `tags` filters by genre, e.g. "jazz" (comma-separated for multiple,
        per Jamendo's tag search syntax)."""
        params = {
            "limit": limit,
            "offset": offset,
            "audioformat": "mp32",
            "include": "musicinfo",
            "order": "popularity_total",
        }
        if tags:
            params["tags"] = tags
        return self._get("/tracks/", params)
