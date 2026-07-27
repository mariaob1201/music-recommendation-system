-- Core schema for the music recommendation system.
-- Embedding dimension (512) matches CLAP audio embeddings; change EMBED_DIM
-- consistently here and in src/musicrec/config.py if you switch models.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE artists (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    canonical_genre TEXT,
    country         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE albums (
    id           BIGSERIAL PRIMARY KEY,
    artist_id    BIGINT NOT NULL REFERENCES artists(id),
    title        TEXT NOT NULL,
    release_date DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tracks (
    id          BIGSERIAL PRIMARY KEY,
    album_id    BIGINT REFERENCES albums(id),
    artist_id   BIGINT NOT NULL REFERENCES artists(id),
    title       TEXT NOT NULL,
    duration_ms INTEGER,
    language    TEXT,
    genre       TEXT,
    explicit    BOOLEAN NOT NULL DEFAULT false,
    audio_path  TEXT,               -- source file/URI used to compute embeddings, if any
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tracks_artist ON tracks(artist_id);
CREATE INDEX idx_tracks_album  ON tracks(album_id);

-- A track can have more than one embedding (e.g. content-based audio embedding
-- vs. a collaborative-filtering embedding). `source` distinguishes them so both
-- can live in the same table and be queried independently or blended later.
CREATE TABLE track_embeddings (
    track_id      BIGINT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    source        TEXT NOT NULL,         -- e.g. 'clap_audio', 'collab_2tower'
    model_version TEXT NOT NULL,
    embedding     vector(512) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (track_id, source)
);

-- Approximate nearest-neighbor index for cosine similarity search.
-- ivfflat requires ANALYZE after bulk load, and `lists` should be tuned to
-- roughly sqrt(row_count) once real data is loaded.
CREATE INDEX idx_track_embeddings_ann
    ON track_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE TABLE users (
    id         BIGSERIAL PRIMARY KEY,
    email      TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw interaction log. day_of_week/hour are derived at query/aggregation
-- time (see src/musicrec/context/buckets.py) rather than stored, so the
-- definition of a "context bucket" can change without a migration.
CREATE TABLE listening_events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id),
    track_id   BIGINT NOT NULL REFERENCES tracks(id),
    ts         TIMESTAMPTZ NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('play', 'save', 'skip', 'like')),
    device     TEXT,
    session_id TEXT
);

CREATE INDEX idx_listening_events_user_ts ON listening_events(user_id, ts DESC);
CREATE INDEX idx_listening_events_track   ON listening_events(track_id);

-- Precomputed taste centroids, one row per (user, context bucket, embedding
-- source). Recomputed periodically by recommend/taste_profile.py rather than
-- derived live on every request.
CREATE TABLE user_taste_profiles (
    user_id         BIGINT NOT NULL REFERENCES users(id),
    context_bucket  TEXT NOT NULL,     -- e.g. 'all', 'night', 'weekend'
    source          TEXT NOT NULL,     -- matches track_embeddings.source
    embedding       vector(512) NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, context_bucket, source)
);
