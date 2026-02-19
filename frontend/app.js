/**
 * CortexAI Frontend — app.js (v2 — Scrollytelling Edition)
 */

/* ─── Config ──────────────────────────────── */
const API_BASE = "http://127.0.0.1:8000";
const API_KEY = "dev-key-1";

/* ─── Model Catalog ───────────────────────── */
const MODELS = {
    openai: ["gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4o-mini"],
    gemini: ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-pro"],
    deepseek: ["deepseek-chat", "deepseek-reasoner"],
    grok: ["grok-4-latest"],
};
const PROVIDER_LABELS = {
    openai: "OpenAI",
    gemini: "Google Gemini",
    deepseek: "DeepSeek",
    grok: "Grok",
};
const WORKSPACE_TAGLINES = {
    single: "Single model · Conversational",
    compare: "Multi-model · Parallel comparison",
};

/* ─── State ───────────────────────────────── */
let currentMode = "single";
let compareSlotCount = 2;
let conversationHistory = [];
let optimizeEnabled = false;
let lastOptimizeResult = null;   // { original, optimized, wasOptimized }

/* ─── DOM References ──────────────────────── */
const $ = id => document.getElementById(id);
const el = {
    hero: $("hero"),
    heroContent: $("heroContent"),
    heroScrollHint: $("heroScrollHint"),
    compactBar: $("compactBar"),
    compactModelInfo: $("compactModelInfo"),
    cBtnSingle: $("cBtnSingle"),
    cBtnCompare: $("cBtnCompare"),
    compactSendBtn: $("compactSendBtn"),
    mainHeader: $("mainHeader"),
    optToggle: $("optToggle"),
    optStatus: $("optStatus"),
    btnSingleMode: $("btnSingleMode"),
    btnCompareMode: $("btnCompareMode"),
    panelSingle: $("panelSingle"),
    panelCompare: $("panelCompare"),
    workspaceTagline: $("workspaceTagline"),
    singleModel: $("singleModel"),
    compareModel1: $("compareModel1"),
    compareModel2: $("compareModel2"),
    compareModel3: $("compareModel3"),
    slot3: $("slot3"),
    btn2Models: $("btn2Models"),
    btn3Models: $("btn3Models"),
    promptCard: $("promptCard"),
    promptInput: $("promptInput"),
    submitBtn: $("submitBtn"),
    submitBtnLabel: $("submitBtnLabel"),
    resultsSection: $("resultsSection"),
    resultsGrid: $("resultsGrid"),
    clearBtn: $("clearBtn"),
    errorBanner: $("errorBanner"),
    errorMsg: $("errorMsg"),
    errorClose: $("errorClose"),
    optViewBtn: $("optViewBtn"),
    optPanel: $("optPanel"),
    optPanelClose: $("optPanelClose"),
    optOriginalText: $("optOriginalText"),
    optOptimizedText: $("optOptimizedText"),
};

/* ═══════════════════════════════════════════
   SCROLL BEHAVIOUR — Hero fade + Compact bar
═══════════════════════════════════════════ */

(function initScrollBehaviour() {
    // 1. Scroll-linked hero opacity/transform via rAF (60fps)
    let ticking = false;
    function onScroll() {
        if (!ticking) {
            requestAnimationFrame(updateHero);
            ticking = true;
        }
    }

    function updateHero() {
        const heroH = el.hero.offsetHeight;
        const scrollY = window.scrollY;
        const prog = Math.min(scrollY / (heroH * 0.7), 1); // 0 → 1 over 70% of hero height

        // Fade + slide the hero content
        el.heroContent.style.opacity = 1 - prog;
        el.heroContent.style.transform = `translateY(${prog * -40}px)`;

        // Header shadow
        if (scrollY > 10) {
            el.mainHeader.classList.add("scrolled");
        } else {
            el.mainHeader.classList.remove("scrolled");
        }

        ticking = false;
    }

    window.addEventListener("scroll", onScroll, { passive: true });

    // 2. IntersectionObserver — show compact bar once hero is mostly gone
    const observer = new IntersectionObserver(
        ([entry]) => {
            const showBar = !entry.isIntersecting;
            el.compactBar.classList.toggle("visible", showBar);
            el.compactBar.setAttribute("aria-hidden", showBar ? "false" : "true");
        },
        { threshold: 0.15 }   // trigger when <15% of hero is visible
    );
    observer.observe(el.hero);
})();

/* ═══════════════════════════════════════════
   COMPACT BAR — SYNC
═══════════════════════════════════════════ */

function updateCompactBar() {
    // Mode buttons
    el.cBtnSingle.classList.toggle("active", currentMode === "single");
    el.cBtnCompare.classList.toggle("active", currentMode === "compare");

    // Model badges
    const badgesHTML = getCompactBadges();
    el.compactModelInfo.innerHTML = badgesHTML;

    // Send label
    el.compactSendBtn.innerHTML = `<span class="btn-icon">⚡</span> ${currentMode === "single" ? "Send" : "Compare"}`;
}

function getCompactBadges() {
    if (currentMode === "single") {
        const { provider, model } = parseKey(el.singleModel.value || "");
        if (!provider) return "";
        return `<span class="compact-model-badge">
              <span class="provider-dot dot-${provider}" style="width:7px;height:7px;border-radius:50%;flex-shrink:0;"></span>
              ${escHtml(model)}
            </span>`;
    }
    return getActiveCompareSelects().map(sel => {
        const { provider, model } = parseKey(sel.value || "");
        if (!provider) return "";
        return `<span class="compact-model-badge">
              <span class="provider-dot dot-${provider}" style="width:7px;height:7px;border-radius:50%;flex-shrink:0;"></span>
              ${escHtml(model)}
            </span>`;
    }).join("");
}

// Main workspace mode toggle buttons
el.btnSingleMode.addEventListener("click", () => setMode("single"));
el.btnCompareMode.addEventListener("click", () => setMode("compare"));

// Compact bar mirrors
el.cBtnSingle.addEventListener("click", () => setMode("single"));
el.cBtnCompare.addEventListener("click", () => setMode("compare"));
el.compactSendBtn.addEventListener("click", handleSubmit);


/* ═══════════════════════════════════════════
   DROPDOWNS
═══════════════════════════════════════════ */

function buildOptions(selectEl, excludeKeys = new Set()) {
    const current = selectEl.value;
    selectEl.innerHTML = "";

    Object.entries(MODELS).forEach(([provider, models]) => {
        const group = document.createElement("optgroup");
        group.label = PROVIDER_LABELS[provider];
        models.forEach(model => {
            const key = `${provider}:${model}`;
            if (excludeKeys.has(key)) return;
            const opt = document.createElement("option");
            opt.value = key;
            opt.textContent = model;
            if (key === current) opt.selected = true;
            group.appendChild(opt);
        });
        if (group.children.length > 0) selectEl.appendChild(group);
    });

    if (!selectEl.value && selectEl.options.length > 0) {
        selectEl.options[0].selected = true;
    }
}

function getActiveCompareSelects() {
    const s = [el.compareModel1, el.compareModel2];
    if (compareSlotCount === 3) s.push(el.compareModel3);
    return s;
}

function syncCompareDropdowns() {
    const selects = getActiveCompareSelects();
    selects.forEach((sel, i) => {
        const others = new Set(selects.filter((_, j) => j !== i).map(s => s.value).filter(Boolean));
        buildOptions(sel, others);
    });
    updateCompactBar();
}

function parseKey(key) {
    const idx = (key || "").indexOf(":");
    if (idx < 0) return { provider: "", model: key };
    return { provider: key.slice(0, idx), model: key.slice(idx + 1) };
}

/* ═══════════════════════════════════════════
   MODE
═══════════════════════════════════════════ */

function setMode(mode) {
    currentMode = mode;

    const isSingle = mode === "single";
    el.btnSingleMode.classList.toggle("active", isSingle);
    el.btnCompareMode.classList.toggle("active", !isSingle);
    el.btnSingleMode.setAttribute("aria-selected", isSingle);
    el.btnCompareMode.setAttribute("aria-selected", !isSingle);

    el.panelSingle.classList.toggle("hidden", !isSingle);
    el.panelCompare.classList.toggle("hidden", isSingle);

    el.submitBtnLabel.textContent = isSingle ? "Send" : "Compare Models";
    el.workspaceTagline.textContent = WORKSPACE_TAGLINES[mode];

    if (!isSingle) syncCompareDropdowns();

    clearResults();
    conversationHistory = [];
    updateCompactBar();
}

/* ═══════════════════════════════════════════
   SLOT COUNT
═══════════════════════════════════════════ */

function setSlotCount(n) {
    compareSlotCount = n;
    el.btn2Models.classList.toggle("active", n === 2);
    el.btn3Models.classList.toggle("active", n === 3);
    el.slot3.classList.toggle("hidden", n < 3);
    syncCompareDropdowns();
}

el.btn2Models.addEventListener("click", () => setSlotCount(2));
el.btn3Models.addEventListener("click", () => setSlotCount(3));

/* ═══════════════════════════════════════════
   PROMPT OPTIMIZATION TOGGLE
═══════════════════════════════════════════ */

el.optToggle.addEventListener("change", () => {
    optimizeEnabled = el.optToggle.checked;
    el.optStatus.textContent = optimizeEnabled ? "On" : "Off";
    el.optStatus.classList.toggle("on", optimizeEnabled);
});

/* ═══════════════════════════════════════════
   PROMPT FOCUS — card glow effect
═══════════════════════════════════════════ */

el.promptInput.addEventListener("focus", () => el.promptCard.classList.add("focused"));
el.promptInput.addEventListener("blur", () => el.promptCard.classList.remove("focused"));

/* ═══════════════════════════════════════════
   EXAMPLE CHIPS
═══════════════════════════════════════════ */

document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
        el.promptInput.value = chip.dataset.prompt;
        el.promptInput.focus();
        // Scroll to workspace smoothly
        document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
    });
});

/* ═══════════════════════════════════════════
   KEYBOARD SHORTCUT
═══════════════════════════════════════════ */

el.promptInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
    }
});

/* ═══════════════════════════════════════════
   OPT PANEL — View / close
═══════════════════════════════════════════ */

// Toggle the panel when ✨ View Optimized is clicked
el.optViewBtn.addEventListener("click", () => {
    const isHidden = el.optPanel.classList.toggle("hidden");
    el.optViewBtn.textContent = isHidden
        ? (lastOptimizeResult?.wasOptimized ? "✨ View Optimized" : "ℹ️ Optimization Off (server)")
        : "✕ Close";
});

// Close the panel via its ✕ button
el.optPanelClose.addEventListener("click", () => {
    el.optPanel.classList.add("hidden");
    if (lastOptimizeResult) {
        el.optViewBtn.textContent = lastOptimizeResult.wasOptimized
            ? "✨ View Optimized"
            : "ℹ️ Optimization Off (server)";
    }
});


/* ═══════════════════════════════════════════
   OPTIMIZE PROMPT CALL
═══════════════════════════════════════════ */

async function callOptimize(prompt) {
    const data = await callAPI("/v1/optimize", { prompt });
    if (!data) return prompt;               // on error fall through

    lastOptimizeResult = {
        original: data.original_prompt,
        optimized: data.optimized_prompt,
        wasOptimized: data.was_optimized,
        serverEnabled: data.server_optimization_enabled,
    };

    // Show / update the View Optimized button
    el.optViewBtn.classList.remove("hidden");
    el.optViewBtn.textContent = data.was_optimized
        ? "✨ View Optimized"
        : "ℹ️ Optimization Off (server)";

    // Pre-fill the panel texts
    el.optOriginalText.textContent = data.original_prompt;
    el.optOptimizedText.textContent = data.optimized_prompt;

    return data.optimized_prompt;
}

/* ═══════════════════════════════════════════
   SUBMIT
═══════════════════════════════════════════ */

el.submitBtn.addEventListener("click", handleSubmit);

async function handleSubmit() {
    const rawPrompt = el.promptInput.value.trim();
    if (!rawPrompt) { el.promptInput.focus(); return; }

    clearError();
    setLoading(true);

    try {
        // Step 1: optionally optimize the prompt
        let prompt = rawPrompt;
        if (optimizeEnabled) {
            prompt = await callOptimize(rawPrompt);
        } else {
            // Hide the panel when opt is off
            el.optViewBtn.classList.add("hidden");
            el.optPanel.classList.add("hidden");
            lastOptimizeResult = null;
        }

        // Step 2: send to chat / compare
        if (currentMode === "single") {
            await doSingleChat(prompt);
        } else {
            await doCompare(prompt);
        }
    } catch (err) {
        showError(err.message || "An unexpected error occurred.");
    } finally {
        setLoading(false);
    }
}

/* ═══════════════════════════════════════════
   SINGLE CHAT
═══════════════════════════════════════════ */

async function doSingleChat(prompt) {
    const { provider, model } = parseKey(el.singleModel.value);
    if (!provider) { showError("Please select a model."); return; }

    const body = {
        prompt,
        provider,
        model,
        ...(conversationHistory.length > 0 ? {
            context: { session_id: "ui-session", conversation_history: conversationHistory }
        } : {}),
    };

    const data = await callAPI("/v1/chat", body);
    if (!data) return;

    conversationHistory.push({ role: "user", content: prompt });
    conversationHistory.push({ role: "assistant", content: data.text || "" });
    if (conversationHistory.length > 20) conversationHistory = conversationHistory.slice(-20);

    showResults([data], false);
}

/* ═══════════════════════════════════════════
   COMPARE
═══════════════════════════════════════════ */

async function doCompare(prompt) {
    const selects = getActiveCompareSelects();
    const targets = selects.map(sel => parseKey(sel.value));

    if (new Set(targets.map(t => `${t.provider}:${t.model}`)).size < targets.length) {
        showError("Please select different models for each slot.");
        return;
    }

    const data = await callAPI("/v1/compare", { prompt, targets });
    if (!data) return;

    showResults(data.responses, true, data);
}

/* ═══════════════════════════════════════════
   API
═══════════════════════════════════════════ */

async function callAPI(path, body) {
    const resp = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
        body: JSON.stringify(body),
    });

    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try { const j = await resp.json(); detail = j.detail || detail; } catch { }
        showError(`API error: ${detail}`);
        return null;
    }
    return resp.json();
}

/* ═══════════════════════════════════════════
   RENDER RESULTS — staggered card animation
═══════════════════════════════════════════ */

function showResults(responses, isMulti, compareData) {
    el.resultsSection.classList.remove("hidden");
    el.resultsGrid.className = isMulti ? "results-grid multi" : "results-grid";

    if (!isMulti) {
        el.resultsGrid.style.gridTemplateColumns = "";
        el.resultsGrid.insertAdjacentHTML("afterbegin", buildResponseCard(responses[0], 0));
    } else {
        // Explicitly match columns to card count — prevents empty 3rd column with 2 cards
        el.resultsGrid.style.gridTemplateColumns = `repeat(${responses.length}, 1fr)`;
        el.resultsGrid.innerHTML = responses.map((r, i) => buildResponseCard(r, i)).join("");
        if (compareData) el.resultsGrid.insertAdjacentHTML("beforeend", buildCompareSummary(compareData));
    }

    // Smooth scroll to results
    setTimeout(() => {
        el.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
}


function buildResponseCard(resp, index) {
    const hasError = !!resp.error;
    const latency = resp.latency_ms != null ? `${resp.latency_ms} ms` : "—";
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const tokens = resp.token_usage ? resp.token_usage.total_tokens : 0;
    const cost = resp.estimated_cost != null ? `$${resp.estimated_cost.toFixed(5)}` : "—";
    const delay = index * 60;

    return `
    <div class="response-card ${hasError ? "error-card" : ""}"
         style="animation: cardIn 0.4s cubic-bezier(.4,0,.2,1) ${delay}ms both;">
      <div class="response-card-header">
        <span class="model-badge">
          <span class="provider-dot dot-${escHtml(resp.provider)}"></span>
          ${escHtml(PROVIDER_LABELS[resp.provider] || resp.provider)} &mdash; ${escHtml(resp.model)}
        </span>
        <span class="latency-badge">⏱ ${latency}</span>
      </div>
      <div class="response-card-body">
        <p class="response-text ${hasError ? "error-text" : ""}">${escHtml(text)}</p>
      </div>
      <div class="response-card-footer">
        <div class="stat-item">
          <span class="stat-label">Tokens</span>
          <span class="stat-value">${tokens.toLocaleString()}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Est. Cost</span>
          <span class="stat-value">${cost}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Finish</span>
          <span class="stat-value">${escHtml(resp.finish_reason || "—")}</span>
        </div>
      </div>
    </div>`;
}

function buildCompareSummary(data) {
    return `
    <div class="response-card" style="grid-column:1/-1;background:#FAFAFA;animation:cardIn 0.4s cubic-bezier(.4,0,.2,1) ${data.responses.length * 60}ms both;">
      <div class="response-card-body" style="padding:12px 16px;">
        <div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
          <div class="stat-item">
            <span class="stat-label">Total Tokens</span>
            <span class="stat-value">${(data.total_tokens || 0).toLocaleString()}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Total Cost</span>
            <span class="stat-value">$${(data.total_cost || 0).toFixed(5)}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Successful</span>
            <span class="stat-value">${data.success_count} / ${data.responses.length}</span>
          </div>
        </div>
      </div>
    </div>`;
}

/* ═══════════════════════════════════════════
   CLEAR / ERROR / LOADING
═══════════════════════════════════════════ */

el.clearBtn.addEventListener("click", () => { clearResults(); conversationHistory = []; });

function clearResults() {
    el.resultsSection.classList.add("hidden");
    el.resultsGrid.innerHTML = "";
}

function showError(msg) {
    el.errorMsg.textContent = msg;
    el.errorBanner.classList.remove("hidden");
}
function clearError() { el.errorBanner.classList.add("hidden"); }
el.errorClose.addEventListener("click", clearError);

function setLoading(loading) {
    el.submitBtn.disabled = loading;
    el.compactSendBtn.disabled = loading;

    if (loading) {
        el.submitBtn.innerHTML = `<span class="spinner"></span> Processing…`;
        el.compactSendBtn.innerHTML = `<span class="spinner"></span>`;
    } else {
        const label = currentMode === "single" ? "Send" : "Compare Models";
        el.submitBtn.innerHTML = `<span class="btn-icon">⚡</span><span id="submitBtnLabel">${label}</span>`;
        el.compactSendBtn.innerHTML = `<span class="btn-icon">⚡</span> ${currentMode === "single" ? "Send" : "Compare"}`;
        // Re-bind the label ref (it gets recreated)
        el.submitBtnLabel = document.getElementById("submitBtnLabel");
    }
}

/* ═══════════════════════════════════════════
   INIT
═══════════════════════════════════════════ */

(function init() {
    buildOptions(el.singleModel, new Set());
    buildOptions(el.compareModel1, new Set());
    buildOptions(el.compareModel2, new Set([el.compareModel1.value]));
    buildOptions(el.compareModel3, new Set([el.compareModel1.value, el.compareModel2.value]));

    // Dedup on change
    [el.compareModel1, el.compareModel2, el.compareModel3].forEach(s =>
        s.addEventListener("change", syncCompareDropdowns)
    );
    el.singleModel.addEventListener("change", updateCompactBar);

    setMode("single");
})();

/* ═══════════════════════════════════════════
   UTILS
═══════════════════════════════════════════ */

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
