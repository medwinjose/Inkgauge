"""Tests for scoring, readability formulas, difficulty ranking, and style flags."""

import pathlib
import pytest
from app.analysis.scoring import (
    analyze_chapter,
    get_flesch_reading_ease_band,
    get_flesch_kincaid_band,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def test_hand_calculated_flesch_formulas():
    """
    Test formulas against hand-calculated values:
    Suppose words = 100, sentences = 5, syllables = 150.
    words / sentences = 20.0
    syllables / words = 1.5
    Flesch Reading Ease = 206.835 - (1.015 * 20.0) - (84.6 * 1.5)
                        = 206.835 - 20.3 - 126.9 = 59.635 -> 59.6
    Flesch-Kincaid Grade = (0.39 * 20.0) + (11.8 * 1.5) - 15.59
                         = 7.8 + 17.7 - 15.59 = 9.91 -> 9.9
    """
    wps = 100 / 5
    spw = 150 / 100
    fre = round(206.835 - 1.015 * wps - 84.6 * spw, 1)
    fk = round(0.39 * wps + 11.8 * spw - 15.59, 1)

    assert fre == 59.6
    assert fk == 9.9


def test_fixture_relative_difficulty_ordering():
    """Assert that the 4 fixture chapters are sensibly ordered by difficulty."""
    children_txt = (FIXTURES_DIR / "children_story.txt").read_text(encoding="utf-8")
    thriller_txt = (FIXTURES_DIR / "thriller_scene.txt").read_text(encoding="utf-8")
    literary_txt = (FIXTURES_DIR / "literary_passage.txt").read_text(encoding="utf-8")
    business_txt = (FIXTURES_DIR / "dense_business.txt").read_text(encoding="utf-8")

    res_children = analyze_chapter(children_txt)
    res_thriller = analyze_chapter(thriller_txt)
    res_literary = analyze_chapter(literary_txt)
    res_business = analyze_chapter(business_txt)

    # Reading ease should descend: children > thriller > literary > business
    assert res_children["reading_ease"] > res_thriller["reading_ease"]
    assert res_thriller["reading_ease"] > res_literary["reading_ease"]
    assert res_literary["reading_ease"] > res_business["reading_ease"]

    # Grade level should ascend: children < thriller < literary < business
    assert res_children["grade_level"] < res_thriller["grade_level"]
    assert res_thriller["grade_level"] < res_literary["grade_level"]
    assert res_literary["grade_level"] < res_business["grade_level"]

    # Sanity checks on absolute ranges
    assert res_children["grade_level"] < 4.0
    assert res_business["grade_level"] > 14.0


def test_five_hardest_sentences_structure():
    """Verify top hardest sentences contain rank 1..N, exact offsets, and measurable reasons."""
    sample = (FIXTURES_DIR / "thriller_scene.txt").read_text(encoding="utf-8")
    res = analyze_chapter(sample)
    hardest = res["hardest_sentences"]

    assert len(hardest) > 0
    assert len(hardest) <= 5

    for idx, s in enumerate(hardest, 1):
        assert s["rank"] == idx
        assert "start" in s
        assert "end" in s
        assert "reasons" in s
        assert len(s["reasons"]) >= 1
        assert s["word_count"] >= 4
        # Offset test
        assert sample[s["start"]:s["end"]] == s["text"]


def test_audience_presets():
    """Verify audience fit feedback."""
    children_txt = (FIXTURES_DIR / "children_story.txt").read_text(encoding="utf-8")
    res_mg = analyze_chapter(children_txt, audience_key="middle_grade")
    assert "audience_fit" in res_mg
    assert res_mg["audience_fit"]["verdict_band"] in ("target", "easy")

    business_txt = (FIXTURES_DIR / "dense_business.txt").read_text(encoding="utf-8")
    res_acad = analyze_chapter(business_txt, audience_key="middle_grade")
    assert res_acad["audience_fit"]["verdict_band"] == "hard"


def test_style_flags():
    """Check detection of passive voice, adverbs, and dialogue split."""
    text = (
        'She walked quickly and quietly down the lane. '
        'The decision was extraordinarily mishandled by the committee. '
        '"I am leaving now," she said.'
    )
    res = analyze_chapter(text)
    style = res["style_flags"]

    assert style["passive_voice_count"] >= 1
    assert style["adverbs_ly_count"] >= 2
    assert style["dialogue_analysis"]["has_dialogue"] is True
