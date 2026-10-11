"""Style flags analysis: passive voice, adverbs, repeated sentence openers, and dialogue vs narration."""

import re
from typing import List, Dict, Any, Optional, Tuple
from app.analysis.tokenize import extract_words
from app.analysis.syllables import count_syllables

# Adjectives or nouns ending in -ly that are NOT adverbs
NON_ADVERB_LY = {
    "lonely", "friendly", "lovely", "ugly", "silly", "holy", "daily", "early",
    "elderly", "lively", "orderly", "deadly", "family", "belly", "fly", "ally",
    "rely", "apply", "supply", "jelly", "italy", "monopoly", "bully", "rally",
    "folly", "gully", "chilly", "homely", "costly", "courtly", "cowardly", "ghastly",
    "heavenly", "kingly", "likely", "manly", "neighbourly", "neighborly", "priestly",
    "scholarly", "timely", "unruly", "wobbly", "curly", "pearly", "surly", "sly"
}

# Forms of 'to be'
TO_BE_VERBS = r"(?:am|is|are|was|were|be|been|being)"

# Irregular past participles
IRREGULAR_PARTICIPLES = (
    r"(?:broken|built|chosen|done|drawn|driven|eaten|fallen|felt|found|given|gone|"
    r"grown|heard|held|kept|known|laid|led|left|lost|made|meant|met|paid|read|"
    r"run|said|seen|sold|sent|set|shown|shut|spent|spoken|spread|struck|taken|"
    r"taught|told|thought|understood|won|worn|written)"
)

# Regular past participles ending in -ed or -en or -d or irregular
PARTICIPLE_PATTERN = rf"(?:[a-z]+(?:ed|en)|{IRREGULAR_PARTICIPLES})"

# Passive voice pattern: to-be + optional 1-2 adverbs + past participle
PASSIVE_VOICE_RE = re.compile(
    rf"\b({TO_BE_VERBS})\s+(?:([a-z]+ly)\s+)?({PARTICIPLE_PATTERN})\b",
    re.IGNORECASE
)

# Dialogue quotes regex
DIALOGUE_RE = re.compile(r'["“][^"“”]+["”]|[\'][^\'\r\n]+[\']')


def find_passive_voice(text: str) -> List[str]:
    """Find passive voice constructions in a sentence or text."""
    matches: List[str] = []
    for m in PASSIVE_VOICE_RE.finditer(text):
        phrase = m.group(0).strip()
        matches.append(phrase)
    return matches


def find_ly_adverbs(words: List[str]) -> List[str]:
    """Find adverbs ending in -ly, excluding common adjectives and nouns."""
    adverbs: List[str] = []
    for w in words:
        low = w.lower()
        if low.endswith("ly") and len(low) > 3 and low not in NON_ADVERB_LY:
            adverbs.append(w)
    return adverbs


def find_repeated_openers(sentences: List[str]) -> List[Dict[str, Any]]:
    """
    Find three or more consecutive sentences that open with the same word.
    Returns list of repeated opener groups.
    """
    if len(sentences) < 3:
        return []

    openers: List[str] = []
    for s in sentences:
        words = extract_words(s)
        if words:
            openers.append(words[0].lower())
        else:
            openers.append("")

    repeated_groups: List[Dict[str, Any]] = []
    i = 0
    while i < len(openers):
        word = openers[i]
        if not word:
            i += 1
            continue

        run_len = 1
        while (i + run_len) < len(openers) and openers[i + run_len] == word:
            run_len += 1

        if run_len >= 3:
            repeated_groups.append({
                "word": word.capitalize(),
                "count": run_len,
                "start_sentence_index": i,
                "end_sentence_index": i + run_len - 1,
            })
            i += run_len
        else:
            i += 1

    return repeated_groups


def calculate_fk_grade(words: List[str], sentence_count: int) -> Optional[float]:
    """Calculate Flesch-Kincaid grade level for a list of words."""
    if not words or sentence_count == 0:
        return None
    num_words = len(words)
    total_syllables = sum(count_syllables(w) for w in words)
    fk = 0.39 * (num_words / sentence_count) + 11.8 * (total_syllables / num_words) - 15.59
    return round(max(0.0, fk), 1)


def analyze_dialogue_vs_narration(text: str) -> Dict[str, Any]:
    """
    Separate text into dialogue (within quotes) and narration (outside quotes),
    and calculate word counts and reading levels for each.
    """
    dialogue_pieces: List[str] = []
    last_end = 0
    narration_pieces: List[str] = []

    for match in DIALOGUE_RE.finditer(text):
        start, end = match.span()
        narration_pieces.append(text[last_end:start])
        dialogue_pieces.append(match.group(0))
        last_end = end
    narration_pieces.append(text[last_end:])

    dialogue_text = " ".join(dialogue_pieces)
    narration_text = " ".join(narration_pieces)

    dialogue_words = extract_words(dialogue_text)
    narration_words = extract_words(narration_text)

    # Estimate sentence counts by punctuation in dialogue / narration
    # Roughly count ., ?, !
    d_sent_count = max(1, len(re.findall(r"[.!?]+", dialogue_text))) if dialogue_words else 0
    n_sent_count = max(1, len(re.findall(r"[.!?]+", narration_text))) if narration_words else 0

    d_grade = calculate_fk_grade(dialogue_words, d_sent_count) if dialogue_words else None
    n_grade = calculate_fk_grade(narration_words, n_sent_count) if narration_words else None

    return {
        "dialogue_word_count": len(dialogue_words),
        "narration_word_count": len(narration_words),
        "dialogue_grade": d_grade,
        "narration_grade": n_grade,
        "has_dialogue": len(dialogue_words) > 0,
    }
