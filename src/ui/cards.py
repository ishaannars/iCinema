"""Card and popup text for iCinema: pure functions with no Streamlit calls, so they're easy to test.

Split out of app.py. Everything here turns a movie, its scores, and the models' reasons into the short
lines a card or popup shows: ratings, genres, the fit pill, the "why" rows, and the tap-to-read story.
"""
import html
import re

from src.cf_model import fan_percentile
from src.descriptions import expanded_card_description, quick_card_description
from src.recommender import GENRES

def card_ratings(movie, live_rating):
    """The one set of ratings a card shows and its explanations cite.

    Live OMDb scores first, then the scores stored with the movie. TMDB's viewer
    score is used only when neither IMDb nor Rotten Tomatoes is available.
    """
    movie, live = movie or {}, live_rating or {}
    def pick(key):
        for source in (live, movie):
            value = source.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        return None
    imdb, rt = pick("imdb"), pick("rt")
    tmdb = None if imdb else pick("tmdb_vote")  # viewer score stands in only when IMDb is missing
    return {"imdb": imdb, "rt": rt, "tmdb_vote": tmdb}


def ratings_text(ratings):
    """'IMDb 7.1 · RT 88%', 'IMDb 7.1 · No RT', or 'Viewers 7.9/10 · No RT'."""
    audience = (f"IMDb {ratings['imdb']:.1f}" if ratings.get("imdb") else
                (f"Viewers {ratings['tmdb_vote']:.1f}/10" if ratings.get("tmdb_vote") else None))
    critics = f"RT {int(ratings['rt'])}%" if ratings.get("rt") else "No RT"
    if not audience and critics == "No RT":
        return []  # nothing to show; the card says "Ratings unavailable"
    return [x for x in (audience, critics) if x]


def with_live_ratings(movie, live_rating):
    """Copy of the movie carrying exactly the ratings shown on its card."""
    movie = dict(movie or {})
    ratings = card_ratings(movie, live_rating)
    for key in ("imdb", "rt"):
        if ratings[key]:
            movie[key] = ratings[key]
        else:
            movie.pop(key, None)
    if ratings["tmdb_vote"]:
        movie["tmdb_vote"] = ratings["tmdb_vote"]
    else:
        movie.pop("tmdb_vote", None)  # explanations cite only what the card shows
    return movie


_PILL_SHORT = {
    "Feels like your favorites": "Like your favorites",
    "Feels like your pick": "Like your pick",
    "Storytelling you like": "Your kind of story",
    "Critically acclaimed": "Critics' pick",
    "Easy to watch tonight": "Streaming now",
    "International pick": "International",
    "Loved by viewers like you": "Fans like you",
    "New, and close to what you like": "New for you",
}


PILL_BUDGET = 25  # characters, including "80% · ", that fit a card pill without clipping


def _short_reason(reason, room):
    """Pill-sized version of a reason label, or None if it can't fit without cutting."""
    label = str((reason or {}).get("label") or "").strip()
    if label.startswith("Loved by fans of "):
        fans = "Fans of " + label[len("Loved by fans of "):]
        label = fans if len(fans) <= room else "Fans like you"
    label = _PILL_SHORT.get(label, label)
    if label.startswith("Your kind of ") and len(label) > room:
        label = label[len("Your kind of "):].strip().capitalize() + " pick"
    return label if label and len(label) <= room else None


def fit_head(payload, match):
    """Rank-based fit: where this movie ranks among every movie iCinema scored for you.

    Accurate by construction (it is a rank, not a probability), and it spreads out
    even when the raw scores of top picks sit close together.
    """
    top = (payload or {}).get("fit_top_pct")
    return f"Top {int(top)}%" if isinstance(top, (int, float)) else f"{int(match or 0)}%"


def fit_label(payload, match):
    top = (payload or {}).get("fit_top_pct")
    if not isinstance(top, (int, float)):
        return match_label(match)
    return "Made for you" if top <= 2 else "Strong match" if top <= 10 else "Good match" if top <= 25 else "Worth a look"


def match_pill(match, reasons, limit=None, taken=(), head=None):
    """Percent plus this movie's strongest reason not already shown in its row.

    Returns (pill_text, label_used). Skipping labels other cards in the row already
    use keeps a row varied, e.g. one "Fans of “Spirited Away”" instead of four.
    """
    match = int(match or 0)
    head = head or f"{match}%"
    room = (limit if limit is not None else PILL_BUDGET) - len(f"{head} · ")
    for reason in reasons or []:
        label = _short_reason(reason, room)
        if label and label not in taken:
            return f"{head} · {label}", label
    return f"{head} for you", None


def match_label(match):
    """Plain-language fit instead of a bare percentage; the % stays in the explanation."""
    match = int(match or 0)
    if match >= 70:
        return "Made for you"
    if match >= 55:
        return "Strong match"
    if match >= 42:
        return "Good match"
    return "Worth a look"


def card_html(toggle_id, art_html, title, movie, identity, lines_html):
    """One card in one block: tap the art to open the full story under it, then the info lines and a
    short description. Keeping it all in one block is what makes the tap work and the spacing even."""
    dm = dict(movie, tagline=identity.get("tagline"), overview=movie.get("overview") or identity.get("overview"))
    full = expanded_card_description(dm)
    short = plain_premise(dm) or " ".join(str(dm.get("overview") or "").split()) or full
    tag = " ".join(str(identity.get("tagline") or "").split())
    tag = tag if 0 < len(tag) <= 80 else ""
    return ('<div class="card-text">'
            f'<input class="card-hook-box" type="checkbox" id="{toggle_id}">'
            f'<label class="art-toggle" for="{toggle_id}" title="Tap for the story">{art_html}</label>'
            f'<div class="premise-panel"><div class="premise-title">{html.escape(str(title))}</div>'
            + (f'<div class="premise-tag">{html.escape(tag)}</div>' if tag else "")
            + f'<div class="premise-copy">{html.escape(short)}</div></div>'
            f'{lines_html}'
            '</div>')


def premise_panel(toggle_id, title, movie, identity):
    """Hidden panel under the art: the title and the full premise, opened by tapping the art."""
    full = expanded_card_description(dict(movie, tagline=identity.get("tagline"),
                                          overview=movie.get("overview") or identity.get("overview")))
    return (f'<input class="card-hook-box" type="checkbox" id="{toggle_id}">'
            f'<div class="premise-panel"><div class="premise-title">{html.escape(str(title))}</div>'
            f'<div class="premise-copy">{html.escape(full)}</div></div>')


def library_lines_html(movie, identity, live_map, watch_html=""):
    """Year and genres, ratings, where to watch: the same lines as a Showroom card."""
    year = identity.get("year") or movie.get("year")
    meta = [str(x) for x in (year, genre_pair(movie)) if x]
    parts = ratings_text(card_ratings(movie, (live_map or {}).get(movie["title"]) or {}))
    return (f'<div class="poster-caption-year card-year">{" · ".join(html.escape(m) for m in meta)}</div>'
            f'<div class="ratings">{" · ".join(parts) or "Ratings unavailable"}</div>'
            + (f'<div class="watch-availability">{watch_html}</div>' if watch_html else ""))


def library_text_html(movie, identity, live_map, watch_html="", premise=""):
    """The Showroom card's text block for Saved / Seen: year and genres, ratings, where to watch."""
    year = identity.get("year") or movie.get("year")
    meta = [str(x) for x in (year, genre_pair(movie)) if x]
    parts = ratings_text(card_ratings(movie, (live_map or {}).get(movie["title"]) or {}))
    return ('<div class="card-text">' + premise +
            f'<div class="poster-caption-year card-year">{" · ".join(html.escape(m) for m in meta)}</div>'
            f'<div class="ratings">{" · ".join(parts) or "Ratings unavailable"}</div>'
            + (f'<div class="watch-availability">{watch_html}</div>' if watch_html else "")
            + '</div>')


def library_ratings_html(movie, identity, live_map):
    """Same ratings line as the Showroom cards (IMDb · RT, 'No RT', or viewer score)."""
    parts = ratings_text(card_ratings(movie, (live_map or {}).get(movie["title"]) or {}))
    return (f'<div class="ratings library-ratings">{" · ".join(parts)}</div>' if parts
            else '<div class="ratings library-ratings muted">Ratings unavailable</div>')


def concise_description(text, limit=138):
    """Return a compact *complete-sounding* description for aligned movie cards.

    Prefer a full first sentence. If the source is longer, shorten on a natural
    phrase boundary and never leave dangling filler words such as "a" or "the".
    """
    text = " ".join(str(text or "").split()).strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    first_sentence = sentences[0].strip() if sentences else text
    if len(first_sentence) <= limit:
        return first_sentence if first_sentence.endswith((".", "!", "?")) else first_sentence + "."

    candidate = first_sentence
    # Prefer a natural clause boundary before falling back to a word boundary.
    boundaries = [m.end() for m in re.finditer(r"[,;:]\s+|\s+[–—-]\s+", candidate[:limit + 1])]
    if boundaries:
        candidate = candidate[:boundaries[-1]].rstrip(" ,;:–—-")
    else:
        candidate = candidate[:limit].rsplit(" ", 1)[0].rstrip(" ,;:–—-")

    dangling = {"a", "an", "the", "and", "or", "but", "with", "to", "of", "in", "for", "from", "by"}
    words = candidate.split()
    while words and words[-1].casefold().strip(".,;:") in dangling:
        words.pop()
    candidate = " ".join(words).rstrip(" ,;:.…")
    return candidate + "." if candidate else first_sentence


def profile_chip_html(items):
    return "".join(f'<span class="profile-chip">{item}</span>' for item in items)


def profile_analysis_html(items):
    return "".join(f'<div class="profile-analysis-row">{item}</div>' for item in items)


def why_rows(reasons, movie=None, live_rating=None, payload=None):
    """Label/number pairs for the % popup. Every value is a number the models actually used."""
    payload = payload or {}
    rows = []
    rank, pool = payload.get("fit_rank"), payload.get("fit_pool")
    if isinstance(rank, int) and isinstance(pool, int) and pool > 0:
        rows.append(("Rank", f"#{rank:,} of {pool:,} movies scored for you"))
    cf = payload.get("cf")
    is_new = fan_percentile(movie) is None
    anchor = next((re.match(r"Loved by fans of “(.+)”", str(r.get("label", ""))).group(1)
                   for r in reasons or [] if re.match(r"Loved by fans of “(.+)”", str(r.get("label", "")))), None)
    if isinstance(cf, (int, float)):
        if is_new:
            rows.append(("New release", f"Its makers sit closer to your likes than {int(round(cf * 100))}% of new releases"))
        else:
            from src import ltr as _l
            rows.append(("Model score" if _l.available() else "Fans like you",
                         (f"Above {int(round(cf * 100))}% of movies, from six models combined" if _l.available()
                          else f"Closer to your likes than {int(round(cf * 100))}% of movies")
                         + (f" · fans of {_short_title(anchor)} love it" if anchor else "")))
    sem = payload.get("semantic_similarity")
    tone = next((re.search(r"like “(.+?)”", str(r.get("text", ""))) for r in reasons or []
                 if str(r.get("label", "")).startswith("Feels like")), None)
    if isinstance(sem, (int, float)) and sem > 0:
        rows.append(("Tone", f"{int(round(sem * 100))}% match on genres and fan tags"
                     + (f" · closest: {_short_title(tone.group(1))}" if tone else "")))
    if any(r.get("label") == "Fits your mood" for r in reasons or []):
        rows.append(("Mood", "In the top 10% of fan-tag matches for your words"))
    rt = (live_rating or {}).get("rt")
    rt = rt if isinstance(rt, (int, float)) else (movie or {}).get("rt")
    imdb = (live_rating or {}).get("imdb")
    imdb = imdb if isinstance(imdb, (int, float)) else (movie or {}).get("imdb")
    scores = [x for x in ((f"RT {int(rt)}%" if isinstance(rt, (int, float)) and rt >= 0 else None),
                          (f"IMDb {imdb:.1f}" if isinstance(imdb, (int, float)) and imdb > 0 else None)) if x]
    if scores:
        rows.append(("Ratings", " · ".join(scores)))
    return rows[:5] or [("Fit", "Ranked high by the models for what you’ve liked")]


def why_sentences(reasons, movie=None, live_rating=None, limit=2):
    """Up to two plain sentences from the model's strongest reasons for this movie, nothing generic."""
    out = []
    rt = (live_rating or {}).get("rt")
    rt = rt if isinstance(rt, (int, float)) else (movie or {}).get("rt")
    for r in reasons or []:
        label, text = str(r.get("label", "")), str(r.get("text", ""))
        m = re.match(r"Loved by fans of “(.+)”", label)
        if m:
            out.append(f"Fans of {_short_title(m.group(1))} love it.")
        elif label == "Fits your mood":
            out.append(text)
        elif label.startswith("Critics") or label == "Critically acclaimed":
            if isinstance(rt, (int, float)) and rt >= 75:
                out.append(f"Critics agree: {int(rt)}% on Rotten Tomatoes.")
        elif label.startswith("New, and close"):
            out.append("New, from people who made movies you liked.")
        elif label in ("What you asked for", "Loved by viewers like you"):
            continue      # too vague to be worth a line
        elif text:
            out.append(text if text.endswith(".") else text + ".")
        if len(out) >= limit:
            break
    return out or ["Ranked high by the models for what you’ve liked."]


def plain_premise(movie):
    """The opening sentence of the plot summary: clear and specific, no marketing tagline."""
    text = " ".join(str((movie or {}).get("overview") or "").split())
    if not text:
        return ""
    first = re.split(r"(?<=[.!?])\s+", text)[0].strip()
    return first if 30 <= len(first) <= 220 else ""


def genre_pair(movie):
    """Two genres, e.g. "Sci-Fi, Action": the main one plus the next genre among its tags."""
    main = (movie or {}).get("genre")
    second = next((t for t in (movie or {}).get("tags") or [] if t in GENRES and t != main), None)
    return ", ".join(x for x in (main, second) if x)


def _short_title(t):
    """'The Lord of the Rings: The Fellowship of the Ring' -> 'The Lord of the Rings' for one-line reasons."""
    t = re.split(r":| - | – ", str(t))[0].strip()
    return t if len(t) <= 26 else t[:24].rsplit(" ", 1)[0] + "…"


def card_reason_line(reasons, row_name=None, movie=None, live_rating=None):
    """One short line saying why this card is here: the row's own job first, then the top personal reason."""
    reasons = reasons or []
    if reasons and reasons[0].get("label") == "Fits your mood":
        return "Fits your mood"
    if row_name == "Critically Acclaimed":
        return "Critics and audiences agree"
    if row_name == "Hidden Gems":
        return "Less known, made for you"
    if row_name == "Something Different":
        return f"New ground: {(movie or {}).get('genre') or 'a different genre'}"
    for r in reasons:
        label = str(r.get("label", ""))
        m = re.match(r"Loved by fans of “(.+)”", label)
        if m:
            return f"Because you loved {_short_title(m.group(1))}"
        if label:
            return label
    return ""
