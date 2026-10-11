"""Tests for tokenization, sentence splitting, word tokenization, and offset preservation."""

import pytest
from app.analysis.tokenize import tokenize_text, extract_words, SentenceSpan, ParagraphData


def test_extract_words():
    text = "The author's state-of-the-art novel sold 100,000 copies in 1984! (Remarkable, right?)"
    words = extract_words(text)
    # A word is a run of letters, digits, apostrophes or hyphens
    assert "author's" in words
    assert "state-of-the-art" in words
    assert "1984" in words
    assert "Remarkable" in words
    assert "!" not in words
    assert "(" not in words


def test_sentence_splitting_abbreviations():
    text = "Dr. Smith and Mr. Brown visited Washington, D.C. yesterday. They had lunch with Prof. Davis."
    result = tokenize_text(text)
    sentences = [s.text for p in result.paragraphs for s in p.sentences]
    assert len(sentences) == 2
    assert sentences[0].startswith("Dr. Smith")
    assert sentences[0].endswith("yesterday.")
    assert sentences[1].startswith("They had lunch")


def test_sentence_splitting_decimals():
    text = "The value was 3.14159 approximately. Next measurement was 42.0 precisely."
    result = tokenize_text(text)
    sentences = [s.text for p in result.paragraphs for s in p.sentences]
    assert len(sentences) == 2
    assert "3.14159" in sentences[0]
    assert "42.0" in sentences[1]


def test_sentence_splitting_ellipses():
    text = "She waited... but nothing happened. Finally, the door creaked open."
    result = tokenize_text(text)
    sentences = [s.text for p in result.paragraphs for s in p.sentences]
    assert len(sentences) == 2
    assert "waited..." in sentences[0]


def test_sentence_splitting_dialogue():
    # Prompt: "a sentence inside quotes stays one sentence, and a speech tag ('she said.') does not become a separate sentence."
    text = '"I do not know," she said. "Wait!" he shouted.'
    result = tokenize_text(text)
    sentences = [s.text for p in result.paragraphs for s in p.sentences]
    assert len(sentences) == 2
    assert sentences[0] == '"I do not know," she said.'
    assert sentences[1] == '"Wait!" he shouted.'


def test_sentence_splitting_dialogue_continuation():
    text = '"Wait," she said, "do not leave yet." He paused at the door.'
    result = tokenize_text(text)
    sentences = [s.text for p in result.paragraphs for s in p.sentences]
    assert len(sentences) == 2
    assert sentences[0] == '"Wait," she said, "do not leave yet."'
    assert sentences[1] == 'He paused at the door.'


def test_offsets_exact_match():
    text = (
        'Chapter One\n\n'
        'It was the best of times, it was the worst of times. '
        'Dr. Jekyll was not at home; Mr. Hyde answered the door.\n\n'
        '"Who is there?" asked the stranger. "No one," replied the boy, smiling quietly.'
    )
    result = tokenize_text(text)
    for p in result.paragraphs:
        for s in p.sentences:
            extracted = text[s.start:s.end]
            assert extracted == s.text, f"Offset mismatch: expected '{s.text}', got '{extracted}'"


def test_empty_and_whitespace():
    assert len(tokenize_text("").paragraphs) == 0
    assert len(tokenize_text("   \n\n  \t  ").paragraphs) == 0


def test_single_sentence():
    text = "Just one lonely sentence here."
    result = tokenize_text(text)
    assert len(result.paragraphs) == 1
    assert len(result.paragraphs[0].sentences) == 1
    assert text[result.paragraphs[0].sentences[0].start:result.paragraphs[0].sentences[0].end] == text
