"""Where to watch: provider names, links, and the streaming line on each card.

Pure functions with no Streamlit state, so they can be unit-tested. Every outside value
(provider names, titles, URLs) is escaped before it reaches the page, and only http(s)
links are ever rendered.
"""
import html
import re
from urllib.parse import quote_plus


def _safe_url(url):
    """Only web links can reach the page; anything else (javascript:, data:) is dropped."""
    url = str(url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else ""


# Streaming services a viewer can pick for Tonight's Pick. Aliases match TMDB/JustWatch
# provider names, including ad tiers and channel variants (e.g. "Netflix basic with Ads").
STREAMING_SERVICES = {
    "Netflix": ("netflix",),
    "Max": ("max", "hbomax"),
    "Hulu": ("hulu",),
    "Prime Video": ("amazonprime", "primevideo"),
    "Disney+": ("disney",),
    "Apple TV+": ("appletvplus",),
    "Peacock": ("peacock",),
    "Paramount+": ("paramount",),
    "Free (Tubi, Pluto & more)": ("tubi", "pluto", "roku", "plex", "freevee", "kanopy", "hoopla"),
}


def _provider_key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).casefold().replace("+", "plus"))


def _on_service(provider, service):
    key = _provider_key(provider)
    return any(key.startswith(alias) for alias in STREAMING_SERVICES.get(service, ()))


# One tap from a recommendation to the service that plays it. Each link opens that
# service's search for the exact title (the closest a public link can get to its
# title page). Services without a dependable public search URL (Max, Peacock,
# Paramount+, Fandango) open TMDB's JustWatch-powered page, which links to them.
PROVIDER_LINKS = [
    ("netflix", "https://www.netflix.com/search?q={q}"),
    ("hulu", "https://www.hulu.com/search?q={q}"),
    ("amazonprime", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("primevideo", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("amazonvideo", "https://www.amazon.com/s?k={q}&i=instant-video"),
    ("disney", "https://www.disneyplus.com/search?q={q}"),
    ("appletv", "https://tv.apple.com/search?term={q}"),
    ("tubi", "https://tubitv.com/search/{q}"),
    ("youtube", "https://www.youtube.com/results?search_query={q}"),
    ("googleplay", "https://play.google.com/store/search?q={q}&c=movies"),
]


def provider_watch_url(provider, title, availability=None):
    from urllib.parse import quote_plus
    key = _provider_key(provider)
    for prefix, template in PROVIDER_LINKS:
        if key.startswith(prefix):
            return template.format(q=quote_plus(str(title)))
    fallback = (availability or {}).get("url")
    return fallback or f"https://www.justwatch.com/us/search?q={quote_plus(str(title))}"


def watch_options(availability, title, services=None, limit=2):
    """[(label, provider, url)] for the best ways to watch, the viewer's services first."""
    availability = availability or {}
    services = list(services or [])
    streaming = list(availability.get("providers") or [])
    renting = list(availability.get("rent_providers") or [])
    if services:
        mine = [p for p in streaming if any(_on_service(p, sv) for sv in services)]
        streaming = mine + [p for p in streaming if p not in mine]
    chosen = [("Watch on", p) for p in streaming[:limit]]
    if not chosen:
        chosen = [("Rent on", p) for p in renting[:limit]]
    seen, out = set(), []
    for verb, provider in chosen:
        name = re.sub(r"\s+(basic\s+)?with\s+ads$|\s+amazon\s+channel$|\s+standard\s+with\s+ads$", "", provider, flags=re.IGNORECASE).strip()
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        out.append((f"{verb} {name}", name, provider_watch_url(provider, title, availability)))
    return out


def watch_line_html(availability, title, services=None):
    """Streaming line where each service name is a one-tap link to it."""
    availability = availability or {}
    options = watch_options(availability, title, services)
    if not options:
        text = concise_availability_text(availability.get("text") or "Where to watch: availability unavailable")
        return html.escape(text)
    verb = "Streaming" if options[0][0].startswith("Watch") else "Rent"

    def _label(name):
        key = _provider_key(name)
        return f"{name} (free with a library card)" if key.startswith(("kanopy", "hoopla")) else name

    def _links(opts):
        return " · ".join(
            (f'<a class="watch-link" href="{html.escape(_safe_url(url), quote=True)}" target="_blank" rel="noopener">{html.escape(_label(name))}</a>'
             if _safe_url(url) else html.escape(_label(name)))
            for _, name, url in opts
        )
    total = len(availability.get("providers") or []) if verb == "Streaming" else len(availability.get("rent_providers") or [])
    more = " + more" if total > len(options) else ""
    picked = [sv for sv in (services or []) if sv in STREAMING_SERVICES]
    if picked and verb == "Streaming":
        mine = [o for o in options if any(_on_service(o[1], sv) for sv in picked)]
        rest = [o for o in options if o not in mine]
        if mine:
            return f"On your services: {_links(mine)}" + (f" · Also on: {_links(rest)}" if rest else "") + more
    return f"{verb}: {_links(options)}{more}"


def movie_on_services(availability, services):
    """True when a movie streams on one of the viewer's services (or on any service if none chosen)."""
    availability = availability or {}
    if not services:
        return availability.get("status") == "streaming"
    return any(_on_service(p, s) for p in (availability.get("providers") or []) for s in services)


def concise_availability_text(text, max_providers=2):
    """Keep watch availability complete and compact instead of visually truncating it."""
    text = " ".join(str(text or "").split()).strip()
    if not text or ":" not in text:
        return text
    label, providers = text.split(":", 1)
    parts = [p.strip(" .") for p in providers.split("·") if p.strip(" .")]
    # Preserve order while removing duplicate provider names.
    unique = []
    seen = set()
    for part in parts:
        key = part.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(part)
    if len(unique) <= max_providers:
        return f"{label.strip()}: " + " · ".join(unique)
    shown = " · ".join(unique[:max_providers])
    return f"{label.strip()}: {shown} + more"
