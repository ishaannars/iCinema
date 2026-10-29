"""Ratings import: turn a Letterboxd or IMDb export into iCinema signals.

Letterboxd lets members export their data as a ZIP of CSV files (from their account settings);
we read ratings.csv (Name, Year, Rating out of 5) from the ZIP or the CSV itself. IMDb's ratings
export (Title, Year, Your Rating out of 10) is read too, halved to the same 5-star scale. The file
is read in the browser session only, and only matched titles are kept.

Rules:
- 4.5 or 5 stars becomes a Favorite, 4 stars a Like, matching the 4+ stars the models were
  trained and tested on as "loved".
- 2 stars or less becomes "Not for me", and 2.5 to 3.5 stars "Seen", but only if
  training/confirm_shelf_and_imports.py showed that signal makes picks better (the app passes
  use_low / use_mid from data/shelf_import_confirm.json).
- Titles are matched to MovieLens by title and year (a year off by one is allowed). At most
  MAX_IMPORT loved titles are kept, newest ratings first.
"""
import csv
import io
import zipfile

FAVORITE_AT = 4.5
LIKE_AT = 4.0
LOW_AT = 2.0
MAX_IMPORT = 300


def _rows_from_csv(text):
    out = []
    reader = csv.DictReader(io.StringIO(text))
    fields = {f.strip().lower(): f for f in (reader.fieldnames or [])}
    imdb = "your rating" in fields
    for row in reader:
        get = lambda k: (row.get(fields.get(k, ""), "") or "").strip()
        name = get("title") if imdb else get("name")
        raw = get("your rating") if imdb else get("rating")
        try:
            rating = float(raw) / (2.0 if imdb else 1.0)
        except ValueError:
            continue
        try:
            year = int(float(get("year") or 0))
        except ValueError:
            year = 0
        date = get("date rated") if imdb else get("date")
        if name and (not imdb or get("title type").lower() in ("", "movie", "tv movie")):
            out.append((name, year, rating, date))
    return out


def read_ratings(data):
    """bytes of a ratings CSV (Letterboxd or IMDb) or of the Letterboxd ZIP -> (name, year, stars/5, date)."""
    raw = data
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = next((n for n in z.namelist() if n.rsplit("/", 1)[-1].lower() == "ratings.csv"), None)
            if name is None:
                return []
            raw = z.read(name)
    return _rows_from_csv(raw.decode("utf-8-sig", errors="replace"))


def to_choices(rows, lookup, use_low=False, use_mid=False):
    """rows from read_ratings; lookup(title, year) -> movie dict or None.

    Returns (choices, summary). choices are (movie, kind), kind in favorite, like, dislike, seen,
    loved movies newest first; summary counts rated, kept, matched and not found."""
    def kind_of(r):
        if r >= FAVORITE_AT:
            return "favorite"
        if r >= LIKE_AT:
            return "like"
        if r <= LOW_AT:
            return "dislike" if use_low else None
        return "seen" if use_mid else None

    kept = [(r, kind_of(r[2])) for r in rows]
    kept = [(r, k) for r, k in kept if k]
    kept.sort(key=lambda x: x[0][3], reverse=True)
    choices, seen, missing, loved = [], set(), 0, 0
    for (name, year, _, _), kind in kept:
        if kind in ("favorite", "like") and loved >= MAX_IMPORT:
            continue
        movie = lookup(name, year)
        if movie is None:
            missing += 1
            continue
        if movie["title"] in seen:
            continue
        seen.add(movie["title"])
        choices.append((movie, kind))
        loved += kind in ("favorite", "like")
    return choices, {"rated": len(rows), "kept": len(kept), "matched": len(choices), "not_found": missing}
