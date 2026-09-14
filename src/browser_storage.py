from pathlib import Path
import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "browser_storage_component"
_browser_storage = components.declare_component(
    "icinema_browser_storage",
    path=str(_COMPONENT_DIR),
)


def browser_storage(action, storage_key, value=None, key=None):
    """Small localStorage bridge used for iCinema profile persistence."""
    return _browser_storage(
        action=action,
        storage_key=storage_key,
        value=value,
        key=key,
        default=None,
    )
