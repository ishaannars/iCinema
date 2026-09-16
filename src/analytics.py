import time
import uuid
from statistics import median

MAX_EVENTS=500

def new_session_id(): return uuid.uuid4().hex[:12]

def ensure_session(state):
    if not state.get("showroom_session_id"):
        state["showroom_session_id"]=new_session_id(); state["showroom_session_start"]=time.time(); state["showroom_impression_keys"]=set()
    return state["showroom_session_id"]

def start_new_session(state):
    state["showroom_session_id"]=new_session_id(); state["showroom_session_start"]=time.time(); state["showroom_impression_keys"]=set(); return state["showroom_session_id"]

def record_event(state,event_type,title,context=None):
    ensure_session(state); context=dict(context or {}); now=time.time()
    event={"event":str(event_type),"title":str(title),"timestamp":now,"session_id":state.get("showroom_session_id"),"elapsed_seconds":max(0.0,now-float(state.get("showroom_session_start") or now)),"row":context.get("row"),"position":context.get("position"),"match":context.get("match"),"model_score":context.get("model_score"),"decision_utility":context.get("decision_utility")}
    events=list(state.get("analytics_events") or []); events.append(event); state["analytics_events"]=events[-MAX_EVENTS:]; return event

def record_impressions(state,contexts):
    ensure_session(state); seen=set(state.get("showroom_impression_keys") or set())
    for title,context in (contexts or {}).items():
        key=(state.get("showroom_session_id"),title,context.get("row"),context.get("position"))
        if key in seen: continue
        record_event(state,"impression",title,context); seen.add(key)
    state["showroom_impression_keys"]=seen

def analytics_insights(events):
    events=list(events or []); saves=[e for e in events if e.get("event")=="save"]; skips=[e for e in events if e.get("event")=="skip"]; seen=[e for e in events if e.get("event")=="seen"]; impressions=[e for e in events if e.get("event")=="impression"]
    first={}
    for e in saves:
        sid=e.get("session_id")
        if sid and sid not in first: first[sid]=float(e.get("elapsed_seconds") or 0)
    times=[v for v in first.values() if v>=0]
    skips_before=[sum(1 for e in skips if e.get("session_id")==sid and float(e.get("elapsed_seconds") or 0)<=t) for sid,t in first.items()]
    saved_titles={e.get("title") for e in saves}; seen_after={e.get("title") for e in seen if e.get("title") in saved_titles}
    positive=saves+seen; exploratory=[e for e in positive if e.get("row") in {"Hidden Gems","Something Different","Critically Acclaimed"}]
    return {"time_to_match_seconds":median(times) if times else None,"avg_skips_before_save":sum(skips_before)/len(skips_before) if skips_before else None,"saved_to_seen_rate":len(seen_after)/len(saved_titles) if saved_titles else None,"discovery_rate":len(exploratory)/len(positive) if positive else None,"impressions":len(impressions),"saves":len(saves),"skips":len(skips),"seen_actions":len(seen),"sessions_with_match":len(first)}
