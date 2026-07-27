import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/musicrec")

# Must match the `vector(N)` dimension used in db/migrations/0001_init.sql.
EMBED_DIM = 512

# Embedding source identifiers, kept centralized so ingestion, taste-profile
# computation, and candidate generation always agree on the strings used in
# track_embeddings.source / user_taste_profiles.source.
SOURCE_CLAP_AUDIO = "clap_audio"
SOURCE_COLLAB = "collab_2tower"

CLAP_MODEL_VERSION = "clap-htsat-fused-v1"
