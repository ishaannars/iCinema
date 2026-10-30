"""When can I stream it? Labeled estimates for movies still in theaters.

Based on Omdia's 2025 tracking of U.S. wide releases: the first rental/purchase window averaged
39 days after the theatrical release (Disney averaged about 62), and subscription streaming
averaged 95 days. These are averages, so the app always calls them estimates.
"""
import datetime

RENT_DAYS, STREAM_DAYS, DISNEY_RENT_DAYS = 39, 95, 62


def estimate(release_date, studios=(), today=None):
    """(rent_date, stream_date) as dates, or None if the movie isn't a recent theatrical release."""
    try:
        released = datetime.date.fromisoformat(str(release_date)[:10])
    except (TypeError, ValueError):
        return None
    today = today or datetime.date.today()
    age = (today - released).days
    if age < 0 or age > STREAM_DAYS + 30:
        return None
    disney = any("disney" in str(s).lower() or "pixar" in str(s).lower() or "marvel" in str(s).lower() for s in studios or ())
    rent = released + datetime.timedelta(days=DISNEY_RENT_DAYS if disney else RENT_DAYS)
    stream = released + datetime.timedelta(days=STREAM_DAYS)
    return rent, stream


def line(release_date, studios=(), today=None):
    """Short card line, or "" when there's nothing to estimate."""
    est = estimate(release_date, studios, today)
    if not est:
        return ""
    today = today or datetime.date.today()
    rent, stream = est
    fmt = lambda d: d.strftime("%b %-d")
    if rent > today:
        return f"In theaters · rent at home ≈ {fmt(rent)} · streaming ≈ {fmt(stream)} (estimates)"
    if stream > today:
        return f"Streaming ≈ {fmt(stream)} (estimate)"
    return ""
