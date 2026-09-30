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
    if changed:
        README.write_text(text)
        print("README.md updated.")
    else:
        print("README.md already up to date.")


if __name__ == "__main__":
    main()
