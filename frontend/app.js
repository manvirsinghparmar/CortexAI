/**
 * CortexAI Frontend — app.js
 * Drives the single-chat and compare-mode UI.
 */

/* ─── Config ────────────────────────────────────── */
const API_BASE = "http://127.0.0.1:8000";
const API_KEY = "dev-key-1";   // matches .env API_KEYS

/* ─── Available Models ──────────────────────────── */
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

const PROVIDER_ICONS = {
    openai: "🟢",
    gemini: "🔵",
    deepseek: "🟣",
    grok: "🔷",
};

// Flat list of all {provider, model} options
const ALL_OPTIONS = Object.entries(MODELS).flatMap(([provider, models]) =>
    models.map(model => ({ provider, model }))
);

const EXAMPLE_PROMPTS = [
    "Explain quantum computing in simple terms",
    "Write a haiku about artificial intelligence",
    "What are the pros and cons of remote work?",
    "Explain the difference between SQL and NoSQL databases",
    "What is the best way to learn a new programming language?",
];

/* ─── State ─────────────────────────────────────── */
let currentMode = "single";  // "single" | "compare"
let compareSlotCount = 2;
let conversationHistory = [];       // for single chat mode
let optimizeEnabled = false;

/* ─── DOM Refs ──────────────────────────────────── */
const $ = id => document.getElementById(id);

const btnSingleMode = $("btnSingleMode");
const btnCompareMode = $("btnCompareMode");
const panelSingle = $("panelSingle");
const panelCompare = $("panelCompare");
const optToggle = $("optToggle");
const optStatus = $("optStatus");
const singleModel = $("singleModel");
const compareModel1 = $("compareModel1");
const compareModel2 = $("compareModel2");
const compareModel3 = $("compareModel3");
const slot3 = $("slot3");
const btn2Models = $("btn2Models");
const btn3Models = $("btn3Models");
const promptInput = $("promptInput");
const submitBtn = $("submitBtn");
const submitBtnLabel = $("submitBtnLabel");
const resultsSection = $("resultsSection");
const resultsGrid = $("resultsGrid");
const clearBtn = $("clearBtn");
const errorBanner = $("errorBanner");
const errorMsg = $("errorMsg");
const errorClose = $("errorClose");

/* ─── Dropdown Helpers ─────────────────────────── */

/**
 * Build <optgroup> options for a select, excluding a set of {provider:model} combos.
 */
function buildOptions(selectEl, excludeKeys = new Set()) {
    const current = selectEl.value; // try to preserve current selection
    selectEl.innerHTML = "";

    Object.entries(MODELS).forEach(([provider, models]) => {
        const group = document.createElement("optgroup");
        group.label = PROVIDER_LABELS[provider];

        models.forEach(model => {
            const key = `${provider}:${model}`;
            if (excludeKeys.has(key)) return; // skip duplicates

            const opt = document.createElement("option");
            opt.value = key;
            opt.textContent = model;
            if (key === current) opt.selected = true;
            group.appendChild(opt);
        });

        if (group.children.length > 0) selectEl.appendChild(group);
    });

    // If nothing selected yet, pick first option
    if (!selectEl.value && selectEl.options.length > 0) {
        selectEl.options[0].selected = true;
    }
}

function getSelectedKey(selectEl) {
    return selectEl.value; // "provider:model"
}

function parseKey(key) {
    const idx = key.indexOf(":");
    return { provider: key.slice(0, idx), model: key.slice(idx + 1) };
}

/** Rebuild all compare dropdowns so no two slots share the same provider:model */
function syncCompareDropdowns() {
    const selects = getActiveCompareSelects();

    selects.forEach((sel, i) => {
        const otherKeys = new Set(
            selects.filter((_, j) => j !== i).map(s => s.value).filter(Boolean)
        );
        buildOptions(sel, otherKeys);
    });
}

function getActiveCompareSelects() {
    const selects = [compareModel1, compareModel2];
    if (compareSlotCount === 3) selects.push(compareModel3);
    return selects;
}

/** Initial population of the single-chat dropdown */
function populateSingleDropdown() {
    buildOptions(singleModel, new Set());
}

/* ─── Mode Toggle ─────────────────────────────── */

function setMode(mode) {
    currentMode = mode;
    btnSingleMode.classList.toggle("active", mode === "single");
    btnCompareMode.classList.toggle("active", mode === "compare");
    btnSingleMode.setAttribute("aria-selected", mode === "single");
    btnCompareMode.setAttribute("aria-selected", mode === "compare");

    if (mode === "single") {
        panelSingle.classList.remove("hidden");
        panelCompare.classList.add("hidden");
        submitBtnLabel.textContent = "Send";
    } else {
        panelSingle.classList.add("hidden");
        panelCompare.classList.remove("hidden");
        submitBtnLabel.textContent = "Compare Models";
        syncCompareDropdowns();
    }

    clearResults();
    conversationHistory = [];
}

/* ─── Slot Count (2 / 3 models) ─────────────────── */

function setSlotCount(n) {
    compareSlotCount = n;
    btn2Models.classList.toggle("active", n === 2);
    btn3Models.classList.toggle("active", n === 3);
    slot3.classList.toggle("hidden", n < 3);
    syncCompareDropdowns();
}

/* ─── Prompt Optimization ─────────────────────── */

optToggle.addEventListener("change", () => {
    optimizeEnabled = optToggle.checked;
    optStatus.textContent = optimizeEnabled ? "On" : "Off";
    optStatus.classList.toggle("on", optimizeEnabled);
});

/* ─── Example Chips ─────────────────────────── */

document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
        promptInput.value = chip.dataset.prompt;
        promptInput.focus();
    });
});

/* ─── Keyboard shortcut Ctrl+Enter ─────────────── */

promptInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
    }
});

/* ─── Submit ────────────────────────────────────── */

submitBtn.addEventListener("click", handleSubmit);

async function handleSubmit() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
        promptInput.focus();
        return;
    }

    clearError();
    setLoading(true);

    try {
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

/* ─── Single Chat ─────────────────────────────── */

async function doSingleChat(prompt) {
    const key = getSelectedKey(singleModel);
    if (!key) { showError("Please select a model."); return; }
    const { provider, model } = parseKey(key);

    const body = {
        prompt,
        provider,
        model,
        ...(conversationHistory.length > 0 ? {
            context: {
                session_id: "ui-session",
                conversation_history: conversationHistory,
            }
        } : {}),
    };

    const data = await callAPI("/v1/chat", body);
    if (!data) return;

    // Update conversation history
    conversationHistory.push({ role: "user", content: prompt });
    conversationHistory.push({ role: "assistant", content: data.text || "" });
    // Keep last 10 exchanges (20 messages)
    if (conversationHistory.length > 20) {
        conversationHistory = conversationHistory.slice(-20);
    }

    showResults([data], false);
}

/* ─── Compare ────────────────────────────────── */

async function doCompare(prompt) {
    const selects = getActiveCompareSelects();
    const targets = selects.map(sel => {
        const { provider, model } = parseKey(sel.value);
        return { provider, model };
    });

    if (new Set(targets.map(t => `${t.provider}:${t.model}`)).size < targets.length) {
        showError("Please select different models for each slot.");
        return;
    }

    const body = {
        prompt,
        targets,
    };

    const data = await callAPI("/v1/compare", body);
    if (!data) return;

    // data.responses is an array of ChatResponseDTO
    showResults(data.responses, true, data);
}

/* ─── API Helper ─────────────────────────────── */

async function callAPI(path, body) {
    const resp = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
        },
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

/* ─── Rendering Results ──────────────────────── */

function showResults(responses, isMulti, compareData) {
    resultsSection.classList.remove("hidden");
    resultsGrid.className = isMulti ? "results-grid multi" : "results-grid";

    if (!isMulti) {
        // For single chat, prepend new card (keep history visible)
        resultsGrid.insertAdjacentHTML("afterbegin", buildResponseCard(responses[0], false));
    } else {
        // For compare, always replace
        resultsGrid.innerHTML = responses.map(r => buildResponseCard(r, true)).join("");

        // Append compare summary footer if applicable
        if (compareData) {
            const summary = buildCompareSummary(compareData);
            resultsGrid.insertAdjacentHTML("beforeend", summary);
        }
    }
}

function buildResponseCard(resp, isCompare) {
    const hasError = !!resp.error;
    const providerClass = `dot-${resp.provider}`;
    const latency = resp.latency_ms != null ? `${resp.latency_ms} ms` : "—";
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const tokens = resp.token_usage ? resp.token_usage.total_tokens : 0;
    const cost = resp.estimated_cost != null ? `$${resp.estimated_cost.toFixed(5)}` : "—";

    return `
    <div class="response-card ${hasError ? "error-card" : ""}">
      <div class="response-card-header">
        <span class="model-badge">
          <span class="provider-dot ${providerClass}"></span>
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
    <div class="response-card" style="grid-column: 1/-1; background: #FAFAFA;">
      <div class="response-card-body" style="padding:14px 16px;">
        <div style="display:flex;gap:24px;flex-wrap:wrap;">
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

/* ─── Clear & Error ──────────────────────────── */

clearBtn.addEventListener("click", () => {
    clearResults();
    conversationHistory = [];
});

function clearResults() {
    resultsSection.classList.add("hidden");
    resultsGrid.innerHTML = "";
}

function showError(msg) {
    errorMsg.textContent = msg;
    errorBanner.classList.remove("hidden");
}

function clearError() {
    errorBanner.classList.add("hidden");
}

errorClose.addEventListener("click", clearError);

/* ─── Loading State ─────────────────────────── */

function setLoading(loading) {
    submitBtn.disabled = loading;
    if (loading) {
        submitBtn.innerHTML = `<span class="spinner"></span> <span>Processing…</span>`;
    } else {
        const label = currentMode === "single" ? "Send" : "Compare Models";
        submitBtn.innerHTML = `<span class="btn-icon">⚡</span><span id="submitBtnLabel">${label}</span>`;
    }
}

/* ─── Event Listeners ─────────────────────────── */

btnSingleMode.addEventListener("click", () => setMode("single"));
btnCompareMode.addEventListener("click", () => setMode("compare"));

btn2Models.addEventListener("click", () => setSlotCount(2));
btn3Models.addEventListener("click", () => setSlotCount(3));

// Sync dropdowns whenever a compare slot changes
[compareModel1, compareModel2, compareModel3].forEach(sel => {
    sel.addEventListener("change", syncCompareDropdowns);
});

/* ─── Init ──────────────────────────────────── */

(function init() {
    populateSingleDropdown();
    buildOptions(compareModel1, new Set());
    buildOptions(compareModel2, new Set([compareModel1.value]));
    buildOptions(compareModel3, new Set([compareModel1.value, compareModel2.value]));
    setMode("single");
})();

/* ─── Utils ─────────────────────────────────── */

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
