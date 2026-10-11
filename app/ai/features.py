"""High-level AI features: sentence rewriting, editor notes, and chapter reads.

Seamlessly supports external LLMs (Claude, Gemini, Ollama) and automatic fallback
to the free, offline Local Editorial Engine so features work 100% of the time with zero API keys.
"""

from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field

from app.analysis.tokenize import extract_words
from app.analysis.syllables import count_syllables
from app.ai.client import call_ai_json
from app.ai import prompts
from app.ai.local_engine import (
    local_rewrite_sentence,
    local_explain_sentence,
    local_chapter_read,
)
from app.config import CHAPTER_READ_MAX_WORDS


class RewriteResponseModel(BaseModel):
    lighter: str = Field(description="Lighter, shorter variant")
    balanced: str = Field(description="Balanced natural variant")
    voice_preserving: str = Field(description="Voice-preserving variant changing fewest words")


class ExplainResponseModel(BaseModel):
    editor_note: str = Field(description="Concise editorial note under 50 words")


class StallPoint(BaseModel):
    paragraph_summary: str
    why_stalled: str
    editorial_tip: str


class ChapterReadResponseModel(BaseModel):
    pacing: str
    clarity: str
    stall_points: List[StallPoint] = Field(min_length=1, max_length=5)


def calculate_sentence_fk_grade(sentence_text: str) -> float:
    """Calculate Flesch-Kincaid grade level for a single sentence using our own pure-Python scoring code."""
    words = extract_words(sentence_text)
    if not words:
        return 0.0
    num_words = len(words)
    total_syllables = sum(count_syllables(w) for w in words)
    fk = 0.39 * num_words + 11.8 * (total_syllables / num_words) - 15.59
    return round(max(0.0, fk), 1)


def rewrite_sentence(
    sentence: str,
    context: str,
    voice_sample: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Generate three rewrite variants (lighter, balanced, voice-preserving),
    and compute their actual FK grades using our pure-Python scoring code.
    Seamlessly uses local NLP engine if no external API key is present.
    """
    orig_grade = calculate_sentence_fk_grade(sentence)

    voice_section = ""
    if voice_sample and voice_sample.strip():
        sample_words = voice_sample.strip().split()[:250]
        cleaned_sample = " ".join(sample_words)
        voice_section = f"\nAuthor's personal voice sample to match:\n<author_voice_sample>\n{cleaned_sample}\n</author_voice_sample>\n"

    user_prompt = prompts.REWRITE_USER_PROMPT.format(
        sentence=sentence.strip(),
        context=context.strip(),
        voice_section=voice_section,
    )

    result, error_signal, provider = call_ai_json(
        system_prompt=prompts.REWRITE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=RewriteResponseModel,
        model_type="fast",
        max_tokens=600,
    )

    if result is not None:
        lighter_txt = result.lighter.strip()
        balanced_txt = result.balanced.strip()
        vp_txt = result.voice_preserving.strip()
    else:
        # Fallback to zero-dependency local engine
        local_res = local_rewrite_sentence(sentence, context, voice_sample)
        lighter_txt = local_res["lighter"]
        balanced_txt = local_res["balanced"]
        vp_txt = local_res["voice_preserving"]
        provider = "local"

    variants = {
        "lighter": {
            "text": lighter_txt,
            "grade": calculate_sentence_fk_grade(lighter_txt),
        },
        "balanced": {
            "text": balanced_txt,
            "grade": calculate_sentence_fk_grade(balanced_txt),
        },
        "voice_preserving": {
            "text": vp_txt,
            "grade": calculate_sentence_fk_grade(vp_txt),
        },
        "original_grade": orig_grade,
        "provider": provider,
    }

    return variants, None


def explain_hard_sentence(
    sentence: str,
    reasons: List[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Generate a concise editor's note grounded in measured reasons.
    Seamlessly uses local engine if no external API key is provided.
    """
    reasons_text = "\n".join(f"- {r}" for r in reasons)
    user_prompt = prompts.EXPLAIN_USER_PROMPT.format(
        sentence=sentence.strip(),
        reasons=reasons_text,
    )

    result, error_signal, provider = call_ai_json(
        system_prompt=prompts.EXPLAIN_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ExplainResponseModel,
        model_type="fast",
        max_tokens=200,
    )

    if result is not None:
        note_txt = result.editor_note.strip()
    else:
        note_txt = local_explain_sentence(sentence, reasons)
        provider = "local"

    return {"editor_note": note_txt, "provider": provider}, None


def read_chapter(
    text: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Produce structured chapter diagnostic.
    Seamlessly uses local developmental engine if external API key is absent.
    """
    words = text.split()
    truncated = False
    if len(words) > CHAPTER_READ_MAX_WORDS:
        words = words[:CHAPTER_READ_MAX_WORDS]
        truncated = True
    processed_text = " ".join(words)

    user_prompt = prompts.CHAPTER_READ_USER_PROMPT.format(text=processed_text)

    result, error_signal, provider = call_ai_json(
        system_prompt=prompts.CHAPTER_READ_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=ChapterReadResponseModel,
        model_type="deep",
        max_tokens=1000,
    )

    if result is not None:
        return {
            "pacing": result.pacing.strip(),
            "clarity": result.clarity.strip(),
            "stall_points": [sp.model_dump() for sp in result.stall_points],
            "truncated": truncated,
            "provider": provider,
        }, None
    else:
        local_res = local_chapter_read(processed_text)
        local_res["provider"] = "local"
        local_res["truncated"] = truncated
        return local_res, None
