/**
 * CortexAI Frontend â€” app.js (v2 â€” Scrollytelling Edition)
 */

/* â”€â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const RUNTIME_CONFIG = window.CORTEX_RUNTIME_CONFIG || {};
const API_BASE = String(
    RUNTIME_CONFIG.apiBase || window.localStorage?.getItem("cortex_api_base") || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const API_KEY = String(
    RUNTIME_CONFIG.apiKey || window.localStorage?.getItem("cortex_api_key") || "dev-key-1"
);

/* â”€â”€â”€ Provider Catalog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
// One entry per provider â€” icon shows in the dropdown, model is the default sent to API
const FALLBACK_PROVIDER_CATALOG = [
    {
        provider: "gemini",
        label: "Gemini",
        icon: "https://www.google.com/s2/favicons?domain_url=gemini.google.com&sz=64",
        color: "#4285F4",
        default_model: "gemini-2.5-flash",
        sort_order: 1,
    },
    {
        provider: "openai",
        label: "ChatGPT",
        icon: "https://www.google.com/s2/favicons?domain_url=openai.com&sz=64",
        color: "#10A37F",
        default_model: "gpt-4o",
        sort_order: 2,
    },
    {
        provider: "deepseek",
        label: "DeepSeek",
        icon: "https://www.google.com/s2/favicons?domain_url=deepseek.com&sz=64",
        color: "#5B5BD6",
        default_model: "deepseek-chat",
        sort_order: 3,
    },
    {
        provider: "grok",
        label: "Grok",
        icon: "https://www.google.com/s2/favicons?domain_url=x.ai&sz=64",
        color: "#1DA1F2",
        default_model: "grok-4-latest",
        sort_order: 4,
    },
    {
        provider: "claude",
        label: "Claude",
        icon: "https://www.google.com/s2/favicons?domain_url=claude.ai&sz=64",
        color: "#D97706",
        default_model: "claude-sonnet-4-5",
        sort_order: 5,
    },
];
// Quick lookup for response card labels (provider key â†’ display label)
const FALLBACK_MODEL_CATALOG = FALLBACK_PROVIDER_CATALOG.map(spec => ({
    provider: spec.provider,
    model: spec.default_model,
    enabled: true,
}));

const PROVIDER_FAVICON_DOMAIN_BY_ID = {
    openai: "openai.com",
    gemini: "gemini.google.com",
    deepseek: "deepseek.com",
    grok: "x.ai",
    claude: "claude.ai",
};

let providerCatalog = [];
let modelCatalog = [];
let providerLabelById = {};
let providerIconById = {};
let providerColorById = {};
let providerDefaultModelById = {};
let providerSortOrderById = {};
let manualDefaultModelKey = "openai:gpt-4o";

const ACTIVE_ROUTING_INDICATORS = {
    auto: "Auto",
    web: "Web",
    rewrite: "Rewrite",
};
const COMPARE_CONTEXT_MODEL_TEXT_LIMIT = 260;
const COMPARE_CONTEXT_TOTAL_LIMIT = 2200;

const LEGACY_SESSION_STORAGE_KEY = "cortex_active_session_id";
const SESSION_STORAGE_KEY_BY_MODE = {
    single: "cortex_active_session_id_single",
    compare: "cortex_active_session_id_compare",
};
const MAX_CONTEXT_MESSAGES_UI = 20;

function toProviderId(value) {
    return String(value || "").trim().toLowerCase();
}

function toSortOrder(value, fallback = 999) {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
}

function toSafeColor(value, fallback = "#94A3B8") {
    const raw = String(value || "").trim();
    if (/^#[0-9a-fA-F]{3,8}$/.test(raw)) {
        return raw;
    }
    return fallback;
}

function toSafeIconUrl(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (raw.startsWith("/")) return raw;
    if (raw.startsWith("./") || raw.startsWith("../")) return raw;
    if (/^https?:\/\/\S+$/i.test(raw)) return raw;
    return "";
}

function defaultProviderIcon(providerRaw) {
    const provider = toProviderId(providerRaw);
    const domain = PROVIDER_FAVICON_DOMAIN_BY_ID[provider];
    if (!domain) return "";
    return `https://www.google.com/s2/favicons?domain_url=${encodeURIComponent(domain)}&sz=64`;
}

function resolveProviderIcon(providerRaw, preferredIcon) {
    const fromPreferred = toSafeIconUrl(preferredIcon);
    if (fromPreferred) return fromPreferred;
    return defaultProviderIcon(providerRaw);
}

function buildProviderLookups() {
    providerLabelById = {};
    providerIconById = {};
    providerColorById = {};
    providerDefaultModelById = {};
    providerSortOrderById = {};

    providerCatalog.forEach((spec, index) => {
        const provider = toProviderId(spec.provider);
        if (!provider) return;
        providerLabelById[provider] = String(spec.label || provider).trim() || provider;
        providerIconById[provider] = resolveProviderIcon(provider, spec.icon);
        providerColorById[provider] = toSafeColor(spec.color, "#94A3B8");
        providerSortOrderById[provider] = toSortOrder(spec.sort_order, index + 100);

        const defaultModel = String(spec.default_model || "").trim();
        if (defaultModel) {
            providerDefaultModelById[provider] = defaultModel;
        }
    });

    manualDefaultModelKey = computeManualDefaultModelKey();
}

function computeManualDefaultModelKey() {
    const preferredProvider = "openai";
    const preferredModel = providerDefaultModelById[preferredProvider];
    if (preferredModel) {
        return `${preferredProvider}:${preferredModel}`;
    }

    for (const spec of providerCatalog) {
        const provider = toProviderId(spec.provider);
        const model = providerDefaultModelById[provider];
        if (provider && model) {
            return `${provider}:${model}`;
        }
    }

    const firstModel = modelCatalog[0];
    if (firstModel && firstModel.provider && firstModel.model) {
        return `${firstModel.provider}:${firstModel.model}`;
    }
    return "openai:gpt-4o";
}

function applyCatalogData(nextProviders, nextModels) {
    const providerRows = Array.isArray(nextProviders) ? nextProviders : [];
    const modelRows = Array.isArray(nextModels) ? nextModels : [];

    const normalizedProviders = providerRows
        .map((row, index) => {
            const ui = row && typeof row.ui === "object" && row.ui ? row.ui : {};
            const provider = toProviderId(row?.provider || row?.key || row?.id);
            if (!provider) return null;
            const label = String(ui.display_name || row?.label || provider).trim() || provider;
            const defaultModel = String(row?.default_model || row?.model || "").trim();
            const icon = resolveProviderIcon(
                provider,
                row?.icon || row?.logo_url || row?.icon_url || ui.icon || ui.logo_url || ui.icon_url
            );
            const color = toSafeColor(row?.color || ui.color, "#94A3B8");
            const sortOrder = toSortOrder(row?.sort_order ?? ui.sort_order, index + 100);

            return {
                provider,
                label,
                icon,
                color,
                default_model: defaultModel,
                sort_order: sortOrder,
            };
        })
        .filter(Boolean);

    providerCatalog = (normalizedProviders.length ? normalizedProviders : FALLBACK_PROVIDER_CATALOG.map(spec => ({ ...spec })))
        .sort((a, b) => {
            const left = toSortOrder(a.sort_order, 999);
            const right = toSortOrder(b.sort_order, 999);
            if (left !== right) return left - right;
            return String(a.label || "").localeCompare(String(b.label || ""));
        });

    const allowedProviders = new Set(providerCatalog.map(spec => toProviderId(spec.provider)));
    const providerOrder = Object.fromEntries(
        providerCatalog.map((spec, index) => [toProviderId(spec.provider), toSortOrder(spec.sort_order, index + 100)])
    );

    const normalizedModels = modelRows
        .map(row => {
            const provider = toProviderId(row?.provider || row?.key || row?.id);
            const model = String(row?.model || row?.name || "").trim();
            if (!provider || !model || !allowedProviders.has(provider)) return null;
            return {
                provider,
                model,
                enabled: row?.enabled !== false,
            };
        })
        .filter(Boolean);

    const byKey = new Map();
    normalizedModels.forEach(item => {
        byKey.set(`${item.provider}:${item.model}`, item);
    });
    providerCatalog.forEach(spec => {
        const provider = toProviderId(spec.provider);
        const defaultModel = String(spec.default_model || "").trim();
        if (!provider || !defaultModel) return;
        const key = `${provider}:${defaultModel}`;
        if (!byKey.has(key)) {
            byKey.set(key, {
                provider,
                model: defaultModel,
                enabled: true,
            });
        }
    });

    modelCatalog = [...byKey.values()];
    if (modelCatalog.length === 0) {
        modelCatalog = FALLBACK_MODEL_CATALOG.map(item => ({ ...item }));
    }

    modelCatalog.sort((a, b) => {
        const leftOrder = toSortOrder(providerOrder[a.provider], 999);
        const rightOrder = toSortOrder(providerOrder[b.provider], 999);
        if (leftOrder !== rightOrder) return leftOrder - rightOrder;
        return String(a.model || "").localeCompare(String(b.model || ""));
    });

    buildProviderLookups();
}

function getManualDefaultModelKey() {
    return manualDefaultModelKey;
}

function getProviderColor(providerRaw) {
    const provider = toProviderId(providerRaw);
    return providerColorById[provider] || "#94A3B8";
}

function buildProviderIconHtml(providerRaw, size = 14, className = "provider-logo provider-logo-inline") {
    const provider = toProviderId(providerRaw);
    const iconUrl = providerIconById[provider] || "";
    if (!iconUrl) return "";
    const px = Number.isFinite(Number(size)) && Number(size) > 0 ? Number(size) : 14;
    return `<img class="${escHtml(className)}" src="${escHtml(iconUrl)}" alt="" width="${px}" height="${px}" loading="lazy" decoding="async" aria-hidden="true" />`;
}

function buildProviderDotHtml(providerRaw, size = 7) {
    const px = Number.isFinite(Number(size)) && Number(size) > 0 ? Number(size) : 7;
    const iconHtml = buildProviderIconHtml(providerRaw, px, "provider-logo provider-logo-inline");
    if (iconHtml) return iconHtml;
    const color = getProviderColor(providerRaw);
    return `<span class="provider-dot" style="width:${px}px;height:${px}px;border-radius:50%;flex-shrink:0;background:${color};"></span>`;
}

function getSelectableModels() {
    return modelCatalog.filter(item => item && item.enabled !== false && item.provider && item.model);
}

function modelKeyOf(provider, model) {
    const providerId = toProviderId(provider);
    const modelName = String(model || "").trim();
    if (!providerId || !modelName) return "";
    return `${providerId}:${modelName}`;
}

function getModelOptionLabel(providerRaw, modelRaw) {
    const provider = toProviderId(providerRaw);
    const model = String(modelRaw || "").trim();
    const label = providerLabelById[provider] || provider || "Model";
    const prefix = "";
    return `${prefix}${label} · ${model}`;
}

applyCatalogData(FALLBACK_PROVIDER_CATALOG, FALLBACK_MODEL_CATALOG);

/* â”€â”€â”€ State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
let currentMode = "single";
let compareSlotCount = 2;
let conversationHistory = [];
let activeSessionId = null;
const activeSessionIdByMode = {
    single: null,
    compare: null,
};
let pendingNewSession = false;
let optimizeEnabled = false;
let smartModeEnabled = true;
let askResearchModeEnabled = true;
let compareResearchModeEnabled = false;
let isSubmitting = false;
let hasReceivedFirstStreamResponse = false;
let historyUiReady = false;
let lastOptimizeResult = null;   // { original, optimized, wasOptimized }
let _historyData = [];   // full fetched list
let streamAutoScrollEnabled = false;
let lastStreamAutoScrollTs = 0;
let pendingBottomScrollRaf = null;
let pendingBottomScrollTimer = null;
const pendingWebSourcesByCard = new Map();
const chipToggleTimers = new WeakMap();
const modelPickerBySelectId = new Map();
let modelPickerOutsideHandlersAttached = false;
const STREAM_AUTO_SCROLL_THROTTLE_MS = 120;
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

/* â”€â”€â”€ DOM References â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
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
};

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   SCROLL BEHAVIOUR â€” Hero fade + Compact bar
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

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
            const prog = Math.min(scrollY / (heroH * 0.7), 1); // 0 â†’ 1 over 70% of hero height

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
        // 2. IntersectionObserver â€” show compact bar once hero is mostly gone
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

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   COMPACT BAR â€” SYNC
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

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
            const fallbackLabel = providerLabelById.openai || providerCatalog[0]?.label || "Assistant";
            return `<span class="compact-model-badge">Using: ${escHtml(fallbackLabel)}</span>`;
        }
        return `<span class="compact-model-badge">
              ${buildProviderDotHtml(provider, 7)}
              ${escHtml(providerLabelById[provider] || model)}
            </span>`;
    }
    return getActiveCompareSelects().map(sel => {
        const { provider, model } = parseKey(sel.value || "");
        if (!provider) return "";
        return `<span class="compact-model-badge">
              ${buildProviderDotHtml(provider, 7)}
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
function getModelPicker(selectEl) {
    if (!selectEl || !selectEl.id) return null;
    return modelPickerBySelectId.get(selectEl.id) || null;
}

function buildModelPickerGlyph(providerRaw, size = 14) {
    const iconHtml = buildProviderIconHtml(providerRaw, size, "model-picker-provider-icon");
    if (iconHtml) return iconHtml;
    const color = getProviderColor(providerRaw);
    return `<span class="model-picker-provider-fallback" style="background:${escHtml(color)};"></span>`;
}

function closeAllModelPickers(exceptSelectId = "") {
    modelPickerBySelectId.forEach((picker, selectId) => {
        const keepOpen = exceptSelectId && selectId === exceptSelectId;
        if (keepOpen) return;
        picker.wrapperEl.classList.remove("is-open");
        picker.wrapperEl.classList.remove("open-up");
        picker.buttonEl.setAttribute("aria-expanded", "false");
    });
}

function positionModelPickerMenu(selectEl) {
    const picker = getModelPicker(selectEl);
    if (!picker) return;

    const buttonRect = picker.buttonEl?.getBoundingClientRect?.();
    const viewportHeight = window?.innerHeight || document?.documentElement?.clientHeight || 0;
    if (!buttonRect || !viewportHeight) return;

    const edgePadding = 8;
    const desiredMaxHeight = 260;
    const spaceAbove = Math.max(0, buttonRect.top - edgePadding);
    const spaceBelow = Math.max(0, viewportHeight - buttonRect.bottom - edgePadding);
    const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
    const available = openUp ? spaceAbove : spaceBelow;
    const nextMaxHeight = Math.max(0, Math.min(desiredMaxHeight, available - 6));

    picker.wrapperEl.classList.toggle("open-up", openUp);
    if (nextMaxHeight > 0) {
        picker.menuEl.style.maxHeight = `${nextMaxHeight}px`;
    } else {
        picker.menuEl.style.removeProperty("max-height");
    }
}

function refreshOpenModelPickerLayouts() {
    modelPickerBySelectId.forEach(picker => {
        if (picker.wrapperEl.classList.contains("is-open")) {
            positionModelPickerMenu(picker.selectEl);
        }
    });
}

function setModelPickerOpen(selectEl, shouldOpen) {
    const picker = getModelPicker(selectEl);
    if (!picker) return;
    if (shouldOpen && picker.buttonEl.disabled) return;

    if (shouldOpen) {
        closeAllModelPickers(selectEl.id);
    }
    picker.wrapperEl.classList.toggle("is-open", !!shouldOpen);
    picker.buttonEl.setAttribute("aria-expanded", shouldOpen ? "true" : "false");

    if (shouldOpen) {
        positionModelPickerMenu(selectEl);
        if (typeof window?.requestAnimationFrame === "function") {
            window.requestAnimationFrame(() => positionModelPickerMenu(selectEl));
        }
    } else {
        picker.wrapperEl.classList.remove("open-up");
    }
}

function renderModelPickerOptions(selectEl) {
    const picker = getModelPicker(selectEl);
    if (!picker) return;

    const options = Array.from(selectEl?.options || []);
    const selectedValue = String(selectEl.value || "");
    if (options.length === 0) {
        picker.menuEl.innerHTML = `<div class="model-picker-empty">No models available</div>`;
        return;
    }

    const optionHtml = options.map(option => {
        const value = String(option?.value || "");
        const isActive = value === selectedValue;
        const { provider, model } = parseKey(value);
        const providerId = toProviderId(provider);
        const providerLabel = providerLabelById[providerId] || providerId || "Model";
        const label = value
            ? `${providerLabel} - ${model}`
            : String(option?.textContent || "Select a model");
        const glyph = providerId ? buildModelPickerGlyph(providerId, 14) : "";

        return `<button type="button"
                class="model-picker-option${isActive ? " is-active" : ""}"
                data-value="${escHtml(value)}"
                role="option"
                aria-selected="${isActive ? "true" : "false"}">
                ${glyph}
                <span class="model-picker-option-label">${escHtml(label)}</span>
            </button>`;
    }).join("");

    picker.menuEl.innerHTML = optionHtml;
}

function syncModelPickerFromNativeSelect(selectEl) {
    const picker = getModelPicker(selectEl);
    if (!picker) return;

    renderModelPickerOptions(selectEl);
    const selectedValue = String(selectEl.value || "");
    const { provider, model } = parseKey(selectedValue);
    const providerId = toProviderId(provider);
    const providerLabel = providerLabelById[providerId] || providerId || "Model";
    const selectedLabel = selectedValue
        ? `${providerLabel} - ${model}`
        : "Select a model";
    const glyph = providerId ? buildModelPickerGlyph(providerId, 14) : "";

    picker.buttonEl.innerHTML = `
        <span class="model-picker-selected">
            ${glyph}
            <span class="model-picker-selected-label">${escHtml(selectedLabel)}</span>
        </span>
        <span class="model-picker-caret" aria-hidden="true">v</span>
    `;
    picker.buttonEl.disabled = !!selectEl.disabled;
    picker.wrapperEl.classList.toggle("is-disabled", !!selectEl.disabled);

    if (selectEl.disabled) {
        setModelPickerOpen(selectEl, false);
    }
}

function attachModelPickerOutsideHandlers() {
    if (modelPickerOutsideHandlersAttached) return;
    if (typeof document?.addEventListener !== "function") return;

    document.addEventListener("click", event => {
        const target = event?.target;
        const pickerHost = target && typeof target.closest === "function"
            ? target.closest(".model-picker")
            : null;
        const keepOpenId = pickerHost ? String(pickerHost.getAttribute("data-select-id") || "") : "";
        closeAllModelPickers(keepOpenId);
    });

    document.addEventListener("keydown", event => {
        if (event?.key === "Escape") {
            closeAllModelPickers();
        }
    });

    if (typeof window?.addEventListener === "function") {
        window.addEventListener("resize", refreshOpenModelPickerLayouts);
        window.addEventListener("scroll", refreshOpenModelPickerLayouts, true);
    }

    modelPickerOutsideHandlersAttached = true;
}

function ensureModelPicker(selectEl) {
    if (!selectEl || !selectEl.id) return;
    if (getModelPicker(selectEl)) return;

    const parent = selectEl.parentElement;
    if (!parent || typeof document?.createElement !== "function" || typeof parent.insertBefore !== "function") {
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "model-picker";
    wrapper.setAttribute("data-select-id", selectEl.id);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "model-picker-btn";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", "Choose model");

    const menu = document.createElement("div");
    menu.className = "model-picker-menu";
    menu.setAttribute("role", "listbox");
    menu.setAttribute("aria-label", "Model options");

    wrapper.appendChild(button);
    wrapper.appendChild(menu);
    parent.insertBefore(wrapper, selectEl.nextSibling);
    selectEl.classList.add("model-select-enhanced");

    modelPickerBySelectId.set(selectEl.id, {
        selectEl,
        wrapperEl: wrapper,
        buttonEl: button,
        menuEl: menu,
    });

    button.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        const isOpen = wrapper.classList.contains("is-open");
        setModelPickerOpen(selectEl, !isOpen);
    });

    menu.addEventListener("click", event => {
        const optionButton = event?.target?.closest?.(".model-picker-option");
        if (!optionButton) return;
        const nextValue = String(optionButton.getAttribute("data-value") || "");
        if (selectEl.value !== nextValue) {
            selectEl.value = nextValue;
            selectEl.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
            syncModelPickerFromNativeSelect(selectEl);
        }
        setModelPickerOpen(selectEl, false);
    });

    selectEl.addEventListener("change", () => {
        syncModelPickerFromNativeSelect(selectEl);
    });

    syncModelPickerFromNativeSelect(selectEl);
    attachModelPickerOutsideHandlers();
}

function syncAllModelPickers() {
    modelPickerBySelectId.forEach(picker => {
        syncModelPickerFromNativeSelect(picker.selectEl);
    });
}

function initModelPickers() {
    [el.singleModel, el.compareModel1, el.compareModel2, el.compareModel3].forEach(ensureModelPicker);
    syncAllModelPickers();
}


/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   DROPDOWNS
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

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

    getSelectableModels().forEach(item => {
        const key = modelKeyOf(item.provider, item.model);
        if (excludeKeys.has(key)) return;
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = getModelOptionLabel(item.provider, item.model);
        if (key === current) opt.selected = true;
        selectEl.appendChild(opt);
    });

    if (!allowEmpty && !selectEl.value && selectEl.options.length > 0) {
        selectEl.options[0].selected = true;
    }

    syncModelPickerFromNativeSelect(selectEl);
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
    closeAllModelPickers();
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
    syncAllModelPickers();
}

function parseKey(key) {
    const idx = (key || "").indexOf(":");
    if (idx < 0) return { provider: "", model: key };
    return { provider: key.slice(0, idx), model: key.slice(idx + 1) };
}

function truncateContextText(value, limit) {
    const maxChars = Number(limit);
    if (!Number.isFinite(maxChars) || maxChars <= 0) return "";
    const text = String(value || "").trim();
    if (text.length <= maxChars) return text;
    return `${text.slice(0, Math.max(0, maxChars - 3)).trim()}...`;
}

function buildCompareAssistantContext(responses) {
    const safeResponses = Array.isArray(responses) ? responses.filter(Boolean) : [];
    if (safeResponses.length === 0) return "";

    const lines = ["Compared model responses:"];
    safeResponses.forEach((resp, index) => {
        const providerRaw = String(resp.provider || "").trim().toLowerCase();
        const modelRaw = String(resp.model || "").trim();
        const providerLabel =
            providerLabelById[providerRaw] ||
            String(resp.provider || "").trim() ||
            `Model ${index + 1}`;
        const modelLabel = modelRaw || `model-${index + 1}`;
        const slotLabel = `${providerLabel} · ${modelLabel}`;

        let responseText = "";
        const errorMessage = String(resp?.error?.message || "").trim();
        if (errorMessage) {
            responseText = `Error: ${errorMessage}`;
        } else {
            responseText = String(resp.text || "").trim() || "(empty response)";
        }

        const compactText = responseText.replace(/\s+/g, " ").trim();
        lines.push(`${slotLabel}: ${truncateContextText(compactText, COMPARE_CONTEXT_MODEL_TEXT_LIMIT)}`);
    });

    return truncateContextText(lines.join("\n"), COMPARE_CONTEXT_TOTAL_LIMIT);
}

function normalizeUiMode(value) {
    return value === "compare" ? "compare" : "single";
}

function historyModeForUiMode(mode = currentMode) {
    return normalizeUiMode(mode) === "compare" ? "compare" : "chat";
}

function normalizeSessionId(value) {
    const raw = String(value || "").trim();
    return raw ? raw.toLowerCase() : null;
}

function loadActiveSessionId(mode = currentMode) {
    const safeMode = normalizeUiMode(mode);
    const storageKey = SESSION_STORAGE_KEY_BY_MODE[safeMode];
    try {
        const scopedValue = normalizeSessionId(window.localStorage.getItem(storageKey));
        if (scopedValue) {
            return scopedValue;
        }
        if (safeMode === "single") {
            return normalizeSessionId(window.localStorage.getItem(LEGACY_SESSION_STORAGE_KEY));
        }
        return null;
    } catch (_) {
        return null;
    }
}

function persistActiveSessionId(mode = currentMode) {
    const safeMode = normalizeUiMode(mode);
    const storageKey = SESSION_STORAGE_KEY_BY_MODE[safeMode];
    const value = normalizeSessionId(
        safeMode === currentMode ? activeSessionId : activeSessionIdByMode[safeMode]
    );

    try {
        if (!value) {
            window.localStorage.removeItem(storageKey);
            if (safeMode === "single") {
                window.localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
            }
            return;
        }
        window.localStorage.setItem(storageKey, value);
        if (safeMode === "single") {
            window.localStorage.setItem(LEGACY_SESSION_STORAGE_KEY, value);
        }
    } catch (_) { /* ignore storage failures */ }
}

function setActiveSessionIdForMode(mode, sessionId, { persist = true } = {}) {
    const safeMode = normalizeUiMode(mode);
    const normalized = normalizeSessionId(sessionId);
    activeSessionIdByMode[safeMode] = normalized;
    if (safeMode === currentMode) {
        activeSessionId = normalized;
    }
    if (persist) {
        persistActiveSessionId(safeMode);
    }
    return normalized;
}

function createSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
        return window.crypto.randomUUID();
    }
    const hex = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx";
    return hex.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === "x" ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function ensureActiveSessionId() {
    const safeMode = normalizeUiMode(currentMode);
    const existing = normalizeSessionId(activeSessionIdByMode[safeMode] || activeSessionId);
    if (existing) {
        activeSessionId = existing;
        activeSessionIdByMode[safeMode] = existing;
        return existing;
    }
    const created = normalizeSessionId(createSessionId());
    setActiveSessionIdForMode(safeMode, created);
    activeSessionId = created;
    return created;
}

function startNewChatSession() {
    const safeMode = normalizeUiMode(currentMode);
    activeSessionId = normalizeSessionId(createSessionId());
    activeSessionIdByMode[safeMode] = activeSessionId;
    pendingNewSession = true;
    conversationHistory = [];
    clearResults();
    clearError();
    persistActiveSessionId(safeMode);
}

function hasSelectedSingleModel() {
    return SmartRoutingState.hasSelectedModelKey(el.singleModel.value || "");
}

function getSingleModelDisplayName() {
    const { provider } = parseKey(el.singleModel.value || "");
    return providerLabelById[provider] || providerLabelById.openai || "Assistant";
}

function ensureSingleManualModelSelection(forceDefault = false) {
    const fallbackModelKey = getManualDefaultModelKey();
    if (forceDefault) {
        el.singleModel.value = fallbackModelKey;
        return;
    }
    el.singleModel.value = SmartRoutingState.resolveManualSelection(
        el.singleModel.value || "",
        fallbackModelKey
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

function scrollResultsToBottom(behavior = "auto") {
    if (!el.resultsSection || el.resultsSection.classList.contains("hidden")) return;

    const lastCard = el.resultsGrid?.lastElementChild || null;
    if (lastCard && typeof lastCard.scrollIntoView === "function") {
        try {
            lastCard.scrollIntoView({ behavior, block: "end", inline: "nearest" });
        } catch (_) {
            lastCard.scrollIntoView(false);
        }
    } else {
        try {
            el.resultsSection.scrollIntoView({ behavior, block: "end" });
        } catch (_) {
            el.resultsSection.scrollIntoView(false);
        }
    }

    el.resultsSection.scrollTop = el.resultsSection.scrollHeight;

    const doc = document.scrollingElement || document.documentElement || document.body;
    if (doc && typeof window.scrollTo === "function") {
        const viewportH = Number(window.innerHeight) || 0;
        const targetTop = Math.max(0, doc.scrollHeight - viewportH);
        try {
            window.scrollTo({ top: targetTop, behavior });
        } catch (_) {
            window.scrollTo(0, targetTop);
        }
    }
}

function scheduleScrollResultsToBottom(options = {}) {
    const behavior = String(options.behavior || "auto");
    const followUpDelayMs = Number.isFinite(options.followUpDelayMs) ? options.followUpDelayMs : 72;

    if (pendingBottomScrollRaf !== null && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(pendingBottomScrollRaf);
        pendingBottomScrollRaf = null;
    }
    if (pendingBottomScrollTimer !== null) {
        clearTimeout(pendingBottomScrollTimer);
        pendingBottomScrollTimer = null;
    }

    const run = () => scrollResultsToBottom(behavior);
    if (typeof requestAnimationFrame === "function") {
        pendingBottomScrollRaf = requestAnimationFrame(() => {
            pendingBottomScrollRaf = null;
            run();
        });
    } else {
        run();
    }

    pendingBottomScrollTimer = setTimeout(() => {
        pendingBottomScrollTimer = null;
        run();
    }, followUpDelayMs);
}

function maybeAutoScrollDuringStream() {
    if (!streamAutoScrollEnabled) return;
    const now = Date.now();
    if (now - lastStreamAutoScrollTs < STREAM_AUTO_SCROLL_THROTTLE_MS) {
        return;
    }
    lastStreamAutoScrollTs = now;
    scrollResultsToBottom("auto");
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
    syncAllModelPickers();
    updateCompactBar();
    updateSendButtonState();
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   MODE
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

function setMode(mode) {
    currentMode = normalizeUiMode(mode);

    const isSingle = currentMode === "single";
    el.btnSingleMode.classList.toggle("active", isSingle);
    el.btnCompareMode.classList.toggle("active", !isSingle);
    el.btnSingleMode.setAttribute("aria-selected", isSingle);
    el.btnCompareMode.setAttribute("aria-selected", !isSingle);

    if (!isSingle) syncCompareDropdowns();
    updateSingleModelRoutingUI();

    const safeMode = normalizeUiMode(currentMode);
    if (!activeSessionIdByMode[safeMode]) {
        activeSessionIdByMode[safeMode] = loadActiveSessionId(safeMode);
    }
    activeSessionId = normalizeSessionId(activeSessionIdByMode[safeMode]);

    const modeLabel = historyModeForUiMode(safeMode);
    if (activeSessionId) {
        hydrateConversationHistoryFromSession(activeSessionId, _historyData, modeLabel);
        renderSessionTranscript(activeSessionId, _historyData, modeLabel);
        pendingNewSession = false;
    } else {
        conversationHistory = [];
        pendingNewSession = true;
        clearResults();
    }

    if (historyUiReady) {
        renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
    }
}

function isSingleModelOverrideActive() {
    return SmartRoutingState.isManualOverrideActive(currentMode, smartModeEnabled, el.singleModel.value || "");
}

function isSingleManualModePendingSelection() {
    return SmartRoutingState.isManualSelectionPending(currentMode, smartModeEnabled, el.singleModel.value || "");
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   SLOT COUNT
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

if (el.compareAddModelBtn) {
    el.compareAddModelBtn.addEventListener("click", () => {
        compareSlotCount = compareSlotCount === 3 ? 2 : 3;
        updateCompareAddButton();
        syncCompareDropdowns();
    });
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   PROMPT OPTIMIZATION TOGGLE
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

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
    if (!button) return;
    const wasStateKnown = button.hasAttribute("aria-checked");
    const previousChecked = button.getAttribute("aria-checked") === "true";

    button.classList.toggle("active", enabled);
    button.setAttribute("aria-checked", enabled ? "true" : "false");
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.setAttribute("title", label);

    if (wasStateKnown && previousChecked !== enabled) {
        triggerChipToggleFeedback(button);
    }
}

function triggerChipToggleFeedback(button) {
    if (!button || button.disabled) return;

    const existingTimer = chipToggleTimers.get(button);
    if (existingTimer) {
        clearTimeout(existingTimer);
    }

    button.classList.remove("is-toggling");
    // Restart the animation reliably on repeated quick toggles.
    void button.offsetWidth;
    button.classList.add("is-toggling");

    const timerId = window.setTimeout(() => {
        button.classList.remove("is-toggling");
        chipToggleTimers.delete(button);
    }, 280);
    chipToggleTimers.set(button, timerId);
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

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   PROMPT FOCUS â€” card glow effect
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

el.promptInput.addEventListener("focus", () => el.promptCard.classList.add("focused"));
el.promptInput.addEventListener("blur", () => el.promptCard.classList.remove("focused"));
el.promptInput.addEventListener("input", updateSendButtonState);

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   EXAMPLE CHIPS
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
        el.promptInput.value = chip.dataset.prompt;
        el.promptInput.focus();
        updateSendButtonState();
        // Scroll to workspace smoothly
        document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
    });
});

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   KEYBOARD SHORTCUT
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

el.promptInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
    }
});

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   OPT PANEL â€” View / close
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   OPTIMIZE PROMPT CALL
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

async function callOptimize(prompt) {
    const data = await callAPI("/v1/optimize", { prompt });
    if (!data) return prompt;               // on error fall through

    lastOptimizeResult = {
        original: data.original_prompt,
        optimized: data.optimized_prompt,
        wasOptimized: data.was_optimized,
        serverEnabled: data.server_optimization_enabled,
    };

    return data.optimized_prompt;
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   SUBMIT
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

el.submitBtn.addEventListener("click", handleSubmit);

async function handleSubmit() {
    const rawPrompt = el.promptInput.value.trim();
    if (!rawPrompt) { el.promptInput.focus(); return; }
    el.promptInput.value = "";
    updateSendButtonState();

    clearError();
    setLoading(true);

    try {
        // Step 1: optionally optimize the prompt
        let prompt = rawPrompt;
        if (optimizeEnabled) {
            prompt = await callOptimize(rawPrompt);
        } else {
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

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   SINGLE CHAT
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

async function doSingleChat(prompt) {
    const { provider, model } = parseKey(el.singleModel.value);
    const manualMode = currentMode === "single" && !smartModeEnabled;
    const useManualModel = manualMode && !!provider;
    if (manualMode && !useManualModel) {
        showError("Please select a model or turn Auto-Select back on.");
        return;
    }

    const sessionId = ensureActiveSessionId();

    const body = {
        prompt,
        ...(useManualModel ? { provider, model } : {}),
        routing: getRoutingPayload(),
        context: {
            session_id: sessionId,
            conversation_history: conversationHistory,
            new_session: pendingNewSession,
        },
    };

    const streamState = initStreamingResults(
        [useManualModel ? { provider, model } : { provider: "Auto", model: "Auto-selected model" }],
        false,
        { append: true, promptText: prompt }
    );
    const cardIndex = streamState.indexMap[0];

    let finalResponse = null;
    streamAutoScrollEnabled = true;
    lastStreamAutoScrollTs = 0;
    try {
        await callAPIStream("/v1/chat/stream", body, async event => {
            if (event.type === "start") {
                setPendingWebSources([cardIndex], event.web_source_items || []);
                return;
            }
            if (event.type === "line") {
                appendStreamLine(cardIndex, event.text || "");
                return;
            }
            if (event.type === "response_done" && event.response) {
                finalResponse = event.response;
                finalizeStreamCard(cardIndex, finalResponse);
                return;
            }
            if (event.type === "error") {
                throw new Error(event.message || "Streaming failed");
            }
        });
    } finally {
        streamAutoScrollEnabled = false;
    }

    if (!finalResponse) {
        throw new Error("Chat stream ended before completion.");
    }

    conversationHistory.push({ role: "user", content: prompt });
    conversationHistory.push({ role: "assistant", content: finalResponse.text || "" });
    if (conversationHistory.length > MAX_CONTEXT_MESSAGES_UI) {
        conversationHistory = conversationHistory.slice(-MAX_CONTEXT_MESSAGES_UI);
    }
    pendingNewSession = false;
    persistActiveSessionId();
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   COMPARE
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

async function doCompare(prompt) {
    const selects = getActiveCompareSelects();
    const targets = selects.map(sel => parseKey(sel.value));
    const sessionId = ensureActiveSessionId();

    if (targets.some(t => !t.provider || !t.model)) {
        showError("Please select a model for each compare slot.");
        return;
    }

    if (new Set(targets.map(t => `${t.provider}:${t.model}`)).size < targets.length) {
        showError("Please select different models for each slot.");
        return;
    }

    const streamState = initStreamingResults(targets, true, { append: true, promptText: prompt });

    const responses = new Array(targets.length).fill(null);
    let comparePayload = null;

    streamAutoScrollEnabled = true;
    lastStreamAutoScrollTs = 0;
    try {
        await callAPIStream("/v1/compare/stream", {
            prompt,
            targets,
            routing: getRoutingPayload(),
            context: {
                session_id: sessionId,
                conversation_history: conversationHistory,
                new_session: pendingNewSession,
            },
        }, async event => {
            if (event.type === "start") {
                setPendingWebSources(streamState.indexMap, event.web_source_items || []);
                return;
            }
            if (event.type === "line" && Number.isInteger(event.index)) {
                const cardIndex = streamState.indexMap[event.index];
                if (cardIndex !== undefined) {
                    appendStreamLine(cardIndex, event.text || "");
                }
                return;
            }
            if (event.type === "response_done" && Number.isInteger(event.index) && event.response) {
                responses[event.index] = event.response;
                const cardIndex = streamState.indexMap[event.index];
                if (cardIndex !== undefined) {
                    finalizeStreamCard(cardIndex, event.response);
                }
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
    } finally {
        streamAutoScrollEnabled = false;
    }

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
    const compareResponsesForContext = Array.isArray(comparePayload?.responses)
        ? comparePayload.responses
        : responses.filter(Boolean);
    const compareAssistantContext = buildCompareAssistantContext(compareResponsesForContext);
    conversationHistory.push({ role: "user", content: prompt });
    if (compareAssistantContext) {
        conversationHistory.push({ role: "assistant", content: compareAssistantContext });
    }
    if (conversationHistory.length > MAX_CONTEXT_MESSAGES_UI) {
        conversationHistory = conversationHistory.slice(-MAX_CONTEXT_MESSAGES_UI);
    }
    pendingNewSession = false;
    persistActiveSessionId();
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   API
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

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

function sourceDomainLabel(url) {
    try {
        const parsed = new URL(String(url || ""));
        return parsed.hostname.replace(/^www\./, "") || parsed.hostname;
    } catch {
        return "";
    }
}

function webSourceListId(index) {
    const normalizedIndex = Number(index);
    return Number.isFinite(normalizedIndex)
        ? `response-sources-list-${normalizedIndex}`
        : "response-sources-list-live";
}

function buildWebSourceChipsHtml(sources) {
    if (!Array.isArray(sources) || sources.length === 0) return "";
    return sources.map((source, idx) => {
        const faviconUrl = `https://www.google.com/s2/favicons?domain_url=${encodeURIComponent(source.url)}&sz=32`;
        const domain = sourceDomainLabel(source.url);
        return `
          <a class="source-chip"
             href="${escHtml(source.url)}"
             target="_blank"
             rel="noopener noreferrer"
             title="${escHtml(source.title)}">
            <img class="source-chip-icon" src="${faviconUrl}" alt="" loading="lazy" decoding="async" />
            <span class="source-chip-label">${escHtml(domain || source.title)}</span>
            <span class="sr-only">Source ${idx + 1}: ${escHtml(source.title)}</span>
          </a>
        `;
    }).join("");
}

function buildWebSourceStripHtml(sources, index) {
    if (!Array.isArray(sources) || sources.length === 0) return "";
    const sourceCount = sources.length;
    const pagesLabel = `${sourceCount} web page${sourceCount === 1 ? "" : "s"}`;
    const listId = webSourceListId(index);

    return `
      <button type="button"
              class="web-source-toggle"
              data-role="source-toggle"
              aria-label="Toggle web sources: ${escHtml(pagesLabel)}"
              aria-expanded="false"
              aria-controls="${listId}">
        <span class="web-source-toggle-leading-icon" aria-hidden="true">
          <svg viewBox="0 0 16 16" focusable="false">
            <path d="M2.5 8a5.5 5.5 0 1 1 11 0a5.5 5.5 0 0 1-11 0Zm2.1 0h6.8M8 2.5c1.25 1.3 2 3.37 2 5.5s-.75 4.2-2 5.5m0-11c-1.25 1.3-2 3.37-2 5.5s.75 4.2 2 5.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </span>
        <span class="web-source-toggle-text">
          <span class="web-source-toggle-count">${sourceCount}</span>
          <span class="web-source-toggle-label">web page${sourceCount === 1 ? "" : "s"}</span>
        </span>
        <span class="web-source-toggle-icon" aria-hidden="true">
          <svg viewBox="0 0 16 16" focusable="false">
            <path d="M4.25 6.25L8 10l3.75-3.75" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
        </span>
      </button>
    `;
}

function setSourceStripExpanded(strip, expanded) {
    if (!strip) return;
    const toggle = strip.querySelector(".web-source-toggle");
    const listId = String(toggle?.getAttribute("aria-controls") || "");
    const list = listId ? document.getElementById(listId) : null;
    const isExpanded = !!expanded;

    strip.classList.toggle("is-expanded", isExpanded);
    if (toggle) {
        toggle.setAttribute("aria-expanded", isExpanded ? "true" : "false");
    }
    if (list) {
        list.setAttribute("aria-hidden", isExpanded ? "false" : "true");
    }
}

function setPendingWebSources(indexes, rawSources) {
    const sources = normalizeWebSources(rawSources);
    indexes.forEach(index => {
        pendingWebSourcesByCard.set(Number(index), sources);
    });
}

function applyPendingWebSources(index, shouldShow = true) {
    const wrap = document.getElementById(`response-sources-${index}`);
    const list = document.getElementById(webSourceListId(index));
    if (!wrap) return;
    const sources = pendingWebSourcesByCard.get(Number(index)) || [];
    pendingWebSourcesByCard.delete(Number(index));
    if (!shouldShow || sources.length === 0) {
        wrap.classList.add("hidden");
        wrap.classList.remove("is-expanded");
        wrap.innerHTML = "";
        if (list) {
            list.classList.add("hidden");
            list.setAttribute("aria-hidden", "true");
            list.innerHTML = "";
        }
        return;
    }
    wrap.classList.remove("hidden");
    wrap.classList.remove("is-expanded");
    wrap.innerHTML = buildWebSourceStripHtml(sources, index);
    if (list) {
        list.classList.remove("hidden");
        list.setAttribute("aria-hidden", "true");
        list.innerHTML = buildWebSourceChipsHtml(sources);
    }
}

function getNextStreamCardIndex() {
    const cards = el.resultsGrid.querySelectorAll("[id^='chat-msg-']");
    let maxIndex = -1;
    cards.forEach(card => {
        const match = /chat-msg-(\d+)$/.exec(card.id || "");
        if (!match) return;
        const idx = Number(match[1]);
        if (Number.isInteger(idx) && idx > maxIndex) {
            maxIndex = idx;
        }
    });
    return maxIndex + 1;
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
        <div class="response-action-group response-action-group-copy" role="group" aria-label="Copy action">
          <button type="button"
                  class="response-action-btn"
                  data-action="copy"
                  data-index="${index}"
                  aria-label="Copy response"
                  title="Copy response">
            ${buildActionIcon("copy")}
          </button>
        </div>
        <div class="response-action-group response-action-group-feedback" role="group" aria-label="Feedback actions">
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
        </div>
      </div>`;
}

function getTokenUsageTotal(tokenUsage) {
    if (!tokenUsage || !Object.prototype.hasOwnProperty.call(tokenUsage, "total_tokens")) {
        return null;
    }
    const value = Number(tokenUsage.total_tokens);
    return Number.isFinite(value) ? value : null;
}

function buildTokenUsageText(tokenUsage, index = null) {
    const total = getTokenUsageTotal(tokenUsage);
    const idAttr = index === null ? "" : ` id="response-token-usage-${index}"`;
    const hiddenClass = total === null ? " hidden" : "";
    const text = total === null ? "" : `Tokens: ${total.toLocaleString()}`;
    return `<span class="response-token-usage${hiddenClass}"${idAttr}>${escHtml(text)}</span>`;
}

function buildResponseProviderMeta(summary, index = null) {
    const safeSummary = String(summary || "").trim() || "Assistant";
    const idAttr = index === null ? "" : ` id="response-provider-summary-${index}"`;
    return `<div class="response-provider-meta"${idAttr} title="${escHtml(safeSummary)}">${escHtml(safeSummary)}</div>`;
}

function buildResponseFooter(index, summary, tokenUsage, webSources = []) {
    const safeSources = Array.isArray(webSources) ? webSources : [];
    const sourceStripHtml = safeSources.length > 0 ? buildWebSourceStripHtml(safeSources, index) : "";
    const sourceListHtml = safeSources.length > 0 ? buildWebSourceChipsHtml(safeSources) : "";

    return `
      <div class="message-footer">
        <div class="message-footer-bar">
          <div class="web-source-strip${webSources.length > 0 ? "" : " hidden"}" id="response-sources-${index}" aria-label="Web sources">${sourceStripHtml}</div>
          <div class="message-footer-meta">
            ${buildResponseProviderMeta(summary, index)}
            ${buildTokenUsageText(tokenUsage, index)}
            ${buildResponseActionButtons(index)}
          </div>
        </div>
        <div class="web-source-list${webSources.length > 0 ? "" : " hidden"}" id="${webSourceListId(index)}" aria-hidden="true">${sourceListHtml}</div>
      </div>`;
}

function getProviderPresentation(providerRaw, modelRaw) {
    const provider = toProviderId(providerRaw);
    const modelText = String(modelRaw || "").trim();
    const label = providerLabelById[provider] || String(providerRaw || "").trim() || "Assistant";
    const icon = buildProviderIconHtml(provider, 14, "compare-model-icon");
    const summary = modelText ? `${label} \u00B7 ${modelText}` : label;
    return { provider, modelText, label, icon, summary };
}

function buildCompareModelHeader(providerRaw, modelRaw) {
    const { icon, summary } = getProviderPresentation(providerRaw, modelRaw);
    return `
      <div class="compare-model-header" title="${escHtml(summary)}">
        ${icon}
        <span class="compare-model-label">${escHtml(summary)}</span>
      </div>`;
}

function getCompareGridClass(columnCount) {
    if (columnCount >= 3) return "compare-grid compare-grid-3";
    if (columnCount === 2) return "compare-grid compare-grid-2";
    return "compare-grid compare-grid-1";
}

function buildUserMessageBubble(promptText, delay = 0) {
    const userPrompt = String(promptText || "").trim();
    if (!userPrompt) return "";
    return `
    <div class="chat-message chat-message-user"
         style="animation: messageIn .2s ease-out ${delay}ms both;">
      <div class="chat-bubble chat-bubble-user">
        <p class="chat-user-text">${escHtml(userPrompt)}</p>
      </div>
    </div>`;
}

function buildStreamingCard(target, index, delay = 0, showProvider = true, options = {}) {
    const compareView = Boolean(options.compareView);
    const { summary } = getProviderPresentation(target.provider, target.model);
    const providerSummary = escHtml(summary);
    const providerSummaryHtml = showProvider ? `<div class="message-provider">${providerSummary}</div>` : "";
    const footerHtml = buildResponseFooter(index, summary, null, []);

    return `
    <div class="chat-message chat-message-ai${compareView ? " compare-response" : ""} is-streaming" id="chat-msg-${index}"
         style="animation: messageIn .2s ease-out ${delay}ms both;">
      <div class="chat-bubble chat-bubble-ai">
        ${providerSummaryHtml}
        <div class="typing-indicator" id="response-typing-${index}" role="status" aria-live="polite">
          <span class="typing-indicator-label" aria-hidden="true">Thinking</span>
          <span class="typing-indicator-dots" aria-hidden="true">
            <span class="typing-indicator-dot">.</span>
            <span class="typing-indicator-dot">.</span>
            <span class="typing-indicator-dot">.</span>
          </span>
          <span class="sr-only">Assistant is thinking</span>
        </div>
        <p class="response-text hidden" id="response-text-${index}" data-empty="true"></p>
        ${footerHtml}
      </div>
    </div>`;
}

function buildCompareStreamingTurn(promptText, targets, indexMap) {
    const gridClass = getCompareGridClass(targets.length);
    const columnsHtml = targets.map((target, offset) => {
        const cardIndex = indexMap[offset];
        return `
          <article class="compare-column">
            ${buildCompareModelHeader(target.provider, target.model)}
            ${buildStreamingCard(target, cardIndex, offset * 35, false, { compareView: true })}
          </article>`;
    }).join("");

    return `
      <section class="compare-turn compare-turn-streaming">
        ${buildUserMessageBubble(promptText)}
        <div class="${gridClass}">
          ${columnsHtml}
        </div>
      </section>`;
}

function buildCompareTurn(promptText, responses, startIndex = 0) {
    const safeResponses = Array.isArray(responses) ? responses.filter(Boolean) : [];
    if (safeResponses.length === 0) {
        return { html: "", nextIndex: startIndex };
    }

    let nextIndex = startIndex;
    const gridClass = getCompareGridClass(safeResponses.length);
    const columnsHtml = safeResponses.map(resp => {
        const index = nextIndex++;
        return `
          <article class="compare-column">
            ${buildCompareModelHeader(resp.provider, resp.model)}
            ${buildResponseCard(resp, index, false, { compareView: true })}
          </article>`;
    }).join("");

    return {
        html: `
          <section class="compare-turn">
            ${buildUserMessageBubble(promptText)}
            <div class="${gridClass}">
              ${columnsHtml}
            </div>
          </section>`,
        nextIndex,
    };
}

function initStreamingResults(targets, isMulti, options = {}) {
    if (isMulti) {
        return initCompareStreamingResults(targets, options);
    }

    const append = Boolean(options.append);
    const promptText = String(options.promptText || "");

    pendingWebSourcesByCard.clear();
    el.resultsSection.classList.remove("hidden");
    el.resultsGrid.className = "results-grid";
    el.resultsGrid.style.gridTemplateColumns = "";

    if (!append) {
        el.resultsGrid.innerHTML = "";
    }

    const baseIndex = append ? getNextStreamCardIndex() : 0;
    const indexMap = targets.map((_, offset) => baseIndex + offset);

    let html = "";
    if (promptText) {
        html += buildUserMessageBubble(promptText);
    }
    html += targets.map((target, offset) => {
        const cardIndex = indexMap[offset];
        return buildStreamingCard(target, cardIndex, offset * 35, isMulti);
    }).join("");

    if (append) {
        el.resultsGrid.insertAdjacentHTML("beforeend", html);
    } else {
        el.resultsGrid.innerHTML = html;
    }

    scheduleScrollResultsToBottom({ behavior: "smooth", followUpDelayMs: 96 });

    return { indexMap };
}

function initCompareStreamingResults(targets, options = {}) {
    const append = options.append === undefined ? true : Boolean(options.append);
    const promptText = String(options.promptText || "");

    pendingWebSourcesByCard.clear();
    el.resultsSection.classList.remove("hidden");
    el.resultsGrid.className = "results-grid compare-transcript";
    el.resultsGrid.style.gridTemplateColumns = "";

    if (!append) {
        el.resultsGrid.innerHTML = "";
    }

    const baseIndex = append ? getNextStreamCardIndex() : 0;
    const indexMap = targets.map((_, offset) => baseIndex + offset);
    const turnHtml = buildCompareStreamingTurn(promptText, targets, indexMap);

    if (append) {
        el.resultsGrid.insertAdjacentHTML("beforeend", turnHtml);
    } else {
        el.resultsGrid.innerHTML = turnHtml;
    }

    scheduleScrollResultsToBottom({ behavior: "smooth", followUpDelayMs: 96 });

    return { indexMap };
}

function appendStreamLine(index, text) {
    const textEl = document.getElementById(`response-text-${index}`);
    if (!textEl) return;
    if (text) markFirstStreamResponseSeen();
    if (textEl.dataset.empty === "true") {
        textEl.textContent = "";
        textEl.dataset.empty = "false";
        textEl.classList.remove("hidden");
        const typingEl = document.getElementById(`response-typing-${index}`);
        if (typingEl) typingEl.classList.add("hidden");
    }
    textEl.textContent += text;
    maybeAutoScrollDuringStream();
}

function finalizeStreamCard(index, resp) {
    const card = document.getElementById(`chat-msg-${index}`);
    if (!card) return;
    markFirstStreamResponseSeen();

    const hasError = !!resp.error;
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const tokens = getTokenUsageTotal(resp.token_usage);
    const { summary } = getProviderPresentation(resp.provider, resp.model);

    const textEl = document.getElementById(`response-text-${index}`);
    const typingEl = document.getElementById(`response-typing-${index}`);
    const tokensEl = document.getElementById(`response-token-usage-${index}`);
    const summaryEl = document.getElementById(`response-provider-summary-${index}`);

    if (textEl) {
        textEl.textContent = text;
        textEl.dataset.empty = "false";
        textEl.classList.remove("hidden");
        textEl.classList.toggle("error-text", hasError);
    }
    if (typingEl) typingEl.classList.add("hidden");
    if (tokensEl) {
        if (tokens === null) {
            tokensEl.textContent = "";
            tokensEl.classList.add("hidden");
        } else {
            tokensEl.textContent = `Tokens: ${tokens.toLocaleString()}`;
            tokensEl.classList.remove("hidden");
        }
    }
    if (summaryEl) summaryEl.textContent = summary;

    card.classList.remove("is-streaming");
    card.classList.toggle("is-error", hasError);
    applyPendingWebSources(index, !hasError);
    maybeAutoScrollDuringStream();
}

function renderCompareSummary(data) {
    const existing = el.resultsGrid.querySelector(".compare-summary-card");
    if (existing) existing.remove();
    el.resultsGrid.insertAdjacentHTML("beforeend", buildCompareSummary(data));
    scheduleScrollResultsToBottom({ behavior: "auto", followUpDelayMs: 64 });
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
    const card = button.closest(".chat-message-ai");
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
        button.closest(".chat-message-ai")?.querySelector(".response-text");
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
    const sourceToggle = event.target.closest(".web-source-toggle");
    if (sourceToggle && el.resultsGrid.contains(sourceToggle)) {
        const sourceStrip = sourceToggle.closest(".web-source-strip");
        if (!sourceStrip) return;
        const shouldExpand = sourceToggle.getAttribute("aria-expanded") !== "true";

        el.resultsGrid.querySelectorAll(".web-source-strip.is-expanded").forEach(openStrip => {
            if (openStrip !== sourceStrip) {
                setSourceStripExpanded(openStrip, false);
            }
        });

        setSourceStripExpanded(sourceStrip, shouldExpand);
        return;
    }

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

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   RENDER RESULTS â€” staggered card animation
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

function showResults(responses, isMulti, compareData) {
    el.resultsSection.classList.remove("hidden");
    el.resultsGrid.className = isMulti ? "results-grid compare-transcript" : "results-grid";
    el.resultsGrid.style.gridTemplateColumns = "";
    if (isMulti) {
        const promptText = String(compareData?.prompt || "");
        const compareTurn = buildCompareTurn(promptText, responses, 0);
        el.resultsGrid.innerHTML = compareTurn.html;
    } else {
        el.resultsGrid.innerHTML = responses.map((r, i) => buildResponseCard(r, i, isMulti)).join("");
    }
    if (compareData) el.resultsGrid.insertAdjacentHTML("beforeend", buildCompareSummary(compareData));

    scheduleScrollResultsToBottom({ behavior: "auto", followUpDelayMs: 96 });
}


function buildResponseCard(resp, index, showProvider = true, options = {}) {
    const compareView = Boolean(options.compareView);
    const hasError = !!resp.error;
    const text = resp.text || (hasError ? `Error: ${resp.error.message}` : "(empty response)");
    const { summary } = getProviderPresentation(resp.provider, resp.model);
    const webSources = normalizeWebSources(resp.web_source_items || []);
    const providerSummaryHtml = showProvider
        ? `<div class="message-provider">${escHtml(summary)}</div>`
        : "";
    const footerHtml = buildResponseFooter(index, summary, resp.token_usage, webSources);

    return `
    <div class="chat-message chat-message-ai${compareView ? " compare-response" : ""} ${hasError ? "is-error" : ""}"
         id="chat-msg-${index}"
         style="animation: messageIn .2s ease-out both;">
      <div class="chat-bubble chat-bubble-ai">
        ${providerSummaryHtml}
        <p class="response-text ${hasError ? "error-text" : ""}" id="response-text-${index}">${escHtml(text)}</p>
        ${footerHtml}
      </div>
    </div>`;
}

function buildCompareSummary(data) {
    const count = Array.isArray(data.responses) ? data.responses.length : 0;
    return `
    <div class="chat-message chat-message-system compare-summary-card" style="animation: messageIn .2s ease-out both;">
      <div class="chat-bubble chat-bubble-system">
        <div class="compare-summary-line">
          <span>Compared ${count} model${count === 1 ? "" : "s"}</span>
          <span>${(data.total_tokens || 0).toLocaleString()} tokens</span>
          <span>${data.success_count || 0}/${count} successful</span>
        </div>
      </div>
    </div>`;
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   CLEAR / ERROR / LOADING
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

el.clearBtn.addEventListener("click", () => { clearResults(); });

function clearResults() {
    el.resultsSection.classList.add("hidden");
    el.resultsGrid.innerHTML = "";
    pendingWebSourcesByCard.clear();
    hasReceivedFirstStreamResponse = false;
    setComposerDocked(true);
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

function resolveCompareSelections(previousValues, slotCount = 3) {
    const rawPrev = Array.isArray(previousValues) ? previousValues : [];
    const availableKeys = getSelectableModels().map(item => modelKeyOf(item.provider, item.model));
    const resolved = [];
    const used = new Set();

    for (let index = 0; index < slotCount; index += 1) {
        const preferred = String(rawPrev[index] || "");
        if (preferred && availableKeys.includes(preferred) && !used.has(preferred)) {
            resolved.push(preferred);
            used.add(preferred);
            continue;
        }
        const fallback = availableKeys.find(key => !used.has(key)) || "";
        resolved.push(fallback);
        if (fallback) {
            used.add(fallback);
        }
    }
    return resolved;
}

function refreshModelSelectors({ preserveSingle = true, preserveCompare = true } = {}) {
    const previousSingle = preserveSingle ? String(el.singleModel.value || "") : "";
    const previousCompare = preserveCompare
        ? [el.compareModel1.value, el.compareModel2.value, el.compareModel3.value]
        : ["", "", ""];

    const availableKeys = getSelectableModels().map(item => modelKeyOf(item.provider, item.model));
    const fallbackSingle = getManualDefaultModelKey();
    const desiredSingle = (previousSingle && availableKeys.includes(previousSingle))
        ? previousSingle
        : SmartRoutingState.resolveManualSelection("", fallbackSingle);

    el.singleModel.value = desiredSingle;
    buildOptions(el.singleModel, new Set());
    if (!el.singleModel.value && availableKeys.length > 0) {
        el.singleModel.value = availableKeys[0];
    }

    const desiredCompare = resolveCompareSelections(previousCompare, 3);
    el.compareModel1.value = desiredCompare[0] || "";
    el.compareModel2.value = desiredCompare[1] || "";
    el.compareModel3.value = desiredCompare[2] || "";
    syncCompareDropdowns();
}

async function fetchCatalogJson(path) {
    const resp = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers: { "X-API-Key": API_KEY },
    });
    if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json();
}

async function loadDynamicProviderModelCatalog() {
    try {
        const [providersPayload, modelsPayload] = await Promise.all([
            fetchCatalogJson("/v1/providers"),
            fetchCatalogJson("/v1/models?enabled_only=true"),
        ]);
        const providers = Array.isArray(providersPayload?.providers) ? providersPayload.providers : [];
        const models = Array.isArray(modelsPayload?.models) ? modelsPayload.models : [];
        if (!providers.length) {
            return;
        }

        applyCatalogData(providers, models);
        refreshModelSelectors({ preserveSingle: true, preserveCompare: true });
        updateSingleModelRoutingUI();
    } catch (error) {
        console.warn("Provider/model discovery unavailable, using fallback catalog.", error);
    }
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   INIT
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

(function init() {
    refreshModelSelectors({ preserveSingle: false, preserveCompare: false });
    initModelPickers();

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
    setComposerDocked(true);
    activeSessionIdByMode.single = loadActiveSessionId("single");
    activeSessionIdByMode.compare = loadActiveSessionId("compare");
    activeSessionId = normalizeSessionId(activeSessionIdByMode.single);
    setMode("single");
    updateSendButtonState();
    void loadDynamicProviderModelCatalog();
})();

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   UTILS
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   HISTORY SIDEBAR
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

const historyEl = {
    sidebar: $("historySidebar"),
    newChatBtn: $("historyNewChatBtn"),
    clearAllBtn: $("historyClearAllBtn"),
    list: $("historyList"),
    empty: $("historyEmpty"),
    search: $("historySearch"),
};
historyUiReady = true;

function normalizeHistoryModeLabel(value) {
    return String(value || "").trim().toLowerCase() === "compare" ? "compare" : "chat";
}

function getSessionEntries(data, sessionId, modeLabel = null) {
    const normalized = normalizeSessionId(sessionId);
    if (!normalized) return [];
    const requiredMode = modeLabel ? normalizeHistoryModeLabel(modeLabel) : null;
    return data.filter(entry => {
        if (normalizeSessionId(entry.session_id) !== normalized) return false;
        if (!requiredMode) return true;
        return normalizeHistoryModeLabel(entry.mode) === requiredMode;
    });
}

function sortHistoryEntries(entries) {
    return [...entries].sort((a, b) => {
        const left = parseHistoryTimestamp(a.timestamp);
        const right = parseHistoryTimestamp(b.timestamp);
        return left - right;
    });
}

function buildConversationHistoryFromEntries(entries) {
    const rebuilt = [];
    const ordered = sortHistoryEntries(entries);
    let activeCompareTurn = null;

    const flushCompareTurn = () => {
        if (!activeCompareTurn) return;
        if (activeCompareTurn.prompt && !isPromptPlaceholder(activeCompareTurn.prompt)) {
            rebuilt.push({ role: "user", content: activeCompareTurn.prompt });
        }
        const assistantContext = buildCompareAssistantContext(activeCompareTurn.responses);
        if (assistantContext) {
            rebuilt.push({ role: "assistant", content: assistantContext });
        }
        activeCompareTurn = null;
    };

    ordered.forEach(entry => {
        const mode = String(entry.mode || "").trim().toLowerCase();
        const prompt = String(entry.prompt || "").trim();
        const response = String(entry.response || "").trim();
        const validPrompt = prompt && !isPromptPlaceholder(prompt);

        if (mode === "compare") {
            if (!activeCompareTurn || (validPrompt && prompt !== activeCompareTurn.prompt)) {
                flushCompareTurn();
                activeCompareTurn = {
                    prompt: validPrompt ? prompt : "[prompt not stored]",
                    responses: [],
                };
            } else if (validPrompt && activeCompareTurn.prompt === "[prompt not stored]") {
                activeCompareTurn.prompt = prompt;
            }

            if (response) {
                activeCompareTurn.responses.push(buildHistoricalAssistantCardPayload(entry));
            }
            return;
        }

        flushCompareTurn();
        if (validPrompt) {
            rebuilt.push({ role: "user", content: prompt });
        }
        if (response && !isResponsePlaceholder(response)) {
            rebuilt.push({ role: "assistant", content: response });
        }
    });
    flushCompareTurn();

    return rebuilt.slice(-MAX_CONTEXT_MESSAGES_UI);
}

function hydrateConversationHistoryFromEntries(entries) {
    conversationHistory = buildConversationHistoryFromEntries(entries);
}

function hydrateConversationHistoryFromSession(
    sessionId,
    data = _historyData,
    modeLabel = historyModeForUiMode()
) {
    const entries = getSessionEntries(data, sessionId, modeLabel);
    hydrateConversationHistoryFromEntries(entries);
}

function buildHistoricalAssistantCardPayload(entry) {
    const response = String(entry.response || "").trim();
    const hasError = isResponsePlaceholder(response);
    const errorMessage = hasError ? response.replace(/^\[error\]\s*/i, "").trim() : "";
    const tokens = Number(entry.tokens);
    const provider = String(entry.provider || "").trim().toLowerCase();
    const model = String(entry.model || "").trim();
    const webSourceItems = normalizeWebSources(entry.web_source_items || []);

    return {
        text: hasError ? `Error: ${errorMessage || "Request failed"}` : response,
        provider,
        model,
        web_source_items: webSourceItems,
        finish_reason: hasError ? "error" : "completed",
        token_usage: { total_tokens: Number.isFinite(tokens) ? tokens : 0 },
        ...(hasError ? { error: { message: errorMessage || "Request failed" } } : {}),
    };
}

function renderConversationFromEntries(entries) {
    const ordered = sortHistoryEntries(entries);
    const htmlParts = [];
    let cardIndex = 0;
    let activeCompareTurn = null;

    const flushCompareTurn = () => {
        if (!activeCompareTurn || activeCompareTurn.responses.length === 0) {
            activeCompareTurn = null;
            return;
        }
        const builtTurn = buildCompareTurn(activeCompareTurn.prompt, activeCompareTurn.responses, cardIndex);
        if (builtTurn.html) {
            htmlParts.push(builtTurn.html);
            cardIndex = builtTurn.nextIndex;
        }
        activeCompareTurn = null;
    };

    ordered.forEach(entry => {
        const mode = String(entry.mode || "").trim().toLowerCase();
        const prompt = String(entry.prompt || "").trim();
        const response = String(entry.response || "").trim();
        const validPrompt = prompt && !isPromptPlaceholder(prompt);

        if (mode === "compare") {
            if (!activeCompareTurn || (validPrompt && prompt !== activeCompareTurn.prompt)) {
                flushCompareTurn();
                activeCompareTurn = {
                    prompt: validPrompt ? prompt : "[prompt not stored]",
                    responses: [],
                };
            } else if (validPrompt && activeCompareTurn.prompt === "[prompt not stored]") {
                activeCompareTurn.prompt = prompt;
            }

            if (response) {
                activeCompareTurn.responses.push(buildHistoricalAssistantCardPayload(entry));
            }
            return;
        }

        flushCompareTurn();

        if (validPrompt) {
            htmlParts.push(buildUserMessageBubble(prompt));
        }
        if (response) {
            htmlParts.push(buildResponseCard(buildHistoricalAssistantCardPayload(entry), cardIndex, true));
            cardIndex += 1;
        }
    });
    flushCompareTurn();

    pendingWebSourcesByCard.clear();
    if (htmlParts.length === 0) {
        clearResults();
        return false;
    }

    el.resultsSection.classList.remove("hidden");
    const hasCompareTurns = htmlParts.some(part => part.includes("compare-turn"));
    el.resultsGrid.className = hasCompareTurns ? "results-grid compare-transcript" : "results-grid";
    el.resultsGrid.style.gridTemplateColumns = "";
    el.resultsGrid.innerHTML = htmlParts.join("");
    hasReceivedFirstStreamResponse = true;
    setComposerDocked(true);
    scheduleScrollResultsToBottom({ behavior: "auto", followUpDelayMs: 80 });
    return true;
}

function renderSessionTranscript(sessionId, data = _historyData, modeLabel = historyModeForUiMode()) {
    const entries = getSessionEntries(data, sessionId, modeLabel);
    return renderConversationFromEntries(entries);
}

function setActiveSession(sessionId, { markNew = false, mode = currentMode } = {}) {
    const safeMode = normalizeUiMode(mode);
    activeSessionId = normalizeSessionId(sessionId) || normalizeSessionId(createSessionId());
    setActiveSessionIdForMode(safeMode, activeSessionId);
    pendingNewSession = Boolean(markNew);
    const sessionEntries = getSessionEntries(
        _historyData,
        activeSessionId,
        historyModeForUiMode(safeMode)
    );
    hydrateConversationHistoryFromEntries(sessionEntries);
    renderConversationFromEntries(sessionEntries);
    renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
}

historyEl.newChatBtn.addEventListener("click", () => {
    startNewChatSession();
    renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
    el.promptInput.focus();
});

historyEl.clearAllBtn.addEventListener("click", async () => {
    if (!confirm("Delete all history?")) return;
    await fetch(`${API_BASE}/v1/history`, {
        method: "DELETE",
        headers: { "X-API-Key": API_KEY },
    });
    conversationHistory = [];
    pendingNewSession = true;
    activeSessionId = null;
    activeSessionIdByMode.single = null;
    activeSessionIdByMode.compare = null;
    persistActiveSessionId("single");
    persistActiveSessionId("compare");
    loadHistory({ restoreActiveTranscript: true });
});

historyEl.search.addEventListener("input", () => {
    renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
});

loadHistory({ restoreActiveTranscript: true });

async function loadHistory({ restoreActiveTranscript = false } = {}) {
    try {
        const resp = await fetch(`${API_BASE}/v1/history?limit=500`, {
            headers: { "X-API-Key": API_KEY },
        });
        if (!resp.ok) return;
        _historyData = await resp.json();

        const safeMode = normalizeUiMode(currentMode);
        const modeLabel = historyModeForUiMode(safeMode);
        if (!activeSessionIdByMode[safeMode]) {
            activeSessionIdByMode[safeMode] = loadActiveSessionId(safeMode);
        }
        activeSessionId = normalizeSessionId(activeSessionIdByMode[safeMode]);

        if (!activeSessionId) {
            const mostRecentWithSession = _historyData.find(entry =>
                normalizeSessionId(entry.session_id) &&
                normalizeHistoryModeLabel(entry.mode) === modeLabel
            );
            if (mostRecentWithSession) {
                activeSessionId = normalizeSessionId(mostRecentWithSession.session_id);
                setActiveSessionIdForMode(safeMode, activeSessionId);
            }
        }

        if (activeSessionId) {
            hydrateConversationHistoryFromSession(activeSessionId, _historyData, modeLabel);
            if (restoreActiveTranscript) {
                renderSessionTranscript(activeSessionId, _historyData, modeLabel);
            }
        } else if (restoreActiveTranscript) {
            conversationHistory = [];
            clearResults();
        }

        renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
    } catch (_) { /* silent */ }
}

function parseHistoryTimestamp(value) {
    const ts = Date.parse(value || "");
    return Number.isFinite(ts) ? ts : 0;
}

function isPromptPlaceholder(prompt) {
    const text = String(prompt || "").trim().toLowerCase();
    return text.startsWith("[prompt hash:") || text.startsWith("[prompt not stored]");
}

function isResponsePlaceholder(response) {
    return String(response || "").trim().toLowerCase().startsWith("[error]");
}

function pickFirstPrompt(entries) {
    const preferred = entries.find(entry => {
        const prompt = String(entry.prompt || "").trim();
        return prompt && !isPromptPlaceholder(prompt);
    });
    if (preferred) return String(preferred.prompt || "").trim();
    const fallback = entries.find(entry => String(entry.prompt || "").trim());
    return fallback ? String(fallback.prompt || "").trim() : "";
}

function pickLatestResponse(entries) {
    const reversed = [...entries].reverse();
    const preferred = reversed.find(entry => {
        const response = String(entry.response || "").trim();
        return response && !isResponsePlaceholder(response);
    });
    if (preferred) return String(preferred.response || "").trim();
    const fallback = reversed.find(entry => String(entry.response || "").trim());
    return fallback ? String(fallback.response || "").trim() : "";
}

function formatHistoryUsd(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return null;
    const safe = Math.max(0, amount);
    const precision = safe >= 1 ? 2 : 4;
    return `$${safe.toLocaleString(undefined, {
        minimumFractionDigits: precision,
        maximumFractionDigits: precision,
    })}`;
}

function buildHistoryThreads(data) {
    const grouped = new Map();
    data.forEach(entry => {
        const sessionId = normalizeSessionId(entry.session_id);
        const modeLabel = normalizeHistoryModeLabel(entry.mode);
        const key = sessionId ? `session:${modeLabel}:${sessionId}` : `entry:${modeLabel}:${entry.id}`;
        if (!grouped.has(key)) {
            grouped.set(key, { key, sessionId, modeLabel, entries: [] });
        }
        grouped.get(key).entries.push(entry);
    });

    const threads = [];
    grouped.forEach(thread => {
        const entries = [...thread.entries].sort((a, b) => {
            return parseHistoryTimestamp(a.timestamp) - parseHistoryTimestamp(b.timestamp);
        });
        const latestEntry = entries[entries.length - 1] || {};
        const latestTimestampMs = parseHistoryTimestamp(latestEntry.timestamp);
        const firstPrompt = pickFirstPrompt(entries);
        const latestResponse = pickLatestResponse(entries);
        const modeLabel = thread.modeLabel || normalizeHistoryModeLabel(latestEntry.mode);
        const providerSet = new Set(entries.map(entry => String(entry.provider || "").trim().toLowerCase()).filter(Boolean));
        const provider = providerSet.size > 1 ? "mixed" : String(latestEntry.provider || "");
        const modelSet = new Set(entries.map(entry => String(entry.model || "").trim()).filter(Boolean));
        const model = modelSet.size > 1 ? "mixed" : String(latestEntry.model || "");
        const totalTokens = entries.reduce((sum, entry) => {
            const n = Number(entry.tokens);
            return Number.isFinite(n) ? sum + n : sum;
        }, 0);
        const totalCost = entries.reduce((sum, entry) => {
            const n = Number(entry.cost);
            return Number.isFinite(n) ? sum + n : sum;
        }, 0);
        const hasCost = entries.some(entry => Number.isFinite(Number(entry.cost)));
        const searchBlob = entries
            .map(entry => [entry.prompt, entry.response, entry.provider, entry.model].join(" ").toLowerCase())
            .join(" ");

        threads.push({
            key: thread.key,
            sessionId: thread.sessionId,
            entries,
            latestEntry,
            latestTimestampMs,
            firstPrompt,
            latestResponse,
            modeLabel,
            provider,
            model,
            totalTokens,
            totalCost,
            hasCost,
            searchBlob,
        });
    });

    return threads.sort((a, b) => b.latestTimestampMs - a.latestTimestampMs);
}

function renderHistory(data, filter = "") {
    const needle = String(filter || "").trim().toLowerCase();
    const threads = buildHistoryThreads(data);
    const filteredThreads = needle
        ? threads.filter(thread => thread.searchBlob.includes(needle))
        : threads;

    if (filteredThreads.length === 0) {
        historyEl.list.innerHTML = "";
        historyEl.empty.style.display = "flex";
        return;
    }
    historyEl.empty.style.display = "none";

    historyEl.list.innerHTML = filteredThreads.map(thread => {
        const rawPrompt = thread.firstPrompt || "[prompt not stored]";
        const promptSnippet = escHtml(rawPrompt.length > 80
            ? rawPrompt.slice(0, 80) + "..."
            : rawPrompt);
        const tokStr = thread.totalTokens ? thread.totalTokens.toLocaleString() : "-";
        const totalCostLabel = thread.hasCost ? formatHistoryUsd(thread.totalCost) : null;
        const isActive = thread.modeLabel === historyModeForUiMode(currentMode)
            && thread.sessionId
            && thread.sessionId === activeSessionId;
        const activeClass = isActive ? " is-active-session" : "";

        return `<li class="history-entry${activeClass}" data-thread-key="${escHtml(thread.key)}" data-session-id="${escHtml(thread.sessionId || "")}">
          <div class="history-entry-top">
            <span class="history-mode-badge history-mode-${thread.modeLabel}">${thread.modeLabel === "compare" ? "Compare" : "Chat"}</span>
          </div>
          <div class="history-prompt">${promptSnippet}</div>
          <div class="history-meta">
            <span class="history-meta-left">
              <span class="history-token-text">Tokens: ${tokStr}</span>
              ${totalCostLabel ? `<span class="history-cost-text">Est. cost: ${escHtml(totalCostLabel)}</span>` : ""}
            </span>
            <button class="history-delete-btn" data-thread-key="${escHtml(thread.key)}" title="Delete chat thread" aria-label="Delete thread">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.7">
                <path d="M4 7H20"></path>
                <path d="M9 7V5.6C9 4.72 9.72 4 10.6 4H13.4C14.28 4 15 4.72 15 5.6V7"></path>
                <rect x="6.5" y="7" width="11" height="13" rx="2"></rect>
                <path d="M10 11V17"></path>
                <path d="M14 11V17"></path>
              </svg>
              <span class="sr-only">Delete thread</span>
            </button>
          </div>
        </li>`;
    }).join("");

    const threadByKey = new Map(filteredThreads.map(thread => [thread.key, thread]));

    historyEl.list.querySelectorAll(".history-delete-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const thread = threadByKey.get(btn.dataset.threadKey || "");
            if (!thread || !thread.entries.length) return;

            for (const entry of thread.entries) {
                await fetch(`${API_BASE}/v1/history/${entry.id}`, {
                    method: "DELETE",
                    headers: { "X-API-Key": API_KEY },
                });
            }

            if (thread.sessionId && thread.sessionId === activeSessionId) {
                startNewChatSession();
            }
            await loadHistory();
        });
    });

    historyEl.list.querySelectorAll(".history-entry").forEach(item => {
        item.addEventListener("click", (e) => {
            if (e.target.classList.contains("history-delete-btn")) return;
            const thread = threadByKey.get(item.dataset.threadKey || "");
            if (!thread) return;

            const targetMode = thread.modeLabel === "compare" ? "compare" : "single";
            if (currentMode !== targetMode) {
                setMode(targetMode);
            }

            const clickedSessionId = normalizeSessionId(thread.sessionId);
            if (clickedSessionId) {
                setActiveSession(clickedSessionId, { markNew: false, mode: targetMode });
            } else {
                activeSessionId = normalizeSessionId(createSessionId());
                setActiveSessionIdForMode(targetMode, activeSessionId);
                pendingNewSession = true;
                hydrateConversationHistoryFromEntries(thread.entries);
                renderConversationFromEntries(thread.entries);
                renderHistory(_historyData, historyEl.search.value.trim().toLowerCase());
            }

            el.promptInput.value = "";
            el.promptInput.focus();
            updateSendButtonState();
            if (!el.resultsSection.classList.contains("hidden")) {
                scheduleScrollResultsToBottom({ behavior: "smooth", followUpDelayMs: 96 });
            } else {
                document.getElementById("workspace").scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    });
}

