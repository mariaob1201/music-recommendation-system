"""Ingest a connected Spotify user's recently-played + saved tracks into
listening_events, upserting artist/album/track rows keyed by Spotify ID
along the way (no audio embeddings — Spotify doesn't provide audio; pair
this with ingest_tracks.py against a separate catalog for that).

Run directly:

    python -m musicrec.ingest.spotify_ingest

First run opens a browser for Spotify login (see spotify_auth.py for
one-time setup); safe to re-run afterward — everything upserts on
Spotify/track IDs and listening_events dedupes on (user, track, ts, action).
"""

import datetime

from musicrec.db import get_connection
from musicrec.ingest.spotify_client import SpotifyClient


def _parse_ts(iso_ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))


def _get_or_create_user(cur, sp_user: dict) -> int:
    cur.execute("SELECT id FROM users WHERE spotify_id = %s", (sp_user["id"],))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO users (email, spotify_id) VALUES (%s, %s) RETURNING id",
        (sp_user.get("email"), sp_user["id"]),
    )
    return cur.fetchone()[0]


def _get_or_create_artist(cur, sp_artist: dict) -> int:
    cur.execute("SELECT id FROM artists WHERE spotify_id = %s", (sp_artist["id"],))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO artists (name, spotify_id) VALUES (%s, %s) RETURNING id",
        (sp_artist["name"], sp_artist["id"]),
    )
    return cur.fetchone()[0]


def _get_or_create_album(cur, artist_id: int, sp_album: dict | None) -> int | None:
    if not sp_album:
        return None
    cur.execute(
        "SELECT id FROM albums WHERE artist_id = %s AND title = %s",
        (artist_id, sp_album["name"]),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO albums (artist_id, title, release_date) VALUES (%s, %s, %s) RETURNING id",
        (artist_id, sp_album["name"], sp_album.get("release_date") or None),
    )
    return cur.fetchone()[0]


def _upsert_track(cur, sp_track: dict) -> int:
    cur.execute("SELECT id FROM tracks WHERE spotify_id = %s", (sp_track["id"],))
    row = cur.fetchone()
    if row:
        return row[0]

    artist_id = _get_or_create_artist(cur, sp_track["artists"][0])
    album_id = _get_or_create_album(cur, artist_id, sp_track.get("album"))

    cur.execute(
        """
        INSERT INTO tracks (album_id, artist_id, title, duration_ms, explicit, spotify_id, isrc)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            album_id,
            artist_id,
            sp_track["name"],
            sp_track.get("duration_ms"),
            sp_track.get("explicit", False),
            sp_track["id"],
            sp_track.get("external_ids", {}).get("isrc"),
        ),
    )
    return cur.fetchone()[0]


def _record_event(cur, user_id: int, track_id: int, ts: datetime.datetime, action: str) -> None:
    cur.execute(
        """
        INSERT INTO listening_events (user_id, track_id, ts, action)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, track_id, ts, action) DO NOTHING
        """,
        (user_id, track_id, ts, action),
    )


def ingest_spotify_history(sp: SpotifyClient) -> int:
    """Returns the internal user_id the ingested events were attributed to."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            user_id = _get_or_create_user(cur, sp.current_user())

            for item in sp.recently_played():
                track_id = _upsert_track(cur, item["track"])
                _record_event(cur, user_id, track_id, _parse_ts(item["played_at"]), "play")

            for item in sp.saved_tracks():
                track_id = _upsert_track(cur, item["track"])
                _record_event(cur, user_id, track_id, _parse_ts(item["added_at"]), "save")

        conn.commit()

    return user_id


if __name__ == "__main__":
    ingested_user_id = ingest_spotify_history(SpotifyClient())
    print(f"Ingested Spotify history for internal user_id={ingested_user_id}")
