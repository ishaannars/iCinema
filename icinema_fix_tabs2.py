"""iCinema: the section tabs remember where you are, with counts back in the top bar.

Streamlit's st.tabs forgets the open tab whenever the page rebuilds (after Save, Seen, Mark
Seen...), so it jumped back to Showroom. The four sections now use a control whose choice is
saved in session state, so it can't reset. Counts ("Saved (3)") stay in the bar and update
without moving you.
"""
import re
p = "app.py"; s = open(p).read(); changes = []

nav = '''with st.container(key="section_nav"):
        _section = st.segmented_control(
            "Section", ["Showroom", "Saved", "Seen", "Profile"], default="Showroom", key="showroom_section",
            label_visibility="collapsed",
            format_func=lambda v: (f"Saved ({len(st.session_state.saved)})" if v == "Saved" else
                                   f"Seen ({len(st.session_state.seen)})" if v == "Seen" else v),
        ) or "Showroom"
    tabs = [st.container(key=("section_on_" if _section == name else "section_off_") + name.lower())
            for name in ("Showroom", "Saved", "Seen", "Profile")]'''
m = re.search(r'tabs=st\.tabs\(\["Showroom",[^\n]*\]\)', s)
if m:
    s = s[:m.start()] + nav + s[m.end():]; changes.append("remembering section bar")

# Counts live in the bar again, so headings go back to plain titles.
s2 = re.sub(r"st\.markdown\(f'<div class=\"(tab-primary-heading[^\"]*)\">(Saved|Seen) · \{len\(st\.session_state\.\w+\)\}</div>', unsafe_allow_html=True\)",
            r"st.markdown('<div class=\"\1\">\2</div>', unsafe_allow_html=True)", s)
if s2 != s:
    s = s2; changes.append("plain headings")

css = """
/* Section bar: looks like tabs, remembers the open section */
[class*="st-key-section_off_"]{display:none !important;}
.st-key-section_nav [data-testid="stButtonGroup"]:has(button){gap:1.6rem;border-bottom:1px solid var(--border);margin-bottom:.6rem}
.st-key-section_nav [data-testid="stButtonGroup"] button{background:transparent !important;border:none !important;border-radius:0 !important;
  border-bottom:2px solid transparent !important;padding:.35rem .1rem !important;color:var(--ivory) !important;box-shadow:none !important}
.st-key-section_nav [data-testid="stButtonGroup"] button[kind*="Active"], .st-key-section_nav [data-testid="stButtonGroup"] button[aria-checked="true"]{
  border-bottom-color:var(--ai) !important;color:var(--ai) !important}
"""
if "remembers the open section" not in s:
    last = s.rindex("</style>"); s = s[:last] + css + s[last:]; changes.append("tab styling")
open(p, "w").write(s)
print("Changes:", ", ".join(changes) if changes else "none (already applied or code differs)")
