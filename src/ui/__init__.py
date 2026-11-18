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


def css_chunks(css, limit=60000):
    """Split minified CSS at rule boundaries into pieces under `limit` characters, in order.

    Browsers and Streamlit's markdown handle several modest <style> blocks reliably; one very large block
    was being cut off, so every rule past the cut silently stopped applying."""
    out, start = [], 0
    while start < len(css):
        end = min(start + limit, len(css))
        if end < len(css):
            cut = css.rfind("}", start, end)
            # Stay outside @media blocks: back up to a "}" that closes a top-level rule.
            while cut > start:
                depth = css.count("{", start, cut + 1) - css.count("}", start, cut + 1)
                if depth == 0:
                    break
                cut = css.rfind("}", start, cut)
            end = cut + 1 if cut > start else end
        out.append(css[start:end])
        start = end
    return out
