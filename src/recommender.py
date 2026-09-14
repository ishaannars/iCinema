
from collections import Counter
import math

GENRES = [
    "Action", "Adventure", "Anime", "Animation", "Comedy", "Documentary",
    "Drama", "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller"
]

MORE_OF_OPTIONS = [
    "Hidden Gems", "Critically Acclaimed", "Recent Releases",
    "International Films", "Classics", "Documentaries"
]

# Traits shown in the profile must come from actual movie tags or user controls.
PROFILE_TRAITS = {
    "Suspenseful", "Thought-provoking", "Character-driven", "Fast-paced",
    "Emotional", "Dark", "Funny", "Visually striking", "Cerebral",
    "Unpredictable", "Heartfelt", "Action-heavy", "Slow-burn", "Stylish",
    "Offbeat", "Romantic", "Intense", "Lighthearted", "Epic", "Grounded",
    "Psychological", "Adventurous", "Nostalgic", "Satirical", "Tense",
    "Moving", "Relaxed"
}

STARTER_MOVIES = [
    {"title":"Interstellar","year":2014,"genre":"Sci-Fi","imdb":8.7,"rt":73,"tags":["Sci-Fi","Drama","Thought-provoking","Emotional","Epic","Visually striking"]},
    {"title":"Parasite","year":2019,"genre":"Thriller","imdb":8.5,"rt":99,"tags":["Thriller","Drama","International","Dark","Suspenseful","Satirical","Unpredictable"]},
    {"title":"The Hangover","year":2009,"genre":"Comedy","imdb":7.7,"rt":79,"tags":["Comedy","Funny","Fast-paced","Lighthearted"]},
    {"title":"Get Out","year":2017,"genre":"Horror","imdb":7.8,"rt":98,"tags":["Thriller","Horror","Dark","Thought-provoking","Psychological","Suspenseful"]},
    {"title":"Whiplash","year":2014,"genre":"Drama","imdb":8.5,"rt":94,"tags":["Drama","Intense","Character-driven","Fast-paced","Critically Acclaimed"]},
    {"title":"The Godfather","year":1972,"genre":"Drama","imdb":9.2,"rt":97,"tags":["Drama","Classic","Dark","Character-driven","Slow-burn","Critically Acclaimed"]},
    {"title":"Arrival","year":2016,"genre":"Sci-Fi","imdb":7.9,"rt":94,"tags":["Sci-Fi","Drama","Emotional","Thought-provoking","Moving","Critically Acclaimed"]},
    {"title":"The Social Network","year":2010,"genre":"Drama","imdb":7.8,"rt":96,"tags":["Drama","Fast-paced","Character-driven","Critically Acclaimed"]},
    {"title":"Spirited Away","year":2001,"genre":"Anime","imdb":8.6,"rt":96,"tags":["Anime","Animation","International","Emotional","Visually striking","Adventurous"]},
    {"title":"The Dark Knight","year":2008,"genre":"Action","imdb":9.0,"rt":94,"tags":["Action","Drama","Dark","Intense","Action-heavy","Critically Acclaimed"]},
    {"title":"Knives Out","year":2019,"genre":"Mystery","imdb":7.9,"rt":97,"tags":["Mystery","Comedy","Funny","Unpredictable","Character-driven","Critically Acclaimed"]},
    {"title":"Oppenheimer","year":2023,"genre":"Drama","imdb":8.3,"rt":93,"tags":["Drama","Historical","Intense","Cerebral","Critically Acclaimed","Recent Release"]},
]

CATALOG = [
    {"title":"Prisoners","year":2013,"genre":"Thriller","imdb":8.2,"rt":81,"tags":["Thriller","Drama","Dark","Intense","Suspenseful","Psychological"],"why":"A detective searches for two missing girls while a desperate father takes matters into his own hands; the film builds pressure through dark, controlled visuals and a slow-burn sense of dread."},
    {"title":"Blade Runner 2049","year":2017,"genre":"Sci-Fi","imdb":8.0,"rt":88,"tags":["Sci-Fi","Thought-provoking","Visually striking","Slow-burn","Cerebral","Critically Acclaimed"],"why":"A replicant officer uncovers a secret that could reshape society; the film pairs a patient mystery with striking production design and carefully composed visuals."},
    {"title":"The Prestige","year":2006,"genre":"Mystery","imdb":8.5,"rt":77,"tags":["Mystery","Drama","Dark","Thought-provoking","Unpredictable","Cerebral"],"why":"Two rival magicians become consumed by outdoing one another; the story uses precise editing and layered reveals to turn obsession into a tightly constructed mystery."},
    {"title":"Nightcrawler","year":2014,"genre":"Thriller","imdb":7.8,"rt":95,"tags":["Thriller","Dark","Psychological","Character-driven","Satirical","Critically Acclaimed"],"why":"An ambitious outsider enters the world of late-night crime journalism; sharp nighttime photography and an unsettling lead performance give the film its cold, satirical edge."},
    {"title":"The Handmaiden","year":2016,"genre":"Thriller","imdb":8.1,"rt":96,"tags":["Thriller","International","Stylish","Unpredictable","Visually striking","Critically Acclaimed"],"why":"A con artist places a pickpocket inside a wealthy household as part of an elaborate scheme; lush production design and shifting perspectives make the thriller feel elegant and unpredictable."},
    {"title":"Past Lives","year":2023,"genre":"Drama","imdb":7.8,"rt":95,"tags":["Drama","Emotional","Character-driven","Moving","Grounded","Critically Acclaimed","Recent Release"],"why":"Two childhood friends reconnect years after their lives have taken different paths; restrained performances and quiet framing keep the focus on memory, timing, and connection."},
    {"title":"Anatomy of a Fall","year":2023,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","Mystery","International","Cerebral","Character-driven","Critically Acclaimed","Recent Release"],"why":"A writer is put on trial after her husband dies under suspicious circumstances; measured courtroom scenes and competing perspectives keep certainty just out of reach."},
    {"title":"Coherence","year":2013,"genre":"Sci-Fi","imdb":7.2,"rt":89,"tags":["Sci-Fi","Thriller","Hidden Gem","Thought-provoking","Unpredictable","Cerebral"],"why":"A dinner party begins to fracture after a strange event in the sky; the film turns a small setting into a tense science-fiction puzzle through uncertainty and escalating mistrust."},
    {"title":"The Invitation","year":2015,"genre":"Thriller","imdb":6.6,"rt":89,"tags":["Thriller","Dark","Hidden Gem","Slow-burn","Suspenseful","Psychological"],"why":"A man attends a dinner hosted by his former partner and begins to suspect something is wrong; patient pacing and restrained tension gradually make the gathering feel threatening."},
    {"title":"Victoria","year":2015,"genre":"Drama","imdb":7.6,"rt":82,"tags":["Drama","International","Hidden Gem","Intense","Fast-paced","Grounded"],"why":"A young woman in Berlin gets pulled into a dangerous night with a group of strangers; the single-take approach gives the film an immediate, real-time intensity."},
    {"title":"The Guilty","year":2018,"genre":"Thriller","imdb":7.5,"rt":98,"tags":["Thriller","International","Hidden Gem","Suspenseful","Psychological","Critically Acclaimed"],"why":"A police dispatcher receives a disturbing emergency call and tries to help from behind a desk; the confined setting creates tension almost entirely through sound, performance, and inference."},
    {"title":"Perfect Days","year":2023,"genre":"Drama","imdb":7.9,"rt":96,"tags":["Drama","International","Grounded","Relaxed","Character-driven","Critically Acclaimed","Recent Release"],"why":"A Tokyo cleaner finds meaning in a simple daily routine; calm observation and careful composition turn ordinary moments into a reflective character study."},
    {"title":"Hunt for the Wilderpeople","year":2016,"genre":"Comedy","imdb":7.8,"rt":97,"tags":["Comedy","Adventure","Funny","Heartfelt","Offbeat","Critically Acclaimed"],"why":"A rebellious boy and his foster uncle become the targets of a national search in the New Zealand bush; playful pacing and warm character comedy keep the adventure light on its feet."},
    {"title":"The Worst Person in the World","year":2021,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","International","Emotional","Character-driven","Romantic","Critically Acclaimed"],"why":"A young woman moves through relationships, work, and uncertainty in Oslo; fluid chapter-based storytelling gives the film an intimate, observant view of adulthood."},
    {"title":"Free Solo","year":2018,"genre":"Documentary","imdb":8.1,"rt":97,"tags":["Documentary","Intense","Tense","Adventurous","Critically Acclaimed"],"why":"Climber Alex Honnold prepares to scale El Capitan without ropes; expansive photography and close observational filmmaking make the physical risk feel immediate."},
    {"title":"Memories of Murder","year":2003,"genre":"Thriller","imdb":8.1,"rt":95,"tags":["Thriller","International","Dark","Character-driven","Suspenseful","Critically Acclaimed"],"why":"Detectives struggle to solve a series of murders in rural South Korea; the film mixes procedural tension, dark humor, and carefully controlled framing to create lasting unease."},
    {"title":"Ex Machina","year":2014,"genre":"Sci-Fi","imdb":7.7,"rt":92,"tags":["Sci-Fi","Thought-provoking","Cerebral","Psychological","Stylish","Critically Acclaimed"],"why":"A programmer is invited to evaluate a highly advanced artificial intelligence; sleek production design and intimate staging turn the experiment into a psychological contest."},
    {"title":"Enemy","year":2013,"genre":"Mystery","imdb":6.9,"rt":72,"tags":["Mystery","Dark","Psychological","Cerebral","Hidden Gem"],"why":"A professor discovers a man who looks exactly like him and becomes obsessed with finding answers; muted imagery and surreal repetition make the mystery deliberately unsettling."},
    {"title":"Burning","year":2018,"genre":"Drama","imdb":7.5,"rt":95,"tags":["Drama","International","Slow-burn","Psychological","Suspenseful","Critically Acclaimed"],"why":"A young man grows suspicious of a wealthy stranger connected to someone he cares about; long takes and patient ambiguity turn everyday interactions into quiet tension."},
    {"title":"Incendies","year":2010,"genre":"Drama","imdb":8.3,"rt":91,"tags":["Drama","International","Dark","Emotional","Intense","Critically Acclaimed"],"why":"Twins follow their late mother’s instructions and uncover a hidden family history; stark imagery and a carefully structured narrative build toward devastating revelations."},
    {"title":"The Lives of Others","year":2006,"genre":"Drama","imdb":8.4,"rt":92,"tags":["Drama","International","Thought-provoking","Character-driven","Slow-burn","Critically Acclaimed"],"why":"An East German surveillance officer becomes increasingly affected by the lives he is monitoring; controlled framing and quiet performances make the moral shift feel gradual and personal."},
    {"title":"A Separation","year":2011,"genre":"Drama","imdb":8.3,"rt":99,"tags":["Drama","International","Grounded","Character-driven","Thought-provoking","Critically Acclaimed"],"why":"A family dispute grows into a larger conflict involving responsibility and truth; naturalistic performances and close observation keep every side understandable."},
    {"title":"The Wailing","year":2016,"genre":"Horror","imdb":7.4,"rt":99,"tags":["Horror","Thriller","International","Dark","Hidden Gem","Unpredictable"],"why":"A rural policeman investigates a wave of disturbing events after a stranger arrives in town; the film mixes mystery, horror, and dark humor while steadily increasing uncertainty."},
    {"title":"Train to Busan","year":2016,"genre":"Horror","imdb":7.6,"rt":95,"tags":["Horror","Action","International","Intense","Fast-paced","Emotional","Critically Acclaimed"],"why":"Passengers fight to survive a fast-moving outbreak aboard a train; energetic staging and emotional character beats keep the action tense without losing its human stakes."},
    {"title":"Your Name","year":2016,"genre":"Anime","imdb":8.4,"rt":98,"tags":["Anime","Animation","Romance","Emotional","Moving","Visually striking","International","Critically Acclaimed"],"why":"Two teenagers discover a mysterious connection that crosses distance and time; detailed animation and expressive color give the romance a sweeping visual scale."},
    {"title":"Princess Mononoke","year":1997,"genre":"Anime","imdb":8.3,"rt":93,"tags":["Anime","Animation","Fantasy","Adventure","International","Epic","Thought-provoking","Classic"],"why":"A young warrior becomes caught between industrial expansion and the spirits of the forest; large-scale animation and morally complex characters give the fantasy unusual weight."},
    {"title":"Akira","year":1988,"genre":"Anime","imdb":8.0,"rt":91,"tags":["Anime","Animation","Sci-Fi","Dark","Classic","International","Visually striking","Intense"],"why":"A biker gang is pulled into a government experiment in a futuristic Tokyo; dense hand-drawn detail and kinetic movement make the city feel volatile and alive."},
    {"title":"The Holdovers","year":2023,"genre":"Drama","imdb":7.9,"rt":97,"tags":["Drama","Comedy","Emotional","Heartfelt","Character-driven","Critically Acclaimed","Recent Release"],"why":"A strict teacher, a troubled student, and a school cook spend the holidays together on an empty campus; warm performances and period detail give the story an understated emotional pull."},
    {"title":"Dune: Part Two","year":2024,"genre":"Sci-Fi","imdb":8.4,"rt":92,"tags":["Sci-Fi","Adventure","Epic","Visually striking","Intense","Critically Acclaimed","Recent Release"],"why":"Paul Atreides joins the Fremen as the conflict over Arrakis intensifies; massive landscapes, precise sound design, and disciplined visual scale make the story feel monumental."},
    {"title":"No Country for Old Men","year":2007,"genre":"Thriller","imdb":8.2,"rt":93,"tags":["Thriller","Drama","Dark","Tense","Slow-burn","Critically Acclaimed","Classic"],"why":"A man who finds drug money becomes the target of a relentless killer; spare dialogue and patient framing let tension build from silence as much as action."},
    {"title":"Mulholland Drive","year":2001,"genre":"Mystery","imdb":7.9,"rt":84,"tags":["Mystery","Psychological","Cerebral","Unpredictable","Classic"],"why":"An aspiring actress becomes entangled in an amnesiac woman’s search for identity; dreamlike editing and shifting reality turn Hollywood into a deliberately unstable mystery."},
    {"title":"The Truman Show","year":1998,"genre":"Drama","imdb":8.2,"rt":94,"tags":["Drama","Comedy","Thought-provoking","Heartfelt","Critically Acclaimed","Classic"],"why":"A man slowly realizes his entire life may be a television production; accessible comedy and carefully controlled artificiality sharpen the film’s ideas about privacy and identity."},
    {"title":"Before Sunrise","year":1995,"genre":"Romance","imdb":8.1,"rt":100,"tags":["Romance","Drama","Emotional","Romantic","Character-driven","Classic","Critically Acclaimed"],"why":"Two strangers meet on a train and spend one night walking through Vienna; long conversational scenes and natural performances make the romance feel immediate and lived-in."},
    {"title":"The Grand Budapest Hotel","year":2014,"genre":"Comedy","imdb":8.1,"rt":92,"tags":["Comedy","Adventure","Stylish","Funny","Visually striking","Critically Acclaimed"],"why":"A hotel concierge and his lobby boy are pulled into a dispute over a valuable painting; symmetrical framing, precise color, and rapid comic timing create a highly controlled visual style."},
    {"title":"The Rescue","year":2021,"genre":"Documentary","imdb":8.3,"rt":96,"tags":["Documentary","Intense","Tense","Critically Acclaimed"],"why":"Rescuers attempt to save a youth soccer team trapped inside a flooded cave; clear reconstruction and firsthand footage turn a complex operation into a gripping survival story."},
    {"title":"Searching for Sugar Man","year":2012,"genre":"Documentary","imdb":8.2,"rt":95,"tags":["Documentary","Hidden Gem","Moving","Unpredictable","Critically Acclaimed"],"why":"Two fans investigate what happened to a little-known musician who became an unexpected icon overseas; the documentary unfolds like a mystery while keeping the focus on music and rediscovery."},
    {"title":"Jiro Dreams of Sushi","year":2011,"genre":"Documentary","imdb":7.8,"rt":99,"tags":["Documentary","International","Character-driven","Grounded","Critically Acclaimed"],"why":"The film follows master sushi chef Jiro Ono and the discipline behind his craft; clean observational filmmaking keeps attention on repetition, precision, and family legacy."},
]

ALL_MOVIES = STARTER_MOVIES + CATALOG
MOVIE_INDEX = {m["title"]: m for m in ALL_MOVIES}


def get_movie(title, extra_movies=None):
    if extra_movies and title in extra_movies:
        return extra_movies[title]
    return MOVIE_INDEX.get(title)


def searchable_titles():
    return sorted(MOVIE_INDEX.keys())


# Explicit feature weights keep the model interpretable and make the effect of
# each behavioral signal reproducible. Favorites remain 3x a standard Like.
SIGNAL_WEIGHTS = {
    "like": 1.0,
    "favorite": 3.0,
    "selected_genre": 4.0,
    "saved": 2.5,
    "seen": 0.5,
    "skip": -2.5,
}


def get_movie(title, extra_movies=None):
    if extra_movies and title in extra_movies:
        return extra_movies[title]
    return MOVIE_INDEX.get(title)


def searchable_titles():
    return sorted(MOVIE_INDEX.keys())


def _movie_signal(movie, weight, trait_counts, genre_counts):
    """Project one movie into interpretable genre + trait feature spaces."""
    genre = movie.get("genre")
    if genre:
        genre_counts[genre] += weight
    for tag in movie.get("tags", []):
        if tag in PROFILE_TRAITS:
            trait_counts[tag] += weight


def _positive_items(counter):
    return [(k, float(v)) for k, v in counter.items() if float(v) > 0]


def _nonzero_items(counter):
    return [(k, float(v)) for k, v in counter.items() if float(v) != 0.0]


def build_profile(
    likes,
    favorites,
    selected_genres,
    review_priority,
    more_of,
    saved_titles=None,
    skipped_titles=None,
    adventure=50,
    extra_movies=None,
    seen_titles=None,
):
    """Build a weighted behavioral feature profile.

    Browser-local history is not just restored for display. Saved, Seen, and Skip
    history is re-projected into the same feature vectors every time the profile is
    rebuilt, so returning users immediately resume with the model they trained.
    """
    saved_titles = set(saved_titles or [])
    skipped_titles = set(skipped_titles or [])
    seen_titles = set(seen_titles or [])
    extra_movies = extra_movies or {}
    likes = set(likes or [])
    favorites = set(favorites or [])

    def lookup(title):
        return extra_movies.get(title) or MOVIE_INDEX.get(title)

    traits = Counter()
    genres = Counter()

    # Explicit onboarding feedback. A Favorite is intentionally 3x a Like.
    for title in likes | favorites:
        movie = lookup(title)
        if not movie:
            continue
        weight = SIGNAL_WEIGHTS["favorite"] if title in favorites else SIGNAL_WEIGHTS["like"]
        _movie_signal(movie, weight, traits, genres)

    # Direct preference controls are strong priors before behavior accumulates.
    for genre in selected_genres or []:
        genres[genre] += SIGNAL_WEIGHTS["selected_genre"]

    # Persistent behavioral feedback. These sets are restored from localStorage.
    for title in saved_titles:
        movie = lookup(title)
        if movie:
            _movie_signal(movie, SIGNAL_WEIGHTS["saved"], traits, genres)

    # Seen is deliberately weak: viewing history is evidence of exposure, not proof
    # of preference. It nudges the model without overpowering explicit feedback.
    for title in seen_titles:
        movie = lookup(title)
        if movie:
            _movie_signal(movie, SIGNAL_WEIGHTS["seen"], traits, genres)

    # Skip is negative evidence in both feature spaces, not merely a UI exclusion.
    for title in skipped_titles:
        movie = lookup(title)
        if movie:
            _movie_signal(movie, SIGNAL_WEIGHTS["skip"], traits, genres)

    # Keep both signed and positive views. The signed vectors are used by ranking,
    # so repeated skips actively push similar candidates down instead of merely
    # disappearing from the visible profile summary.
    signed_trait_scores = dict(_nonzero_items(traits))
    signed_genre_scores = dict(_nonzero_items(genres))
    trait_scores = sorted(_positive_items(traits), key=lambda x: (-x[1], x[0]))
    genre_scores = sorted(_positive_items(genres), key=lambda x: (-x[1], x[0]))

    top_traits = [t for t, _ in trait_scores[:3]] or ["Story-driven"]
    top_genres = [g for g, _ in genre_scores[:3]] or ["Drama"]

    matters = []
    if review_priority <= 35:
        matters.append("Strong reviews")
    elif review_priority >= 65:
        matters.append("Entertainment value")
    else:
        matters.append("A balance of reviews and entertainment")

    if trait_scores:
        strongest = trait_scores[0][0]
        if strongest in {"Character-driven", "Emotional", "Heartfelt", "Moving", "Grounded"}:
            matters.append("Character and story")
        elif strongest in {"Suspenseful", "Tense", "Psychological", "Unpredictable"}:
            matters.append("Tension and suspense")
        elif strongest in {"Visually striking", "Stylish", "Epic"}:
            matters.append("Strong visual style")
        elif strongest in {"Thought-provoking", "Cerebral"}:
            matters.append("Ideas and complexity")
        elif strongest in {"Funny", "Lighthearted", "Offbeat"}:
            matters.append("Humor and personality")

    priorities = list((more_of or [])[:4]) if more_of else ["Balanced recommendations"]

    patterns = []
    if any(t in top_traits for t in ["Suspenseful", "Tense", "Psychological", "Dark"]):
        patterns.append("Leans toward higher-tension stories")
    if any(t in top_traits for t in ["Character-driven", "Emotional", "Heartfelt", "Moving"]):
        patterns.append("Responds to character-focused stories")
    if any(t in top_traits for t in ["Thought-provoking", "Cerebral", "Unpredictable"]):
        patterns.append("Likes stories that reward attention")
    if any(t in top_traits for t in ["Funny", "Lighthearted", "Offbeat"]):
        patterns.append("Enjoys humor and lighter energy")
    if any(t in top_traits for t in ["Visually striking", "Stylish", "Epic"]):
        patterns.append("Notices strong visual presentation")
    if not patterns:
        patterns.append("Shows a broad viewing range")

    if adventure <= 30:
        adventure_text = "Mostly familiar"
    elif adventure >= 70:
        adventure_text = "Open to unexpected picks"
    else:
        adventure_text = "Balanced between familiar and new"

    if review_priority <= 35:
        review_text = "Reviews matter a lot"
    elif review_priority >= 65:
        review_text = "Entertainment comes first"
    else:
        review_text = "Reviews and enjoyment are balanced"

    balance = [adventure_text, review_text]

    trait_text = ", ".join(t.lower() for t in top_traits[:2])
    genre_text = " and ".join(top_genres[:2]).lower()
    if top_traits and top_traits[0] != "Story-driven":
        summary = f"You favor {trait_text} {genre_text} titles that match the priorities you selected."
    else:
        summary = f"You favor {genre_text} titles that match the priorities you selected."

    return {
        "traits": top_traits,
        "genres": top_genres,
        "matters": matters[:3],
        "priorities": priorities,
        "patterns": patterns[:3],
        "balance": balance,
        "summary": summary,
        "trait_scores": dict(trait_scores),
        "genre_scores": dict(genre_scores),
        "signed_trait_scores": signed_trait_scores,
        "signed_genre_scores": signed_genre_scores,
        "controls": {
            "review_priority": int(review_priority),
            "adventure": int(adventure),
            "selected_genres": list(selected_genres or []),
            "priorities": list(more_of or []),
        },
        "model_version": "v2-full-signal",
        "behavior_counts": {
            "liked": len(likes - favorites),
            "favorited": len(favorites),
            "saved": len(saved_titles),
            "seen": len(seen_titles),
            "skipped": len(skipped_titles),
        },
    }


def _num(value, default=0.0):
    try:
        return float(value) if value is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _signed_cosine(user_scores, movie_features):
    """Cosine similarity in a signed feature space, mapped from [-1, 1] to [0, 1]."""
    if not user_scores or not movie_features:
        return 0.5
    keys = set(user_scores) | set(movie_features)
    dot = sum(float(user_scores.get(k, 0.0)) * float(movie_features.get(k, 0.0)) for k in keys)
    u_norm = math.sqrt(sum(float(user_scores.get(k, 0.0)) ** 2 for k in keys))
    m_norm = math.sqrt(sum(float(movie_features.get(k, 0.0)) ** 2 for k in keys))
    if not u_norm or not m_norm:
        return 0.5
    cosine = max(-1.0, min(1.0, dot / (u_norm * m_norm)))
    return (cosine + 1.0) / 2.0


def _content_signals(movie, profile):
    """Genre + semantic-trait affinity using the full signed behavioral profile."""
    signed_genres = profile.get("signed_genre_scores") or profile.get("genre_scores", {}) or {}
    signed_traits = profile.get("signed_trait_scores") or profile.get("trait_scores", {}) or {}

    movie_genres = {}
    primary = movie.get("genre")
    if primary:
        movie_genres[primary] = 1.0
    # TMDB tags can contain additional genres. Give them lower weight than primary genre.
    for tag in movie.get("tags", []):
        if tag in GENRES and tag != primary:
            movie_genres[tag] = max(movie_genres.get(tag, 0.0), 0.65)

    movie_traits = {tag: 1.0 for tag in movie.get("tags", []) if tag in PROFILE_TRAITS}
    genre_affinity = _signed_cosine(signed_genres, movie_genres)
    trait_affinity = _signed_cosine(signed_traits, movie_traits)
    return genre_affinity, trait_affinity


def _quality_signal(movie, review_priority):
    """Continuously blend critic and audience evidence with confidence shrinkage."""
    rt = _num(movie.get("rt"), -1)
    imdb = _num(movie.get("imdb"), -1)
    tmdb_vote = _num(movie.get("tmdb_vote"), -1)
    vote_count = max(0.0, _num(movie.get("tmdb_vote_count"), 0.0))

    critic = rt / 100.0 if rt >= 0 else None
    audience_values = []
    if imdb >= 0:
        audience_values.append(imdb / 10.0)
    if tmdb_vote >= 0:
        audience_values.append(tmdb_vote / 10.0)
    audience = sum(audience_values) / len(audience_values) if audience_values else None

    if critic is None and audience is None:
        observed = 0.5
    elif critic is None:
        observed = audience
    elif audience is None:
        observed = critic
    else:
        # Step 2 prompt is directly embedded: 0 = reviews first, 100 = enjoyment first.
        audience_weight = max(0.0, min(1.0, float(review_priority) / 100.0))
        observed = critic * (1.0 - audience_weight) + audience * audience_weight

    # TMDB vote_count is used as a reliability feature. Sparse titles are gently
    # shrunk toward neutral rather than being allowed to dominate on a tiny sample.
    confidence = 1.0 - math.exp(-vote_count / 450.0) if vote_count else (0.72 if imdb >= 0 or rt >= 0 else 0.0)
    return max(0.0, min(1.0, 0.5 + (float(observed) - 0.5) * confidence))


def _priority_signal(movie, profile):
    """Directly encode every Step 3 card selection as a candidate feature."""
    tags = set(movie.get("tags", []))
    priorities = set(profile.get("controls", {}).get("priorities") or profile.get("priorities", []))
    priorities.discard("Balanced recommendations")
    if not priorities:
        return 0.5

    year = int(_num(movie.get("year")))
    popularity = max(0.0, _num(movie.get("popularity"), 0.0))
    tests = {
        "International Films": "International" in tags or str(movie.get("original_language") or "en").lower() != "en",
        "Hidden Gems": "Hidden Gem" in tags or (0 < popularity < 28),
        "Critically Acclaimed": "Critically Acclaimed" in tags or _num(movie.get("rt"), -1) >= 90 or _num(movie.get("imdb"), -1) >= 8.0,
        "Recent Releases": "Recent Release" in tags or year >= 2023,
        "Classics": "Classic" in tags or (0 < year <= 2005),
        "Documentaries": movie.get("genre") == "Documentary" or "Documentary" in tags,
    }
    values = [1.0 if tests.get(priority, False) else 0.0 for priority in priorities if priority in tests]
    return sum(values) / len(values) if values else 0.5


def _discovery_signal(movie, profile, adventure):
    """Use Step 2 openness across genre novelty, language, popularity and age."""
    openness = max(0.0, min(1.0, float(adventure) / 100.0))
    preferred_genres = set(profile.get("controls", {}).get("selected_genres") or profile.get("genres", []))
    familiar_genre = movie.get("genre") in preferred_genres
    genre_novelty = 0.0 if familiar_genre else 1.0

    language_novelty = 1.0 if str(movie.get("original_language") or "en").lower() not in {"", "en"} else 0.0
    popularity = max(0.0, _num(movie.get("popularity"), 0.0))
    # Lower-popularity titles are a discovery signal, but cap the effect so obscure
    # metadata never overwhelms actual preference similarity.
    popularity_novelty = 1.0 / (1.0 + popularity / 35.0) if popularity else 0.45
    year = int(_num(movie.get("year"), 0))
    era_novelty = 1.0 if year and (year <= 2005 or year >= 2023) else 0.35

    novelty = 0.52 * genre_novelty + 0.20 * language_novelty + 0.18 * popularity_novelty + 0.10 * era_novelty
    familiarity = 1.0 - novelty
    return max(0.0, min(1.0, openness * novelty + (1.0 - openness) * familiarity))


def score_movie_components(movie, profile, adventure, review_priority):
    """Return the full, inspectable feature decomposition for one candidate."""
    genre_affinity, trait_affinity = _content_signals(movie, profile)
    quality = _quality_signal(movie, review_priority)
    discovery = _discovery_signal(movie, profile, adventure)
    priority = _priority_signal(movie, profile)

    # Every onboarding prompt and behavioral action reaches one of these components.
    # The calculation is intentionally local and O(features), so adding data depth does
    # not add network latency to each recommendation render.
    components = {
        "genre_affinity": genre_affinity,
        "trait_affinity": trait_affinity,
        "quality_alignment": quality,
        "discovery_alignment": discovery,
        "priority_alignment": priority,
    }
    raw = (
        0.22 * genre_affinity
        + 0.20 * trait_affinity
        + 0.23 * quality
        + 0.17 * discovery
        + 0.18 * priority
    )
    components["raw_score"] = max(0.0, min(1.0, raw))
    return components


def score_movie(movie, profile, adventure, review_priority):
    """Calibrate the full-signal model to iCinema's consumer-facing match percent."""
    raw = score_movie_components(movie, profile, adventure, review_priority)["raw_score"]
    calibrated = 55.0 + (43.0 * raw)
    return int(round(max(55.0, min(98.0, calibrated))))


def rank_movies(movies, profile, adventure, review_priority, excluded=None, limit=None):
    """Rank any candidate pool with the same weighted personalization model."""
    excluded = set(excluded or [])
    scored = []
    seen_keys = set()
    for movie in movies:
        if not movie or movie.get("title") in excluded:
            continue
        key = (str(movie.get("title", "")).casefold(), int(movie.get("year") or 0))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        scored.append((score_movie(movie, profile, adventure, review_priority), movie))
    scored.sort(
        key=lambda x: (
            x[0],
            _quality_signal(x[1], review_priority),
            _num(x[1].get("tmdb_vote")),
        ),
        reverse=True,
    )
    return scored if limit is None else scored[:limit]


def recommend(profile, adventure, review_priority, excluded=None, limit=16):
    return rank_movies(CATALOG, profile, adventure, review_priority, excluded, limit)
