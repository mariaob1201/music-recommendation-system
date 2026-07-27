# music-recommendation-system

Embedding-space music recommendation: audio/metadata → embeddings → Postgres
(pgvector) → per-user, per-context taste profiles → similarity search +
hybrid re-ranking.

## Architecture

```
db/migrations/0001_init.sql   Postgres schema (artists, albums, tracks,
                               track_embeddings, users, listening_events,
                               user_taste_profiles)

src/musicrec/
  config.py                   DB URL, embedding dim, source identifiers
  db.py                       connection helper (registers pgvector type)

  embeddings/
    audio_embed.py            audio file -> CLAP embedding (optional, heavy deps)

  context/
    buckets.py                derives context buckets ("all", "night",
                               "weekend") from an event timestamp

  ingest/
    ingest_tracks.py          upserts artist/album/track rows + audio embedding
    spotify_auth.py           Spotify OAuth (Authorization Code + PKCE), token cache
    spotify_client.py         thin wrapper over the Spotify Web API endpoints used here
    spotify_ingest.py         pulls a user's recently-played + saved tracks into listening_events

  recommend/
    taste_profile.py          per-user, per-bucket weighted centroid of
                               liked/played track embeddings
    candidate_gen.py          ANN search (pgvector cosine) + hard filters
                               (language, already-heard)
    rerank.py                 blends content similarity with a collaborative-
                               filtering score (CF model not implemented yet)
```

## Data sources (none of this is bundled — bring your own)

- **Metadata** (artist/album/track/genre/language): MusicBrainz or Discogs API.
- **Audio files** (only needed for real `clap_audio` embeddings): Free Music
  Archive, Jamendo, or your own library.
- **Listening history** (`listening_events`): your own app's usage once it
  has users; for prototyping without real users, the Million Song Dataset's
  Echo Nest Taste Profile subset or the Last.fm 1K/360K datasets work well.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .            # core deps
pip install -e ".[audio]"   # + torch/CLAP, only if computing real audio embeddings

export DATABASE_URL=postgresql://localhost/musicrec
./scripts/init_db.sh        # requires the `vector` extension to be installable
```

## Ingesting real Spotify history

1. Create an app at https://developer.spotify.com/dashboard.
2. Add `http://127.0.0.1:8080/callback` as a Redirect URI (must match exactly —
   Spotify requires the literal IP `127.0.0.1`, not `localhost`).
3. `export SPOTIFY_CLIENT_ID=<your client id>` (no client secret needed — this
   uses the Authorization Code + PKCE flow).
4. `python -m musicrec.ingest.spotify_ingest` — opens a browser for one-time
   login, then writes your recently-played + saved tracks into
   `listening_events`. Safe to re-run; it dedupes and upserts.

Note: Spotify doesn't provide raw audio or audio-feature vectors to new apps
(restricted since Nov 2024), so this only populates listening history —
pair it with `ingest_tracks.py` against a separate audio-bearing catalog
(e.g. Jamendo, Free Music Archive, or the Million Song Dataset) to get
`track_embeddings` for content-based similarity.

## Status

Scaffold only — schema, connection plumbing, and the pipeline's function
signatures are in place; each module is a working skeleton that still needs:

- a real audio catalog wired into `ingest_tracks.py` to get content embeddings
- ISRC-based matching between Spotify tracks and an audio-bearing catalog
- a trained collaborative-filtering model feeding `rerank.hybrid_rerank`
- an evaluation harness (offline recall@K, later online skip/save-rate)
