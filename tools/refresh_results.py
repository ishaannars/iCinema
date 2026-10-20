"""Rebuild the results in README.md and MODEL_CARD.md from data/cf_results.json.

No retraining needed. It saves the exact lift into the results file, then writes
the same numbers everywhere (README, model card, and the app, which reads the file).

    python tools/refresh_results.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "training"))
from train_cf import build_report, compute_lifts, replace_between_markers  # noqa: E402


BSTART, BEND = "<!-- CF_BENCHMARK:START -->", "<!-- CF_BENCHMARK:END -->"


def benchmark_block():
    b = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    order = ["Popularity", "SVD, 64 dims (current)", "SVD, 128 dims", "SVD 64, recency-weighted (half-life 20 likes)",
             "Implicit ALS", "EASE", "EASE, top-100 per movie (shippable)", "item-kNN", "item-kNN, top-100 per movie (shippable)"]
    names = {"SVD, 64 dims (current)": "SVD, 64 dims (old model)"}
    lines = ["| Model | Hit@1, 3 random likes | NDCG@10, 3 random likes | Hit@1, 3 most recent likes | Hit@1, full history | Size |",
             "|---|---|---|---|---|---|"]
    conf_path = ROOT / "data" / "long_tail_confirm.json"
    conf = json.loads(conf_path.read_text()) if conf_path.exists() else {}
    rp3_ships = bool(conf.get("replaces_item_knn"))
    for n in order:
        r = b["results"][n]
        label = names.get(n, n)
        if n == b["winner"]:
            label = f"**{label.replace(' (shippable)', '')} ({'shipped for most viewers and similar movies' if rp3_ships else 'shipped'})**"
        size = "—" if n == "Popularity" else f"{r['model_size_mb']:.0f} MB"
        lines.append(f"| {label} | {r['random3']['hit@1']:.1%} | {r['random3']['ndcg@10']:.3f} | "
                     f"{r['last3']['hit@1']:.1%} | {r['full']['hit@1']:.1%} | {size} |")
    if rp3_ships:
        r = conf["rp3beta_on_benchmark_test"]
        lines.append(f"| **RP3beta (beta {conf['beta']:g}), top-100 per movie (shipped for less mainstream taste)** | {r['random3']['hit@1']:.1%} | "
                     f"{r['random3']['ndcg@10']:.3f} | {r['last3']['hit@1']:.1%} | {r['full']['hit@1']:.1%} | 5 MB |")
        rt_path = ROOT / "data" / "routing_confirm.json"
        rt = json.loads(rt_path.read_text()) if rt_path.exists() else {}
        if rt.get("ship_routing"):
            r = rt["routed_on_benchmark_test"]
            lines.append(f"| **Routed: RP3beta for less mainstream likes, item-kNN otherwise (what the app does)** | {r['random3']['hit@1']:.1%} | "
                         f"{r['random3']['ndcg@10']:.3f} | {r['last3']['hit@1']:.1%} | {r['full']['hit@1']:.1%} | 10 MB |")
    d = b["dataset"]
    lines += ["", f"{d['user_sample']}: {d['users']:,} viewers, {d['movies']:,} movies, {d['positives']:,} ratings of 4+ stars. "
              f"Settings were picked on {d['validation_users']:,} validation viewers and scored once on {d['test_users']:,} different test viewers. "
              "From `training/benchmark_cf.py`."]
    return "\n".join(lines)


TSTART, TEND = "<!-- TESTED:START -->", "<!-- TESTED:END -->"
ESTART, EEND = "<!-- ERRORS:START -->", "<!-- ERRORS:END -->"


def tested_block():
    b = json.loads((ROOT / "data" / "cf_benchmark.json").read_text())
    br = json.loads((ROOT / "data" / "blend_results.json").read_text())
    r = b["results"]
    w, old, pop = r[b["winner"]]["random3"], r["SVD, 64 dims (current)"]["random3"], r["Popularity"]["random3"]
    cb, wn = br["content_blend"], br["whats_next"]
    conf_path = ROOT / "data" / "long_tail_confirm.json"
    lt_path = ROOT / "data" / "long_tail_results.json"
    rec = r["SVD 64, recency-weighted (half-life 20 likes)"]["random3"]
    rows = [
        ("Viewers like you", "9 models, 3 random likes, 3,000 test viewers",
         f"item-kNN won: {w['hit@1']:.1%} first-pick hits vs {pop['hit@1']:.1%} popularity and {old['hit@1']:.1%} old SVD",
         "✅ item-kNN for most viewers"),
        ("Content vs viewers like you", "Every weight from 0% to 100% content",
         f"{cb['best_weight']:.0%} content was best (NDCG {cb['test_best']['ndcg@10']:.3f} vs {cb['test_current']['ndcg@10']:.3f} at the old "
         f"{cb['current_weight']:.0%}). With no floor, {cb['best_weight_without_floor']:.0%} was best",
         f"✅ {cb['best_weight']:.0%} content, {1 - cb['best_weight']:.0%} viewers like you"),
        ("What's next", "Every mix of similarity to the watched movie and personal match",
         f"{wn['best_weight']:.0%} similarity was best (NDCG {wn['test_best']['ndcg@10']:.3f} vs {wn['test_current']['ndcg@10']:.3f} at the old "
         f"{wn['current_weight']:.0%}). With no floor, {wn['best_weight_without_floor']:.0%} was best",
         f"✅ {wn['best_weight']:.0%} similarity, {1 - wn['best_weight']:.0%} personal match"),
        ("Recency-weighted likes", "SVD with newer likes weighted more", f"{rec['hit@1']:.1%} vs {old['hit@1']:.1%}, no real gain", "❌ No"),
        ("Row goals (how much each row leans on its kind)", "Not testable offline", "They define what each row is for", "Design choice"),
        ("Personal Save/Skip model (22%)", "Needs real app users", "Live AUC shows in the Profile tab", "Design choice"),
        ("Section order", "Not an accuracy question", "Your Step 3 picks decide which section comes after Top Matches", "Design choice"),
        ("Hidden Gems", "Definition", "Under 4,000 TMDB votes, or outside the 20% most-loved MovieLens movies when votes are missing, plus a few hand-picked gems", "Design choice"),
        ("Card descriptions", "Rules checked by unit tests", "Each line is scored for being specific, standing on its own, and describing the story. No text is generated", "✅ Rule-based"),
    ]
    st = json.loads((ROOT / "data" / "steps_results.json").read_text()) if (ROOT / "data" / "steps_results.json").exists() else None
    if st:
        v = st["validation_ndcg_by_content_weight"]
        s23, lr = st["steps_2_3_value"], st["learned_ranker"]
        rows.insert(2, ("Every onboarding step (Steps 1–3)", "The app's own scoring, with each viewer's Step 2–3 answers filled in from their history",
                        f"At {st['current_content_weight']:.0%} content, Steps 2–3 didn't move hit rates (NDCG {s23['ndcg_diff_all_steps_vs_likes_only']:+.3f}, "
                        f"95% CI {s23['ci95'][0]:+.3f} to {s23['ci95'][1]:+.3f}). {st['best_content_weight']:.0%} content was best on validation "
                        f"(NDCG {v[str(st['best_content_weight'])]:.4f} vs {v['0.0']:.4f} with no content)",
                        f"✅ Kept at {st['current_content_weight']:.0%}, so your answers count at no cost"))
        nt = st.get("niche_taste")
        if nt:
            rows.insert(3, ("More content for niche taste (on top of RP3beta)", f"Viewers whose 3 likes are less-loved movies ({nt['test_viewers']:,} test viewers)",
                            (f"The current {nt['best_content_weight']:.0%} was already best for them on validation"
                             if nt["best_content_weight"] == st["current_content_weight"] else
                             f"{nt['best_content_weight']:.0%} content was best on validation and the gain on test wasn't significant "
                             f"(NDCG {nt['ndcg_diff_vs_current']:+.3f}, CI {nt['ci95'][0]:+.3f} to {nt['ci95'][1]:+.3f})"),
                            "No change needed"))
        rows.insert(4 if nt else 3, ("Learned ranker", "Logistic regression on viewers like you plus every content part",
                        f"Worse than the current blend (NDCG {lr['vs_current']['ndcg_diff']:+.3f})", "❌ No"))
    if conf_path.exists() and lt_path.exists():
        cf_, lt = json.loads(conf_path.read_text()), json.loads(lt_path.read_text())
        tried = [k for k in lt["validation_ndcg_niche"] if k != "item-kNN (shipped)"]
        rows.insert(1, ("Less mainstream taste", f"{len(tried)} fixes for popularity bias (popularity penalties, ALS, EASE, blends, RP3beta), "
                        f"then a fresh check on {cf_['fresh_viewers']:,} untouched viewers",
                        f"RP3beta (beta {cf_['beta']:g}) lifted niche viewers' NDCG {cf_['niche_ndcg_diff']:+.4f} "
                        f"(95% CI {cf_['niche_ci95'][0]:+.4f} to {cf_['niche_ci95'][1]:+.4f}) with no loss overall "
                        f"({cf_['all_ndcg_diff']:+.4f}, CI {cf_['all_ci95'][0]:+.4f} to {cf_['all_ci95'][1]:+.4f}). Every other fix made things worse",
                        "✅ Used for less mainstream likes (see routing)" if cf_["replaces_item_knn"] else "❌ No"))
        rt_path = ROOT / "data" / "routing_confirm.json"
        if rt_path.exists():
            rt = json.loads(rt_path.read_text())
            rows.insert(2, ("Routing between the two", f"RP3beta for less mainstream likes, item-kNN otherwise, on {rt['viewers']:,} brand-new viewers "
                            "(a separate slice of MovieLens, models rebuilt, nothing tuned)",
                            f"Beat RP3beta for everyone (NDCG {rt['routed_vs_rp3_all']['ndcg_diff']:+.4f}, CI {rt['routed_vs_rp3_all']['ci95'][0]:+.4f} to "
                            f"{rt['routed_vs_rp3_all']['ci95'][1]:+.4f}) and item-kNN for everyone ({rt['routed_vs_knn_all']['ndcg_diff']:+.4f}, CI "
                            f"{rt['routed_vs_knn_all']['ci95'][0]:+.4f} to {rt['routed_vs_knn_all']['ci95'][1]:+.4f})",
                            "✅ What the app does" if rt["ship_routing"] else "❌ No"))
    rows_path = ROOT / "data" / "rows_results.json"
    if rows_path.exists():
        rr = json.loads(rows_path.read_text())["rows"]
        kinds = {"Hidden Gems": "outside the 20% most-loved movies", "Critically Acclaimed": "4.0+ stars from 500+ ratings",
                 "Something Different": "outside your 3 most-liked genres"}
        for name, v in rr.items():
            rows.append((f"{name} row", f"Within movies {kinds[name]}, vs the most popular of that kind ({v['viewers']:,} viewers)",
                         f"Found a movie the viewer later loved in its top 10 {v['hit@10_shipped']:.1%} of the time vs "
                         f"{v['hit@10_popular_of_that_kind']:.1%} (CI {v['ci95'][0]:+.3f} to {v['ci95'][1]:+.3f})",
                         "✅ Supported" if v["supported"] else "❌ Not supported"))
    lines = ["| Part | Test | Result | In the app |", "|---|---|---|---|"]
    lines += [f"| {a} | {b_} | {c} | {d} |" for a, b_, c, d in rows]
    lines += ["", "MovieLens has no onboarding answers, so Step 2–3 answers were filled in from each viewer's own history. "
              "Content and personal match always keep at least 20%, so your answers always count. "
              "From the scripts in `training/`."]
    return "\n".join(lines)


def errors_block():
    e = json.loads((ROOT / "data" / "blend_results.json").read_text())["errors"]
    h = {x["liked_movies"]: x["hit@1"] for x in e["by_history"]}
    g = {x["group"].split(" (")[0]: x["hit@1"] for x in e["by_taste"]}
    return "\n".join([
        f"First-pick hit rate for the shipped model from 3 random likes ({e['overall_hit@1']:.1%} overall).",
        "",
        f"- **Viewers with little history are hardest.** {h['3–10']:.1%} for viewers with 3–10 liked movies, "
        f"{h['100+']:.1%} for 100+. They have fewer later favorites to hit.",
        f"- **Niche taste is hardest.** {g['Niche taste']:.1%} for viewers whose later favorites were the least popular movies, "
        f"{g['Mainstream taste']:.1%} for the most popular. Movies with few fans have fewer neighbors to draw on.",
        "- New movies that aren't in MovieLens get no \"viewers like you\" score, so content alone ranks them.",
    ])


def _put(body, start, end, text):
    if start not in body:
        return body
    i, j = body.index(start) + len(start), body.index(end)
    return body[:i] + "\n" + text + "\n" + body[j:]


def main():
    path = ROOT / "data" / "cf_results.json"
    results = json.loads(path.read_text())
    results["lifts_three_likes_vs_popularity"] = compute_lifts(results)
    path.write_text(json.dumps(results, indent=2))
    report = build_report(results)
    (ROOT / "data" / "cf_results.md").write_text(report)
    for doc in ("README.md", "MODEL_CARD.md"):
        if replace_between_markers(ROOT / doc, report.strip()):
            print(f"Updated results in {doc}")
    readme = ROOT / "README.md"
    body = readme.read_text()
    body = _put(body, BSTART, BEND, benchmark_block())
    if (ROOT / "data" / "blend_results.json").exists():
        body = _put(body, TSTART, TEND, tested_block())
        body = _put(body, ESTART, EEND, errors_block())
    readme.write_text(body)
    print("Updated benchmark, tested-parts, and error tables in README.md")
    lifts = results["lifts_three_likes_vs_popularity"]
    print(f"Tonight's Show lift: +{lifts.get('hit@1')}%  |  rows: NDCG +{lifts.get('ndcg@10')}%, Recall +{lifts.get('recall@10')}%")


if __name__ == "__main__":
    main()
