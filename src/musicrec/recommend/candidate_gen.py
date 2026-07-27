"""Candidate generation: ANN search of a user's taste centroid against the
track embedding index, with hard filters applied after the vector search
(not baked into the similarity score itself).
"""

from musicrec.db import get_connection


def generate_candidates(
    user_id: int,
    source: str,
    context_bucket: str = "all",
    top_k: int = 50,
    language: str | None = None,
    exclude_heard: bool = True,
) -> list[dict]:
    """Return up to `top_k` candidate tracks for a user, ranked by cosine
    similarity to their taste centroid for the given context bucket.

    Falls back to the "all" bucket if the user has no profile yet for the
    requested bucket (e.g. a new user with too little night-time history).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT embedding FROM user_taste_profiles
                WHERE user_id = %s AND source = %s AND context_bucket = %s
                """,
                (user_id, source, context_bucket),
            )
            row = cur.fetchone()
            if row is None and context_bucket != "all":
                cur.execute(
                    """
                    SELECT embedding FROM user_taste_profiles
                    WHERE user_id = %s AND source = %s AND context_bucket = 'all'
                    """,
                    (user_id, source),
                )
                row = cur.fetchone()

            if row is None:
                return []  # cold-start user: no history to build a profile from yet

            taste_vector = row[0]

            cur.execute(
                """
                SELECT t.id, t.title, t.artist_id, t.language,
                       1 - (te.embedding <=> %(vec)s) AS similarity
                FROM track_embeddings te
                JOIN tracks t ON t.id = te.track_id
                WHERE te.source = %(source)s
                  AND (%(language)s IS NULL OR t.language = %(language)s)
                  AND (
                        NOT %(exclude_heard)s
                        OR t.id NOT IN (
                            SELECT track_id FROM listening_events WHERE user_id = %(user_id)s
                        )
                      )
                ORDER BY te.embedding <=> %(vec)s
                LIMIT %(top_k)s
                """,
                {
                    "vec": taste_vector,
                    "source": source,
                    "language": language,
                    "exclude_heard": exclude_heard,
                    "user_id": user_id,
                    "top_k": top_k,
                },
            )
            return [
                {
                    "track_id": r[0],
                    "title": r[1],
                    "artist_id": r[2],
                    "language": r[3],
                    "content_similarity": r[4],
                }
                for r in cur.fetchall()
            ]
