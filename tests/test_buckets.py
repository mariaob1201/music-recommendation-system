import datetime

from musicrec.context.buckets import buckets_for_timestamp


def test_weekday_afternoon_is_just_all():
    ts = datetime.datetime(2026, 7, 27, 15, 0)  # Monday, 3pm
    assert buckets_for_timestamp(ts) == ["all"]


def test_weekday_late_night_is_night():
    ts = datetime.datetime(2026, 7, 27, 23, 30)  # Monday, 11:30pm
    assert buckets_for_timestamp(ts) == ["all", "night"]


def test_weekday_early_morning_is_night():
    ts = datetime.datetime(2026, 7, 27, 3, 0)  # Monday, 3am
    assert buckets_for_timestamp(ts) == ["all", "night"]


def test_saturday_afternoon_is_weekend():
    ts = datetime.datetime(2026, 8, 1, 15, 0)  # Saturday, 3pm
    assert buckets_for_timestamp(ts) == ["all", "weekend"]


def test_saturday_night_is_both():
    ts = datetime.datetime(2026, 8, 1, 23, 30)  # Saturday, 11:30pm
    assert buckets_for_timestamp(ts) == ["all", "night", "weekend"]
