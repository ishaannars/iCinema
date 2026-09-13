
from collections import Counter

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


def get_movie(title):
    return MOVIE_INDEX.get(title)


def searchable_titles():
    return sorted(MOVIE_INDEX.keys())


def _movie_signal(movie, weight, trait_counts, genre_counts):
    genre_counts[movie["genre"]] += weight
    for tag in movie.get("tags", []):
        if tag in PROFILE_TRAITS:
            trait_counts[tag] += weight


def build_profile(likes, favorites, selected_genres, review_priority, more_of, saved_titles=None, skipped_titles=None, adventure=45):
    saved_titles = saved_titles or set()
    skipped_titles = skipped_titles or set()

    traits = Counter()
    genres = Counter()
    negative_traits = Counter()

    # Likes/favorites
    for title in likes:
        movie = MOVIE_INDEX.get(title)
        if not movie:
            continue
        weight = 3 if title in favorites else 1
        _movie_signal(movie, weight, traits, genres)

    # Directly selected genres matter strongly.
    for genre in selected_genres:
        genres[genre] += 4

    # Saved titles refine the profile.
    for title in saved_titles:
        movie = MOVIE_INDEX.get(title)
        if movie:
            _movie_signal(movie, 2, traits, genres)

    # Skipped titles reduce matching traits.
    for title in skipped_titles:
        movie = MOVIE_INDEX.get(title)
        if not movie:
            continue
        for tag in movie.get("tags", []):
            if tag in PROFILE_TRAITS:
                negative_traits[tag] += 2

    trait_scores = []
    for trait, count in traits.items():
        score = count - negative_traits.get(trait, 0)
        if score > 0:
            trait_scores.append((trait, score))
    trait_scores.sort(key=lambda x: (-x[1], x[0]))

    top_traits = [t for t, _ in trait_scores[:3]]
    if not top_traits:
        top_traits = ["Story-driven"]

    top_genres = [g for g, _ in genres.most_common(3)]
    if not top_genres:
        top_genres = ["Drama"]

    # What matters most is derived only from controls / observed ratings preference.
    matters = []
    if review_priority <= 35:
        matters.append("Strong reviews")
    elif review_priority >= 65:
        matters.append("Entertainment value")
    else:
        matters.append("A balance of reviews and entertainment")

    # Add evidence-backed preference from repeated movie traits.
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

    # Step 3 is explicitly a recommendation priority.
    priorities = list(more_of[:4]) if more_of else ["Balanced recommendations"]

    # Analytical section 1: viewing patterns from repeated evidence.
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

    # Analytical section 2: direct slider interpretation.
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

    # Natural-language summary generated from strongest real signals.
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
    }


def score_movie(movie, profile, adventure, review_priority):
    score = 68.0
    tags = set(movie.get("tags", []))

    if movie["genre"] in profile["genres"]:
        score += 9

    for trait in profile["traits"]:
        if trait in tags:
            score += 5

    if review_priority <= 35 and movie.get("rt", 0) >= 90:
        score += 5

    if "International Films" in profile["priorities"] and "International" in tags:
        score += 5
    if "Hidden Gems" in profile["priorities"] and "Hidden Gem" in tags:
        score += 5
    if "Critically Acclaimed" in profile["priorities"] and "Critically Acclaimed" in tags:
        score += 5
    if "Recent Releases" in profile["priorities"] and "Recent Release" in tags:
        score += 5
    if "Classics" in profile["priorities"] and "Classic" in tags:
        score += 5
    if "Documentaries" in profile["priorities"] and movie["genre"] == "Documentary":
        score += 5

    if adventure >= 70 and movie["genre"] not in profile["genres"]:
        score += 4

    return max(72, min(98, int(round(score))))


def recommend(profile, adventure, review_priority, excluded=None, limit=16):
    excluded = set(excluded or [])
    scored = []
    for movie in CATALOG:
        if movie["title"] in excluded:
            continue
        scored.append((score_movie(movie, profile, adventure, review_priority), movie))
    scored.sort(key=lambda x: (x[0], x[1].get("rt", 0), x[1].get("imdb", 0)), reverse=True)
    return [(score, movie) for score, movie in scored[:limit]]
