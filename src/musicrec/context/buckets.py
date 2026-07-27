"""Context-bucket definitions.

A listening event can belong to more than one bucket (e.g. a Saturday
midnight play is both "night" and "weekend"). Buckets are derived here from
the event timestamp rather than stored, so redefining them later doesn't
require a migration or backfill.

`ts` is expected to already be in the listener's local time.
"""

import datetime

NIGHT_START_HOUR = 22  # 22:00
NIGHT_END_HOUR = 6  # 06:00, exclusive


def buckets_for_timestamp(ts: datetime.datetime) -> list[str]:
    buckets = ["all"]

    if ts.hour >= NIGHT_START_HOUR or ts.hour < NIGHT_END_HOUR:
        buckets.append("night")

    if ts.weekday() >= 5:  # Saturday=5, Sunday=6
        buckets.append("weekend")

    return buckets
