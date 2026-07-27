import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/musicrec")

# Spotify OAuth (Authorization Code + PKCE — no client secret required).
# Register a Spotify Developer Dashboard app with this exact redirect URI.
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8080/callback")
SPOTIFY_TOKEN_CACHE_PATH = Path(
    os.environ.get("SPOTIFY_TOKEN_CACHE_PATH", Path.home() / ".musicrec" / "spotify_token.json")
)

# Must match the `vector(N)` dimension used in db/migrations/0001_init.sql.
EMBED_DIM = 512

# Embedding source identifiers, kept centralized so ingestion, taste-profile
# computation, and candidate generation always agree on the strings used in
# track_embeddings.source / user_taste_profiles.source.
SOURCE_CLAP_AUDIO = "clap_audio"
SOURCE_COLLAB = "collab_2tower"

CLAP_MODEL_VERSION = "clap-htsat-fused-v1"
