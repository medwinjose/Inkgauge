"""Generate rule-based, measured explanations for why a sentence is difficult."""

from typing import List

NUMBER_WORDS = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
    11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen"
}


def explain_sentence_difficulty(
    sentence_text: str,
    word_count: int,
    chapter_avg_words: float,
    long_words: List[str],
    clause_count: int,
    passive_phrases: List[str],
    sentence_grade: float,
) -> List[str]:
    """
    Return 1 to 3 short, specific, rule-based reasons explaining why the sentence is hard.
    Every reason must cite something measurable in the sentence.
    """
    reasons: List[str] = []

    # Reason 1: Length in words relative to chapter
    if word_count >= 28 or (word_count >= chapter_avg_words * 1.5 and word_count >= 20):
        reasons.append(
            f"{word_count} words long. The chapter average is {round(chapter_avg_words)}."
        )

    # Reason 2: Long / multisyllabic words
    if len(long_words) >= 2:
        num_str = NUMBER_WORDS.get(len(long_words), str(len(long_words)))
        samples = ", ".join(f"'{w.lower()}'" for w in long_words[:3])
        if len(long_words) > 3:
            samples += ", ..."
        reasons.append(
            f"{num_str} words of three or more syllables: {samples}."
        )

    # Reason 3: Heavy clause load or multiple conjunctions
    if clause_count >= 3:
        num_str = NUMBER_WORDS.get(clause_count, str(clause_count))
        reasons.append(
            f"{num_str} clauses and parentheticals connected by punctuation."
        )

    # Reason 4: Passive voice
    if passive_phrases:
        reasons.append(
            f"Passive voice: '{passive_phrases[0]}'."
        )

    # Fallback if none of the above triggered but sentence was ranked top
    if not reasons:
        if word_count > chapter_avg_words:
            reasons.append(
                f"{word_count} words long (above chapter average of {round(chapter_avg_words)})."
            )
        else:
            reasons.append(
                f"Elevated syllable complexity yielding a Grade {round(sentence_grade, 1)} reading level."
            )

    return reasons[:3]
