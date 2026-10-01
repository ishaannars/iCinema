"""Add the ranking-details section and watch-link limitation to README.md.

Safe to run more than once: it only inserts what is missing and never touches
the auto-generated results between the RESULTS markers.

    python tools/update_readme.py
"""
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

LIMITATION = ("- Watch links open each service's search for the title, because public links can't open a movie "
              "inside Netflix or Hulu directly. Services without a dependable search link (Max, Peacock, "
              "Paramount+) open TMDB's watch page, which then links to the service.")

FRESHNESS = ("- **Freshness for returning viewers.** Impression discounting lowers a title a little for each earlier "
             "visit where it was shown but got no Save, Seen, or Skip (capped at five visits), and a small per-visit "
             "shuffle varies near-ties. Both are stable within a visit, so rows never jump while browsing. "
             "The candidate pool also widens: each return visit starts deeper in TMDB's catalog, and dedicated "
             "channels pull the most popular and best-rated titles in the viewer's top two genres.")

FEEDBACK = ("- **Explicit vs. implicit negatives.** Skip means \"not now\" and is a weak signal; \"Not for me\" "
            "(in each card's explanation and beside Tonight's Show) is an explicit dislike. It pushes the content profile "
            "and collaborative-filtering taste vector away about four times harder, counts as a double-weight negative "
            "label for the behavioral model, and the title never returns. Undo reverses either one.")
MODEL_CARD = README.parent / "MODEL_CARD.md"
OLD_LIMIT = "- **Every Skip is treated as a dislike.**"
NEW_LIMIT = ("- **Skip is ambiguous by design.** A Skip may mean \"already seen\" or \"not tonight,\" so it is only a weak "
             "negative; the explicit \"Not for me\" signal carries strong dislikes. Skip reasons were considered and left out "
             "to keep feedback to one tap.")

# Keep product text in step with the app (old phrase -> current phrase). Safe to re-run.
PHRASE_FIXES = [
    ("as one compact card with a one-tap **Watch on …** button,", "as one compact card with one-tap links to where it streams,"),
    ("trained on each user's Save/Skip feedback", "trained on each user's Save, Skip, and \"Not for me\" feedback"),
    ("- Save, Seen, and Skip feedback, with Undo for accidental skips",
     "- Save, Seen, Skip, and \"Not for me\" feedback, with Undo for accidental taps\n"
     "- Skip on the Step 1 shelf for movies you don't recognize\n"
     "- Fresh picks on every visit, so returning viewers don't see the same ignored movies"),
]

COMING_NEXT = """## Coming Next

- **For Critics tab:** search the full catalog and narrow it by IMDb, Rotten Tomatoes, Metacritic, and runtime. Refine chips (Critics' favorites, Hidden gems, Under 2 hours) re-rank results with your taste profile instead of acting as plain filters.
- **"Only my services" mode** so every row shows only what you can play tonight, with no repeats across rows.
- **Rate what you've watched:** thumbs up or down on Seen movies, separating intent (Save) from post-watch satisfaction.
- **Add likes from the Showroom:** search for movies you already love and add them anytime, not just during onboarding.

### Evaluation and code quality

- **Stronger offline baseline.** The collaborative-filtering results are compared only with a popularity baseline. Next is adding item-kNN and ALS comparisons so the lift is measured against standard recommenders.
- **Refactor.** `app.py` is about 7,000 lines with layered CSS from rapid iteration. Next is splitting it into modules and consolidating the styles.

"""

WHATS_NEXT_FEATURE = "- \"What's next\" under every Seen movie: a personalized follow-up pick, with Save and Another pick"
WHATS_NEXT_DETAIL = ("- **What's next.** For each Seen movie, candidates are scored 60% on collaborative-filtering similarity "
                     "to that movie (the same MovieLens viewers loved both) and 40% on the viewer's personalized match. When the "
                     "watched movie isn't in MovieLens, genre and tag overlap stand in. Each Seen movie gets a different pick, and "
                     "nothing already saved, seen, skipped, or disliked is suggested. What's next has not been evaluated offline; "
                     "the reported results cover the collaborative-filtering ranking only.")

DETAILS = """## Ranking Details

The Profile tab keeps this short for viewers; here is the full picture.

- **Collaborative filtering.** Truncated SVD on 15.8 million positive MovieLens ratings (4 stars and up) from 198,954 users learns 64-dimension embeddings for 14,407 movies. A viewer's likes, favorites (weighted double), and saves pull their taste vector toward similar movies; skips push it away. Candidates are scored by cosine similarity.
- **Content model.** TF-IDF and Truncated SVD over plot and metadata measure theme and tone. Genre, storytelling traits, Bayesian-adjusted ratings, discovery fit, and Step 2–3 answers complete the content score.
- **Hybrid ranking.** Score = 65% content + 35% collaborative. Each Showroom row blends in its own goal: Critically Acclaimed (30% ratings), Hidden Gems (28% less-popular but well rated), and Something Different (32% novelty in genre, language, and era, plus a mainstream penalty). The blend weights are hand-set design choices. MMR reranking removes near-duplicates, and titles on the viewer's services rank as easier to watch tonight.
- **Behavioral model.** After 50 Save/Skip outcomes (12+ of each), Logistic Regression trains on the viewer's own feedback; Gradient Boosting is compared at 100 and the better model on a chronological holdout is used. It contributes 22% of the score. Recent choices weigh more (120-day half-life), display position is excluded so exposure isn't mistaken for taste, and Undo removes a skip from training data.
- **Live metrics.** NDCG@4 and MRR appear after 5 Saves; calibration error after 20 Saves and Skips, so a handful of clicks never shows a misleading "perfect" score.
- **Explanations.** Each card's reasons are the components that contributed most to that movie's score. "Loved by fans of …" names only movies the viewer liked, favorited, or saved, never ones merely marked Seen.

"""


def main():
    text = README.read_text()
    changed = False
    if LIMITATION not in text:
        anchor = "- Streaming availability is for the United States."
        if anchor in text:
            text = text.replace(anchor, anchor + "\n" + LIMITATION, 1)
        else:
            text = text.replace("## Technical Depth", "## Current Status and Limitations\n\n" + LIMITATION + "\n\n## Technical Depth", 1)
        changed = True
    if "## Ranking Details" not in text and "## Technical Depth" in text:
        text = text.replace("## Technical Depth", DETAILS + "## Technical Depth", 1)
        changed = True
    if FRESHNESS not in text and "## Ranking Details" in text:
        anchor = "- **Live metrics.**"
        if anchor in text:
            text = text.replace(anchor, FRESHNESS + "\n" + anchor, 1)
            changed = True
    if FEEDBACK not in text and "## Ranking Details" in text:
        anchor = "- **Live metrics.**"
        if anchor in text:
            text = text.replace(anchor, FEEDBACK + "\n" + anchor, 1)
            changed = True
    if MODEL_CARD.exists():
        card = MODEL_CARD.read_text()
        if OLD_LIMIT in card:
            start = card.index(OLD_LIMIT)
            end = card.find("\n", start)
            card = card[:start] + NEW_LIMIT + (card[end:] if end != -1 else "")
            MODEL_CARD.write_text(card)
            print("MODEL_CARD.md updated.")
    for old, new in PHRASE_FIXES:
        if old in text and new not in text:
            text = text.replace(old, new, 1)
            changed = True
    if "## Coming Next" in text and COMING_NEXT not in text:
        # Replace the whole section (up to the next top-level heading) with the current list.
        start = text.index("## Coming Next")
        nxt = text.find("\n## ", start + 1)
        text = text[:start] + COMING_NEXT + (text[nxt + 1:] if nxt != -1 else "")
        changed = True
    elif "## Coming Next" not in text and "## Retraining the Collaborative-Filtering Model" in text:
        text = text.replace("## Retraining the Collaborative-Filtering Model",
                            COMING_NEXT + "## Retraining the Collaborative-Filtering Model", 1)
        changed = True
    if WHATS_NEXT_FEATURE not in text:
        anchor = "- Browser-local preference persistence with no account required"
        if anchor in text:
            text = text.replace(anchor, WHATS_NEXT_FEATURE + "\n" + anchor, 1)
            changed = True
    if WHATS_NEXT_DETAIL not in text and "- **Live metrics.**" in text:
        text = text.replace("- **Live metrics.**", WHATS_NEXT_DETAIL + "\n- **Live metrics.**", 1)
        changed = True
    if changed:
        README.write_text(text)
        print("README.md updated.")
    else:
        print("README.md already up to date.")


if __name__ == "__main__":
    main()
