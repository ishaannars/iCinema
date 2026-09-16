"""Browser-local supervised learning and evaluation for iCinema.

The analytical hybrid recommender is the cold-start model. Once a browser has
collected enough labeled recommendation outcomes, this module trains two real
supervised classifiers, evaluates them on held-out interactions, and returns the
better model for blending into live ranking. No synthetic outcomes are used.
"""
from dataclasses import dataclass
import math
from typing import Dict, List, Optional
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

FEATURE_NAMES = [
    "genre_affinity", "trait_affinity", "semantic_similarity",
    "quality_alignment", "discovery_alignment", "priority_alignment",
    "availability_alignment", "vote_confidence", "profile_confidence",
    "model_score", "decision_utility", "match_scaled", "position_scaled",
]

@dataclass
class LearningResult:
    ready: bool
    model_name: str = "Hybrid analytical model"
    model: object = None
    metrics: dict = None
    samples: int = 0
    positives: int = 0
    negatives: int = 0


def _features_from_context(ctx):
    ctx = ctx or {}
    def f(name, default=.5):
        try: return float(ctx.get(name, default))
        except (TypeError, ValueError): return float(default)
    return [
        f("genre_affinity"), f("trait_affinity"), f("semantic_similarity"),
        f("quality_alignment"), f("discovery_alignment"), f("priority_alignment"),
        f("availability_alignment"), f("vote_confidence"), f("profile_confidence"),
        f("model_score"), f("decision_utility"), f("match",50)/100.0,
        min(1.0,max(0.0,(f("position",2)-1.0)/3.0)),
    ]


def labeled_examples(events):
    """Join impressions to subsequent explicit Save/Seen/Skip labels."""
    events=list(events or [])
    impressions={}
    for e in events:
        if e.get("event") == "impression":
            key=(e.get("session_id"),e.get("title"))
            # Keep first exposure in a session to avoid repeated-render leakage.
            impressions.setdefault(key,e)
    labels={}
    for e in events:
        typ=e.get("event")
        if typ not in {"save","seen","skip"}: continue
        key=(e.get("session_id"),e.get("title"))
        # Save/Seen are positive outcomes, Skip is explicit negative feedback.
        labels[key]=1 if typ in {"save","seen"} else 0
    X=[]; y=[]
    for key,label in labels.items():
        imp=impressions.get(key)
        if not imp: continue
        X.append(_features_from_context(imp)); y.append(label)
    if not X: return np.empty((0,len(FEATURE_NAMES))),np.asarray([],dtype=int)
    return np.asarray(X,dtype=float),np.asarray(y,dtype=int)


def train_learning_model(events, min_samples=24):
    X,y=labeled_examples(events)
    positives=int(y.sum()) if len(y) else 0; negatives=int(len(y)-positives)
    base=LearningResult(False,samples=len(y),positives=positives,negatives=negatives,metrics={})
    # Both classes and enough examples are required. This avoids pretending a
    # learned model is reliable when the browser only contains a handful of actions.
    if len(y)<min_samples or positives<6 or negatives<6:
        return base
    try:
        Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.28,random_state=42,stratify=y)
        candidates=[
            ("Logistic Regression",LogisticRegression(max_iter=1000,class_weight="balanced",random_state=42)),
            ("Gradient Boosting",GradientBoostingClassifier(random_state=42,n_estimators=90,max_depth=2,learning_rate=.05)),
        ]
        results=[]
        for name,model in candidates:
            model.fit(Xtr,ytr)
            prob=model.predict_proba(Xte)[:,1]
            pred=(prob>=.5).astype(int)
            auc=float(roc_auc_score(yte,prob)) if len(set(yte))>1 else .5
            acc=float(accuracy_score(yte,pred))
            loss=float(log_loss(yte,np.clip(prob,1e-5,1-1e-5),labels=[0,1]))
            # AUC leads model selection; log loss breaks near-ties.
            selection=auc-.08*loss
            results.append((selection,name,model,{"auc":auc,"accuracy":acc,"log_loss":loss}))
        results.sort(key=lambda x:x[0],reverse=True)
        _,name,best,metrics=results[0]
        # Refit selected architecture on all available labeled interactions.
        best.fit(X,y)
        metrics["compared_models"]=[x[1] for x in results]
        return LearningResult(True,name,best,metrics,len(y),positives,negatives)
    except Exception:
        return base


def predict_success(result, context):
    if not result or not result.ready or result.model is None:
        return None
    try:
        x=np.asarray([_features_from_context(context)],dtype=float)
        return float(result.model.predict_proba(x)[0,1])
    except Exception:
        return None


def ranking_metrics(events, k=4):
    """Compute recommender ranking metrics from real browser interaction sessions."""
    events=list(events or [])
    by_session={}
    outcomes={}
    row_order={"Top Matches for You":0,"Critically Acclaimed":1,"Hidden Gems":2,"Something Different":3}
    for e in events:
        sid=e.get("session_id"); title=e.get("title")
        if not sid or not title: continue
        if e.get("event")=="impression":
            rank=row_order.get(e.get("row"),9)*4+int(e.get("position") or 4)
            by_session.setdefault(sid,{})[title]=min(rank,by_session.setdefault(sid,{}).get(title,999))
        elif e.get("event") in {"save","seen"}: outcomes[(sid,title)]=1
        elif e.get("event")=="skip" and (sid,title) not in outcomes: outcomes[(sid,title)]=0

    precisions=[]; recalls=[]; hits=[]; ndcgs=[]; rrs=[]
    for sid,ranks in by_session.items():
        relevant={title for (s,title),y in outcomes.items() if s==sid and y==1}
        if not relevant: continue
        ordered=sorted(ranks,key=ranks.get)
        top=ordered[:k]
        hit_count=sum(t in relevant for t in top)
        precisions.append(hit_count/max(1,k)); recalls.append(hit_count/len(relevant)); hits.append(1.0 if hit_count else 0.0)
        dcg=sum((1.0/math.log2(i+2)) for i,t in enumerate(top) if t in relevant)
        ideal=sum(1.0/math.log2(i+2) for i in range(min(k,len(relevant))))
        ndcgs.append(dcg/ideal if ideal else 0.0)
        rr=0.0
        for i,t in enumerate(ordered,1):
            if t in relevant: rr=1.0/i; break
        rrs.append(rr)
    def avg(xs): return sum(xs)/len(xs) if xs else None
    return {"precision_at_k":avg(precisions),"recall_at_k":avg(recalls),"hit_rate_at_k":avg(hits),"ndcg_at_k":avg(ndcgs),"mrr":avg(rrs),"evaluated_sessions":len(precisions),"k":k}


def calibration_metrics(events):
    """Observed positive rates by displayed Match band + simple calibration error."""
    events=list(events or [])
    impressions={}
    labels={}
    for e in events:
        key=(e.get("session_id"),e.get("title"))
        if e.get("event")=="impression" and key not in impressions: impressions[key]=e
        elif e.get("event") in {"save","seen"}: labels[key]=1
        elif e.get("event")=="skip" and key not in labels: labels[key]=0
    bins={"20–59":[],"60–69":[],"70–79":[],"80–89":[],"90–97":[]}
    errors=[]
    for key,y in labels.items():
        imp=impressions.get(key)
        if not imp or imp.get("match") is None: continue
        m=float(imp.get("match")); p=m/100.0; errors.append(abs(p-y))
        label="20–59" if m<60 else ("60–69" if m<70 else ("70–79" if m<80 else ("80–89" if m<90 else "90–97")))
        bins[label].append(y)
    return {"mae":sum(errors)/len(errors) if errors else None,"bands":{b:(sum(v)/len(v) if v else None) for b,v in bins.items()},"labeled":len(errors)}
