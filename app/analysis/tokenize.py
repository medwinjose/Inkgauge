"""Sentence and word tokenization with exact offset tracking and dialogue preservation."""

import re
from dataclasses import dataclass, field
from typing import List, Tuple
import pysbd

# Word tokenization regex: runs of alphanumeric characters with internal hyphens or apostrophes
WORD_RE = re.compile(r"[a-zA-Z0-9]+(?:['’\-][a-zA-Z0-9]+)*")

# Paragraph splitter regex: one or more blank lines (handling \r?\n)
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

# Common dialogue speech verbs in lowercase
SPEECH_VERBS = {
    "said", "asked", "replied", "whispered", "shouted", "yelled", "murmured",
    "muttered", "screamed", "cried", "gasped", "snapped", "groaned", "laughed",
    "sighed", "stammered", "stuttered", "breathed", "demanded", "inquired",
    "continued", "added", "remarked", "answered", "called", "echoed"
}


@dataclass
class SentenceSpan:
    text: str
    start: int
    end: int
    words: List[str]
    word_count: int


@dataclass
class ParagraphData:
    index: int
    start: int
    end: int
    sentences: List[SentenceSpan]


@dataclass
class TokenizeResult:
    paragraphs: List[ParagraphData]
    total_sentences: int
    total_words: int


def extract_words(text: str) -> List[str]:
    """Extract words (runs of letters, digits, hyphens, or apostrophes). Ignores pure punctuation."""
    return WORD_RE.findall(text)


def _should_merge_dialogue(prev_text: str, curr_text: str) -> bool:
    """
    Check if curr_text is a speech tag or dialogue continuation belonging to prev_text.
    e.g. prev: '"Wait!"' curr: 'she said.'
    or prev: '"Wait," she said,' curr: '"do not leave yet."'
    """
    prev_stripped = prev_text.strip()
    curr_stripped = curr_text.strip()
    if not prev_stripped or not curr_stripped:
        return False

    # Case 1: prev ends with quote after punctuation, curr starts with lowercase speech tag
    # e.g. prev: '"Where are you going?"', curr: 'she asked softly.'
    if (prev_stripped.endswith(('!"', '?"', "!'", "?'")) or prev_stripped.endswith(('!"', '?"', '”', '’'))) and curr_stripped[0].islower():
        return True

    # Case 2: prev ends with speech tag comma, curr starts with continuing quote
    # e.g. prev: '"Wait," she said,', curr: '"don't leave."'
    if prev_stripped.endswith((',', ',"', ",'", ',”', '’')) and (curr_stripped.startswith(('"', "'", '“', '‘')) or curr_stripped[0].islower()):
        return True

    # Case 3: curr starts with common speech tag e.g. 'said John.' or 'asked Mary.'
    first_word = curr_stripped.split()[0].lower().strip(".,!?;:'\"") if curr_stripped.split() else ""
    if first_word in SPEECH_VERBS and (prev_stripped.endswith(('"', "'", '”', '’'))):
        return True

    return False


def tokenize_text(text: str) -> TokenizeResult:
    """
    Split text into paragraphs on blank lines, then into sentences with exact character offsets.
    Guarantees text[sentence.start:sentence.end] == sentence.text.
    """
    if not text or not text.strip():
        return TokenizeResult(paragraphs=[], total_sentences=0, total_words=0)

    segmenter = pysbd.Segmenter(language="en", clean=False)
    paragraphs: List[ParagraphData] = []
    total_sentences = 0
    total_words = 0

    # Split paragraphs by blank lines while preserving exact offsets
    # Match non-blank blocks
    raw_paras: List[Tuple[int, int, str]] = []
    # Use finditer on non-blank chunks
    for match in re.finditer(r"[^\r\n]+(?:\r?\n(?!\r?\n)[^\r\n]+)*", text):
        raw_paras.append((match.start(), match.end(), match.group(0)))

    for p_idx, (p_start, p_end, p_raw) in enumerate(raw_paras):
        if not p_raw.strip():
            continue

        raw_segments = segmenter.segment(p_raw)
        if not raw_segments:
            continue

        # Merge split dialogue tags where pysbd split '"Wait!"' and 'she said.'
        merged_segments: List[str] = []
        for seg in raw_segments:
            if merged_segments and _should_merge_dialogue(merged_segments[-1], seg):
                merged_segments[-1] = merged_segments[-1] + seg
            else:
                merged_segments.append(seg)

        # Locate exact offsets for each sentence inside p_raw
        sentences: List[SentenceSpan] = []
        search_offset = 0

        for seg in merged_segments:
            if not seg.strip():
                continue

            # Find where this segment begins in p_raw starting from search_offset
            seg_pos = p_raw.find(seg, search_offset)
            if seg_pos == -1:
                # Fallback if find fails
                seg_pos = search_offset

            # Trim leading/trailing whitespace to get precise highlight boundaries
            lead_spaces = len(seg) - len(seg.lstrip())
            tail_spaces = len(seg) - len(seg.rstrip())

            s_text = seg.strip()
            if not s_text:
                search_offset = seg_pos + len(seg)
                continue

            s_start = p_start + seg_pos + lead_spaces
            s_end = p_start + seg_pos + len(seg) - tail_spaces

            # Assert offset consistency with original text
            actual_slice = text[s_start:s_end]
            if actual_slice != s_text:
                # Exact adjust if any whitespace discrepancy
                s_text = actual_slice

            words = extract_words(s_text)
            sentences.append(
                SentenceSpan(
                    text=s_text,
                    start=s_start,
                    end=s_end,
                    words=words,
                    word_count=len(words),
                )
            )
            search_offset = seg_pos + len(seg)

        if sentences:
            paragraphs.append(
                ParagraphData(
                    index=p_idx,
                    start=sentences[0].start,
                    end=sentences[-1].end,
                    sentences=sentences,
                )
            )
            total_sentences += len(sentences)
            total_words += sum(s.word_count for s in sentences)

    return TokenizeResult(
        paragraphs=paragraphs,
        total_sentences=total_sentences,
        total_words=total_words,
    )
