
from collections import Counter

GENRES=["Action","Adventure","Anime","Animation","Comedy","Documentary","Drama","Fantasy","Horror","Mystery","Romance","Sci-Fi","Thriller"]
MORE_OF_OPTIONS=["Hidden Gems","Critically Acclaimed","Recent Releases","International Films","Classics","Documentaries"]

STARTER_MOVIES=[
{"title":"Interstellar","year":2014,"genre":"Sci-Fi","imdb":8.7,"rt":73,"tags":["Sci-Fi","Drama","Atmospheric","Thought-provoking","Critically Acclaimed"]},
{"title":"Parasite","year":2019,"genre":"Thriller","imdb":8.5,"rt":99,"tags":["Thriller","Drama","International","Dark","Critically Acclaimed"]},
{"title":"The Hangover","year":2009,"genre":"Comedy","imdb":7.7,"rt":79,"tags":["Comedy","Funny","Entertaining"]},
{"title":"Get Out","year":2017,"genre":"Horror","imdb":7.8,"rt":98,"tags":["Thriller","Horror","Dark","Thought-provoking","Critically Acclaimed"]},
{"title":"Whiplash","year":2014,"genre":"Drama","imdb":8.5,"rt":94,"tags":["Drama","Intense","Critically Acclaimed"]},
{"title":"The Godfather","year":1972,"genre":"Drama","imdb":9.2,"rt":97,"tags":["Drama","Classic","Critically Acclaimed","Dark"]},
{"title":"Arrival","year":2016,"genre":"Sci-Fi","imdb":7.9,"rt":94,"tags":["Sci-Fi","Drama","Emotional","Atmospheric","Critically Acclaimed"]},
{"title":"The Social Network","year":2010,"genre":"Drama","imdb":7.8,"rt":96,"tags":["Drama","Fast-paced","Critically Acclaimed"]},
{"title":"Spirited Away","year":2001,"genre":"Anime","imdb":8.6,"rt":96,"tags":["Anime","Animation","International","Emotional","Critically Acclaimed"]},
{"title":"The Dark Knight","year":2008,"genre":"Action","imdb":9.0,"rt":94,"tags":["Action","Drama","Dark","Critically Acclaimed"]},
{"title":"Knives Out","year":2019,"genre":"Mystery","imdb":7.9,"rt":97,"tags":["Mystery","Comedy","Entertaining","Critically Acclaimed"]},
{"title":"Oppenheimer","year":2023,"genre":"Drama","imdb":8.3,"rt":93,"tags":["Drama","Historical","Intense","Critically Acclaimed","Recent Release"]},
]

CATALOG=[
{"title":"Prisoners","year":2013,"genre":"Thriller","imdb":8.2,"rt":81,"tags":["Thriller","Drama","Dark","Intense"],"why":"A tense, character-driven thriller with strong atmosphere."},
{"title":"Blade Runner 2049","year":2017,"genre":"Sci-Fi","imdb":8.0,"rt":88,"tags":["Sci-Fi","Atmospheric","Thought-provoking","Critically Acclaimed"],"why":"Visually ambitious science fiction with a patient, immersive tone."},
{"title":"The Prestige","year":2006,"genre":"Mystery","imdb":8.5,"rt":77,"tags":["Mystery","Drama","Dark","Thought-provoking"],"why":"A layered story built around obsession, rivalry, and reveal."},
{"title":"Nightcrawler","year":2014,"genre":"Thriller","imdb":7.8,"rt":95,"tags":["Thriller","Dark","Critically Acclaimed"],"why":"A sharp, unsettling thriller with a distinctive point of view."},
{"title":"The Handmaiden","year":2016,"genre":"Thriller","imdb":8.1,"rt":96,"tags":["Thriller","International","Critically Acclaimed","Atmospheric"],"why":"A stylish international thriller with strong critical reception."},
{"title":"The Banshees of Inisherin","year":2022,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","Dark","Critically Acclaimed"],"why":"Character-focused drama with dark humor and precise filmmaking."},
{"title":"Past Lives","year":2023,"genre":"Drama","imdb":7.8,"rt":95,"tags":["Drama","Emotional","Critically Acclaimed","Recent Release"],"why":"A restrained, emotionally focused story with exceptional reviews."},
{"title":"Anatomy of a Fall","year":2023,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","Mystery","International","Critically Acclaimed","Recent Release"],"why":"A cerebral courtroom drama driven by ambiguity and performance."},
{"title":"Coherence","year":2013,"genre":"Sci-Fi","imdb":7.2,"rt":89,"tags":["Sci-Fi","Thriller","Hidden Gem","Thought-provoking"],"why":"Low-budget science fiction built around a clever high-concept premise."},
{"title":"The Invitation","year":2015,"genre":"Thriller","imdb":6.6,"rt":89,"tags":["Thriller","Dark","Hidden Gem"],"why":"A slow-building psychological thriller with escalating tension."},
{"title":"Victoria","year":2015,"genre":"Drama","imdb":7.6,"rt":82,"tags":["Drama","International","Hidden Gem","Intense"],"why":"An intense real-time drama known for its single-take execution."},
{"title":"The Guilty","year":2018,"genre":"Thriller","imdb":7.5,"rt":98,"tags":["Thriller","International","Hidden Gem","Critically Acclaimed"],"why":"A tightly contained thriller carried by voice, tension, and inference."},
{"title":"Perfect Days","year":2023,"genre":"Drama","imdb":7.9,"rt":96,"tags":["Drama","International","Relaxing","Critically Acclaimed","Recent Release"],"why":"A quieter, reflective film that expands beyond high-intensity picks."},
{"title":"Hunt for the Wilderpeople","year":2016,"genre":"Comedy","imdb":7.8,"rt":97,"tags":["Comedy","Adventure","Funny","Critically Acclaimed"],"why":"Warm, funny, and highly rated without relying on familiar thriller beats."},
{"title":"The Worst Person in the World","year":2021,"genre":"Drama","imdb":7.7,"rt":96,"tags":["Drama","International","Emotional","Critically Acclaimed"],"why":"A modern character study with emotional range and strong reviews."},
{"title":"Free Solo","year":2018,"genre":"Documentary","imdb":8.1,"rt":97,"tags":["Documentary","Intense","Critically Acclaimed"],"why":"A documentary that delivers genuine tension without fictional stakes."},
{"title":"Memories of Murder","year":2003,"genre":"Thriller","imdb":8.1,"rt":95,"tags":["Thriller","International","Dark","Critically Acclaimed"],"why":"A meticulous thriller balancing tension, character, and ambiguity."},
{"title":"Ex Machina","year":2014,"genre":"Sci-Fi","imdb":7.7,"rt":92,"tags":["Sci-Fi","Thought-provoking","Atmospheric","Critically Acclaimed"],"why":"A focused science-fiction story built around intelligence, control, and trust."},
{"title":"Enemy","year":2013,"genre":"Mystery","imdb":6.9,"rt":72,"tags":["Mystery","Dark","Atmospheric","Hidden Gem"],"why":"A compact psychological mystery with an unsettling atmosphere."},
{"title":"Burning","year":2018,"genre":"Drama","imdb":7.5,"rt":95,"tags":["Drama","International","Atmospheric","Critically Acclaimed"],"why":"A slow-burn mystery driven by mood, uncertainty, and character."},
{"title":"Incendies","year":2010,"genre":"Drama","imdb":8.3,"rt":91,"tags":["Drama","International","Dark","Emotional","Critically Acclaimed"],"why":"An emotionally intense drama with a carefully constructed mystery."},
{"title":"The Lives of Others","year":2006,"genre":"Drama","imdb":8.4,"rt":92,"tags":["Drama","International","Critically Acclaimed","Thought-provoking"],"why":"A precise political drama centered on surveillance, loyalty, and change."},
{"title":"A Separation","year":2011,"genre":"Drama","imdb":8.3,"rt":99,"tags":["Drama","International","Critically Acclaimed","Thought-provoking"],"why":"A deeply human drama built around difficult choices and competing truths."},
{"title":"The Wailing","year":2016,"genre":"Horror","imdb":7.4,"rt":99,"tags":["Horror","Thriller","International","Dark","Hidden Gem"],"why":"A genre-blending mystery with escalating dread and ambiguity."},
{"title":"Train to Busan","year":2016,"genre":"Horror","imdb":7.6,"rt":95,"tags":["Horror","Action","International","Intense","Critically Acclaimed"],"why":"Fast, emotional horror with strong momentum and character stakes."},
{"title":"Your Name","year":2016,"genre":"Anime","imdb":8.4,"rt":98,"tags":["Anime","Animation","Romance","Emotional","International","Critically Acclaimed"],"why":"A visually polished anime romance with an inventive narrative structure."},
{"title":"Princess Mononoke","year":1997,"genre":"Anime","imdb":8.3,"rt":93,"tags":["Anime","Animation","Fantasy","Adventure","International","Classic"],"why":"Epic animated fantasy with moral complexity and enduring visual craft."},
{"title":"Akira","year":1988,"genre":"Anime","imdb":8.0,"rt":91,"tags":["Anime","Animation","Sci-Fi","Dark","Classic","International"],"why":"A landmark science-fiction anime with striking world-building."},
{"title":"The Tale of the Princess Kaguya","year":2013,"genre":"Anime","imdb":8.0,"rt":100,"tags":["Anime","Animation","Emotional","International","Critically Acclaimed"],"why":"Distinctive hand-drawn animation with an emotional, reflective story."},
{"title":"The Holdovers","year":2023,"genre":"Drama","imdb":7.9,"rt":97,"tags":["Drama","Comedy","Emotional","Critically Acclaimed","Recent Release"],"why":"Warm character-driven drama with humor and emotional restraint."},
{"title":"Dune: Part Two","year":2024,"genre":"Sci-Fi","imdb":8.5,"rt":92,"tags":["Sci-Fi","Adventure","Atmospheric","Critically Acclaimed","Recent Release"],"why":"Large-scale science fiction with immersive world-building and visual ambition."},
{"title":"Civil War","year":2024,"genre":"Drama","imdb":7.0,"rt":81,"tags":["Drama","Intense","Recent Release"],"why":"A tense contemporary drama with strong visual storytelling."},
{"title":"The Substance","year":2024,"genre":"Horror","imdb":7.3,"rt":89,"tags":["Horror","Dark","Recent Release","Critically Acclaimed"],"why":"A bold body-horror film with a sharp satirical edge."},
{"title":"No Country for Old Men","year":2007,"genre":"Thriller","imdb":8.2,"rt":93,"tags":["Thriller","Drama","Dark","Critically Acclaimed","Classic"],"why":"A spare, tense thriller with exceptional craft and atmosphere."},
{"title":"Mulholland Drive","year":2001,"genre":"Mystery","imdb":7.9,"rt":84,"tags":["Mystery","Atmospheric","Thought-provoking","Classic"],"why":"A dreamlike mystery built for viewers who enjoy ambiguity and interpretation."},
{"title":"The Truman Show","year":1998,"genre":"Drama","imdb":8.2,"rt":94,"tags":["Drama","Comedy","Thought-provoking","Classic","Critically Acclaimed"],"why":"Accessible, thoughtful storytelling with a memorable high-concept premise."},
{"title":"Before Sunrise","year":1995,"genre":"Romance","imdb":8.1,"rt":100,"tags":["Romance","Drama","Emotional","Classic","Critically Acclaimed"],"why":"Dialogue-driven romance with warmth, intimacy, and a strong sense of place."},
{"title":"The Grand Budapest Hotel","year":2014,"genre":"Comedy","imdb":8.1,"rt":92,"tags":["Comedy","Adventure","Distinctive","Critically Acclaimed"],"why":"Highly stylized comedy with precise visual design and playful storytelling."},
{"title":"The Rescue","year":2021,"genre":"Documentary","imdb":8.3,"rt":96,"tags":["Documentary","Intense","Critically Acclaimed"],"why":"A gripping documentary structured with the tension of a thriller."},
{"title":"Searching for Sugar Man","year":2012,"genre":"Documentary","imdb":8.2,"rt":95,"tags":["Documentary","Hidden Gem","Emotional","Critically Acclaimed"],"why":"A surprising music documentary built around mystery and rediscovery."},
{"title":"Jiro Dreams of Sushi","year":2011,"genre":"Documentary","imdb":7.8,"rt":99,"tags":["Documentary","International","Critically Acclaimed"],"why":"A focused documentary about craft, discipline, and mastery."},
]
ALL_MOVIES=STARTER_MOVIES+CATALOG
MOVIE_INDEX={m["title"]:m for m in ALL_MOVIES}

def get_movie(title): return MOVIE_INDEX.get(title)

def _tag_counts(titles,weight):
    c=Counter()
    for t in titles:
        m=MOVIE_INDEX.get(t)
        if not m: continue
        c[m["genre"]]+=weight
        for tag in m.get("tags",[]): c[tag]+=weight
    return c

def build_profile(likes,favorites,selected_genres,review_priority,more_of,saved_titles=None,skipped_titles=None):
    saved_titles=saved_titles or set(); skipped_titles=skipped_titles or set()
    tags=Counter(); genres=Counter()
    for t in likes:
        m=MOVIE_INDEX.get(t)
        if not m: continue
        w=2 if t in favorites else 1
        genres[m["genre"]]+=w
        for tag in m.get("tags",[]): tags[tag]+=w
    for g in selected_genres:
        genres[g]+=3; tags[g]+=1
    tags.update(_tag_counts(saved_titles,2))
    neg=_tag_counts(skipped_titles,1)
    top=[g for g,_ in genres.most_common(3)]
    for f in ["Thriller","Sci-Fi","Drama"]:
        if len(top)>=3: break
        if f not in top: top.append(f)
    blocked=set(GENRES)|{"Critically Acclaimed","International","Hidden Gem","Classic","Recent Release","Documentary"}
    lean=[tag for tag,count in tags.most_common() if tag not in blocked and count>neg.get(tag,0)][:3]
    for f in ["Atmospheric","Thought-provoking","Intense"]:
        if len(lean)>=3: break
        if f not in lean: lean.append(f)
    stands=["Strong storytelling","Distinctive filmmaking"]
    stands.insert(1,"High critical reception" if review_priority<55 else "Entertainment value")
    drawn=list(more_of[:3]) if more_of else ["Hidden Gems","Critically Acclaimed","International Films"]
    return {"lean":lean,"genres":top,"stands_out":stands,"drawn_to":drawn,
            "summary":"You favor well-crafted titles with strong atmosphere and compelling stories.",
            "positive_tags":dict(tags),"negative_tags":dict(neg)}

def _score(m,p,adventure,review_priority):
    s=58.0; pos=p.get("positive_tags",{}); neg=p.get("negative_tags",{})
    s+=pos.get(m["genre"],0)*3
    for tag in m.get("tags",[]): s+=pos.get(tag,0)*2-neg.get(tag,0)*2.5
    if m["genre"] in p["genres"]: s+=9
    if any(tag in p["lean"] for tag in m.get("tags",[])): s+=7
    if review_priority<50: s+=max(0,m["rt"]-80)*.28+max(0,m["imdb"]-7)*2
    else: s+=max(0,m["imdb"]-7)*1.4
    if adventure>=65 and m["genre"] not in p["genres"]: s+=7
    elif adventure<=35 and m["genre"] in p["genres"]: s+=6
    return s

def _row_bonus(m,kind,p):
    tags=set(m.get("tags",[]))
    if kind=="top": return 8
    if kind=="acclaimed": return 16 if "Critically Acclaimed" in tags or m["rt"]>=90 else -8
    if kind=="hidden": return 18 if "Hidden Gem" in tags else -7
    if kind=="different":
        b=11 if m["genre"] not in p["genres"] else 0
        if "International" in tags or "Documentary" in tags or "Anime" in tags: b+=5
        return b
    return 0

def recommend_for_row(profile,row_kind,adventure,review_priority,excluded,limit=4):
    scored=[]
    for m in CATALOG:
        if m["title"] in excluded: continue
        s=_score(m,profile,adventure,review_priority)+_row_bonus(m,row_kind,profile)
        tags=set(m.get("tags",[]))
        if "Hidden Gems" in profile["drawn_to"] and "Hidden Gem" in tags: s+=6
        if "Critically Acclaimed" in profile["drawn_to"] and "Critically Acclaimed" in tags: s+=6
        if "International Films" in profile["drawn_to"] and "International" in tags: s+=6
        if "Recent Releases" in profile["drawn_to"] and "Recent Release" in tags: s+=6
        if "Classics" in profile["drawn_to"] and "Classic" in tags: s+=6
        if "Documentaries" in profile["drawn_to"] and m["genre"]=="Documentary": s+=8
        scored.append((s,m))
    scored.sort(key=lambda x:(x[0],x[1]["imdb"],x[1]["rt"]),reverse=True)
    out=[]
    for s,m in scored[:limit]:
        x=dict(m); x["match"]=int(round(max(72,min(98,s)))); out.append(x)
    return out
