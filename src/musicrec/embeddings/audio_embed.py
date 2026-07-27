"""Audio -> embedding via CLAP.

Requires the `audio` optional dependency group (`pip install .[audio]`),
which pulls in torch + laion-clap. Kept separate from the core deps because
they're large and unnecessary for anything that only reads existing
embeddings from the database.
"""

import numpy as np

from musicrec.config import EMBED_DIM

_model = None


def _load_model():
    global _model
    if _model is None:
        import laion_clap

        _model = laion_clap.CLAP_Module(enable_fusion=True)
        _model.load_ckpt()  # downloads pretrained weights on first run
    return _model


def embed_audio(audio_path: str) -> np.ndarray:
    """Return a single L2-normalized embedding vector for an audio file.

    Normalized so downstream cosine-similarity queries (pgvector
    `<=>` / dot product) behave consistently.
    """
    model = _load_model()
    embedding = model.get_audio_embedding_from_filelist(
        x=[audio_path], use_tensor=False
    )[0]
    assert embedding.shape[0] == EMBED_DIM, (
        f"CLAP returned dim {embedding.shape[0]}, expected {EMBED_DIM} "
        "(update EMBED_DIM and the migration if the model changed)"
    )
    return embedding / np.linalg.norm(embedding)
