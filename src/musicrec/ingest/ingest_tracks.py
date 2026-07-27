"""Ingest track metadata (+ optional audio embedding) into the database.

Usage sketch:

    from musicrec.ingest.ingest_tracks import ingest_track

    ingest_track({
        "artist_name": "Boards of Canada",
        "album_title": "Music Has the Right to Children",
        "track_title": "Roygbiv",
        "language": "instrumental",
        "genre": "electronic",
        "audio_path": "/data/audio/roygbiv.flac",  # omit to skip embedding
    })

This is intentionally minimal upsert logic, not a full ETL framework — swap
in a real metadata source (MusicBrainz, Spotify, MSD) by mapping its records
into this same dict shape before calling ingest_track.
"""

from musicrec.config import SOURCE_CLAP_AUDIO, CLAP_MODEL_VERSION
from musicrec.db import get_connection


def _get_or_create_artist(cur, name: str, genre: str | None = None) -> int:
    cur.execute("SELECT id FROM artists WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO artists (name, canonical_genre) VALUES (%s, %s) RETURNING id",
        (name, genre),
    )
    return cur.fetchone()[0]


def _get_or_create_album(cur, artist_id: int, title: str) -> int:
    cur.execute(
        "SELECT id FROM albums WHERE artist_id = %s AND title = %s",
        (artist_id, title),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO albums (artist_id, title) VALUES (%s, %s) RETURNING id",
        (artist_id, title),
    )
    return cur.fetchone()[0]


def ingest_track(metadata: dict) -> int:
    """Insert artist/album/track rows (idempotent) and, if `audio_path` is
    given, compute and store its audio embedding. Returns the track id.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            artist_id = _get_or_create_artist(
                cur, metadata["artist_name"], metadata.get("genre")
            )

            album_id = None
            if metadata.get("album_title"):
                album_id = _get_or_create_album(
                    cur, artist_id, metadata["album_title"]
                )

            cur.execute(
                """
                INSERT INTO tracks
                    (album_id, artist_id, title, duration_ms, language, genre,
                     explicit, audio_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    album_id,
                    artist_id,
                    metadata["track_title"],
                    metadata.get("duration_ms"),
                    metadata.get("language"),
                    metadata.get("genre"),
                    metadata.get("explicit", False),
                    metadata.get("audio_path"),
                ),
            )
            track_id = cur.fetchone()[0]

            if metadata.get("audio_path"):
                # Deferred import: keeps the (heavy, optional) audio deps
                # out of the path for callers who only ingest metadata.
                from musicrec.embeddings.audio_embed import embed_audio

                embedding = embed_audio(metadata["audio_path"])
                cur.execute(
                    """
                    INSERT INTO track_embeddings (track_id, source, model_version, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (track_id, source) DO UPDATE
                        SET embedding = EXCLUDED.embedding,
                            model_version = EXCLUDED.model_version
                    """,
                    (track_id, SOURCE_CLAP_AUDIO, CLAP_MODEL_VERSION, embedding),
                )

        conn.commit()

    return track_id
