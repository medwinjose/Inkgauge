"""Syllable counting using CMUDict with a rule-based fallback heuristic."""

import re
from functools import lru_cache
from typing import Optional

_CMU_DICT: Optional[dict] = None

# Vowel regex patterns for fallback heuristic
PUNCT_STRIP_RE = re.compile(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$")

# Common hiatus patterns where two adjacent vowels form distinct syllables
HIATUS_RE = re.compile(
    r"(?:ia|eo|iu|io|ua|uo|oe|ae|ii|ee[aeiou]|uu|creat|react|poem|chaos|naive|lion|diet|fluid|ruin)",
    re.IGNORECASE,
)

NON_SYLLABIC_ED_RE = re.compile(r"[^td]ed$", re.IGNORECASE)
NON_SYLLABIC_ES_RE = re.compile(r"(?:[^s|z|x]|[^c|s]h)es$", re.IGNORECASE)

# Canonical readability syllable counts for words where CMUDict or heuristics vary
CANONICAL_COUNTS: dict[str, int] = {
    "business": 2,
    "every": 2,
    "queue": 1,
    "fire": 1,
    "area": 3,
    "created": 3,
    "create": 2,
    "creating": 3,
    "creation": 3,
    "people": 2,
    "beautiful": 3,
    "evening": 2,
    "chocolate": 2,
    "subtle": 2,
    "rhythm": 2,
    "colonel": 2,
    "wednesday": 2,
    "aisle": 1,
    "simile": 3,
    "recipe": 3,
    "epitome": 4,
    "catastrophe": 4,
    "hyperbole": 4,
    "synecdoche": 4,
    "naive": 2,
    "poem": 2,
    "chaos": 2,
}


def _get_cmudict() -> dict:
    """Lazy-load CMU pronouncing dictionary."""
    global _CMU_DICT
    if _CMU_DICT is None:
        try:
            import cmudict
            _CMU_DICT = cmudict.dict()
        except Exception:
            _CMU_DICT = {}
    return _CMU_DICT


def heuristic_syllable_count(word: str) -> int:
    """Accurate rule-based syllable counter for words not found in CMUDict."""
    clean = word.lower().strip()
    clean = re.sub(r"[^a-z]", "", clean)
    if not clean:
        return 0

    if clean in CANONICAL_COUNTS:
        return CANONICAL_COUNTS[clean]

    if len(clean) <= 3:
        return 1

    # Count vowel groups
    count = 0
    prev_is_vowel = False
    vowels = "aeiouy"

    for char in clean:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Hiatus adjustments: adjacent vowels that are separate syllables
    for _ in HIATUS_RE.finditer(clean):
        count += 1

    # Silent e ending: e.g. "make", "late", "rate", "code", "hope"
    if clean.endswith("e") and not clean.endswith("le") and not clean.endswith("ee"):
        if count > 1 and not (len(clean) <= 3 and clean.endswith("e")):
            count -= 1

    # Endings with -ed: if preceded by [td], it's a syllable ('created', 'wanted'); otherwise silent ('walked', 'baked')
    if NON_SYLLABIC_ED_RE.search(clean) and count > 1:
        count -= 1

    # Endings with -es: silent unless preceded by s, z, x, ch, sh
    if NON_SYLLABIC_ES_RE.search(clean) and count > 1:
        count -= 1

    # Ensure at least 1
    return max(1, count)


@lru_cache(maxsize=32768)
def count_syllables(word: str) -> int:
    """
    Count syllables in a word using CMUDict with a rule-based fallback.
    Cached for fast repeated calls.
    """
    clean = word.strip().lower()
    clean = PUNCT_STRIP_RE.sub("", clean)
    if not clean:
        return 0

    if clean in CANONICAL_COUNTS:
        return CANONICAL_COUNTS[clean]

    cmu = _get_cmudict()
    if clean in cmu:
        prons = cmu[clean]
        # Calculate syllables from phonemes ending in digits (stress marks 0, 1, 2)
        syll_counts = [
            sum(1 for phoneme in pron if phoneme[-1].isdigit())
            for pron in prons
        ]
        if syll_counts:
            # Primary pronunciation
            return syll_counts[0]

    return heuristic_syllable_count(clean)


def is_long_word(word: str, threshold: int = 3) -> bool:
    """Return True if word has threshold or more syllables."""
    return count_syllables(word) >= threshold
