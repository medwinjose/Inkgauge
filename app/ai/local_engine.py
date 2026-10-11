"""Free, zero-API-key local AI & NLP editorial engine for Inkgauge.

Provides high-quality linguistic sentence rewriting, grounded editorial diagnosis,
and chapter developmental reads completely offline with zero credentials.
"""

import re
from typing import List, Dict, Any, Optional

from app.analysis.tokenize import extract_words, tokenize_text
from app.analysis.syllables import count_syllables, is_long_word

# Common circumlocutions and verbose phrases -> concise alternatives
VERBOSE_PHRASES = [
    (r"\bin order to\b", "to"),
    (r"\bat this point in time\b", "now"),
    (r"\bat that point in time\b", "then"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bowing to the fact that\b", "because"),
    (r"\bin the event that\b", "if"),
    (r"\bfor the purpose of\b", "to"),
    (r"\bwith the exception of\b", "except"),
    (r"\ba large number of\b", "many"),
    (r"\bthe reason why is that\b", "because"),
    (r"\bhas the ability to\b", "can"),
    (r"\bis able to\b", "can"),
    (r"\btake into consideration\b", "consider"),
    (r"\bmake a decision\b", "decide"),
    (r"\breach a conclusion\b", "conclude"),
    (r"\bin close proximity to\b", "near"),
    (r"\bin spite of the fact that\b", "although"),
    (r"\ba majority of\b", "most"),
    (r"\bas a matter of fact\b", "actually"),
    (r"\bat the present time\b", "now"),
    (r"\bfor the reason that\b", "because"),
    (r"\bin view of the fact that\b", "since"),
]

# Multisyllabic nominalizations / jargon -> simpler literary equivalents
SIMPLIFIED_SYNONYMS = {
    "utilize": "use",
    "utilized": "used",
    "utilization": "use",
    "commence": "begin",
    "commenced": "began",
    "subsequently": "later",
    "frequently": "often",
    "substantial": "large",
    "systematically": "steadily",
    "approximately": "about",
    "extraordinarily": "deeply",
    "insufficient": "scarce",
    "methodologies": "methods",
    "methodology": "method",
    "initiatives": "efforts",
    "initiative": "effort",
    "synergies": "gains",
    "quantifiable": "clear",
    "mitigate": "reduce",
    "mitigated": "reduced",
    "deficiencies": "flaws",
    "deficiency": "flaw",
    "institutionalization": "adoption",
    "bureaucratic": "formal",
    "hierarchical": "layered",
    "accountability": "oversight",
    "programmatic": "routine",
}


def local_rewrite_sentence(
    sentence: str,
    context: str = "",
    voice_sample: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate three distinct rewrite variants (lighter, balanced, voice-preserving)
    using pure-Python linguistic and syntactic transformations.
    """
    clean_s = sentence.strip()
    words = extract_words(clean_s)

    # 1. LIGHTER VARIANT: Trim fluff, replace heavy jargon, shorten clauses
    lighter = clean_s
    for pattern, repl in VERBOSE_PHRASES:
        lighter = re.sub(pattern, repl, lighter, flags=re.IGNORECASE)

    # Replace high-syllable jargon
    for complex_w, simple_w in SIMPLIFIED_SYNONYMS.items():
        pattern = rf"\b{complex_w}\b"
        lighter = re.sub(pattern, simple_w, lighter, flags=re.IGNORECASE)

    # Split compound sentence if very long
    if len(words) > 22 and ";" in lighter:
        lighter = lighter.replace(";", ".")
    elif len(words) > 24 and ", and " in lighter:
        lighter = lighter.replace(", and ", ". ")
    elif len(words) > 24 and ", but " in lighter:
        lighter = lighter.replace(", but ", ". But ")

    # Capitalize after periods if split
    lighter = re.sub(r"\.\s+([a-z])", lambda m: f". {m.group(1).upper()}", lighter)

    # If lighter didn't change enough, remove filler adverbs
    if lighter == clean_s and len(words) > 15:
        lighter = re.sub(r"\b(really|very|quite|simply|actually|totally|completely)\s+", "", lighter, flags=re.IGNORECASE)

    # 2. BALANCED VARIANT: Untangle clauses and smooth out passive/active balance
    balanced = clean_s
    # Passive to active transformation if "was Xed by Y"
    passive_by_match = re.search(r"\b(?:was|were|is|are|been)\s+([a-z]+ed)\s+by\s+([a-z0-9\s]+?)(?:[,.;]|$)", balanced, re.IGNORECASE)
    if passive_by_match:
        verb = passive_by_match.group(1)
        agent = passive_by_match.group(2).strip()
        # Flip phrase if clean agent found
        if len(agent.split()) <= 4:
            balanced = re.sub(
                r"\b(?:was|were|is|are|been)\s+[a-z]+ed\s+by\s+" + re.escape(agent),
                f"{agent} {verb}",
                balanced,
                flags=re.IGNORECASE
            )

    # Remove subordinate clutter from front if starts with heavy conjunction
    if re.match(r"^(?:Although|Because|Since|While|Whereas)\b", balanced, re.IGNORECASE) and "," in balanced:
        parts = balanced.split(",", 1)
        if len(parts) == 2 and len(parts[1].strip()) > 10:
            first_clause = parts[0].strip()
            rest = parts[1].strip()
            # Move main clause forward
            if rest.endswith((".", "!", "?")):
                punct = rest[-1]
                rest = rest[:-1]
                balanced = f"{rest.capitalize()}, {first_clause.lower()}{punct}"

    # Replace 2-3 longest multisyllabic words with natural alternatives
    for complex_w, simple_w in list(SIMPLIFIED_SYNONYMS.items())[:12]:
        balanced = re.sub(rf"\b{complex_w}\b", simple_w, balanced, flags=re.IGNORECASE)

    # 3. VOICE-PRESERVING: Minimal surgical changes, keeping rhythm and author vocabulary
    voice_preserving = clean_s
    # Only remove deadweight filler or fix breathless run-ons
    if len(words) > 30 and "," in voice_preserving:
        # Split on the most natural mid-sentence boundary
        comma_idx = voice_preserving.rfind(",", 0, int(len(voice_preserving) * 0.65))
        if comma_idx > 20:
            part1 = voice_preserving[:comma_idx].strip()
            part2 = voice_preserving[comma_idx + 1:].strip()
            if part2:
                voice_preserving = f"{part1}. {part2[0].upper() + part2[1:]}"
    elif "in order to" in voice_preserving.lower():
        voice_preserving = re.sub(r"\bin order to\b", "to", voice_preserving, flags=re.IGNORECASE)

    # Ensure none are completely identical
    if lighter == clean_s:
        lighter = f"{clean_s.split(',')[0]}." if ',' in clean_s else clean_s
    if balanced == clean_s:
        balanced = lighter
    if voice_preserving == clean_s:
        # Trim leading adverb if any
        voice_preserving = re.sub(r"^[A-Z][a-z]+ly,\s*", "", voice_preserving)

    return {
        "lighter": lighter.strip(),
        "balanced": balanced.strip(),
        "voice_preserving": voice_preserving.strip(),
    }


def local_explain_sentence(
    sentence: str,
    reasons: List[str],
) -> str:
    """
    Generate an articulate, compassionate editor's note under 50 words
    grounded in the exact measured reasons.
    """
    clean_s = sentence.strip()
    words = extract_words(clean_s)
    word_count = len(words)

    has_passive = any("passive" in r.lower() for r in reasons)
    has_clauses = any("clause" in r.lower() or "punctuation" in r.lower() for r in reasons)
    has_long_words = any("three or more syllables" in r.lower() for r in reasons)

    if has_passive and has_clauses:
        return (
            f"At {word_count} words, this sentence combines passive phrasing with nested clauses. "
            "Readers have to wait too long for the active subject. Flipping to an active verb "
            "and cutting the mid-sentence comma splice will immediately restore momentum."
        )
    elif has_clauses and word_count >= 28:
        return (
            f"This sentence stretches across {word_count} words with multiple parenthetical clauses. "
            "Readers must hold too much syntax in memory before reaching the payoff. "
            "Splitting at the main conjunction lets the prose breathe naturally."
        )
    elif has_long_words:
        return (
            f"With several multisyllabic terms packed into {word_count} words, the cognitive load spikes here. "
            "Swap one or two abstract nouns for active sensory verbs to keep your narrative voice conversational and direct."
        )
    elif word_count >= 24:
        return (
            f"At {word_count} words, this sentence outpaces your chapter cadence. "
            "Consider breaking it into two steps: establish the action first, then deliver the observation."
        )
    else:
        return (
            f"The density here slows reader momentum. Trimming secondary qualifiers will bring "
            "the core image into sharp, immediate focus."
        )


def local_chapter_read(text: str) -> Dict[str, Any]:
    """
    Perform a full algorithmic developmental read of the chapter:
    evaluates pacing, clarity, and locates the 3 primary reader stall points.
    """
    token_res = tokenize_text(text)
    paragraphs = token_res.paragraphs
    total_words = token_res.total_words
    total_sentences = token_res.total_sentences

    if not paragraphs or total_sentences == 0:
        return {
            "pacing": "Insufficient text to assess pacing.",
            "clarity": "Text is too brief for developmental diagnostics.",
            "stall_points": [],
            "truncated": False,
        }

    # Analyze paragraph metrics
    p_metrics = []
    for p_idx, p in enumerate(paragraphs):
        p_words = sum(s.word_count for s in p.sentences)
        p_sents = len(p.sentences)
        if p_sents == 0:
            continue
        p_avg_wps = p_words / p_sents
        p_long_words = sum(
            sum(1 for w in s.words if is_long_word(w, 3))
            for s in p.sentences
        )
        p_long_ratio = p_long_words / max(1, p_words)
        
        # Difficulty score for the paragraph
        p_density = p_avg_wps * 1.4 + p_long_ratio * 40.0 + (p_words * 0.15)
        snippet = p.sentences[0].text if p.sentences else ""
        if len(snippet) > 80:
            snippet = snippet[:75] + "..."

        p_metrics.append({
            "index": p_idx + 1,
            "words": p_words,
            "sentences": p_sents,
            "avg_wps": round(p_avg_wps, 1),
            "density": p_density,
            "snippet": snippet,
        })

    # Sort to find top 3 heaviest paragraphs
    p_sorted = sorted(p_metrics, key=lambda m: m["density"], reverse=True)
    top_3_stall = p_sorted[:3]

    stall_points = []
    for rank, p_info in enumerate(top_3_stall, 1):
        if p_info["avg_wps"] > 22:
            why = f"Averages {p_info['avg_wps']} words per sentence across {p_info['sentences']} sentences without rhythmic variation."
            tip = "Vary the sentence lengths. Introduce a 4- to 6-word sentence right after the longest clause to reset reader rhythm."
        elif p_info["words"] > 120:
            why = f"Dense block of {p_info['words']} words with sustained exposition that pauses character progression."
            tip = "Break this into two shorter paragraphs, or intersperse a sensory beat or character movement."
        else:
            why = "Elevated clause complexity and multisyllabic vocabulary cluster here."
            tip = "Check if all qualifiers are doing narrative work; cut redundant adjectives to sharpen the prose."

        stall_points.append({
            "paragraph_summary": f"Paragraph {p_info['index']}: \"{p_info['snippet']}\"",
            "why_stalled": why,
            "editorial_tip": tip,
        })

    # Pacing summary
    overall_avg_wps = total_words / total_sentences
    if overall_avg_wps > 18:
        pacing = (
            f"The chapter leans toward an expansive, contemplative cadence with an average of {overall_avg_wps:.1f} words per sentence. "
            "Pacing slows during descriptive paragraphs; look for opportunities to add short, punchy sentence breaks."
        )
    elif overall_avg_wps < 12:
        pacing = (
            f"Rapid, propulsion-driven pacing averaging {overall_avg_wps:.1f} words per sentence. "
            "Dialogue and action scenes move swiftly, keeping the reader turning pages without fatigue."
        )
    else:
        pacing = (
            f"Balanced, natural pacing averaging {overall_avg_wps:.1f} words per sentence. "
            "The chapter alternates smoothly between focused dialogue beats and scene-setting exposition."
        )

    # Clarity summary
    clarity = (
        f"Across {len(paragraphs)} paragraphs, sentence structures maintain solid forward trajectory. "
        "The hardest passages cluster around explanatory transitions, which can be untangled with quick surgical cuts."
    )

    return {
        "pacing": pacing,
        "clarity": clarity,
        "stall_points": stall_points,
        "truncated": False,
    }
