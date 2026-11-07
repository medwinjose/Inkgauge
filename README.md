# Inkgauge - A copyeditor's proof sheet

[![CI](https://github.com/medwinjose/Inkgauge/actions/workflows/ci.yml/badge.svg)](https://github.com/medwinjose/Inkgauge/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Inkgauge is a web app that scores the readability of a pasted English chapter and marks the five sentences that carry the most reading load, each with the measured reasons. Live at [inkgauge.vercel.app](https://inkgauge.vercel.app).

## The Problem

Authors and editors revising a chapter need to know where a reader will slow down. Standard readability formulas such as Flesch Reading Ease and Flesch-Kincaid grade return one number for the whole text. That number says whether a chapter is hard, but not which sentences make it hard or why.

Finding those sentences by hand means rereading the whole chapter. Generic sentence splitters also break fiction dialogue such as `"Wait!" he shouted.` into two fragments, which distorts per-sentence counts.

## The Solution

Inkgauge computes the standard chapter scores and then ranks every sentence by its own load, so the reader-stopping sentences are highlighted in place:

- **Sentence splitting that keeps dialogue intact.** Text is split with `pysbd`, then speech tags such as "she said" are merged back onto their quotation. Character offsets match the original text exactly, so highlights land on the right words.
- **Syllables from a pronunciation dictionary.** Counts come from CMUdict, with a rule-based fallback for unknown words and fixed counts for conversational pronunciations such as "every" (2) and "business" (2).
- **A per-sentence load score.** Each sentence of four or more words is scored from its grade, length, share of words with three or more syllables, clause count and passive voice. The top five are numbered in the text and in the margin. Shorter sentences still count in the chapter totals.
- **Reasons in plain words.** Each ranked sentence lists what was measured, for example its length against the chapter average and its long words.
- **Chapter metrics and audience fit.** Flesch Reading Ease, Flesch-Kincaid grade, words per sentence (mean and median), share of long words and reading time at 238 words per minute. The grade is compared with one of six audience targets: middle grade, young adult, commercial fiction, literary fiction, nonfiction or business, and academic.
- **Style counts.** Passive voice, -ly adverbs, repeated sentence openers, and separate grades for dialogue and narration.
- **Navigation.** A strip of bars, one per sentence, shows load across the chapter; clicking a bar jumps to that sentence. Optional heat shading colours every sentence by load.
- **Rewrite, explain and chapter read.** Three rewrites of a sentence (lighter, balanced, voice-preserving), each regraded by the app's own scoring code; a note of 50 words or fewer on why a sentence is hard; and a chapter read covering pacing, clarity and three stall points, over the first 12,000 words. These use Anthropic, Google Gemini or a local Ollama server when one is configured. Otherwise a built-in rule-based engine answers from phrase substitutions and sentence statistics, with no key and no network.
- **No storage.** Text is processed in memory per request. There is no database and no account.

![Inkgauge in dark theme after analysing the thriller sample: readability scores on the left, the chapter in the centre, ranked hardest sentences with rewrite suggestions on the right](docs/screenshot.png)

| Design decision | Instead of | Why |
|---|---|---|
| Readability formulas implemented in the app | An external readability library | Every score traces to code, and the formulas are checked against hand-calculated values in the tests |
| CMUdict with a rule-based fallback | A heuristic syllable counter alone | Dictionary accuracy for known words, coverage for unknown ones |
| Server-rendered Jinja2 page with plain JavaScript | A single-page framework | No frontend build step |
| Built-in rule-based engine as the last fallback | Requiring a provider key | Every feature works offline and without an account |
| Processing in memory | Storing manuscripts | Nothing to retain or secure at rest |

## Architecture

Every analysis request runs through one pipeline in `app/analysis`; the assist features go through one provider chain in `app/ai`:

```
POST /api/analyze
  text → tokenize (pysbd + dialogue-tag merge, exact offsets)
       → syllables (CMUdict → fallback rules)
       → scoring (chapter formulas, per-sentence load, top 5, audience fit)
       → style (passive voice, -ly adverbs, openers, dialogue vs narration)
       → JSON for the proof sheet

POST /api/ai/rewrite | /api/ai/explain | /api/ai/chapter-read
  Anthropic (if key) → Gemini (if key) → Ollama (if reachable) → built-in rule-based engine
```

The same FastAPI app runs under Uvicorn locally, in the `Dockerfile` image, and on Vercel through `api/index.py` and `vercel.json`.

## Results

The four sample chapters in `tests/fixtures` (63 to 88 words each), analysed through `POST /api/analyze` at commit `8324f11` on 2026-11-07 with the default audience (demo):

| Sample | Words / sentences | Flesch Reading Ease | Flesch-Kincaid grade |
|---|---|---|---|
| Children's story | 63 / 7 | 109.1 | 0.3 |
| Thriller scene | 82 / 8 | 76.8 | 5.1 |
| Literary passage | 88 / 3 | 15.6 | 18.4 |
| Dense business prose | 65 / 3 | -85.9 | 30.6 |

- **Ordering (tested):** the test suite asserts that reading ease falls and grade rises in this order, with the children's story below grade 4 and the business prose above grade 14 (`test_fixture_relative_difficulty_ordering`).
- **Formulas (tested):** Flesch Reading Ease and Flesch-Kincaid grade match hand-calculated values of 59.6 and 9.9 on a fixed passage (`test_hand_calculated_flesch_formulas`).

The command that produces the table is in the quick start below.

## Engineering

- **Structure:** a FastAPI app with three parts: `app/analysis` (tokenising, syllables, scoring, style flags, plain-word reasons), `app/ai` (provider client, prompts, built-in engine), and a Jinja2 template with plain JavaScript and CSS, including light and dark themes.
- **Security:** Content Security Policy (scripts from the app's own origin only), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: strict-origin-when-cross-origin` on every response. Input over 150,000 characters is rejected with HTTP 413. Per-IP limits return HTTP 429 after 30 analyses a minute or 30 assist calls an hour. Provider keys are read from the server environment and never sent to the browser.
- **Interfaces:** a JSON HTTP API: `POST /api/analyze`, `POST /api/ai/rewrite`, `POST /api/ai/explain`, `POST /api/ai/chapter-read` and `GET /api/health`.
- **Verification:** unit tests for syllable counting (dictionary and fallback), sentence splitting and dialogue merging, the chapter formulas, the hardest-sentence ranking and offsets, audience presets and style flags; HTTP tests through FastAPI's test client for each endpoint, security headers, input limits, rate limiting, and mocked Anthropic and Gemini responses. 32 tests pass (`pytest -q`, 2026-11-07, commit `8324f11`, Python 3.13).
- **CI:** GitHub Actions runs the test suite on Python 3.11, 3.12 and 3.13 for every push to `main` and every pull request.

## Quick start

Requires Python 3.11 or newer and git.

```bash
git clone https://github.com/medwinjose/Inkgauge.git
cd Inkgauge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
```

Run the app, then open http://127.0.0.1:8000:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

To use an external provider, copy the example settings and fill in a key; without one, the built-in engine is used:

```bash
cp .env.example .env
```

Reproduce the results table:

```bash
python - <<'EOF'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
for name in ["children_story", "thriller_scene", "literary_passage", "dense_business"]:
    text = open(f"tests/fixtures/{name}.txt").read()
    r = client.post("/api/analyze", json={"text": text}).json()
    print(name, r["word_count"], r["sentence_count"], r["reading_ease"], r["grade_level"])
EOF
```

## Status and limits

Inkgauge is a working side project in beta. Analysis, the proof-sheet interface, the three assist features with their provider chain and fallback, and CI are complete.

The formulas are calibrated for English; other languages get a notice and approximate scores. Flesch Reading Ease is not clamped to 0-100, as the samples above show. Rate limits and the one-hour cache of assist responses live in process memory and reset with each process. When a provider key is set, the sentence or chapter is sent to that provider. Rewrites from the built-in engine are phrase substitutions and can repeat across the three variants. The Ollama path has no test.

## Repository layout

| Path | Contents |
|---|---|
| `app/analysis` | Tokenising, syllable counting, scoring, style flags, reasons |
| `app/ai` | Provider client (Anthropic, Gemini, Ollama), prompts, built-in rule-based engine |
| `app/templates`, `app/static` | Proof-sheet page, JavaScript and CSS |
| `app/main.py` | FastAPI routes, security headers, input limits |
| `tests` | Pytest suites and the four sample chapters |
| `api/index.py`, `vercel.json`, `public/static` | Vercel entrypoint, routing and static assets |
| `Dockerfile` | Container image running the app with Uvicorn |
| `docs` | Screenshot used in this README |

## License

MIT License. See [LICENSE](LICENSE).
