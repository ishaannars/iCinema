from pathlib import Path
import streamlit.components.v1 as components

_scroll_keeper = components.declare_component(
    "icinema_scroll_keeper",
    path=str(Path(__file__).resolve().parent / "scroll_keeper_component"),
)


def scroll_keeper():
    """Invisible helper that keeps the viewer's scroll position through reruns.

    Rendered with the same key and arguments on every run, so Streamlit keeps the
    same iframe alive and its listeners persist.
    """
    return _scroll_keeper(key="icinema_scroll_keeper", default=None)
