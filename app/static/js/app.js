/**
 * Inkgauge Client Application
 * Vanilla JS - Copyeditor's Proof Sheet
 */

(function () {
  "use strict";

  // Elements
  const themeToggle = document.getElementById("theme-toggle");
  const aboutBtn = document.getElementById("about-btn");
  const closeAboutBtn = document.getElementById("close-about-btn");
  const aboutPanel = document.getElementById("about-panel");

  const inputPanel = document.getElementById("input-panel");
  const proofPanel = document.getElementById("proof-panel");
  const chapterInput = document.getElementById("chapter-input");
  const charCounter = document.getElementById("char-counter");
  const sampleSelect = document.getElementById("sample-select");
  const analyzeBtn = document.getElementById("analyze-btn");
  const statusMessage = document.getElementById("status-message");
  const editTextBtn = document.getElementById("edit-text-btn");

  const manuscriptSurface = document.getElementById("manuscript-surface");
  const marginNotesList = document.getElementById("margin-notes-list");
  const connectorCanvas = document.getElementById("connector-canvas");
  const difficultyStrip = document.getElementById("difficulty-strip");
  const heatShadingToggle = document.getElementById("heat-shading-toggle");
  const audienceSelect = document.getElementById("audience-select");
  const audienceVerdict = document.getElementById("audience-verdict");
  const languageNotice = document.getElementById("language-notice");

  const copyReportBtn = document.getElementById("copy-report-btn");
  const chapterReadBtn = document.getElementById("chapter-read-btn");
  const chapterReadResults = document.getElementById("chapter-read-results");
  const chapterReadContent = document.getElementById("chapter-read-content");
  const closeChapterReadBtn = document.getElementById("close-chapter-read-btn");

  // State
  let analysisData = null;
  let currentRawText = "";
  let voiceSampleText = "";

  // Sample texts
  const SAMPLES = {
    thriller: `The rain hammered against the windshield as Miller killed the engine. 

"Did you bring the file?" asked Chen, staring into the dark alley. 

"It is in the trunk," Miller replied, checking his watch. The digital display read midnight. He unholstered his weapon and pushed the car door open into the damp cold. 

A shadow darted across the loading dock. Chen leaned forward, whispering, "Someone is watching the exit." Miller did not answer; he drew a breath and ran toward the iron stairs.`,

    literary: `The afternoon light filtered through the amber curtains, casting long, melancholy shadows across the parquetry floor of the grandfather's study. 

For many unremembered years, the house had harbored an inexplicable silence, broken only by the intermittent ticking of an ornamental French clock whose pendulum swung with relentless, mechanical indifference. 

She turned the delicate vellum page with deliberate slowness, conscious of the dust that rose in miniature constellations toward the high ceiling, wondering whether the forgotten correspondent had foreseen the quiet tragedy that would ultimately engulf their ancestral estate.`,

    business: `Organizational restructuring initiatives frequently encounter substantial bureaucratic resistance when hierarchical accountability mechanisms fail to align with programmatic performance metrics. 

The institutionalization of cross-functional operational synergies was systematically hindered by legacy infrastructure deficiencies and insufficient resource allocation methodologies. 

Consequently, comprehensive diagnostic assessments must be rigorously conducted by multidisciplinary leadership committees to establish quantifiable benchmarks, mitigate systemic liabilities, and maximize shareholder capital utilization across volatile macroeconomic environments.`,

    children: `The little red dog ran down the hill. He saw a blue ball in the green grass. 

"Look at that!" barked the dog to his friend the cat. The cat sat on the warm fence and smiled. 

The dog picked up the ball and ran back home. His bowl was full of fresh water. It was a good sunny day in the yard.`
  };

  // Preload a default paragraph
  chapterInput.value = SAMPLES.thriller;
  updateCharCount();

  // Initialize Theme
  function initTheme() {
    const saved = localStorage.getItem("inkgauge_theme");
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    setTheme(theme);
  }

  function setTheme(theme) {
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem("inkgauge_theme", theme);
    if (themeToggle) {
      themeToggle.querySelector(".theme-label").textContent = theme === "dark" ? "Light theme" : "Dark theme";
    }
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = document.body.getAttribute("data-theme") || "light";
      setTheme(current === "dark" ? "light" : "dark");
      requestAnimationFrame(layoutMarginNotes);
    });
  }

  // About Panel
  if (aboutBtn && aboutPanel && closeAboutBtn) {
    aboutBtn.addEventListener("click", () => {
      const isHidden = aboutPanel.classList.contains("hidden");
      aboutPanel.classList.toggle("hidden", !isHidden);
      aboutPanel.setAttribute("aria-hidden", String(!isHidden));
      aboutBtn.setAttribute("aria-expanded", String(isHidden));
    });
    closeAboutBtn.addEventListener("click", () => {
      aboutPanel.classList.add("hidden");
      aboutPanel.setAttribute("aria-hidden", "true");
      aboutBtn.setAttribute("aria-expanded", "false");
    });
  }

  // Character counter
  function updateCharCount() {
    const len = chapterInput.value.length;
    charCounter.textContent = `${len.toLocaleString()} / 150,000`;
    if (len > 150000) {
      charCounter.style.color = "#C0392B";
      analyzeBtn.disabled = true;
      statusMessage.textContent = `That's ${len.toLocaleString()} characters. Inkgauge handles up to 150,000. Paste one chapter at a time.`;
      statusMessage.className = "status-message error";
    } else {
      charCounter.style.color = "";
      analyzeBtn.disabled = false;
      if (statusMessage.classList.contains("error")) {
        statusMessage.textContent = "";
        statusMessage.className = "status-message";
      }
    }
  }

  chapterInput.addEventListener("input", updateCharCount);

  // Sample selector
  if (sampleSelect) {
    sampleSelect.addEventListener("change", (e) => {
      const key = e.target.value;
      if (SAMPLES[key]) {
        chapterInput.value = SAMPLES[key];
        updateCharCount();
        statusMessage.textContent = "";
      }
    });
  }

  // Analyze Action
  analyzeBtn.addEventListener("click", performAnalysis);

  async function performAnalysis() {
    const text = chapterInput.value.trim();
    if (!text) {
      statusMessage.textContent = "Please paste chapter text to analyze.";
      statusMessage.className = "status-message error";
      return;
    }

    currentRawText = chapterInput.value;
    analyzeBtn.disabled = true;
    statusMessage.textContent = "Analyzing proof sheet...";
    statusMessage.className = "status-message";

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: currentRawText,
          audience: audienceSelect ? audienceSelect.value : "commercial_fiction"
        })
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = data.error ? data.error.message : "Analysis failed.";
        statusMessage.textContent = errorMsg;
        statusMessage.className = "status-message error";
        analyzeBtn.disabled = false;
        return;
      }

      analysisData = data;
      renderResults(data);
      statusMessage.textContent = "";
      analyzeBtn.disabled = false;

    } catch (err) {
      statusMessage.textContent = "Network error. Could not reach analysis server.";
      statusMessage.className = "status-message error";
      analyzeBtn.disabled = false;
    }
  }

  // Switch to edit mode
  if (editTextBtn) {
    editTextBtn.addEventListener("click", () => {
      proofPanel.classList.add("hidden");
      proofPanel.setAttribute("aria-hidden", "true");
      inputPanel.classList.remove("hidden");
      inputPanel.setAttribute("aria-hidden", "false");
      chapterInput.focus();
    });
  }

  // Render Analysis Results
  function renderResults(data) {
    // 1. Populate Left Rail Metrics
    document.getElementById("stat-reading-ease").textContent = data.reading_ease.toFixed(1);
    document.getElementById("band-reading-ease").textContent = data.reading_ease_band;

    document.getElementById("stat-grade-level").textContent = data.grade_level.toFixed(1);
    document.getElementById("band-grade-level").textContent = data.grade_level_band;

    document.getElementById("stat-wps").textContent = data.words_per_sentence_mean.toFixed(1);
    document.getElementById("stat-wps-sub").textContent = `Median: ${data.words_per_sentence_median.toFixed(1)}`;

    document.getElementById("stat-long-words").textContent = `${data.long_words_pct}%`;
    document.getElementById("stat-word-count").textContent = data.word_count.toLocaleString();
    document.getElementById("stat-reading-time").textContent = `Reading time: ${data.reading_time_display}`;

    // Style stats
    document.getElementById("stat-passive").textContent = data.style_flags.passive_voice_count;
    document.getElementById("stat-adverbs").textContent = data.style_flags.adverbs_ly_count;

    const diag = data.style_flags.dialogue_analysis;
    document.getElementById("stat-dialogue-grade").textContent = diag.has_dialogue ? `Grade ${diag.dialogue_grade}` : "None";
    document.getElementById("stat-narration-grade").textContent = diag.narration_grade !== null ? `Grade ${diag.narration_grade}` : "—";

    // Audience Verdict
    if (data.audience_fit && audienceVerdict) {
      const fit = data.audience_fit;
      audienceVerdict.textContent = `${fit.verdict} (Target: ${fit.target_grade_range})`;
      audienceVerdict.className = `audience-verdict ${fit.verdict_band}`;
    }

    // Language notice
    if (languageNotice) {
      if (data.language_notice) {
        languageNotice.textContent = data.language_notice;
        languageNotice.classList.remove("hidden");
      } else {
        languageNotice.classList.add("hidden");
      }
    }

    // Enable action buttons
    copyReportBtn.disabled = false;
    chapterReadBtn.disabled = false;

    // 2. Render Difficulty Strip
    renderDifficultyStrip(data);

    // 3. Render Manuscript Surface
    renderManuscriptSurface(data);

    // 4. Render Margin Notes
    renderMarginNotes(data);

    // Switch panels
    inputPanel.classList.add("hidden");
    inputPanel.setAttribute("aria-hidden", "true");
    proofPanel.classList.remove("hidden");
    proofPanel.setAttribute("aria-hidden", "false");

    // Layout margin notes and lines
    setTimeout(() => {
      layoutMarginNotes();
    }, 100);
  }

  // Difficulty Strip Timeline
  function renderDifficultyStrip(data) {
    difficultyStrip.innerHTML = "";
    difficultyStrip.classList.remove("strip-drawing");

    const hardestRanks = new Map();
    data.hardest_sentences.forEach(s => hardestRanks.set(s.text, s.rank));

    let allSentences = [];
    data.paragraphs.forEach(p => {
      p.sentences.forEach(s => allSentences.push(s));
    });

    allSentences.forEach((s, idx) => {
      const bar = document.createElement("div");
      bar.className = "strip-bar";
      bar.setAttribute("tabindex", "0");
      bar.setAttribute("role", "option");
      bar.setAttribute("aria-label", `Sentence ${idx + 1}, difficulty ${s.difficulty}%`);

      // Scale height: 4px to 26px
      const height = Math.max(4, Math.round((s.difficulty / 100) * 26));
      bar.style.height = `${height}px`;

      // Opacity along difficulty
      const opacity = 0.25 + (s.difficulty / 100) * 0.75;
      bar.style.opacity = opacity.toFixed(2);

      const rank = hardestRanks.get(s.text);
      if (rank !== undefined) {
        bar.classList.add("is-hardest");
        bar.title = `Hardest #${rank}: ${s.text.slice(0, 45)}...`;
      } else {
        bar.title = `Sentence ${idx + 1}: Grade ${s.grade}`;
      }

      // Click / enter jumps to sentence
      const jumpToSentence = () => {
        const target = document.getElementById(`sentence-item-${idx}`);
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "center" });
          target.classList.add("active");
          setTimeout(() => target.classList.remove("active"), 1200);
        }
      };

      bar.addEventListener("click", jumpToSentence);
      bar.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          jumpToSentence();
        }
      });

      difficultyStrip.appendChild(bar);
    });

    // Orchestrated draw animation
    void difficultyStrip.offsetWidth;
    difficultyStrip.classList.add("strip-drawing");
  }

  // Manuscript Surface Rendering
  function renderManuscriptSurface(data) {
    manuscriptSurface.innerHTML = "";

    const hardestMap = new Map();
    data.hardest_sentences.forEach(s => {
      hardestMap.set(s.start, s);
    });

    let globalSentenceIndex = 0;

    data.paragraphs.forEach(p => {
      const pElem = document.createElement("p");
      pElem.className = "manuscript-paragraph";

      p.sentences.forEach(s => {
        const isHardest = hardestMap.has(s.start);
        const hardData = hardestMap.get(s.start);

        let sElem;
        if (isHardest) {
          sElem = document.createElement("mark");
          sElem.className = `manuscript-sentence highlight-sentence wipe-in wipe-rank-${hardData.rank}`;
          sElem.id = `hardest-sentence-${hardData.rank}`;
          sElem.setAttribute("data-rank", hardData.rank);
          sElem.setAttribute("tabindex", "0");

          const rankSpan = document.createElement("span");
          rankSpan.className = "highlight-rank";
          rankSpan.setAttribute("aria-label", `Difficulty rank ${hardData.rank}`);
          rankSpan.textContent = hardData.rank;
          sElem.appendChild(rankSpan);

          const textNode = document.createTextNode(s.text + " ");
          sElem.appendChild(textNode);
        } else {
          sElem = document.createElement("span");
          sElem.className = "manuscript-sentence";
          sElem.textContent = s.text + " ";
        }

        sElem.id = `sentence-item-${globalSentenceIndex}`;
        sElem.setAttribute("data-sentence-index", globalSentenceIndex);

        // Heat shading color calculation (ultramarine ramp 0% to 18% opacity)
        const ultraOpacity = (s.difficulty / 100) * 0.18;
        sElem.style.setProperty("--heat-color", `rgba(43, 63, 214, ${ultraOpacity.toFixed(3)})`);

        // Hover linkages
        if (isHardest) {
          sElem.addEventListener("mouseenter", () => activatePair(hardData.rank));
          sElem.addEventListener("mouseleave", () => deactivatePair(hardData.rank));
          sElem.addEventListener("focus", () => activatePair(hardData.rank));
          sElem.addEventListener("blur", () => deactivatePair(hardData.rank));
        }

        pElem.appendChild(sElem);
        globalSentenceIndex++;
      });

      manuscriptSurface.appendChild(pElem);
    });
  }

  // Margin Notes Rendering
  function renderMarginNotes(data) {
    marginNotesList.innerHTML = "";

    data.hardest_sentences.forEach(s => {
      const card = document.createElement("article");
      card.className = "margin-note-card";
      card.id = `margin-note-${s.rank}`;
      card.setAttribute("data-rank", s.rank);
      card.setAttribute("tabindex", "0");

      // Head
      const head = document.createElement("div");
      head.className = "note-head";

      const badge = document.createElement("div");
      badge.className = "note-rank-badge";
      badge.innerHTML = `<span class="note-rank">${s.rank}</span> Sentence #${s.rank}`;

      const meta = document.createElement("span");
      meta.className = "note-meta";
      meta.textContent = `${s.word_count} words · Grade ${s.grade.toFixed(1)}`;

      head.appendChild(badge);
      head.appendChild(meta);
      card.appendChild(head);

      // Quote preview
      const quote = document.createElement("blockquote");
      quote.className = "note-quote";
      quote.textContent = s.text.length > 110 ? s.text.slice(0, 105) + "..." : s.text;
      card.appendChild(quote);

      // Reasons list
      const reasonsList = document.createElement("ul");
      reasonsList.className = "note-reasons";
      s.reasons.forEach(r => {
        const li = document.createElement("li");
        li.textContent = r;
        reasonsList.appendChild(li);
      });
      card.appendChild(reasonsList);

      // Actions (AI features)
      const actions = document.createElement("div");
      actions.className = "note-actions";

      const rewriteBtn = document.createElement("button");
      rewriteBtn.className = "btn-note-action";
      rewriteBtn.type = "button";
      rewriteBtn.textContent = "Suggest rewrites";
      rewriteBtn.addEventListener("click", () => triggerRewrite(s, card));

      const explainBtn = document.createElement("button");
      explainBtn.className = "btn-note-action";
      explainBtn.type = "button";
      explainBtn.textContent = "Why is this hard?";
      explainBtn.addEventListener("click", () => triggerExplain(s, card));

      actions.appendChild(rewriteBtn);
      actions.appendChild(explainBtn);
      card.appendChild(actions);

      // AI Result Container
      const aiContainer = document.createElement("div");
      aiContainer.className = "ai-note-result hidden";
      card.appendChild(aiContainer);

      // Hover / focus linkages
      card.addEventListener("mouseenter", () => activatePair(s.rank));
      card.addEventListener("mouseleave", () => deactivatePair(s.rank));
      card.addEventListener("focus", () => activatePair(s.rank));
      card.addEventListener("blur", () => deactivatePair(s.rank));

      marginNotesList.appendChild(card);
    });
  }

  // Active pair coordination
  function activatePair(rank) {
    const sElem = document.getElementById(`hardest-sentence-${rank}`);
    const note = document.getElementById(`margin-note-${rank}`);
    const line = document.getElementById(`connector-line-${rank}`);

    if (sElem) sElem.classList.add("active");
    if (note) note.classList.add("active");
    if (line) line.classList.add("active");
  }

  function deactivatePair(rank) {
    const sElem = document.getElementById(`hardest-sentence-${rank}`);
    const note = document.getElementById(`margin-note-${rank}`);
    const line = document.getElementById(`connector-line-${rank}`);

    if (sElem) sElem.classList.remove("active");
    if (note) note.classList.remove("active");
    if (line) line.classList.remove("active");
  }

  // Margin Notes Vertical Alignment & Connectors (Desktop)
  function layoutMarginNotes() {
    if (window.innerWidth <= 900 || !analysisData) {
      connectorCanvas.innerHTML = "";
      return;
    }

    const gutterRect = marginNotesList.getBoundingClientRect();
    const surfaceRect = manuscriptSurface.getBoundingClientRect();

    connectorCanvas.innerHTML = "";
    connectorCanvas.setAttribute("height", String(marginNotesList.scrollHeight || 1200));

    let lastBottom = 0;
    const cards = Array.from(marginNotesList.getElementsByClassName("margin-note-card"));

    cards.forEach(card => {
      const rank = card.getAttribute("data-rank");
      const sentenceElem = document.getElementById(`hardest-sentence-${rank}`);
      if (!sentenceElem) return;

      const sRect = sentenceElem.getBoundingClientRect();
      const idealTop = sRect.top - gutterRect.top;

      // Push down if overlapping previous card
      const assignedTop = Math.max(idealTop, lastBottom + 16);
      card.style.position = "absolute";
      card.style.top = `${assignedTop}px`;
      card.style.width = "100%";

      const cardHeight = card.offsetHeight;
      lastBottom = assignedTop + cardHeight;

      // Draw connector line
      // From right edge of sentence to left edge of note card
      const startX = -12; // In SVG canvas coords relative to right gutter
      const startY = (sRect.top + sRect.height / 2) - gutterRect.top;
      const endX = 0;
      const endY = assignedTop + 20;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.id = `connector-line-${rank}`;
      path.setAttribute("class", "connector-line");

      // Bezier curve
      const cp1X = startX + (endX - startX) * 0.5;
      const d = `M ${startX} ${startY} C ${cp1X} ${startY}, ${cp1X} ${endY}, ${endX} ${endY}`;
      path.setAttribute("d", d);
      connectorCanvas.appendChild(path);
    });

    // Adjust container height to contain all pushed notes
    marginNotesList.style.minHeight = `${lastBottom + 32}px`;
  }

  window.addEventListener("resize", () => {
    requestAnimationFrame(layoutMarginNotes);
  });

  // Heat shading toggle
  heatShadingToggle.addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const sentences = manuscriptSurface.querySelectorAll(".manuscript-sentence");
    sentences.forEach(s => {
      s.classList.toggle("heat-shaded", isChecked);
    });
  });

  // Audience selector change
  if (audienceSelect) {
    audienceSelect.addEventListener("change", () => {
      if (analysisData && currentRawText) {
        performAnalysis();
      }
    });
  }

  // Copy plain-text report
  copyReportBtn.addEventListener("click", () => {
    if (!analysisData) return;

    let report = `INKGAUGE READABILITY REPORT\n`;
    report += `==========================\n\n`;
    report += `• Flesch Reading Ease: ${analysisData.reading_ease.toFixed(1)} (${analysisData.reading_ease_band})\n`;
    report += `• Flesch-Kincaid Grade: ${analysisData.grade_level.toFixed(1)} (${analysisData.grade_level_band})\n`;
    report += `• Words per Sentence: ${analysisData.words_per_sentence_mean.toFixed(1)} mean, ${analysisData.words_per_sentence_median.toFixed(1)} median\n`;
    report += `• Word Count: ${analysisData.word_count.toLocaleString()} words (Est. Reading Time: ${analysisData.reading_time_display})\n`;
    report += `• Long Words (3+ syllables): ${analysisData.long_words_pct}%\n`;
    report += `• Audience Assessment (${analysisData.audience_fit.audience_label}): ${analysisData.audience_fit.verdict}\n\n`;

    report += `FIVE HARDEST SENTENCES:\n`;
    report += `-----------------------\n`;
    analysisData.hardest_sentences.forEach(s => {
      report += `\n[#${s.rank}] Grade ${s.grade.toFixed(1)} (${s.word_count} words)\n`;
      report += `"${s.text}"\n`;
      report += `Reasons:\n`;
      s.reasons.forEach(r => {
        report += `  - ${r}\n`;
      });
    });

    navigator.clipboard.writeText(report).then(() => {
      const origText = copyReportBtn.textContent;
      copyReportBtn.textContent = "Report copied!";
      setTimeout(() => {
        copyReportBtn.textContent = origText;
      }, 2000);
    }).catch(() => {
      alert("Could not copy to clipboard.");
    });
  });

  // AI Feature 1: Suggest Rewrites
  async function triggerRewrite(sentenceData, cardElem) {
    const aiContainer = cardElem.querySelector(".ai-note-result");
    aiContainer.classList.remove("hidden");
    aiContainer.innerHTML = `<span class="note-meta">Consulting Claude for three rewrite variants...</span>`;
    layoutMarginNotes();

    // Find paragraph context
    const context = findSentenceParagraphContext(sentenceData.start);

    try {
      const response = await fetch("/api/ai/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sentence: sentenceData.text,
          context: context,
          voice_sample: voiceSampleText || null,
        })
      });

      const res = await response.json();
      if (!response.ok) {
        aiContainer.innerHTML = `<div class="status-message error">${res.error ? res.error.message : "Rewrite request failed."}</div>`;
        layoutMarginNotes();
        return;
      }

      const v = res.variants;
      const providerLabel = v.provider === "local"
        ? "Local AI Engine (100% free, runs offline, no API key)"
        : `Generated via ${v.provider}`;

      aiContainer.innerHTML = `
        <div class="ai-rewrites-list">
          <div class="rewrite-item">
            <div class="rewrite-label-row">
              <strong>Lighter</strong>
              <span>Grade ${v.lighter.grade} (was ${v.original_grade})</span>
            </div>
            <p class="rewrite-text">"${v.lighter.text}"</p>
          </div>
          <div class="rewrite-item">
            <div class="rewrite-label-row">
              <strong>Balanced</strong>
              <span>Grade ${v.balanced.grade} (was ${v.original_grade})</span>
            </div>
            <p class="rewrite-text">"${v.balanced.text}"</p>
          </div>
          <div class="rewrite-item">
            <div class="rewrite-label-row">
              <strong>Voice-preserving</strong>
              <span>Grade ${v.voice_preserving.grade} (was ${v.original_grade})</span>
            </div>
            <p class="rewrite-text">"${v.voice_preserving.text}"</p>
          </div>
        </div>
        <div class="ai-disclaimer">${providerLabel} · Grades computed in pure Python. Check against your story voice.</div>
      `;
      layoutMarginNotes();

    } catch (err) {
      aiContainer.innerHTML = `<div class="status-message error">Connection error calling AI rewrite.</div>`;
      layoutMarginNotes();
    }
  }

  // AI Feature 2: Editor's Note (Why is this hard?)
  async function triggerExplain(sentenceData, cardElem) {
    const aiContainer = cardElem.querySelector(".ai-note-result");
    aiContainer.classList.remove("hidden");
    aiContainer.innerHTML = `<span class="note-meta">Generating editor's diagnostic note...</span>`;
    layoutMarginNotes();

    try {
      const response = await fetch("/api/ai/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sentence: sentenceData.text,
          reasons: sentenceData.reasons,
        })
      });

      const res = await response.json();
      if (!response.ok) {
        aiContainer.innerHTML = `<div class="status-message error">${res.error ? res.error.message : "Editor note failed."}</div>`;
        layoutMarginNotes();
        return;
      }

      const providerLabel = res.provider === "local"
        ? "Local AI Editor (100% free, no API key)"
        : `Generated via ${res.provider}`;

      aiContainer.innerHTML = `
        <p class="ai-editor-text">"${res.editor_note}"</p>
        <div class="ai-disclaimer">${providerLabel} · Grounded in measured sentence statistics.</div>
      `;
      layoutMarginNotes();

    } catch (err) {
      aiContainer.innerHTML = `<div class="status-message error">Connection error calling AI explain.</div>`;
      layoutMarginNotes();
    }
  }

  // AI Feature 3: Chapter Read
  chapterReadBtn.addEventListener("click", async () => {
    if (!currentRawText) return;

    chapterReadBtn.disabled = true;
    chapterReadResults.classList.remove("hidden");
    chapterReadContent.innerHTML = `<span class="note-meta">Generating senior developmental read of chapter...</span>`;

    try {
      const response = await fetch("/api/ai/chapter-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: currentRawText })
      });

      const res = await response.json();
      chapterReadBtn.disabled = false;

      if (!response.ok) {
        chapterReadContent.innerHTML = `<div class="status-message error">${res.error ? res.error.message : "Chapter read failed."}</div>`;
        return;
      }

      const providerLabel = res.provider === "local"
        ? "Local AI Developmental Reader (100% free, runs offline, no API key)"
        : `Generated via ${res.provider}`;

      let html = `
        <div class="ai-disclaimer" style="margin-bottom: 0.85rem; font-weight: 500; color: var(--color-pine);">${providerLabel}</div>
        <div class="read-diagnostic-section">
          <h4>Pacing & Prose Density</h4>
          <p>${res.pacing}</p>
        </div>
        <div class="read-diagnostic-section">
          <h4>Clarity & Voice</h4>
          <p>${res.clarity}</p>
        </div>
        <div class="read-diagnostic-section">
          <h4>Potential Reader Stall Points</h4>
      `;

      res.stall_points.forEach((sp, i) => {
        html += `
          <div class="stall-point-card">
            <div><strong>${i + 1}. ${sp.paragraph_summary}</strong></div>
            <div><em>Why a reader might stall:</em> ${sp.why_stalled}</div>
            <div><em>Editor's tip:</em> ${sp.editorial_tip}</div>
          </div>
        `;
      });

      html += `</div>`;
      chapterReadContent.innerHTML = html;

    } catch (err) {
      chapterReadBtn.disabled = false;
      chapterReadContent.innerHTML = `<div class="status-message error">Network error calling chapter read.</div>`;
    }
  });

  if (closeChapterReadBtn) {
    closeChapterReadBtn.addEventListener("click", () => {
      chapterReadResults.classList.add("hidden");
    });
  }

  function findSentenceParagraphContext(startOffset) {
    if (!analysisData) return "";
    for (const p of analysisData.paragraphs) {
      if (startOffset >= p.start && startOffset <= p.end) {
        return p.sentences.map(s => s.text).join(" ");
      }
    }
    return "";
  }

  // Start app
  initTheme();

})();
