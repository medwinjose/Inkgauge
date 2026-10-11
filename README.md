# Inkgauge

> A copyeditor's proof sheet for fiction and nonfiction authors.

Inkgauge is a free, privacy-first web diagnostic tool designed for authors, editors, and creative writing students. Paste a chapter (up to 150,000 characters) to instantly view readability metrics, style flags, and the **five hardest sentences** highlighted directly in your text with numbered editorial margin notes.

---

## AI Features (100% Free & Local by Default)

**No API keys or logins required.** Inkgauge includes a **built-in Local Offline AI Engine** out of the box, with optional support for **Google Gemini (free tier)**, **Ollama**, or **Anthropic Claude**:

1. **Suggest Rewrites**: Returns three distinct revisions (lighter, balanced, voice-preserving) with new grade levels calculated by our own pure-Python scoring code.
2. **Why Is This Hard?**: A concise 50-word editor's note grounded in measured sentence statistics (clause load, passive phrasing, polysyllabic density).
3. **Chapter Read**: A structured developmental overview covering pacing, clarity, and three potential reader stall points.

### Supported AI Providers
- **Built-in Local Engine (Default)**: Runs 100% locally in pure Python. Instant, zero setup, completely offline, zero API keys.
- **Google Gemini (Free tier)**: Set `GEMINI_API_KEY` in `.env` to use Google's free Gemini 1.5 Flash models.
- **Ollama (Free local LLMs)**: Point to a running Ollama instance (`http://localhost:11434`) with models like `llama3.2`, `mistral`, or `gemma2`.
- **Anthropic Claude**: Set `ANTHROPIC_API_KEY` to use Claude 3.5 Sonnet & Haiku.

---

## Features

- **Marked-up Proof Sheet Design**: Your manuscript sits in a calm reading column. The five hardest sentences are highlighted with editorial strokes and linked to numbered margin notes vertically aligned with connector lines.
- **Difficulty Strip Timeline**: An interactive timeline across the top representing every sentence in the chapter. Taller and darker bars indicate higher cognitive load; click any bar to jump directly to that sentence.
- **Core Readability Metrics**:
  - **Flesch Reading Ease** with plain-language audience bands.
  - **Flesch-Kincaid Grade Level** calculated via pure Python.
  - Words per sentence (mean and median), word count, percentage of long words (3+ syllables), and estimated reading time (238 wpm).
- **Target Audience Presets**: Compare your text against Middle Grade, Young Adult, Commercial Fiction, Literary Fiction, Nonfiction/Business, or Academic targets.
- **Style Flags**: In-depth counts and diagnostics for passive voice, -ly adverbs, repeated sentence openers, and separate dialogue vs. narration reading levels.
- **Heat Shading**: Optional single-hue ultramarine ramp shading every sentence across the chapter by cognitive load.
- **Zero Login & Zero Storage**: Analyzed strictly in-memory; user text is never stored, logged, or retained.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- **Text Analysis**: Pure-Python analysis engine (`analysis/`):
  - `cmudict` for syllable accuracy + rule-based fallback heuristic
  - `pysbd` for accurate sentence boundary disambiguation with dialogue tag preservation
- **Frontend**: Jinja2 templates, vanilla JavaScript, hand-written CSS with dark/light themes (no React, Tailwind, or component libraries)
- **Local AI & NLP**: `app/ai/local_engine.py` (offline linguistic transform engine)
- **Multi-Provider Cloud AI**: Optional Google Gemini, Ollama, and Anthropic Claude
- **Testing**: `pytest`, `httpx`

---

## Quickstart

### 1. Local Setup with Python

```bash
# Clone the repository
git clone https://github.com/your-username/inkgauge.git
cd inkgauge

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Copy environment variables if you want to use Google Gemini or Claude
cp .env.example .env
```

### 2. Run the Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### 3. Run Tests

```bash
pytest -v
```

---

## Privacy & Security

- **In-Memory Only**: Manuscript text is received and processed in transient memory and discarded after response generation.
- **No Database**: No database or user account tracking exists in the system.
- **Offline Capable**: With the built-in local engine, not a single byte of manuscript data ever leaves your computer.
- **Strict Headers**: Content Security Policy (`CSP`), `X-Content-Type-Options: nosniff`, and `Referrer-Policy` enabled.
