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
    jamendo_client.py         thin wrapper over the Jamendo API (public catalog + audio)
    jamendo_ingest.py         bulk-ingests Jamendo tracks + computes real CLAP embeddings

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
pair it with the Jamendo ingestion below (or `ingest_tracks.py` against
another audio-bearing catalog) to get `track_embeddings` for content-based
similarity.

## Ingesting a real audio catalog (Jamendo)

1. Get a free `client_id` at https://devportal.jamendo.com/ (instant, no
   OAuth needed for these read-only endpoints).
2. `export JAMENDO_CLIENT_ID=<your client id>`
3. `pip install -e ".[audio]"` — this step downloads real audio and computes
   CLAP embeddings, so the heavy deps are required here (unlike the
   Spotify ingestion above).
4. `python -m musicrec.ingest.jamendo_ingest --limit 200 --tags jazz` —
   pulls tracks matching the tag, downloads each preview, embeds it, and
   upserts into `tracks` / `track_embeddings`. Safe to re-run: upserts on
   `jamendo_id`, skips tracks that already have an embedding.

This is what `candidate_gen.py` actually searches against — run it before
expecting `generate_candidates()` to return anything.

## Status

Schema, connection plumbing, and both ingestion paths (Spotify for history,
Jamendo for real audio + embeddings) work end-to-end for a single user /
small catalog. Still needed:

- ISRC-based matching between Spotify tracks and the Jamendo catalog (right
  now they're ingested as unrelated tracks, so a track played on Spotify
  won't be recognized as "already heard" against the Jamendo candidate pool)
- a trained collaborative-filtering model feeding `rerank.hybrid_rerank`
- an evaluation harness (offline recall@K, later online skip/save-rate)
