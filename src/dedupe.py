"""Keep one movie per series and drop making-of specials across the Showroom."""
import re

MAKING_OF = re.compile(r"\b(the making of|making of|making season|behind the scenes|featurette)\b", re.I)


def franchise(title):
    """'The Lord of the Rings: The Two Towers' and '...Return of the King' -> 'the lord of the rings'."""
    t = " ".join(re.sub(r"[^\w\s:–-]", " ", str(title or "").casefold()).split())
    head = re.split(r"\s*[:–]\s*|\s+-\s+", t)[0]
    head = re.sub(r"\s+(\d+|ii|iii|iv|v|vi|part \w+|chapter \w+)$", "", head).strip()
    return head if len(head.split()) >= 2 or head != t else t
