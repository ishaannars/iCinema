"""Presentation helpers for the Streamlit app."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def app_css():
    """The app's stylesheet (src/ui/styles.css), read and minified once per process.

    It's sent with every page run, so comments and whitespace are stripped to keep each click light.
    """
    import re
    css = (Path(__file__).parent / "styles.css").read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    css = re.sub(r":\s+", ":", css)       # "color: red" -> "color:red"; a space before ":" (selectors) is kept
    return css.replace(";}", "}").strip()
