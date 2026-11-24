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
    "Apple TV+": ("appletvplus", "appletv"),      # Apple renamed it "Apple TV" in 2025; streaming lists only
    "Peacock": ("peacock",),
    "Paramount+": ("paramount",),
    "Free (Tubi, Pluto & more)": ("tubi", "pluto", "roku", "therokuchannel", "plex", "freevee",
                                  "amazonfreevee", "crackle", "kanopy", "hoopla"),
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


_CHANNEL = re.compile(r"\s+(?:basic\s+|standard\s+)?with\s+ads$|\s+(?:amazon|roku\s+premium|apple\s+tv)\s+channel$|\s+premium$",
                      re.IGNORECASE)


def clean_provider(name):
    """One name per service: "AMC+ Roku Premium Channel", "Netflix Standard with Ads" and "Kanopy (free with a
    library card)" read "AMC+", "Netflix" and "Kanopy"."""
    return _CHANNEL.sub("", re.sub(r"\s*\([^)]*\)", "", str(name or ""))).strip()


def unique_providers(names):
    """Cleaned provider names, duplicates dropped, order kept."""
    seen, out = set(), []
    for n in names or []:
        c = clean_provider(n)
        if c and c.casefold() not in seen:
            seen.add(c.casefold())
            out.append((c, n))
    return out


def _major(name):
    return any(_on_service(name, sv) for sv in STREAMING_SERVICES)


def watch_options(availability, title, services=None, limit=1):
    """[(label, provider, url)] for the best ways to watch: your services first, then the big services
    people recognise, then the rest. One name by default, so the line never wraps."""
    availability = availability or {}
    services = list(services or [])
    streaming = unique_providers(availability.get("providers"))
    renting = unique_providers(availability.get("rent_providers"))
    def order(items):
        mine = [x for x in items if services and any(_on_service(x[1], sv) for sv in services)]
        big = [x for x in items if x not in mine and _major(x[1])]
        return mine + big + [x for x in items if x not in mine and x not in big]
    chosen = [("Watch on", x) for x in order(streaming)[:limit]]
    if not chosen:
        chosen = [("Rent on", x) for x in renting[:limit]]
    return [(f"{verb} {name}", name, provider_watch_url(raw, title, availability)) for verb, (name, raw) in chosen]


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
        return f"{name} (library)" if key.startswith(("kanopy", "hoopla")) else name

    def _links(opts):
        return " · ".join(
            (f'<a class="watch-link" href="{html.escape(_safe_url(url), quote=True)}" target="_blank" rel="noopener">{html.escape(_label(name))}</a>'
             if _safe_url(url) else html.escape(_label(name)))
            for _, name, url in opts
        )
    total = len(unique_providers(availability.get("providers") if verb == "Streaming" else availability.get("rent_providers")))
    extra = max(0, total - len(options))
    page = _safe_url(availability.get("url"))
    # TMDB's watch page often lists nothing outside its own region; JustWatch's search always works.
    from urllib.parse import quote_plus as _qp
    page = f"https://www.justwatch.com/us/search?q={_qp(str(title))}" if title else page
    # "+ N more" opens the full where-to-watch page, so every option is one tap away.
    more = ("" if not extra else
            f' <a class="watch-link watch-more" href="{html.escape(page, quote=True)}" target="_blank" rel="noopener">+ {extra} more</a>'
            if page else f" + {extra} more")
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
