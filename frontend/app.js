/**
 * CortexAI Frontend — app.js (v2 — Scrollytelling Edition)
 */

/* ─── Config ──────────────────────────────── */
const API_BASE = "http://127.0.0.1:8000";
const API_KEY = "dev-key-1";

/* ─── Provider Catalog ────────────────────── */
// One entry per provider — icon shows in the dropdown, model is the default sent to API
const PROVIDERS = [
    { key: "gemini", label: "Gemini", icon: "⭐", model: "gemini-2.5-flash" },
    { key: "openai", label: "ChatGPT", icon: "🎯", model: "gpt-4o" },
    { key: "deepseek", label: "DeepSeek", icon: "🧠", model: "deepseek-chat" },
    { key: "grok", label: "Grok", icon: "🤖", model: "grok-4-latest" },
];
// Quick lookup for response card labels (provider key → display label)
const PROVIDER_LABELS = Object.fromEntries(PROVIDERS.map(p => [p.key, p.label]));
const PROVIDER_ICONS = Object.fromEntries(PROVIDERS.map(p => [p.key, p.icon]));
// Default model per provider (for API calls)
const PROVIDER_DEFAULT_MODEL = Object.fromEntries(PROVIDERS.map(p => [p.key, p.model]));
const MANUAL_DEFAULT_PROVIDER = "openai";
const MANUAL_FALLBACK_PROVIDER = PROVIDERS[0] || { key: "openai", model: "gpt-4o" };
const MANUAL_DEFAULT_MODEL_KEY = `${PROVIDER_DEFAULT_MODEL[MANUAL_DEFAULT_PROVIDER] ? MANUAL_DEFAULT_PROVIDER : MANUAL_FALLBACK_PROVIDER.key}:${PROVIDER_DEFAULT_MODEL[MANUAL_DEFAULT_PROVIDER] || MANUAL_FALLBACK_PROVIDER.model}`;

const ACTIVE_ROUTING_INDICATORS = {
    auto: "Auto",
    web: "Web",
    rewrite: "Rewrite",
};

/* ─── State ───────────────────────────────── */
let currentMode = "single";
let compareSlotCount = 2;
let conversationHistory = [];
let optimizeEnabled = false;
let smartModeEnabled = true;
let askResearchModeEnabled = true;
let compareResearchModeEnabled = false;
let isSubmitting = false;
let hasReceivedFirstStreamResponse = false;
let lastOptimizeResult = null;   // { original, optimized, wasOptimized }
const pendingWebSourcesByCard = new Map();
const SmartRoutingState = window.CortexSmartRoutingState || {
    parseKey: key => {
        const raw = String(key || "");
        const idx = raw.indexOf(":");
        if (idx < 0) return { provider: "", model: raw };
        return { provider: raw.slice(0, idx), model: raw.slice(idx + 1) };
    },
    hasSelectedModelKey: key => {
        const raw = String(key || "");
        return raw.includes(":") && raw.split(":")[0].length > 0;
    },
    deriveSmartModeFromSelection: key => !(String(key || "").includes(":") && String(key || "").split(":")[0].length > 0),
    isManualOverrideActive: (mode, smartOn, key) => mode === "single" && !smartOn && (String(key || "").includes(":") && String(key || "").split(":")[0].length > 0),
    isManualSelectionPending: (mode, smartOn, key) => mode === "single" && !smartOn && !(String(key || "").includes(":") && String(key || "").split(":")[0].length > 0),
    isModelDropdownVisible: (mode, smartOn) => mode === "single" && !smartOn,
    resolveManualSelection: (selectedKey, fallbackKey) => {
        const raw = String(selectedKey || "");
        if (raw.includes(":") && raw.split(":")[0].length > 0) return raw;
        return String(fallbackKey || "");
    },
};

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
    btnSingleMode: $("btnSingleMode"),
    btnCompareMode: $("btnCompareMode"),
    workspaceTagline: $("workspaceTagline"),
    singleRoutingControls: $("singleRoutingControls"),
    singleModelWrap: $("singleModelWrap"),
    singleModelLabel: $("singleModelLabel"),
    singleModel: $("singleModel"),
    compareModelWrap: $("compareModelWrap"),
    compareModel3Wrap: $("compareModel3Wrap"),
    compareAddModelBtn: $("compareAddModelBtn"),
    compareModel1: $("compareModel1"),
    compareModel2: $("compareModel2"),
    compareModel3: $("compareModel3"),
    promptCard: $("promptCard"),
    promptInput: $("promptInput"),
    submitBtn: $("submitBtn"),
    routeOptimizeBtn: $("routeOptimizeBtn"),
    routeSmartBtn: $("routeSmartBtn"),
    routeResearchBtn: $("routeResearchBtn"),
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
    const hasHero = Boolean(el.hero && el.heroContent);
    const compactBarRevealOffset = 160;

    // 1. Scroll-linked transforms via rAF (60fps)
    let ticking = false;
    function onScroll() {
        if (!ticking) {
            requestAnimationFrame(updateHero);
            ticking = true;
        }
    }

    function updateHero() {
        const scrollY = window.scrollY;

        if (hasHero) {
            const heroH = el.hero.offsetHeight;
            const prog = Math.min(scrollY / (heroH * 0.7), 1); // 0 → 1 over 70% of hero height

            // Fade + slide the hero content
            el.heroContent.style.opacity = 1 - prog;
            el.heroContent.style.transform = `translateY(${prog * -40}px)`;
        } else {
            const showBar = scrollY > compactBarRevealOffset;
            el.compactBar.classList.toggle("visible", showBar);
            el.compactBar.setAttribute("aria-hidden", showBar ? "false" : "true");
        }

        // Header shadow
        if (scrollY > 10) {
            el.mainHeader.classList.add("scrolled");
        } else {
            el.mainHeader.classList.remove("scrolled");
        }

        ticking = false;
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    updateHero();

    if (hasHero) {
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
    }
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
    el.compactSendBtn.innerHTML = `<span class="btn-icon">&uarr;</span> ${currentMode === "single" ? "Send" : "Compare"}`;
}

function getCompactBadges() {
    if (currentMode === "single") {
        const { provider, model } = parseKey(el.singleModel.value || "");
        if (smartModeEnabled) {
            return `<span class="compact-model-badge">Auto</span>`;
        }
        if (!provider) {
            return `<span class="compact-model-badge">Using: ChatGPT</span>`;
        }
        return `<span class="compact-model-badge">
              <span class="provider-dot dot-${provider}" style="width:7px;height:7px;border-radius:50%;flex-shrink:0;"></span>
              ${escHtml(PROVIDER_LABELS[provider] || model)}
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

function buildOptions(selectEl, excludeKeys = new Set(), options = {}) {
    const { allowEmpty = false, emptyLabel = "Select a model" } = options;
    const current = selectEl.value;
    selectEl.innerHTML = "";

    if (allowEmpty) {
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = emptyLabel;
        selectEl.appendChild(placeholder);
    }

    PROVIDERS.forEach(p => {
        const key = `${p.key}:${p.model}`;
        if (excludeKeys.has(key)) return;
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = `${p.icon}  ${p.label}`;
        if (key === current) opt.selected = true;
        selectEl.appendChild(opt);
    });

    if (!allowEmpty && !selectEl.value && selectEl.options.length > 0) {
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

function updateCompareAddButton() {
    const showThird = compareSlotCount === 3;
    if (el.compareModel3Wrap) {
        el.compareModel3Wrap.classList.toggle("hidden", !showThird);
    }
    if (el.compareAddModelBtn) {
        el.compareAddModelBtn.textContent = showThird ? "- Remove Model" : "+ Add Model";
        el.compareAddModelBtn.setAttribute("aria-expanded", showThird ? "true" : "false");
    }
}

function parseKey(key) {
    const idx = (key || "").indexOf(":");
    if (idx < 0) return { provider: "", model: key };
    return { provider: key.slice(0, idx), model: key.slice(idx + 1) };
}

function hasSelectedSingleModel() {
    return SmartRoutingState.hasSelectedModelKey(el.singleModel.value || "");
}

function getSingleModelDisplayName() {
    const { provider } = parseKey(el.singleModel.value || "");
    return PROVIDER_LABELS[provider] || "ChatGPT";
}

function ensureSingleManualModelSelection(forceDefault = false) {
    if (forceDefault) {
        el.singleModel.value = MANUAL_DEFAULT_MODEL_KEY;
        return;
    }
    el.singleModel.value = SmartRoutingState.resolveManualSelection(
        el.singleModel.value || "",
        MANUAL_DEFAULT_MODEL_KEY
    );
}

function updateSingleModelLabel() {
    const label = "Using:";
    if (el.singleModelLabel) {
        el.singleModelLabel.textContent = label;
    }
    el.singleModel.setAttribute("aria-label", `Using: ${getSingleModelDisplayName()}`);
}

function setComposerDocked(docked) {
    el.promptCard.classList.toggle("docked", docked);
}

function markFirstStreamResponseSeen() {
    if (hasReceivedFirstStreamResponse) return;
    hasReceivedFirstStreamResponse = true;
    setComposerDocked(true);
}

function updateRoutingHint() {
    el.workspaceTagline.innerHTML = "";
}

function isResearchEnabledForCurrentMode() {
    return currentMode === "single" ? askResearchModeEnabled : compareResearchModeEnabled;
}

function setResearchEnabledForCurrentMode(enabled) {
    if (currentMode === "single") {
        askResearchModeEnabled = enabled;
        return;
    }
    compareResearchModeEnabled = enabled;
}

function updateSingleModelRoutingUI() {
    const showModelDropdown = SmartRoutingState.isModelDropdownVisible(currentMode, smartModeEnabled);
    const showCompareControls = currentMode === "compare";
    if (showModelDropdown) {
        ensureSingleManualModelSelection();
    }
    updateSingleModelLabel();

    if (el.singleModelWrap) {
        el.singleModelWrap.classList.toggle("hidden", !showModelDropdown);
    }
    if (el.compareModelWrap) {
        el.compareModelWrap.classList.toggle("hidden", !showCompareControls);
    }
    if (el.compareAddModelBtn) {
        el.compareAddModelBtn.disabled = !showCompareControls;
    }
    el.singleModel.disabled = !showModelDropdown;
    updateCompareAddButton();

    updateRoutingButtons();
    updateCompactBar();
    updateSendButtonState();
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

    if (!isSingle) syncCompareDropdowns();
    updateSingleModelRoutingUI();

    clearResults();
    conversationHistory = [];
    updateRoutingButtons();
    updateCompactBar();
    updateSendButtonState();
}

function isSingleModelOverrideActive() {
    return SmartRoutingState.isManualOverrideActive(currentMode, smartModeEnabled, el.singleModel.value || "");
}

function isSingleManualModePendingSelection() {
    return SmartRoutingState.isManualSelectionPending(currentMode, smartModeEnabled, el.singleModel.value || "");
}

/* ═══════════════════════════════════════════
   SLOT COUNT
═══════════════════════════════════════════ */

if (el.compareAddModelBtn) {
    el.compareAddModelBtn.addEventListener("click", () => {
        compareSlotCount = compareSlotCount === 3 ? 2 : 3;
        updateCompareAddButton();
        syncCompareDropdowns();
    });
}

/* ═══════════════════════════════════════════
   PROMPT OPTIMIZATION TOGGLE
═══════════════════════════════════════════ */

el.routeOptimizeBtn.addEventListener("click", () => {
    optimizeEnabled = !optimizeEnabled;
    updateRoutingButtons();
});

el.routeSmartBtn.addEventListener("click", () => {
    if (currentMode !== "single") return;
    smartModeEnabled = !smartModeEnabled;
    if (!smartModeEnabled) {
        ensureSingleManualModelSelection(true);
    }
    updateSingleModelRoutingUI();
});

el.routeResearchBtn.addEventListener("click", () => {
    setResearchEnabledForCurrentMode(!isResearchEnabledForCurrentMode());
    updateRoutingButtons();
});

function setRoutingButtonState(button, label, enabled) {
    button.classList.toggle("active", enabled);
    button.setAttribute("aria-checked", enabled ? "true" : "false");
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.setAttribute("title", label);
}

function updateRoutingButtons() {
    setRoutingButtonState(el.routeOptimizeBtn, "Rewrite", optimizeEnabled);
    const smartAllowed = currentMode === "single";
    const smartChipWrap = el.routeSmartBtn ? el.routeSmartBtn.closest(".feature-chip-wrap") : null;
    if (smartChipWrap) {
        smartChipWrap.classList.toggle("hidden", !smartAllowed);
        smartChipWrap.setAttribute("aria-hidden", smartAllowed ? "false" : "true");
    }
    el.routeSmartBtn.disabled = !smartAllowed;
    setRoutingButtonState(el.routeSmartBtn, "Auto (Recommended)", smartAllowed && smartModeEnabled);
    setRoutingButtonState(el.routeResearchBtn, "Web", isResearchEnabledForCurrentMode());
    updateRoutingHint();
}

function updateSendButtonState() {
    const hasPrompt = el.promptInput.value.trim().length > 0;
    const missingManualModel = isSingleManualModePendingSelection();
    const disabled = isSubmitting || !hasPrompt || missingManualModel;
    el.submitBtn.disabled = disabled;
    el.compactSendBtn.disabled = disabled;
    const isExpanded = autoSizePromptInput(hasPrompt);
    el.promptCard.classList.toggle("expanded", isExpanded);
}

function autoSizePromptInput(hasPrompt) {
    const collapsedHeight = 56;
    const expandedMaxHeight = 240;
    const multilineThreshold = 4;

    el.promptInput.style.height = "auto";
    if (!hasPrompt) {
        el.promptInput.style.height = `${collapsedHeight}px`;
        return false;
    }

    const contentHeight = el.promptInput.scrollHeight;
    const shouldExpand = contentHeight > (collapsedHeight + multilineThreshold);
    const nextHeight = shouldExpand
        ? Math.min(contentHeight, expandedMaxHeight)
        : collapsedHeight;
    el.promptInput.style.height = `${nextHeight}px`;
    return shouldExpand;
}

function getRoutingPayload() {
    return {
        smart_mode: currentMode === "single" ? smartModeEnabled : false,
        research_mode: isResearchEnabledForCurrentMode(),
    };
}

/* ═══════════════════════════════════════════
   PROMPT FOCUS — card glow effect
═══════════════════════════════════════════ */

el.promptInput.addEventListener("focus", () => el.promptCard.classList.add("focused"));
el.promptInput.addEventListener("blur", () => el.promptCard.classList.remove("focused"));
el.promptInput.addEventListener("input", updateSendButtonState);

/* ═══════════════════════════════════════════
   EXAMPLE CHIPS
═══════════════════════════════════════════ */

document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
        el.promptInput.value = chip.dataset.prompt;
        el.promptInput.focus();
        updateSendButtonState();
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
        // Refresh history panel (silently, whether open or not, so next open is fresh)
        loadHistory();
    }
}

/* ═══════════════════════════════════════════
   SINGLE CHAT
═══════════════════════════════════════════ */

async function doSingleChat(prompt) {
    const { provider, model } = parseKey(el.singleModel.value);
    const manualMode = currentMode === "single" && !smartModeEnabled;
    const useManualModel = manualMode && !!provider;
    if (manualMode && !useManualModel) {
        showError("Please select a model or turn Auto-Select back on.");
        return;
    }

    const body = {
        prompt,
        ...(useManualModel ? { provider, model } : {}),
        routing: getRoutingPayload(),
        ...(conversationHistory.length > 0 ? {
            context: { session_id: "ui-session", conversation_history: conversationHistory }
        } : {}),
    };

    initStreamingResults(
        [useManualModel ? { provider, model } : { provider: "Auto", model: "Auto-selected model" }],
        false
    );

    let finalResponse = null;
    await callAPIStream("/v1/chat/stream", body, async event => {
        if (event.type === "start") {
            setPendingWebSources([0], event.web_source_items || []);
            return;
        }
        if (event.type === "line") {
            appendStreamLine(0, event.text || "");
            return;
        }
        if (event.type === "response_done" && event.response) {
            finalResponse = event.response;
            finalizeStreamCard(0, finalResponse);
            return;
        }
        if (event.type === "error") {
            throw new Error(event.message || "Streaming failed");
        }
    });

    if (!finalResponse) {
        throw new Error("Chat stream ended before completion.");
    }

    conversationHistory.push({ role: "user", content: prompt });
    conversationHistory.push({ role: "assistant", content: finalResponse.text || "" });
    if (conversationHistory.length > 20) {
        conversationHistory = conversationHistory.slice(-20);
    }
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

    initStreamingResults(targets, true);

    const responses = new Array(targets.length).fill(null);
    let comparePayload = null;

    await callAPIStream("/v1/compare/stream", { prompt, targets, routing: getRoutingPayload() }, async event => {
        if (event.type === "start") {
            setPendingWebSources(targets.map((_, i) => i), event.web_source_items || []);
            return;
        }
        if (event.type === "line" && Number.isInteger(event.index)) {
            appendStreamLine(event.index, event.text || "");
            return;
        }
        if (event.type === "response_done" && Number.isInteger(event.index) && event.response) {
            responses[event.index] = event.response;
            finalizeStreamCard(event.index, event.response);
            return;
        }
        if (event.type === "done" && event.compare) {
            comparePayload = event.compare;
            return;
        }
        if (event.type === "error") {
            throw new Error(event.message || "Streaming failed");
        }
    });

    if (!comparePayload) {
        const completed = responses.filter(Boolean);
        comparePayload = {
            responses: completed,
            total_tokens: completed.reduce((sum, r) => sum + (r.token_usage?.total_tokens || 0), 0),
            total_cost: completed.reduce((sum, r) => sum + (r.estimated_cost || 0), 0),
            success_count: completed.reduce((sum, r) => sum + (r.error ? 0 : 1), 0),
        };
    }

    renderCompareSummary(comparePayload);
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

async function callAPIStream(path, body, onEvent) {
    const resp = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/x-ndjson",
            "X-API-Key": API_KEY,
        },
        body: JSON.stringify(body),
    });

    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
            const j = await resp.json();
            detail = j.detail || detail;
        } catch {
            try { detail = await resp.text(); } catch { }
        }
        throw new Error(`API error: ${detail}`);
    }

    if (!resp.body) {
        throw new Error("Streaming is not supported in this browser.");
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let newlineIdx = buffer.indexOf("\n");
        while (newlineIdx >= 0) {
            const raw = buffer.slice(0, newlineIdx).trim();
            buffer = buffer.slice(newlineIdx + 1);
            if (raw) {
                let event = null;
                try { event = JSON.parse(raw); } catch { }
                if (event && onEvent) await onEvent(event);
            }
            newlineIdx = buffer.indexOf("\n");
        }
    }

    const tail = (buffer + decoder.decode()).trim();
    if (tail) {
        try {
            const event = JSON.parse(tail);
            if (onEvent) await onEvent(event);
        } catch { }
    }
}

function normalizeWebSources(rawSources) {
    if (!Array.isArray(rawSources)) return [];
    return rawSources
        .map(src => {
            const title = String(src?.title || "").trim();
            const url = String(src?.url || "").trim();
            const safeUrl = toSafeHttpUrl(url);
            if (!safeUrl) return null;
            return {
                title: title || safeUrl,
                url: safeUrl,
            };
        })
        .filter(Boolean)
        .slice(0, 6);
}

function toSafeHttpUrl(url) {
    try {
        const parsed = new URL(String(url || ""));
        if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
            return "";
        }
        return parsed.toString();
    } catch {
        return "";
    }
}

function buildWebSourceIconsHtml(sources) {
    const chips = sources.map((source, idx) => {
        const faviconUrl = `https://www.google.com/s2/favicons?domain_url=${encodeURIComponent(source.url)}&sz=32`;
        return `
          <a class="web-source-icon-link"
             href="${escHtml(source.url)}"
             target="_blank"
             rel="noopener noreferrer"
             title="${escHtml(source.title)}">
            <img class="web-source-icon" src="${faviconUrl}" alt="" loading="lazy" decoding="async" />
            <span class="sr-only">Source ${idx + 1}: ${escHtml(source.title)}</span>
          </a>
        `;
    }).join("");
    return `
      <span class="web-source-label">Sources</span>
      <span class="web-source-icons">${chips}</span>
    `;
}

function setPendingWebSources(indexes, rawSources) {
    const sources = normalizeWebSources(rawSources);
    indexes.forEach(index => {
        pendingWebSourcesByCard.set(Number(index), sources);
    });
}

function applyPendingWebSources(index, shouldShow = true) {
    const wrap = document.getElementById(`response-sources-${index}`);
    if (!wrap) return;
    const sources = pendingWebSourcesByCard.get(Number(index)) || [];
    pendingWebSourcesByCard.delete(Number(index));
    if (!shouldShow || sources.length === 0) {
        wrap.classList.add("hidden");
        wrap.innerHTML = "";
        return;
    }
    wrap.classList.remove("hidden");
    wrap.innerHTML = buildWebSourceIconsHtml(sources);
}

function initStreamingResults(targets, isMulti) {
    pendingWebSourcesByCard.clear();
    el.resultsSection.classList.remove("hidden");
    el.resultsGrid.className = isMulti ? "results-grid multi" : "results-grid";
    el.resultsGrid.style.gridTemplateColumns = isMulti ? `repeat(${targets.length}, 1fr)` : "";
    el.resultsGrid.innerHTML = targets.map((target, index) => buildStreamingCard(target, index)).join("");

    setTimeout(() => {
        el.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
}

function buildActionIcon(action) {
    if (action === "copy") {
        return `
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8">
            <rect x="9" y="9" width="10" height="10" rx="2"></rect>
            <rect x="5" y="5" width="10" height="10" rx="2"></rect>
          </svg>`;
    }
    if (action === "like") {
        return `
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="currentColor">
            <path d="M9 11V20H5V11H9Z"></path>
            <path d="M11 20H17.6C18.42 20 19.14 19.45 19.36 18.66L20.81 13.66C21.12 12.59 20.31 11.52 19.19 11.52H15V7.74C15 6.78 14.22 6 13.26 6C12.92 6 12.59 6.1 12.31 6.29L9.82 11H11V20Z"></path>
          </svg>`;
    }
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="currentColor">
        <path d="M15 13V4H19V13H15Z"></path>
        <path d="M13 4H6.4C5.58 4 4.86 4.55 4.64 5.34L3.19 10.34C2.88 11.41 3.69 12.48 4.81 12.48H9V16.26C9 17.22 9.78 18 10.74 18C11.08 18 11.41 17.9 11.69 17.71L14.18 13H13V4Z"></path>
      </svg>`;
}

function buildResponseActionButtons(index) {
    return `
      <div class="response-actions" role="group" aria-label="Response actions">
        <button type="button"
                class="response-action-btn"
                data-action="copy"
                data-index="${index}"
                aria-label="Copy response"
                title="Copy response">
          ${buildActionIcon("copy")}
        </button>
        <button type="button"
                class="response-action-btn"
                data-action="like"
                data-index="${index}"
                aria-label="Like response"
                aria-pressed="false"
                title="Like response">
          ${buildActionIcon("like")}
        </button>
        <button type="button"
                class="response-action-btn"
                data-action="dislike"
                data-index="${index}"
                aria-label="Dislike response"
                aria-pressed="false"
                title="Dislike response">
          ${buildActionIcon("dislike")}
        </button>
      </div>`;
}

function buildStreamingCard(target, index) {
    const provider = target.provider || "";
    const label = PROVIDER_LABELS[provider] || provider || "Model";
    const modelSuffix = target.model ? ` · ${target.model}` : "";
    const icon = PROVIDER_ICONS[provider] || "🤖";
    const delay = index * 60;

    return `
    <div class="response-card loading-card" id="response-card-${index}"
         style="animation: cardIn 0.4s cubic-bezier(.4,0,.2,1) ${delay}ms both;">
      <div class="response-card-header">
        <span class="model-badge" id="response-model-badge-${index}">
          <span class="provider-icon">${icon}</span>
          ${escHtml(label + modelSuffix)}
        </span>
      </div>
      <div class="response-card-body">
        <p class="response-text" id="response-text-${index}" data-empty="true">Waiting for response…</p>
      </div>
      <div class="response-card-footer">
        <div class="response-stats">
          <div class="stat-item">
            <span class="stat-label">Tokens</span>
            <span class="stat-value" id="response-tokens-${index}">0</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Finish</span>
            <span class="stat-value" id="response-finish-${index}">-</span>
          </div>
        </div>
        ${buildResponseActionButtons(index)}
      </div>
      <div class="web-source-strip hidden" id="response-sources-${index}" aria-label="Web sources"></div>
    </div>`;
}

function appendStreamLine(index, text) {
    const textEl = document.getElementById(`response-text-${index}`);
    if (!textEl) return;
    if (text) markFirstStreamResponseSeen();
    if (textEl.dataset.empty === "true") {
        textEl.textContent = "";
        textEl.dataset.empty = "false";
    }
    textEl.textContent += text;
}

function finalizeStreamCard(index, resp) {
    const card = document.getElementById(`response-card-${index}`);
    if (!card) return;
    markFirstStreamResponseSeen();

    const hasError = !!resp.error;
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const tokens = resp.token_usage ? resp.token_usage.total_tokens : 0;
    const finish = resp.finish_reason || "—";
    const provider = resp.provider || "";
    const label = PROVIDER_LABELS[provider] || provider || "Model";
    const modelSuffix = resp.model ? ` · ${resp.model}` : "";
    const icon = PROVIDER_ICONS[provider] || "🤖";

    const textEl = document.getElementById(`response-text-${index}`);
    const tokensEl = document.getElementById(`response-tokens-${index}`);
    const finishEl = document.getElementById(`response-finish-${index}`);
    const badgeEl = document.getElementById(`response-model-badge-${index}`);

    if (textEl) {
        textEl.textContent = text;
        textEl.dataset.empty = "false";
        textEl.classList.toggle("error-text", hasError);
    }
    if (tokensEl) tokensEl.textContent = tokens.toLocaleString();
    if (finishEl) finishEl.textContent = finish;
    if (badgeEl) {
        badgeEl.innerHTML = `
          <span class="provider-icon">${icon}</span>
          ${escHtml(label + modelSuffix)}
        `;
    }

    card.classList.remove("loading-card");
    card.classList.toggle("error-card", hasError);
    applyPendingWebSources(index, !hasError);
}

function renderCompareSummary(data) {
    const existing = el.resultsGrid.querySelector(".compare-summary-card");
    if (existing) existing.remove();
    el.resultsGrid.insertAdjacentHTML("beforeend", buildCompareSummary(data));
}

async function copyTextToClipboard(text) {
    const value = String(text || "").trim();
    if (!value) return false;
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
        }
    } catch (_) { /* fallback */ }

    try {
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        return copied;
    } catch (_) {
        return false;
    }
}

function setActionPressed(button, pressed) {
    button.classList.toggle("is-active", pressed);
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
}

function handleReactionAction(button, action) {
    const card = button.closest(".response-card");
    if (!card) return;
    const likeBtn = card.querySelector('.response-action-btn[data-action="like"]');
    const dislikeBtn = card.querySelector('.response-action-btn[data-action="dislike"]');
    if (!likeBtn || !dislikeBtn) return;

    const targetBtn = action === "like" ? likeBtn : dislikeBtn;
    const otherBtn = action === "like" ? dislikeBtn : likeBtn;
    const shouldActivate = !targetBtn.classList.contains("is-active");

    setActionPressed(otherBtn, false);
    setActionPressed(targetBtn, shouldActivate);
}

async function handleCopyAction(button) {
    const index = button.dataset.index || "";
    const textEl =
        document.getElementById(`response-text-${index}`) ||
        button.closest(".response-card")?.querySelector(".response-text");
    const text = textEl ? textEl.textContent : "";
    const copied = await copyTextToClipboard(text);
    button.classList.toggle("copied", copied);
    const nextTitle = copied ? "Copied" : "Copy unavailable";
    button.setAttribute("title", nextTitle);
    button.setAttribute("aria-label", nextTitle);
    window.setTimeout(() => {
        button.classList.remove("copied");
        button.setAttribute("title", "Copy response");
        button.setAttribute("aria-label", "Copy response");
    }, 1000);
}

el.resultsGrid.addEventListener("click", event => {
    const button = event.target.closest(".response-action-btn");
    if (!button || !el.resultsGrid.contains(button)) return;
    const action = button.dataset.action;
    if (action === "copy") {
        handleCopyAction(button);
        return;
    }
    if (action === "like" || action === "dislike") {
        handleReactionAction(button, action);
    }
});

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
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const tokens = resp.token_usage ? resp.token_usage.total_tokens : 0;
    const delay = index * 60;

    return `
    <div class="response-card ${hasError ? "error-card" : ""}"
         id="response-card-${index}"
         style="animation: cardIn 0.4s cubic-bezier(.4,0,.2,1) ${delay}ms both;">
      <div class="response-card-header">
        <span class="model-badge">
          <span class="provider-icon">${PROVIDER_ICONS[resp.provider] || "🤖"}</span>
          ${escHtml(PROVIDER_LABELS[resp.provider] || resp.provider)}
        </span>
      </div>
      <div class="response-card-body">
        <p class="response-text ${hasError ? "error-text" : ""}" id="response-text-${index}">${escHtml(text)}</p>
      </div>
      <div class="response-card-footer">
        <div class="response-stats">
          <div class="stat-item">
            <span class="stat-label">Tokens</span>
            <span class="stat-value">${tokens.toLocaleString()}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Finish</span>
            <span class="stat-value">${escHtml(resp.finish_reason || "-")}</span>
          </div>
        </div>
        ${buildResponseActionButtons(index)}
      </div>
    </div>`;
}

function buildCompareSummary(data) {
    const count = Array.isArray(data.responses) ? data.responses.length : 0;
    return `
    <div class="response-card compare-summary-card" style="grid-column:1/-1;background:#FAFAFA;animation:cardIn 0.4s cubic-bezier(.4,0,.2,1) ${count * 60}ms both;">
      <div class="response-card-body" style="padding:12px 16px;">
        <div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
          <div class="stat-item">
            <span class="stat-label">Total Tokens</span>
            <span class="stat-value">${(data.total_tokens || 0).toLocaleString()}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Successful</span>
            <span class="stat-value">${data.success_count || 0} / ${count}</span>
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
    pendingWebSourcesByCard.clear();
    hasReceivedFirstStreamResponse = false;
    setComposerDocked(false);
}

function showError(msg) {
    el.errorMsg.textContent = msg;
    el.errorBanner.classList.remove("hidden");
}
function clearError() { el.errorBanner.classList.add("hidden"); }
el.errorClose.addEventListener("click", clearError);

function setLoading(loading) {
    isSubmitting = loading;

    if (loading) {
        el.submitBtn.innerHTML = `<span class="spinner"></span>`;
        el.compactSendBtn.innerHTML = `<span class="spinner"></span>`;
    } else {
        el.submitBtn.innerHTML = `<span class="btn-icon">&uarr;</span>`;
        el.compactSendBtn.innerHTML = `<span class="btn-icon">&uarr;</span> ${currentMode === "single" ? "Send" : "Compare"}`;
    }
    updateSendButtonState();
}

/* ═══════════════════════════════════════════
   INIT
═══════════════════════════════════════════ */

(function init() {
    buildOptions(el.singleModel, new Set());
    el.singleModel.value = SmartRoutingState.resolveManualSelection("", MANUAL_DEFAULT_MODEL_KEY);
    buildOptions(el.compareModel1, new Set());
    buildOptions(el.compareModel2, new Set([el.compareModel1.value]));
    buildOptions(el.compareModel3, new Set([el.compareModel1.value, el.compareModel2.value]));

    // Dedup on change
    [el.compareModel1, el.compareModel2, el.compareModel3].forEach(s =>
        s.addEventListener("change", syncCompareDropdowns)
    );
    el.singleModel.addEventListener("change", () => {
        if (hasSelectedSingleModel()) {
            smartModeEnabled = false;
        }
        updateSingleModelRoutingUI();
    });

    updateRoutingButtons();
    updateSingleModelRoutingUI();
    setComposerDocked(false);
    setMode("single");
    updateSendButtonState();
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

/* ═══════════════════════════════════════════
   HISTORY SIDEBAR
═══════════════════════════════════════════ */

const historyEl = {
    sidebar: $("historySidebar"),
    clearAllBtn: $("historyClearAllBtn"),
    list: $("historyList"),
    empty: $("historyEmpty"),
    search: $("historySearch"),
};

let _historyData = [];   // full fetched list

historyEl.clearAllBtn.addEventListener("click", async () => {
    if (!confirm("Delete all history?")) return;
    await fetch(`${API_BASE}/v1/history`, {
        method: "DELETE",
        headers: { "X-API-Key": API_KEY },
    });
    loadHistory();
});

historyEl.search.addEventListener("input", () => {
    renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
});

loadHistory();

async function loadHistory() {
    try {
        const resp = await fetch(`${API_BASE}/v1/history?limit=200`, {
            headers: { "X-API-Key": API_KEY },
        });
        if (!resp.ok) return;
        _historyData = await resp.json();
        renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
    } catch (_) { /* silent */ }
}

function renderHistory(data, filter = "") {
    const filtered = filter
        ? data.filter(e =>
            e.prompt.toLowerCase().includes(filter) ||
            e.provider.toLowerCase().includes(filter) ||
            e.model.toLowerCase().includes(filter))
        : data;

    if (filtered.length === 0) {
        historyEl.list.innerHTML = "";
        historyEl.empty.style.display = "flex";
        return;
    }
    historyEl.empty.style.display = "none";

    historyEl.list.innerHTML = filtered.map(entry => {
        const icon = entry.mode === "compare" ? "⚖️" : "💬";
        const date = new Date(entry.timestamp).toLocaleString(undefined, {
            month: "short", day: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
        const promptSnippet = escHtml(entry.prompt.length > 80
            ? entry.prompt.slice(0, 80) + "…"
            : entry.prompt);
        const responseSnippet = escHtml(entry.response.length > 120
            ? entry.response.slice(0, 120) + "…"
            : entry.response);
        const tokStr = entry.tokens != null ? entry.tokens.toLocaleString() : "—";
        const modeLabel = entry.mode === "compare" ? "compare" : "chat";

        return `<li class="history-entry" data-id="${entry.id}">
          <div class="history-entry-top">
            <span class="history-mode-badge history-mode-${modeLabel}">${icon} ${modeLabel}</span>
            <span class="history-provider-badge">${escHtml(entry.provider)}</span>
            <span class="history-date">${date}</span>
            <button class="history-delete-btn" data-id="${entry.id}" title="Delete entry" aria-label="Delete">🗑</button>
          </div>
          <div class="history-prompt">${promptSnippet}</div>
          <div class="history-response">${responseSnippet}</div>
          <div class="history-meta">
            <span>Tokens: ${tokStr}</span>
          </div>
        </li>`;
    }).join("");

    // Delete button listeners
    historyEl.list.querySelectorAll(".history-delete-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            await fetch(`${API_BASE}/v1/history/${id}`, {
                method: "DELETE",
                headers: { "X-API-Key": API_KEY },
            });
            loadHistory();
        });
    });

    // Click entry to replay prompt in textarea
    historyEl.list.querySelectorAll(".history-entry").forEach(item => {
        item.addEventListener("click", (e) => {
            if (e.target.classList.contains("history-delete-btn")) return;
            const entry = filtered.find(en => en.id === Number(item.dataset.id));
            if (!entry) return;
            el.promptInput.value = entry.prompt;
            el.promptInput.focus();
            updateSendButtonState();
            document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });
}




