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

## Status

Scaffold only — schema, connection plumbing, and the pipeline's function
signatures are in place; each module is a working skeleton that still needs:

- a real metadata/audio ingestion source wired into `ingest_tracks.py`
- a trained collaborative-filtering model feeding `rerank.hybrid_rerank`
- an evaluation harness (offline recall@K, later online skip/save-rate)
