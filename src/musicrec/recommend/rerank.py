"""Blend content-similarity candidates with a collaborative-filtering signal.

`collab_scores` is a stub interface (track_id -> score in roughly [0, 1])
for whatever CF model gets trained later (implicit-feedback ALS, a
two-tower model, etc.) — not implemented yet. Until then this is a no-op
that just returns the content ranking, so candidate_gen output can be
served directly while the CF model is built separately.
"""


def hybrid_rerank(
    candidates: list[dict],
    collab_scores: dict[int, float] | None = None,
    alpha: float = 0.7,
) -> list[dict]:
    """alpha weights content_similarity; (1 - alpha) weights collab_scores."""
    if not collab_scores:
        return sorted(candidates, key=lambda c: c["content_similarity"], reverse=True)

    for c in candidates:
        collab = collab_scores.get(c["track_id"], 0.0)
        c["score"] = alpha * c["content_similarity"] + (1 - alpha) * collab

    return sorted(candidates, key=lambda c: c["score"], reverse=True)
