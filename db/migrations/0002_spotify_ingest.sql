-- Supports ingesting real Spotify listening history: lets upserts key off
-- Spotify's own IDs (idempotent re-ingestion) and keeps the ISRC around for
-- later bridging to MusicBrainz/audio-catalog datasets for embeddings.

ALTER TABLE users   ADD COLUMN spotify_id TEXT UNIQUE;
ALTER TABLE artists ADD COLUMN spotify_id TEXT UNIQUE;
ALTER TABLE tracks  ADD COLUMN spotify_id TEXT UNIQUE;
ALTER TABLE tracks  ADD COLUMN isrc TEXT;

-- Recently-played can overlap across ingestion runs; this makes re-running
-- the Spotify ingest safe to call repeatedly (ON CONFLICT DO NOTHING).
ALTER TABLE listening_events
    ADD CONSTRAINT uq_listening_event UNIQUE (user_id, track_id, ts, action);
