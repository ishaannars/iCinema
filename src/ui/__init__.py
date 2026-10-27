"""Presentation helpers for the Streamlit app."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def app_css():
    """The app's stylesheet (src/ui/styles.css), read once per process."""
    return (Path(__file__).parent / "styles.css").read_text()
