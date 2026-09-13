
# iCinema

**Personalized movie discovery, built around taste rather than endless scrolling.**

iCinema is an AI-assisted recommendation experience that learns a viewer's preferences through a lightweight three-step calibration and turns those signals into a personalized showroom of movies, series, and documentaries.

> Portfolio project focused on recommendation systems, personalization, product design, and media discovery.

---

## Why I Built It

Finding something to watch often takes longer than it should. Streaming platforms surface large catalogs, but the experience can still feel repetitive, overly broad, or disconnected from the way people actually choose a film.

I built iCinema around a simple question:

**What if movie discovery felt curated from the start?**

Instead of requiring a long questionnaire, iCinema collects a small number of high-signal preferences, builds a concise Cinema Profile, and uses that profile to rank a personalized showroom.

---

## Product Flow

### 1. Rate the Shelf
Users tap films they already like and can mark stronger favorites.

### 2. Tune Your Taste
Users calibrate:
- **Great reviews** vs. **Just entertaining**
- Current mood: **Dark, Funny, Emotional, Intense, Relaxing**
- **Familiar picks** vs. **Surprise me**

### 3. Choose What You Want More Of
Users select categories such as:
- Hidden Gems
- Critically Acclaimed
- Recent Releases
- International Films
- Classics
- Documentaries

### Cinema Profile
The app converts those choices into:
- tonal preferences
- top genres
- decision factors
- discovery categories
- a concise profile statement

### Personalized Showroom
Recommendations are grouped into curated shelves such as:
- Top Matches for You
- Critically Acclaimed
- Hidden Gems
- Something Different

Users can **Save**, mark titles as **Seen**, or **Skip** them. Those actions are designed to become future recommendation signals.

---

## Recommendation Logic

The current MVP uses a transparent, weighted scoring system based on:

- genre overlap
- tonal/tag similarity
- critical-review preference
- requested discovery categories
- willingness to explore outside familiar genres

This keeps the recommendation process explainable while leaving room for a future hybrid recommender using embeddings, collaborative filtering, or learned ranking.

---

## Ratings

The UI is designed around three layers of confidence:

- **iCinema Match** — personalized recommendation score
- **IMDb** — audience-facing rating signal
- **Rotten Tomatoes** — critic score

The included demo data is static so the repository runs immediately without API keys. A production version can replace the demo catalog with TMDB/OMDb-backed metadata and ratings.

---

## Tech Stack

**Runtime:** Python 3.10+


- **Python**
- **Streamlit**
- Session-state personalization
- Rule-based recommendation scoring
- Modular recommendation logic

Planned API integration:
- **TMDB** — catalog, posters, metadata, discovery
- **OMDb** — IMDb and Rotten Tomatoes ratings

---

## Run Locally

```bash
git clone <your-repo-url>
cd icinema
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

---

## Project Structure

```text
icinema/
├── app.py
├── src/
│   └── recommender.py
├── assets/
├── .streamlit/
│   └── config.toml
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Next Steps

- Connect live TMDB catalog and poster data
- Add OMDb rating enrichment
- Add persistent user profiles
- Move from rule-based scoring to a hybrid recommender
- Add title-level explanations and “more like this”
- Add movie / series / documentary filters
- Deploy as a public web app

---

## Portfolio Focus

This project demonstrates:

- recommendation-system thinking
- preference modeling
- API-oriented product architecture
- stateful interactive UX
- explainable ranking
- rapid product prototyping

