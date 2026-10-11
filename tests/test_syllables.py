"""Unit tests for syllable counting in app.analysis.syllables."""

import pytest
from app.analysis.syllables import count_syllables, is_long_word, heuristic_syllable_count


# 60 tricky words with expected syllable counts
TRICKY_WORDS = [
    ("business", 2),
    ("every", 2),
    ("queue", 1),
    ("fire", 1),         # Monosyllabic / falling diphthong in modern reading
    ("area", 3),
    ("created", 3),
    ("people", 2),
    ("beautiful", 3),
    ("chocolate", 2),
    ("evening", 2),
    ("family", 3),
    ("different", 2),
    ("interesting", 4),
    ("rhythm", 2),
    ("quiet", 2),
    ("poem", 2),
    ("chaos", 2),
    ("naive", 2),
    ("simile", 3),
    ("recipe", 3),
    ("epitome", 4),
    ("catastrophe", 4),
    ("subtle", 2),
    ("aisle", 1),
    ("colonel", 2),
    ("wednesday", 2),
    ("comfortable", 4),
    ("camera", 2),
    ("memory", 3),
    ("history", 2),
    ("vegetable", 3),
    ("diamond", 2),
    ("separate", 3),
    ("several", 2),
    ("temperature", 4),
    ("general", 2),
    ("natural", 2),
    ("probably", 2),
    ("actually", 4),
    ("usually", 3),
    ("finally", 3),
    ("literature", 4),
    ("miniature", 4),
    ("jewellery", 3),
    ("library", 3),
    ("secretary", 4),
    ("military", 4),
    ("necessary", 4),
    ("extraordinary", 5),
    ("imaginary", 5),
    ("laboratory", 4),
    ("author", 2),
    ("readability", 5),
    ("monosyllable", 5),
    ("polysyllable", 5),
    ("onomatopoeia", 6),
    ("encyclopedia", 6),
    ("anemone", 4),
    ("hyperbole", 4),
    ("synecdoche", 4),
]


def test_tricky_words_count():
    """Verify that all 60 tricky words return realistic syllable counts."""
    assert len(TRICKY_WORDS) == 60
    for word, expected in TRICKY_WORDS:
        count = count_syllables(word)
        assert abs(count - expected) <= 1, f"Word '{word}' syllable count was {count}, expected ~{expected}"


def test_core_tricky_words_exact():
    """Exact checks for prompt-specified words."""
    assert count_syllables("business") == 2
    assert count_syllables("every") == 2
    assert count_syllables("queue") == 1
    assert count_syllables("area") == 3
    assert count_syllables("created") == 3
    assert count_syllables("people") == 2
    assert count_syllables("beautiful") == 3
    assert count_syllables("fire") in (1, 2)


def test_heuristic_fallback_directly():
    """Check that the heuristic works when CMUDict is bypassed."""
    assert heuristic_syllable_count("business") == 2
    assert heuristic_syllable_count("queue") == 1
    assert heuristic_syllable_count("created") == 3
    assert heuristic_syllable_count("catastrophe") == 4
    assert heuristic_syllable_count("the") == 1
    assert heuristic_syllable_count("unbelievable") >= 4


def test_is_long_word():
    assert is_long_word("institutional", 3) is True
    assert is_long_word("bureaucracy", 3) is True
    assert is_long_word("cat", 3) is False
    assert is_long_word("simple", 3) is False


def test_punctuation_stripping():
    assert count_syllables("!beautiful?") == 3
    assert count_syllables('"business"') == 2
    assert count_syllables("people,") == 2
