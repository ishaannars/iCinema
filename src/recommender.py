
from collections import Counter

STARTER_MOVIES = [
    {"title":"Interstellar","year":2014,"genre":"Sci-Fi","tags":["Sci-Fi","Drama","Atmospheric","Thought-provoking"]},
    {"title":"Parasite","year":2019,"genre":"Thriller","tags":["Thriller","Drama","International","Dark"]},
    {"title":"The Hangover","year":2009,"genre":"Comedy","tags":["Comedy","Funny","Entertaining"]},
    {"title":"Get Out","year":2017,"genre":"Horror","tags":["Thriller","Horror","Dark","Thought-provoking"]},
    {"title":"Whiplash","year":2014,"genre":"Drama","tags":["Drama","Intense","Critically Acclaimed"]},
    {"title":"The Godfather","year":1972,"genre":"Crime","tags":["Crime","Drama","Classic","Critically Acclaimed"]},
    {"title":"Arrival","year":2016,"genre":"Sci-Fi","tags":["Sci-Fi","Drama","Emotional","Atmospheric"]},
    {"title":"The Social Network","year":2010,"genre":"Drama","tags":["Drama","Fast-paced","Critically Acclaimed"]},
    {"title":"Spirited Away","year":2001,"genre":"Animation","tags":["Animation","International","Emotional"]},
    {"title":"The Dark Knight","year":2008,"genre":"Action","tags":["Action","Crime","Dark","Critically Acclaimed"]},
    {"title":"Knives Out","year":2019,"genre":"Mystery","tags":["Mystery","Comedy","Entertaining"]},
    {"title":"Oppenheimer","year":2023,"genre":"Drama","tags":["Drama","Historical","Intense","Critically Acclaimed"]},
]

SHOWROOM_ROWS = {
    "Top Matches for You": [
        {"title":"Prisoners","year":2013,"genre":"Thriller","imdb":8.2,"rt":81,"tags":["Thriller","Drama","Dark","Intense"],"why":"A tense, character-driven thriller with strong atmosphere."},
        {"title":"Blade Runner 2049","year":2017,"genre":"Sci-Fi","imdb":8.0,"rt":88,"tags":["Sci-Fi","Atmospheric","Thought-provoking","Critically Acclaimed"],"why":"Visually ambitious science fiction with a patient, immersive tone."},
        {"title":"The Prestige","year":2006,"genre":"Mystery","imdb":8.5,"rt":77,"tags":["Mystery","Drama","Dark","Thought-provoking"],"why":"A layered story built around obsession, rivalry, and reveal."},
        {"title":"Nightcrawler","year":2014,"genre":"Thriller","imdb":7.8,"rt":95,"tags":["Thriller","Dark","Critically Acclaimed"],"why":"A sharp, unsettling thriller with a distinctive point of view."},
    ],
    "Critically Acclaimed": [
        {"title":"The Handmaiden","year":2016,"genre":"Thriller","imdb":8.1,"rt":96,"tags":["Thriller","International","Critically Acclaimed","Atmospheric"],"why":"A stylish international thriller with strong critical reception."},
        {"title":"The Banshees of Inisherin","year":2022,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","Dark","Critically Acclaimed"],"why":"Character-focused drama with dark humor and precise filmmaking."},
        {"title":"Past Lives","year":2023,"genre":"Drama","imdb":7.8,"rt":95,"tags":["Drama","Emotional","Critically Acclaimed"],"why":"A restrained, emotionally focused story with exceptional reviews."},
        {"title":"Anatomy of a Fall","year":2023,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","Mystery","International","Critically Acclaimed"],"why":"A cerebral courtroom drama driven by ambiguity and performance."},
    ],
    "Hidden Gems": [
        {"title":"Coherence","year":2013,"genre":"Sci-Fi","imdb":7.2,"rt":89,"tags":["Sci-Fi","Thriller","Hidden Gem","Thought-provoking"],"why":"Low-budget science fiction built around a clever high-concept premise."},
        {"title":"The Invitation","year":2015,"genre":"Thriller","imdb":6.6,"rt":89,"tags":["Thriller","Dark","Hidden Gem"],"why":"A slow-building psychological thriller with escalating tension."},
        {"title":"Victoria","year":2015,"genre":"Crime","imdb":7.6,"rt":82,"tags":["Crime","International","Hidden Gem","Intense"],"why":"An intense real-time crime drama known for its single-take execution."},
        {"title":"The Guilty","year":2018,"genre":"Thriller","imdb":7.5,"rt":98,"tags":["Thriller","International","Hidden Gem","Critically Acclaimed"],"why":"A tightly contained thriller carried by voice, tension, and inference."},
    ],
    "Something Different": [
        {"title":"Perfect Days","year":2023,"genre":"Drama","imdb":7.9,"rt":96,"tags":["Drama","International","Relaxing","Critically Acclaimed"],"why":"A quieter, reflective film that expands beyond high-intensity picks."},
        {"title":"Hunt for the Wilderpeople","year":2016,"genre":"Comedy","imdb":7.8,"rt":97,"tags":["Comedy","Adventure","Funny","Critically Acclaimed"],"why":"Warm, funny, and highly rated without leaning on familiar thriller beats."},
        {"title":"The Worst Person in the World","year":2021,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","International","Emotional","Critically Acclaimed"],"why":"A modern character study with emotional range and strong reviews."},
        {"title":"Free Solo","year":2018,"genre":"Documentary","imdb":8.1,"rt":97,"tags":["Documentary","Intense","Critically Acclaimed"],"why":"A documentary that delivers genuine tension without fictional stakes."},
    ],
}

def build_profile(likes, favorites, moods, review_priority, more_of):
    chosen = [m for m in STARTER_MOVIES if m["title"] in likes or m["title"] in favorites]
    tags = Counter()
    genres = Counter()
    for movie in chosen:
        weight = 2 if movie["title"] in favorites else 1
        genres[movie["genre"]] += weight
        for tag in movie["tags"]:
            tags[tag] += weight

    for mood in moods:
        tags[mood] += 2

    top_genres = [g for g,_ in genres.most_common(3)]
    if len(top_genres) < 3:
        for g in ["Thriller","Sci-Fi","Drama"]:
            if g not in top_genres:
                top_genres.append(g)
            if len(top_genres) == 3:
                break

    style_candidates = [
        x for x,_ in tags.most_common()
        if x not in top_genres and x not in ["Critically Acclaimed","International","Hidden Gem","Classic","Documentary"]
    ]
    lean = style_candidates[:3]
    for x in ["Intense","Atmospheric","Thought-provoking"]:
        if len(lean) >= 3: break
        if x not in lean: lean.append(x)

    stands_out = ["Strong storytelling", "Distinctive filmmaking"]
    if review_priority < 55:
        stands_out.insert(1, "High critical reception")
    else:
        stands_out.insert(1, "Immediate entertainment value")

    drawn_to = more_of[:3] if more_of else ["Hidden Gems","Critically Acclaimed","International Films"]

    summary = "You favor well-crafted films with strong atmosphere and compelling stories."
    if "Funny" in moods:
        summary = "You favor polished films that balance strong storytelling with an entertaining tone."
    elif "Relaxing" in moods:
        summary = "You favor thoughtful, well-crafted films with an immersive and measured tone."

    return {
        "lean": lean,
        "genres": top_genres,
        "stands_out": stands_out,
        "drawn_to": drawn_to,
        "summary": summary,
    }

def score_movie(movie, profile, adventure, review_priority):
    score = 70
    profile_terms = set(profile["lean"] + profile["genres"])
    overlap = len(profile_terms.intersection(set(movie["tags"])))
    score += overlap * 5
    if movie["rt"] >= 90 and review_priority < 55:
        score += 5
    if "International" in movie["tags"] and "International Films" in profile["drawn_to"]:
        score += 3
    if "Hidden Gem" in movie["tags"] and "Hidden Gems" in profile["drawn_to"]:
        score += 3
    if adventure > 65 and movie["genre"] not in profile["genres"]:
        score += 4
    return max(72, min(98, score))
