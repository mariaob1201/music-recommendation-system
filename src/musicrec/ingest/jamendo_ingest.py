"""Bulk-ingest a slice of the Jamendo catalog: metadata + a real CLAP audio
embedding per track, so candidate_gen.py has content to search against.
Unlike spotify_ingest.py (history only, no audio access), this is the
piece that actually populates track_embeddings.

Requires the `audio` optional dependency group (torch + laion-clap), since
this downloads real audio and embeds it.

Run directly:

    python -m musicrec.ingest.jamendo_ingest --limit 200 --tags jazz

Safe to re-run: artists/albums/tracks upsert on jamendo_id, and embedding
computation is skipped for tracks that already have one.
"""

import argparse
import tempfile

import requests

from musicrec.config import CLAP_MODEL_VERSION, SOURCE_CLAP_AUDIO
from musicrec.db import get_connection
from musicrec.ingest.jamendo_client import JamendoClient


def _get_or_create_artist(cur, jamendo_artist_id: str, name: str) -> int:
    cur.execute("SELECT id FROM artists WHERE jamendo_id = %s", (jamendo_artist_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO artists (name, jamendo_id) VALUES (%s, %s) RETURNING id",
        (name, jamendo_artist_id),
    )
    return cur.fetchone()[0]


def _get_or_create_album(
    cur, artist_id: int, jamendo_album_id: str | None, title: str | None
) -> int | None:
    if not jamendo_album_id:
        return None
    cur.execute("SELECT id FROM albums WHERE jamendo_id = %s", (jamendo_album_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO albums (artist_id, title, jamendo_id) VALUES (%s, %s, %s) RETURNING id",
        (artist_id, title, jamendo_album_id),
    )
    return cur.fetchone()[0]


def _upsert_track(cur, track: dict) -> int:
    cur.execute("SELECT id FROM tracks WHERE jamendo_id = %s", (track["id"],))
    row = cur.fetchone()
    if row:
        return row[0]

    artist_id = _get_or_create_artist(cur, track["artist_id"], track["artist_name"])
    album_id = _get_or_create_album(cur, artist_id, track.get("album_id"), track.get("album_name"))
    genres = track.get("musicinfo", {}).get("tags", {}).get("genres", [])

    cur.execute(
        """
        INSERT INTO tracks (album_id, artist_id, title, duration_ms, language, genre, jamendo_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            album_id,
            artist_id,
            track["name"],
            int(track["duration"]) * 1000 if track.get("duration") else None,
            track.get("lang"),
            genres[0] if genres else None,
            track["id"],
        ),
    )
    return cur.fetchone()[0]


def _has_embedding(cur, track_id: int) -> bool:
    cur.execute(
        "SELECT 1 FROM track_embeddings WHERE track_id = %s AND source = %s",
        (track_id, SOURCE_CLAP_AUDIO),
    )
    return cur.fetchone() is not None


def _embed_and_store(cur, track_id: int, audio_url: str) -> None:
    from musicrec.embeddings.audio_embed import embed_audio  # deferred: heavy optional deps

    response = requests.get(audio_url, timeout=60)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(response.content)
        f.flush()
        embedding = embed_audio(f.name)

    cur.execute(
        """
        INSERT INTO track_embeddings (track_id, source, model_version, embedding)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (track_id, source) DO UPDATE
            SET embedding = EXCLUDED.embedding, model_version = EXCLUDED.model_version
        """,
        (track_id, SOURCE_CLAP_AUDIO, CLAP_MODEL_VERSION, embedding),
    )


def ingest_jamendo_catalog(limit: int = 200, tags: str | None = None, batch_size: int = 50) -> int:
    """Ingests up to `limit` tracks (paginated in batches of `batch_size`),
    computing a CLAP embedding for each. Returns the number of tracks
    processed (inserted or already present)."""
    client = JamendoClient()
    processed = 0

    with get_connection() as conn:
        offset = 0
        while processed < limit:
            page = client.tracks(limit=min(batch_size, limit - processed), offset=offset, tags=tags)
            if not page:
                break

            with conn.cursor() as cur:
                for track in page:
                    track_id = _upsert_track(cur, track)
                    if not _has_embedding(cur, track_id) and track.get("audiodownload"):
                        try:
                            _embed_and_store(cur, track_id, track["audiodownload"])
                        except requests.RequestException as e:
                            # Jamendo's storage CDN occasionally 500s on a
                            # specific track; skip it rather than losing the
                            # rest of the batch. The track row is kept
                            # without an embedding and will be retried on
                            # the next run.
                            print(f"Skipping track {track_id} ({track.get('name')}): {e}")
                    processed += 1
            conn.commit()

            offset += len(page)

    return processed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--tags", type=str, default=None, help="e.g. jazz, electronic")
    args = parser.parse_args()

    count = ingest_jamendo_catalog(limit=args.limit, tags=args.tags)
    print(f"Ingested {count} Jamendo tracks")
