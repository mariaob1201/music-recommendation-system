-- Supports idempotent bulk ingestion from Jamendo (real, downloadable audio
-- used to compute genuine CLAP embeddings, unlike Spotify's history-only data).

ALTER TABLE artists ADD COLUMN jamendo_id TEXT UNIQUE;
ALTER TABLE albums  ADD COLUMN jamendo_id TEXT UNIQUE;
ALTER TABLE tracks  ADD COLUMN jamendo_id TEXT UNIQUE;
