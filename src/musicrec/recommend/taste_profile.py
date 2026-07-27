"""Compute per-user, per-context-bucket taste centroids.

A user's taste profile is a weighted average of the embeddings of tracks
they've interacted with — recent interactions and stronger signals (save,
like) count more than old ones or plain plays. One centroid is stored per
context bucket ("all", "night", "weekend", ...) so recommendations can be
conditioned on the listener's current context (see context/buckets.py).

This recomputes from full history on each call, which is fine at prototype
scale; if listening_events grows large, switch to an incremental update
(decay the stored centroid and blend in only new events) instead of
rescanning everything.
"""

import datetime

import numpy as np

from musicrec.context.buckets import buckets_for_timestamp
from musicrec.db import get_connection

ACTION_WEIGHTS = {
    "play": 1.0,
    "like": 3.0,
    "save": 3.0,
    "skip": 0.0,  # excluded from the centroid, not treated as negative signal (yet)
}


def _recency_weight(ts: datetime.datetime, half_life_days: float) -> float:
    age_days = (datetime.datetime.now(tz=ts.tzinfo) - ts).days
    return 0.5 ** (age_days / half_life_days)


def compute_and_store_taste_profiles(
    user_id: int, source: str, half_life_days: float = 30.0
) -> dict[str, np.ndarray]:
    """Recompute all context-bucket centroids for one user/embedding-source
    pair and upsert them into user_taste_profiles. Returns the computed
    centroids keyed by bucket name.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT le.ts, le.action, te.embedding
                FROM listening_events le
                JOIN track_embeddings te ON te.track_id = le.track_id
                WHERE le.user_id = %s AND te.source = %s
                """,
                (user_id, source),
            )
            rows = cur.fetchall()

            weighted_sums: dict[str, np.ndarray] = {}
            weight_totals: dict[str, float] = {}

            for ts, action, embedding in rows:
                action_weight = ACTION_WEIGHTS.get(action, 0.0)
                if action_weight == 0.0:
                    continue

                weight = action_weight * _recency_weight(ts, half_life_days)
                embedding = np.asarray(embedding)

                for bucket in buckets_for_timestamp(ts):
                    weighted_sums[bucket] = weighted_sums.get(
                        bucket, np.zeros_like(embedding)
                    ) + weight * embedding
                    weight_totals[bucket] = weight_totals.get(bucket, 0.0) + weight

            profiles = {}
            for bucket, total in weight_totals.items():
                centroid = weighted_sums[bucket] / total
                norm = np.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm
                profiles[bucket] = centroid

                cur.execute(
                    """
                    INSERT INTO user_taste_profiles (user_id, context_bucket, source, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, context_bucket, source) DO UPDATE
                        SET embedding = EXCLUDED.embedding,
                            updated_at = now()
                    """,
                    (user_id, bucket, source, centroid),
                )

        conn.commit()

    return profiles
