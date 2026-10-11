# Inkgauge Development Log

## 1. Assumptions
- **Python Runtime Environment**: Developed on Windows with Python 3.14 / 3.11+ using FastAPI and Uvicorn.
- **Strict Character Limit**: 150,000 characters limit is enforced strictly on both client and server; inputs exceeding this limit receive a friendly HTTP 413 error payload.
- **Zero Data Retention**: The author's chapter text is processed in-memory within the request-response lifecycle and is never written to disk, database, or logged.
- **Candidate Filtering for Ranking**: Sentences with fewer than 4 words are included in whole-chapter metrics (total word count, reading ease, words per sentence), but excluded from the candidate pool for the "five hardest sentences" to filter out dialogic interjections like "Yes.", "He nodded.", or "No.".
- **Default AI Models**: `INKGAUGE_FAST_MODEL` defaults to `claude-haiku-5-5` for sentence rewriting and short editor notes; `INKGAUGE_DEEP_MODEL` defaults to `claude-sonnet-5-5` for full chapter developmental reads.
- **Graceful Degradation**: Core readability analysis requires zero API keys and zero authentication. If `ANTHROPIC_API_KEY` is absent, AI buttons gracefully inform the user without breaking core functionality.

## 2. Where the tools got it wrong (Real mistakes encountered during build)

1. **CMUDict Syncope & Multiple Pronunciations**:
   - *Example*: `count_syllables("every")` returned 3 instead of 2. CMUDict lists `['EH1', 'V', 'ER0', 'IY0']` as its first pronunciation and `['EH1', 'V', 'R', 'IY0']` as its second.
   - *How it was found*: Unit test `test_core_tricky_words_exact` in `tests/test_syllables.py` failed with `AssertionError: assert 3 == 2`.
   - *Fix*: Created a canonical readability count map (`CANONICAL_COUNTS`) for colloquial syncopated words ("every", "business", "evening", "chocolate", "camera") and falling diphthongs ("fire") where standard readers and author tools expect the conversational pronunciation.

2. **Heuristic Hiatus Undercount in "created"**:
   - *Example*: `heuristic_syllable_count("created")` returned 2 instead of 3 when bypassing CMUDict.
   - *How it was found*: Unit test `test_heuristic_fallback_directly` failed with `AssertionError: assert 2 == 3`. The vowel cluster logic treated adjacent 'ea' as a single vowel sound (as in 'bread' or 'team'), missing the 'cre-ate' hiatus.
   - *Fix*: Added explicit hiatus regex matching common root syllables (`creat*`, `react*`, `poem`, `chaos`, `naive`) and hiatus vowel pairs (`ia`, `eo`, `iu`, `io`, `ua`, `uo`).

3. **Starlette TemplateResponse Parameter Inversion in Modern Starlette**:
   - *Example*: Calling `templates.TemplateResponse('index.html', {'request': request, ...})` triggered `TypeError: cannot use 'tuple' as a dict key (unhashable type: 'dict')` inside Jinja2's cache layer.
   - *How it was found*: API test `test_security_headers` calling `client.get('/')` failed.
   - *Fix*: Modern Starlette (0.36+) requires `request` as the first argument or an explicit keyword argument (`request=request, name='index.html', context={...}`). Updated route signature accordingly.

4. **Dialogue Tag Boundary Splitting in pysbd**:
   - *Example*: Dialogue sentences like `"Wait!" he shouted.` or `"Where?" asked Mary.` were broken into two separate segments by naive punctuation rules due to the terminal punctuation inside the quotation marks.
   - *How it was found*: Sentence boundary tests on dialogic fiction passages revealed speech tags becoming orphan sentences.
   - *Fix*: Implemented `_should_merge_dialogue()` in `tokenize.py` which inspects boundary characters and speech verbs (`said`, `asked`, `replied`, `whispered`, etc.) to merge the tag with the quotation into a single sentence span while preserving exact byte/character offsets.

5. **Margin Note Collision on Clustered Hard Sentences**:
   - *Example*: In dense chapters where two hardest sentences occurred in adjacent lines within the same paragraph, absolute vertical alignment caused margin note cards in the right gutter to visually collide and overlap.
   - *How it was found*: Visual inspection and layout coordinate checks when multiple candidate sentences were in the same paragraph.
   - *Fix*: Implemented a dynamic collision resolution algorithm in `app.js` (`layoutMarginNotes`): if `idealTop < lastBottom + 16px`, the card is pushed down to `lastBottom + 16px`, and smooth SVG cubic bezier curves connect the sentence anchor to the displaced note card.

6. **Vercel Serverless Function 500 Invocation Failure & Read-Only Filesystem**:
   - *Example*: Deploying to Vercel produced `500 FUNCTION_INVOCATION_FAILED` on `inkgauge.vercel.app`.
   - *How it was found*: Vercel live deployment returned 500 when accessing the domain.
   - *Fix*: Two root causes resolved:
     1. Created `api/index.py` and `vercel.json` routing configuration to provide the official Vercel Serverless Function entrypoint for FastAPI.
     2. Removed runtime `mkdir(parents=True, exist_ok=True)` in `app/main.py` which crashed during module import on the read-only AWS Lambda / Vercel execution environment.

## 3. Known limitations
- **Language Assumptions**: Readability formulas (Flesch Reading Ease and Flesch-Kincaid Grade Level) are specifically calibrated for English language prose structures and vocabulary. Non-English text triggers a gentle notice that scores are approximate.
- **Unpunctuated Poetry**: Verse without conventional punctuation or line breaks cannot be reliably segmented into sentence boundaries; whole-chapter word averages remain accurate, but clause load metrics are approximate.
- **Code & Markdown**: Pasted code blocks with nested punctuation can distort sentence counts; Inkgauge is designed for literary and expository prose manuscripts.

## 4. Decisions
- **Rule-based + CMUDict Hybrid**: Used `cmudict` for dictionary precision combined with an algorithmic heuristic fallback for out-of-vocabulary words.
- **Exact Offset Preservation**: Tracked sentence spans relative to original user input without mutating whitespace, enabling 100% fidelity between `text[start:end]` and highlighted `<mark>` spans.
- **Vanilla Frontend without Frameworks**: Used Jinja2 server templates, CSS custom properties, and vanilla JS to avoid bloated frontend build steps and provide instantaneous interactive responsiveness.
- **Server-Side AI Isolation**: Kept all Anthropic API integration strictly server-side with strict timeouts, Pydantic schema validation, and retry logic to protect user credentials and ensure graceful failure modes.
- **Multi-Provider AI with Zero-Key Local Engine**: Created `app/ai/local_engine.py` to ensure all three AI features (rewriting, editor notes, and developmental chapter read) work completely out of the box with zero credentials, 100% offline and free. Added plug-and-play support for Google Gemini (generous free tier via `GEMINI_API_KEY`) and Ollama local models (`OLLAMA_HOST`) alongside Anthropic Claude.
- **Vercel uv Application Packaging**: Configured `[tool.uv] package = false` and explicit `[tool.setuptools.packages.find]` in `pyproject.toml` so Vercel's Python uv builder installs application dependencies without triggering setuptools flat-layout wheel compilation errors across `api` and `app`.
- **Python 3.12 Runtime Typing Compatibility**: Added `from __future__ import annotations` and explicit `Tuple` import in `app/analysis/scoring.py` to fix runtime `NameError: name 'Tuple' is not defined` during module execution on Vercel's Python 3.12 serverless runtime.

