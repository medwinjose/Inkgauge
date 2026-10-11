"""Readability scoring: Flesch Reading Ease, Flesch-Kincaid Grade, sentence difficulty, and audience targets."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from app.analysis.tokenize import TokenizeResult, SentenceSpan, extract_words
from app.analysis.syllables import count_syllables, is_long_word
from app.analysis.explain import explain_sentence_difficulty
from app.analysis.style import find_passive_voice, find_ly_adverbs, find_repeated_openers, analyze_dialogue_vs_narration
from app.config import READING_SPEED_WPM

# Subordinating conjunctions regex for clause load counting
SUBORDINATING_CONJUNCTIONS_RE = re.compile(
    r"\b(although|because|since|unless|whereas|while|whilst|despite|even though|"
    r"inasmuch as|provided that|so that|in order that|as though|as if|whenever|wherever)\b",
    re.IGNORECASE,
)

# Common English stop words for language heuristic
COMMON_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this", "but",
    "his", "by", "from", "they", "we", "say", "her", "she", "or", "an", "will",
    "my", "one", "all", "would", "there", "their", "what", "so", "up", "out",
    "if", "about", "who", "get", "which", "go", "me", "when", "make", "can"
}

# Audience targets dictionary
AUDIENCE_PRESETS: Dict[str, Dict[str, Any]] = {
    "middle_grade": {
        "label": "Middle grade",
        "description": "Ages 8-12, upper elementary to early middle school",
        "target_grade_min": 4.0,
        "target_grade_max": 6.5,
        "target_wps_min": 10.0,
        "target_wps_max": 14.0,
    },
    "young_adult": {
        "label": "Young adult",
        "description": "Ages 12-18, fast-paced, direct sentence structures",
        "target_grade_min": 6.5,
        "target_grade_max": 8.5,
        "target_wps_min": 12.0,
        "target_wps_max": 16.0,
    },
    "commercial_fiction": {
        "label": "Commercial fiction",
        "description": "Thriller, romance, mystery, accessible pacing",
        "target_grade_min": 6.0,
        "target_grade_max": 8.5,
        "target_wps_min": 11.0,
        "target_wps_max": 16.0,
    },
    "literary_fiction": {
        "label": "Literary fiction",
        "description": "Rich texture, layered clauses, nuanced cadence",
        "target_grade_min": 9.0,
        "target_grade_max": 12.5,
        "target_wps_min": 15.0,
        "target_wps_max": 22.0,
    },
    "nonfiction_business": {
        "label": "Nonfiction / business",
        "description": "Clear professional prose, executive summaries, popular science",
        "target_grade_min": 8.0,
        "target_grade_max": 10.5,
        "target_wps_min": 14.0,
        "target_wps_max": 18.0,
    },
    "academic": {
        "label": "Academic",
        "description": "Scholarly publications, formal monographs, dense thesis prose",
        "target_grade_min": 12.0,
        "target_grade_max": 16.5,
        "target_wps_min": 18.0,
        "target_wps_max": 28.0,
    },
}


def get_flesch_reading_ease_band(score: float) -> str:
    """Return plain-language band for Flesch Reading Ease."""
    if score >= 90.0:
        return "Very easy: 5th grade level, conversational"
    elif score >= 80.0:
        return "Easy: 6th grade level, effortless reading"
    elif score >= 70.0:
        return "Fairly easy: 7th grade level, casual prose"
    elif score >= 60.0:
        return "Plain: easy for most adults"
    elif score >= 50.0:
        return "Fairly hard: some complex phrasing"
    elif score >= 30.0:
        return "Hard: expect re-reading"
    else:
        return "Very hard: dense academic or technical prose"


def get_flesch_kincaid_band(grade: float) -> str:
    """Return plain-language band for Flesch-Kincaid Grade Level."""
    if grade <= 5.0:
        return "Elementary reading level"
    elif grade <= 8.5:
        return "Middle school reading level"
    elif grade <= 10.5:
        return "Early high school (grades 9–10)"
    elif grade <= 12.5:
        return "Upper high school (grades 11–12)"
    elif grade <= 16.0:
        return "College undergraduate level"
    else:
        return "Graduate / professional level"


def count_clause_load(sentence_text: str) -> int:
    """Count commas, semicolons, colons, dashes, and subordinating conjunctions."""
    punc_count = len(re.findall(r"[,;:\—\–\-]", sentence_text))
    conj_count = len(SUBORDINATING_CONJUNCTIONS_RE.findall(sentence_text))
    return punc_count + conj_count


def calculate_sentence_raw_difficulty(
    sentence: SentenceSpan,
    chapter_avg_wps: float,
) -> Dict[str, Any]:
    """
    Compute sentence difficulty from:
    1. Flesch-Kincaid grade of the sentence alone
    2. Sentence length in words
    3. Share of long words (3+ syllables)
    4. Clause load: count of commas, semicolons, colons, dashes, and subordinating conjunctions
    5. Passive-voice presence (small penalty)

    Documented formula:
      Raw = 1.8 * FK_Grade + 1.2 * Word_Count + 35.0 * Long_Word_Share + 4.0 * Clause_Load + Passive_Penalty
    """
    word_count = sentence.word_count
    if word_count == 0:
        return {
            "raw_score": 0.0,
            "grade": 0.0,
            "long_words": [],
            "long_word_share": 0.0,
            "clause_count": 0,
            "passive_phrases": [],
        }

    syllables = sum(count_syllables(w) for w in sentence.words)
    long_words = [w for w in sentence.words if is_long_word(w, 3)]
    long_word_share = len(long_words) / word_count

    # Sentence Flesch-Kincaid grade: 0.39 * (words / 1) + 11.8 * (syllables / words) - 15.59
    fk_grade = max(0.0, 0.39 * word_count + 11.8 * (syllables / word_count) - 15.59)

    clause_count = count_clause_load(sentence.text)
    passive_phrases = find_passive_voice(sentence.text)
    passive_penalty = 6.0 if passive_phrases else 0.0

    raw_score = (
        1.8 * fk_grade
        + 1.2 * word_count
        + 35.0 * long_word_share
        + 4.0 * clause_count
        + passive_penalty
    )

    return {
        "raw_score": raw_score,
        "grade": round(fk_grade, 1),
        "long_words": long_words,
        "long_word_share": round(long_word_share, 3),
        "clause_count": clause_count,
        "passive_phrases": passive_phrases,
    }


def assess_audience_fit(
    chapter_grade: float,
    chapter_avg_wps: float,
    audience_key: str,
    hardest_sentences: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Assess how the chapter fits the selected audience target."""
    preset = AUDIENCE_PRESETS.get(audience_key, AUDIENCE_PRESETS["commercial_fiction"])
    target_min = preset["target_grade_min"]
    target_max = preset["target_grade_max"]

    if chapter_grade < target_min - 1.5:
        verdict = "A little easier than this audience expects"
        verdict_band = "easy"
    elif target_min <= chapter_grade <= target_max:
        verdict = "Right on target"
        verdict_band = "target"
    elif chapter_grade <= target_max + 2.0:
        verdict = "A little hard for this audience"
        verdict_band = "moderate"
    else:
        verdict = "Much harder than this audience expects"
        verdict_band = "hard"

    # Sentences pushing the grade above target max
    pushing_sentences = [
        s["rank"] for s in hardest_sentences if s.get("grade", 0.0) > target_max
    ]

    return {
        "audience_key": audience_key,
        "audience_label": preset["label"],
        "target_grade_range": f"Grade {target_min:.0f}–{target_max:.0f}",
        "target_wps_range": f"{preset['target_wps_min']:.0f}–{preset['target_wps_max']:.0f} words",
        "verdict": verdict,
        "verdict_band": verdict_band,
        "pushing_sentence_ranks": pushing_sentences,
    }


def check_language(all_words: List[str]) -> Tuple[bool, Optional[str]]:
    """Heuristic to detect non-English input."""
    if len(all_words) < 20:
        return True, None

    english_count = sum(1 for w in all_words if w.lower() in COMMON_ENGLISH_WORDS)
    ratio = english_count / len(all_words)
    if ratio < 0.06:
        return (
            False,
            "Notice: Inkgauge readability formulas are calibrated for English prose. Scores on non-English text are approximate.",
        )
    return True, None


def analyze_chapter(text: str, audience_key: str = "commercial_fiction") -> Dict[str, Any]:
    """
    Perform full core readability and style analysis on a chapter.
    Returns scores, hardest sentences, paragraph heatmaps, and style flags.
    """
    token_res = TokenizeResult(paragraphs=[], total_sentences=0, total_words=0)
    from app.analysis.tokenize import tokenize_text
    token_res = tokenize_text(text)

    all_sentences: List[SentenceSpan] = []
    for p in token_res.paragraphs:
        all_sentences.extend(p.sentences)

    total_sentences = len(all_sentences)
    all_words = [w for s in all_sentences for w in s.words]
    total_words = len(all_words)

    # Handle edge case: empty or zero words
    if total_words == 0 or total_sentences == 0:
        return {
            "reading_ease": 0.0,
            "reading_ease_band": "No text provided",
            "grade_level": 0.0,
            "grade_level_band": "No text provided",
            "word_count": 0,
            "sentence_count": 0,
            "words_per_sentence_mean": 0.0,
            "words_per_sentence_median": 0.0,
            "long_words_pct": 0.0,
            "reading_time_minutes": 0.0,
            "reading_time_display": "0 min",
            "hardest_sentences": [],
            "paragraphs": [],
            "audience_fit": assess_audience_fit(0.0, 0.0, audience_key, []),
            "style_flags": {
                "passive_voice_count": 0,
                "adverbs_ly_count": 0,
                "repeated_openers": [],
                "dialogue_analysis": {"has_dialogue": False, "dialogue_grade": None, "narration_grade": None},
            },
            "language_notice": None,
        }

    # Syllables
    word_syllables = [count_syllables(w) for w in all_words]
    total_syllables = sum(word_syllables)
    long_words_count = sum(1 for syl in word_syllables if syl >= 3)
    long_words_pct = round((long_words_count / total_words) * 100, 1)

    # Whole text formulas
    avg_wps = total_words / total_sentences
    sentence_word_counts = [s.word_count for s in all_sentences]
    median_wps = round(statistics.median(sentence_word_counts), 1) if sentence_word_counts else 0.0
    mean_wps = round(avg_wps, 1)

    syl_per_word = total_syllables / total_words

    # Flesch Reading Ease = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    flesch_reading_ease = round(206.835 - 1.015 * avg_wps - 84.6 * syl_per_word, 1)

    # Flesch-Kincaid grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
    fk_grade = round(max(0.0, 0.39 * avg_wps + 11.8 * syl_per_word - 15.59), 1)

    reading_time_mins = round(total_words / READING_SPEED_WPM, 1)
    reading_time_display = f"{max(1, round(total_words / READING_SPEED_WPM))} min" if total_words > 120 else "< 1 min"

    # Sentence difficulties
    sentence_analysis_map: Dict[int, Dict[str, Any]] = {}
    raw_scores: List[float] = []

    for s_idx, sentence in enumerate(all_sentences):
        metrics = calculate_sentence_raw_difficulty(sentence, avg_wps)
        sentence_analysis_map[s_idx] = metrics
        raw_scores.append(metrics["raw_score"])

    # Normalization (0 to 100) for difficulty strip and heat shading
    min_raw = min(raw_scores) if raw_scores else 0.0
    max_raw = max(raw_scores) if raw_scores else 1.0
    raw_range = max_raw - min_raw if max_raw > min_raw else 1.0

    normalized_scores: List[float] = []
    for r in raw_scores:
        norm = ((r - min_raw) / raw_range) * 100.0
        normalized_scores.append(round(norm, 1))

    # Rank the 5 hardest sentences:
    # "Skip sentences with fewer than 4 words when ranking 'hardest' (they are noise), but still count them in totals."
    candidates = []
    for s_idx, sentence in enumerate(all_sentences):
        if sentence.word_count >= 4:
            candidates.append((sentence_analysis_map[s_idx]["raw_score"], s_idx, sentence))

    candidates.sort(key=lambda c: c[0], reverse=True)
    top_candidates = candidates[:5]

    hardest_sentences: List[Dict[str, Any]] = []
    for rank, (score, s_idx, s) in enumerate(top_candidates, 1):
        metrics = sentence_analysis_map[s_idx]
        reasons = explain_sentence_difficulty(
            sentence_text=s.text,
            word_count=s.word_count,
            chapter_avg_words=avg_wps,
            long_words=metrics["long_words"],
            clause_count=metrics["clause_count"],
            passive_phrases=metrics["passive_phrases"],
            sentence_grade=metrics["grade"],
        )
        hardest_sentences.append({
            "rank": rank,
            "start": s.start,
            "end": s.end,
            "text": s.text,
            "score": round(score, 1),
            "difficulty_norm": normalized_scores[s_idx],
            "grade": metrics["grade"],
            "word_count": s.word_count,
            "reasons": reasons,
        })

    # Prepare paragraphs with per-sentence difficulty for frontend heatmap
    paragraphs_payload: List[Dict[str, Any]] = []
    global_s_idx = 0
    for p in token_res.paragraphs:
        p_sentences = []
        for s in p.sentences:
            p_sentences.append({
                "text": s.text,
                "start": s.start,
                "end": s.end,
                "word_count": s.word_count,
                "difficulty": normalized_scores[global_s_idx],
                "grade": sentence_analysis_map[global_s_idx]["grade"],
                "index": global_s_idx,
            })
            global_s_idx += 1
        paragraphs_payload.append({
            "index": p.index,
            "start": p.start,
            "end": p.end,
            "sentences": p_sentences,
        })

    # Style flags
    all_sentence_texts = [s.text for s in all_sentences]
    passive_phrases_total = sum(len(sentence_analysis_map[i]["passive_phrases"]) for i in range(len(all_sentences)))
    ly_adverbs = find_ly_adverbs(all_words)
    repeated_openers = find_repeated_openers(all_sentence_texts)
    dialogue_info = analyze_dialogue_vs_narration(text)

    # Audience assessment
    audience_fit = assess_audience_fit(fk_grade, avg_wps, audience_key, hardest_sentences)

    # Non-English check
    is_english, lang_notice = check_language(all_words)

    return {
        "reading_ease": flesch_reading_ease,
        "reading_ease_band": get_flesch_reading_ease_band(flesch_reading_ease),
        "grade_level": fk_grade,
        "grade_level_band": get_flesch_kincaid_band(fk_grade),
        "word_count": total_words,
        "sentence_count": total_sentences,
        "words_per_sentence_mean": mean_wps,
        "words_per_sentence_median": median_wps,
        "long_words_pct": long_words_pct,
        "reading_time_minutes": reading_time_mins,
        "reading_time_display": reading_time_display,
        "hardest_sentences": hardest_sentences,
        "paragraphs": paragraphs_payload,
        "audience_fit": audience_fit,
        "style_flags": {
            "passive_voice_count": passive_phrases_total,
            "adverbs_ly_count": len(ly_adverbs),
            "repeated_openers": repeated_openers,
            "dialogue_analysis": dialogue_info,
        },
        "language_notice": lang_notice,
    }
