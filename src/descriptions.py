"""Card and synopsis text for iCinema, built only from text TMDB publishes about each movie.

No text is generated. Each card line is a complete sentence or clause from the plot summary,
TMDB's tagline, or a plain description from the movie's own details.
"""
import re


def clean_movie_copy(text, ensure_terminal=True):
    """Normalize movie copy so UI summaries never end on awkward fragments."""
    value = " ".join(str(text or "").split()).strip()
    if not value:
        return ""

    # Normalize punctuation spacing and repeated punctuation.
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,;:]){2,}", r"\1", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = value.strip(" \t\n,;:–—-")

    # Remove dangling connector/article words caused by safe truncation.
    dangling = {
        "a", "an", "the", "and", "or", "but", "with", "to", "of", "in",
        "for", "from", "by", "as", "at", "into", "onto", "on", "its", "his",
        "her", "their", "who", "that", "which"
    }
    words = value.rstrip(".!?").split()
    while words and words[-1].casefold().strip(".,;:") in dangling:
        words.pop()
    value = " ".join(words).rstrip(" ,;:")

    if ensure_terminal and value and value[-1] not in ".!?":
        value += "."
    return value


_HOOK_VERBS = set("""
is are was were be becomes become finds find follows follow discovers discover tries try must has have
gets get enters enter returns return meets meet faces face uncovers uncover struggles struggle begins begin
turns turn joins join grows grow investigates investigate reconnects reconnect attempts attempt receives
receive attends attend moves move prepares prepare realizes realize spends spend fights fight searches search
takes take makes make lives live works work falls fall goes go comes come leads lead learns learn sets set
plans plan hunts hunt runs run seeks seek wants want needs need loses lose wins win tells tell decides decide
agrees agree forms form builds build hides hide escapes escape travels travel embarks embark stumbles stumble
must wakes wake kills kill saves save protects protect helps help leaves leave arrives arrive teams team
tracks track confronts confront battles battle pursues pursue sparks spark unravels unravel navigates navigate
inherits inherit befriends befriend infiltrates infiltrate recruits recruit risks risk chases chase
""".split())
_HOOK_DANGLING_END = {
    "a", "an", "the", "and", "or", "but", "with", "to", "of", "in", "for", "from", "by", "as", "at",
    "into", "onto", "on", "its", "his", "her", "their", "who", "that", "which", "young", "whose", "when",
}
_HOOK_SPLITS = ("; ", " — ", " – ", ": ", ", and ", ", but ", ", who ", ", where ", ", when ", " when ",
                ", while ", ", as ", ", until ", " until ", ", before ", ", after ", ", only to ", " in order to ", " after ", " before ", " while ")


def _hook_is_complete(text, limit, need_verb=True):
    text = clean_movie_copy(text, ensure_terminal=False)
    if not text or len(text) < 24 or len(text) > limit:
        return False
    words = [w.casefold().strip(".,;:!?()[]{}\"'") for w in text.split()]
    if len(words) < 5 or words[-1] in _HOOK_DANGLING_END:
        return False
    if words[0] in {"in", "on", "at", "during", "after", "before", "while", "when", "with", "without",
                    "through", "across", "amid", "following"}:
        return False
    return (not need_verb) or any(w in _HOOK_VERBS for w in words[1:])


_HOOK_LEADS = (r"^(?:in|on|at|during|after|before|following|inside|across|amid|within|when|while|as|once|until|"
               r"years after|decades after|set in|in the)\b[^,]{2,110},\s+(.+)$")
_HOOK_PRONOUN_START = {"he", "she", "they", "it", "his", "her", "their", "its", "this", "these", "there", "but", "and", "then"}


_HOOK_AUX = {"is", "are", "was", "were", "has", "have", "had", "must", "can", "could", "will",
             "would", "should", "may", "might", "does", "did", "gets", "got"}


# Words that start a setup phrase ("Years later,", "Meanwhile,", "All unemployed,").
# A name can never be trimmed because it is never on this list.
_SETUP_OPENERS = {
    "years", "months", "weeks", "days", "decades", "centuries", "hours", "moments", "minutes",
    "meanwhile", "now", "today", "tonight", "soon", "later", "once", "all", "after", "before",
    "during", "following", "since", "still", "suddenly", "eventually", "finally", "together",
    "alone", "newly", "recently", "long", "back", "far", "deep", "high", "just", "one", "two",
    "desperate", "determined", "unemployed", "broke", "orphaned", "widowed", "haunted",
    "estranged", "exiled", "stranded", "trapped", "armed", "fresh", "fed", "tired", "bored",
    "lonely", "unable", "eager", "reluctant", "grieving", "struggling", "having", "faced",
    "facing", "left", "raised", "born", "set",
}


def _is_setup_opener(words):
    first = words[0].strip(".,;:!?\"'") if words else ""
    return first in _SETUP_OPENERS


def _starts_with_subject(text):
    """False when a clause would begin with its verb, or is only an appositive
    ("a young man, is ...") whose real subject was the name before it."""
    words = [w.casefold().strip(".,;:!?\"'") for w in text.split()]
    if not words or words[0] in _HOOK_AUX or words[0] in _HOOK_VERBS:
        return False
    if words[0] in {"a", "an", "the", "his", "her", "their", "its"}:
        comma = text.find(", ")
        if 0 < comma <= 60:
            after = text[comma + 2:].split()
            if after and (after[0].casefold() in _HOOK_AUX or after[0].casefold() in _HOOK_VERBS):
                return False
    return True


def _hook_variants(sentence):
    """(text, is_whole_clause) options: the sentence, its main clause after up to two
    leading setup phrases, and safe clause cuts. Whole clauses are grammatical by
    construction; cuts must also pass the verb check."""
    whole = [sentence]
    current = sentence
    for _ in range(2):
        lead = re.match(_HOOK_LEADS, current, flags=re.IGNORECASE)
        if lead:
            rest = lead.group(1).strip()
            if not _starts_with_subject(rest):
                break  # never leave a clause that begins with its verb
            current = rest
        else:
            # Short verbless opener such as "All unemployed," or "Years later,".
            comma = current.find(", ")
            opener = current[:comma].casefold().split() if 0 < comma <= 30 else None
            if not opener or any(w in _HOOK_VERBS for w in opener) or not _is_setup_opener(opener):
                break  # only clear setup phrases are trimmed; names never are
            rest = current[comma + 2:].strip()
            if not _starts_with_subject(rest):
                break  # "Hana, a young girl, is captured..." keeps its subject
            current = rest
        whole.append(current[:1].upper() + current[1:])
    variants = [(w, True) for w in whole]
    for source in whole:
        for marker in _HOOK_SPLITS:
            pos = source.find(marker)
            if pos > 20 and not (marker.startswith(",") and "," in source[:pos]):
                variants.append((source[:pos], False))
    return variants


_SCENE_SETTING = re.compile(
    r"^(?:it['’]s|it is|it was)\s+(?:the\s+)?(?:\d{4}s?|year|summer|winter|spring|fall|autumn|"
    r"early|late|mid|eve|night|day|end|dawn|future|era|age)\b"
    r"|^the year is\b|^set (?:in|during|against)\b|^welcome to\b|^once upon a time\b",
    re.IGNORECASE,
)


def _is_scene_setting(sentence):
    """Opening narration ("It's the 1940s, and ...") sets a scene but says nothing about the story."""
    return bool(_SCENE_SETTING.match(str(sentence or "").strip()))


def _ends_on_bare_infinitive(text):
    """Cuts like "... hope to join" drop the object and read as unfinished."""
    words = [w.casefold().strip(".,;:!?\"'") for w in str(text or "").split()]
    return len(words) >= 2 and words[-2] == "to"


# Openings that only make sense after an earlier sentence ("Within this world ...").
_CONTEXT_OPENERS = re.compile(
    r"^(?:within|in|inside|across|throughout|from)\s+(?:this|that|these|those|the same)\b"
    r"|^(?:this|that|these|those)\s+(?:world|film|movie|story|place|time|city|town|land|group|war)\b"
    r"|^the (?:film|movie|story|series|sequel|documentary)\b|^(?:here|now),",
    re.IGNORECASE,
)
# Poster copy that praises the movie instead of describing it.
_MARKETING = re.compile(
    r"\b(?:masterpiece|critics|acclaimed|award|oscar|must-see|the event|of the year|from the (?:director|makers|creators)|"
    r"never be the same|unforgettable|experience|you['’]ll|you['’]ve|you\b|your\b|in theaters|coming soon)",
    re.IGNORECASE,
)
_STOP = {"a", "an", "the", "of", "to", "in", "on", "at", "and", "or", "but", "is", "are", "was", "were", "be",
         "with", "for", "by", "from", "as", "his", "her", "their", "its", "who", "that", "this", "into", "one",
         "someone", "something", "everyone", "nothing", "day", "new"}
_LANGUAGES = {"ja": "Japanese", "ko": "Korean", "fr": "French", "es": "Spanish", "de": "German", "it": "Italian",
              "zh": "Chinese", "cn": "Cantonese", "hi": "Hindi", "pt": "Portuguese", "sv": "Swedish", "da": "Danish",
              "no": "Norwegian", "ru": "Russian", "th": "Thai", "tr": "Turkish", "pl": "Polish", "fa": "Persian",
              "nl": "Dutch", "fi": "Finnish", "id": "Indonesian", "te": "Telugu", "ta": "Tamil", "ar": "Arabic"}
_TONE_WORDS = ("Dark", "Funny", "Tense", "Suspenseful", "Emotional", "Heartfelt", "Lighthearted", "Offbeat",
               "Intense", "Romantic", "Cerebral", "Stylish", "Epic", "Psychological", "Thought-provoking")


def _tidy(text):
    """Collapse odd punctuation from taglines: '....' -> '.', stray quotes and spaces."""
    t = re.sub(r"\s*(?:\.{2,}|…)+\s*$", ".", str(text or "").strip())
    t = re.sub(r"\s*(?:\.{2,}|…)\s*", " … ", t).replace(" … .", ".")
    return clean_movie_copy(t.strip(" \"'“”"), ensure_terminal=True)


def _line_score(text, source):
    """Higher is better. Specific, complete story lines win; vague or promotional lines lose."""
    words = re.findall(r"[\w'’-]+", text)
    content = [w for w in words if w.casefold() not in _STOP and len(w) > 2]
    score = min(len(content), 9)                       # specific detail, capped so long lines don't win by length
    if len(words) < 6:
        score -= 6                                     # "Someone is missing." says almost nothing
    if _CONTEXT_OPENERS.match(text):
        score -= 8                                     # needs the sentence before it
    if _MARKETING.search(text):
        score -= 5                                     # praise is not a premise
    if any(w[:1].isupper() for w in words[1:]):
        score += 1                                     # a named character or place is concrete
    score += {"summary": 2, "first": 1, "tagline": 0}[source]
    return score


def _details_line(movie):
    """A plain, true line from the movie's own details when the summary has nothing usable."""
    movie = movie or {}
    genre = str(movie.get("genre") or "").strip()
    year = str(movie.get("year") or "").strip()
    lang = _LANGUAGES.get(str(movie.get("original_language") or "").casefold())
    tags = [t for t in (movie.get("tags") or []) if t in _TONE_WORDS]
    tone = tags[0].lower() if tags else ""
    kind = {"Anime": "anime", "Documentary": "documentary", "Animation": "animated film"}.get(genre, f"{genre.lower()} film" if genre else "film")
    parts = [p for p in (tone, lang if lang and kind != "anime" else "", kind) if p]
    phrase = " ".join(parts)
    article = "An" if phrase[:1].lower() in "aeiou" else "A"
    return f"{article} {phrase}" + (f" from {year}." if year else ".")


def quick_card_description(movie, limit=110):
    """One real, specific, complete line about the movie. Never cut mid-sentence.

    Candidates: the catalog's hand-written hook; complete clauses from the first four plot
    sentences; TMDB's tagline; the opening sentence whole. Each is scored for being specific,
    standing on its own, and describing the story instead of praising it. If nothing scores
    well, a plain line from the movie's details is used (genre, tone, language, year).
    """
    movie = movie or {}
    why = clean_movie_copy(movie.get("why"), ensure_terminal=True)
    if why and len(why) <= limit + 30:
        return why
    full = clean_movie_copy(movie.get("overview") or movie.get("why"), ensure_terminal=False)
    sentences = [s.strip().rstrip(".;:, ") for s in re.split(r"(?<=[.!?])\s+", full) if s.strip()] if full else []

    candidates = []
    for pos, sentence in enumerate(sentences[:4]):
        if pos > 0 and sentence.split()[0].casefold().strip(",") in _HOOK_PRONOUN_START:
            continue  # later sentences that lean on earlier context read as fragments
        if _is_scene_setting(sentence):
            continue
        for c, is_whole in _hook_variants(sentence):
            if _hook_is_complete(c, limit, need_verb=not is_whole) and (is_whole or not _ends_on_bare_infinitive(c)):
                text = clean_movie_copy(c, ensure_terminal=True)
                candidates.append((_line_score(text, "summary") - 0.5 * pos, len(text), text))
    tagline = _tidy(movie.get("tagline"))
    if tagline and 12 <= len(tagline) <= limit:
        candidates.append((_line_score(tagline, "tagline"), len(tagline), tagline))
    if sentences:
        first = clean_movie_copy(sentences[0], ensure_terminal=True)
        if len(first) <= limit and not _is_scene_setting(sentences[0]):
            candidates.append((_line_score(first, "first"), len(first), first))

    if candidates:
        best = max(candidates)
        if best[0] >= 4:
            return best[2]
    if tagline and len(tagline.split()) >= 3 and len(tagline) <= limit and not _MARKETING.search(tagline):
        return tagline        # "Welcome to the Real World." beats "An action film from 1999."
    return _details_line(movie)


def tonight_description(movie, limit=160):
    """Tonight's Show line: the one-line hook when it says something about the story,
    otherwise the opening premise in complete sentences (the hero card has room).

    Fixes lines like "It's the 1940s, and the notorious Axe Gang terrorizes Shanghai.",
    scene-setting narration that the hook logic only uses as a last resort.
    """
    hook = quick_card_description(movie, limit=limit)
    full = clean_movie_copy((movie or {}).get("overview"), ensure_terminal=False)
    if not full:
        return hook
    sentences = [x.strip().rstrip(".;:, ") for x in re.split(r"(?<=[.!?])\s+", full) if x.strip()]
    if len(sentences) < 2:
        return hook
    first = clean_movie_copy(sentences[0], ensure_terminal=True)
    weak = hook == _details_line(movie) or (hook == first and _is_scene_setting(sentences[0]))
    if not weak:
        return hook
    second = sentences[1]
    if len(first) + len(second) > 260:
        # Keep the second sentence's opening clause: after the scene, "...hope to join" reads fine.
        m = re.search(r",\s+(?:but|and|while|until|when|as|only)\b|;\s+|\s+[–—]\s+", second)
        if m and len(second[:m.start()].split()) >= 4:
            second = second[:m.start()]
        else:
            return first
    return f"{first} {clean_movie_copy(second, ensure_terminal=True)}"


def expanded_card_description(movie, max_chars=320):
    """The premise: the opening of the TMDB overview, in complete sentences.

    Always starts at the beginning, since later sentences ("Then, a man...") lean on
    earlier ones. Adds whole sentences while they fit and never cuts one mid-way.
    """
    full = clean_movie_copy(
        (movie or {}).get("overview") or (movie or {}).get("why"),
        ensure_terminal=False,
    )
    if not full:
        return "iCinema does not have a longer premise for this title yet."
    sentences = [
        clean_movie_copy(part, ensure_terminal=True)
        for part in re.split(r"(?<=[.!?])\s+", full)
        if clean_movie_copy(part, ensure_terminal=False)
    ]
    chosen, total = [], 0
    for sentence in sentences[:3]:
        projected = total + len(sentence) + (1 if chosen else 0)
        if chosen and projected > max_chars:
            break
        chosen.append(sentence)  # the first sentence is always kept whole
        total = projected
    return " ".join(chosen).strip()
