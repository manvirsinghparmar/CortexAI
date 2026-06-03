import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

class FakeClassList {
    constructor() {
        this._set = new Set();
    }

    add(...names) {
        names.forEach(name => this._set.add(String(name)));
    }

    remove(...names) {
        names.forEach(name => this._set.delete(String(name)));
    }

    contains(name) {
        return this._set.has(String(name));
    }

    toggle(name, force) {
        const key = String(name);
        if (typeof force === "boolean") {
            if (force) this._set.add(key);
            else this._set.delete(key);
            return force;
        }
        if (this._set.has(key)) {
            this._set.delete(key);
            return false;
        }
        this._set.add(key);
        return true;
    }
}

class FakeElement {
    constructor(id = "", tagName = "div") {
        this.id = id;
        this.tagName = String(tagName || "div").toUpperCase();
        this.dataset = {};
        this.style = {};
        this.value = "";
        this.textContent = "";
        this.disabled = false;
        this._innerHTML = "";
        this._children = [];
        this._attrs = {};
        this._listeners = {};
        this.classList = new FakeClassList();
        this.scrollTop = 0;
        this.scrollHeight = 0;
        this.offsetHeight = 120;
        this._closest = null;
    }

    get innerHTML() {
        return this._innerHTML;
    }

    set innerHTML(value) {
        this._innerHTML = String(value ?? "");
        if (this.tagName === "SELECT") {
            this._children = [];
            this.value = "";
        }
    }

    get options() {
        return this._children;
    }

    appendChild(child) {
        const node = child || new FakeElement("", "div");
        node._parent = this;
        this._children.push(node);
        if (this.tagName === "SELECT") {
            const isSelected = Boolean(node.selected);
            if (isSelected || !this.value) {
                this.value = String(node.value || "");
            }
        }
        return node;
    }

    addEventListener(type, fn) {
        const key = String(type || "");
        if (!this._listeners[key]) {
            this._listeners[key] = [];
        }
        this._listeners[key].push(fn);
    }

    dispatchEvent(type, event = {}) {
        const handlers = this._listeners[String(type || "")] || [];
        handlers.forEach(fn => fn(event));
    }

    setAttribute(name, value) {
        this._attrs[String(name)] = String(value);
    }

    getAttribute(name) {
        return this._attrs[String(name)];
    }

    hasAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this._attrs, String(name));
    }

    closest() {
        return this._closest;
    }

    querySelectorAll() {
        return [];
    }

    focus() {}
    blur() {}
    scrollIntoView() {}
}

function createRuntime({ providersPayload, modelsPayload, requireDevSessionForCatalog = false }) {
    const elementIds = [
        "mainHeader",
        "btnSingleMode",
        "btnCompareMode",
        "workspaceTagline",
        "singleRoutingControls",
        "singleModelWrap",
        "singleModelLabel",
        "singleModel",
        "compareModelWrap",
        "compareModel3Wrap",
        "compareAddModelBtn",
        "compareModel1",
        "compareModel2",
        "compareModel3",
        "compareRemoveModel1",
        "compareRemoveModel2",
        "compareRemoveModel3",
        "promptCard",
        "promptInput",
        "submitBtn",
        "routeOptimizeBtn",
        "routeSmartBtn",
        "routeResearchBtn",
        "resultsSection",
        "resultsGrid",
        "clearBtn",
        "errorBanner",
        "errorMsg",
        "errorClose",
        "optViewBtn",
        "optPanel",
        "optPanelClose",
        "optOriginalText",
        "optOptimizedText",
        "historySidebar",
        "historyNewChatBtn",
        "historyClearAllBtn",
        "historyList",
        "historyEmpty",
        "historySearch",
        "workspace",
    ];

    const elements = new Map();
    elementIds.forEach(id => {
        const lowerId = id.toLowerCase();
        const tagName = lowerId.endsWith("btn") || lowerId.startsWith("compareremovemodel")
            ? "button"
            : lowerId.includes("model") && !id.includes("Wrap") && !id.includes("Slot")
                ? "select"
                : id === "promptInput"
                    ? "textarea"
                    : "div";
        elements.set(id, new FakeElement(id, tagName));
    });

    const smartChipWrap = new FakeElement("routeSmartChipWrap", "span");
    elements.get("routeSmartBtn")._closest = smartChipWrap;
    elements.get("compareRemoveModel1").setAttribute("data-compare-slot", "0");
    elements.get("compareRemoveModel2").setAttribute("data-compare-slot", "1");
    elements.get("compareRemoveModel3").setAttribute("data-compare-slot", "2");

    const document = {
        getElementById(id) {
            return elements.get(String(id)) || null;
        },
        createElement(tag) {
            return new FakeElement("", tag);
        },
        querySelectorAll() {
            return [];
        },
    };

    const storage = new Map();
    const localStorage = {
        getItem(key) {
            return storage.has(key) ? storage.get(key) : null;
        },
        setItem(key, value) {
            storage.set(key, String(value));
        },
        removeItem(key) {
            storage.delete(key);
        },
    };

    const fetchCalls = [];
    let devSessionReady = false;
    async function fetch(url) {
        const text = String(url || "");
        fetchCalls.push(text);
        if (text.includes("/v1/auth/cognito-config")) {
            return {
                ok: true,
                status: 200,
                async json() {
                    return {};
                },
            };
        }
        if (text.includes("/v1/auth/me")) {
            if (devSessionReady) {
                return {
                    ok: true,
                    status: 200,
                    async json() {
                        return { authenticated: true };
                    },
                };
            }
            return {
                ok: false,
                status: 401,
                async json() {
                    return { detail: "Not authenticated" };
                },
            };
        }
        if (text.includes("/v1/auth/dev-login")) {
            devSessionReady = true;
            return {
                ok: true,
                status: 200,
                async json() {
                    return { ok: true };
                },
            };
        }
        if (text.includes("/v1/providers")) {
            if (requireDevSessionForCatalog && !devSessionReady) {
                return {
                    ok: false,
                    status: 403,
                    async json() {
                        return { detail: "session_auth_required" };
                    },
                };
            }
            return {
                ok: true,
                status: 200,
                async json() {
                    return providersPayload;
                },
            };
        }
        if (text.includes("/v1/models?enabled_only=true")) {
            if (requireDevSessionForCatalog && !devSessionReady) {
                return {
                    ok: false,
                    status: 403,
                    async json() {
                        return { detail: "session_auth_required" };
                    },
                };
            }
            return {
                ok: true,
                status: 200,
                async json() {
                    return modelsPayload;
                },
            };
        }
        if (text.includes("/v1/history")) {
            return {
                ok: true,
                status: 200,
                async json() {
                    return [];
                },
            };
        }
        return {
            ok: true,
            status: 200,
            async json() {
                return {};
            },
            async text() {
                return "";
            },
        };
    }

    const window = {
        scrollY: 0,
        addEventListener() {},
        removeEventListener() {},
        setTimeout,
        clearTimeout,
        localStorage,
        crypto: {
            randomUUID: () => "11111111-1111-4111-8111-111111111111",
        },
    };

    const context = {
        window,
        document,
        fetch,
        confirm: () => true,
        console,
        setTimeout,
        clearTimeout,
        requestAnimationFrame: fn => {
            if (typeof fn === "function") fn();
            return 1;
        },
        cancelAnimationFrame: () => {},
        URL,
        URLSearchParams,
        Promise,
        Math,
        Date,
        JSON,
    };
    context.globalThis = context;

    return { context, elements, fetchCalls };
}

function optionValues(selectEl) {
    return (selectEl?.options || []).map(option => String(option.value || ""));
}

function optionTexts(selectEl) {
    return (selectEl?.options || []).map(option => String(option.textContent || ""));
}

function optionByValue(selectEl, value) {
    return (selectEl?.options || []).find(
        option => String(option.value || "") === String(value || ""),
    ) || null;
}

function isOptionDisabled(selectEl, value) {
    return (selectEl?.options || []).some(
        option => String(option.value || "") === String(value || "") && Boolean(option.disabled),
    );
}

async function createCompareRemovalRuntime() {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
            { provider: "zai", label: "Z.AI", default_model: "zai-chat", ui: { display_name: "Z.AI" } },
            { provider: "claude", label: "Claude", default_model: "claude-sonnet-4-5", ui: { display_name: "Claude" } },
        ],
        total: 4,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "gemini", model: "gemini-2.5-flash", enabled: true },
            { provider: "zai", model: "zai-chat", enabled: true },
            { provider: "claude", model: "claude-sonnet-4-5", enabled: true },
        ],
        total: 4,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const runtime = createRuntime({ providersPayload, modelsPayload });
    vm.createContext(runtime.context);
    vm.runInContext(source, runtime.context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    runtime.elements.get("btnCompareMode").dispatchEvent("click");
    runtime.elements.get("compareAddModelBtn").dispatchEvent("click");
    return runtime;
}

function activeCompareValues(context) {
    return Array.from(context.getActiveCompareSelects(), selectEl => String(selectEl.value || ""));
}

test("dynamic discovery updates frontend selectors with new provider/models", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            {
                provider: "openai",
                label: "OpenAI",
                default_model: "gpt-4o",
                ui: { display_name: "ChatGPT", icon_token: "target", color: "#10A37F", sort_order: 2 },
            },
            {
                provider: "zai",
                label: "Z.AI",
                default_model: "zai-chat",
                ui: { display_name: "Z.AI", icon_token: "star", color: "#2563EB", sort_order: 5 },
            },
        ],
        total: 2,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "zai", model: "zai-chat", enabled: true },
        ],
        total: 2,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context, elements, fetchCalls } = createRuntime({
        providersPayload,
        modelsPayload,
    });

    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    assert.ok(fetchCalls.some(url => url.includes("/v1/providers")));
    assert.ok(fetchCalls.some(url => url.includes("/v1/models?enabled_only=true")));
    assert.ok(fetchCalls.some(url => url.includes("/v1/auth/dev-login")));

    const singleModel = elements.get("singleModel");
    const values = optionValues(singleModel);
    const texts = optionTexts(singleModel);
    const zaiOption = optionByValue(singleModel, "zai:zai-chat");

    assert.ok(values.includes("zai:zai-chat"));
    assert.ok(texts.some(text => text.includes("Z.AI Chat")));
    assert.equal(zaiOption?.textContent, "Z.AI Chat");
    assert.equal(zaiOption?.getAttribute("aria-label"), "Z.AI Chat (zai-chat)");
    assert.equal(zaiOption?.getAttribute("title"), "Z.AI Chat\nzai-chat");
});

test("catalog discovery waits for local dev session before loading compare models", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
        ],
        total: 2,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "openai", model: "gpt-5.4", enabled: true },
            { provider: "gemini", model: "gemini-2.5-pro", enabled: true },
        ],
        total: 3,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context, elements, fetchCalls } = createRuntime({
        providersPayload,
        modelsPayload,
        requireDevSessionForCatalog: true,
    });

    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    const devLoginIndex = fetchCalls.findIndex(url => url.includes("/v1/auth/dev-login"));
    const providersIndex = fetchCalls.findIndex(url => url.includes("/v1/providers"));
    const modelsIndex = fetchCalls.findIndex(url => url.includes("/v1/models?enabled_only=true"));
    const historyIndex = fetchCalls.findIndex(url => url.includes("/v1/history"));
    assert.ok(devLoginIndex >= 0);
    assert.ok(providersIndex > devLoginIndex);
    assert.ok(modelsIndex > devLoginIndex);
    assert.ok(historyIndex > devLoginIndex);

    const compareValues = optionValues(elements.get("compareModel1"));
    assert.ok(compareValues.includes("openai:gpt-4o"));
    assert.ok(compareValues.includes("openai:gpt-5.4"));
    assert.ok(compareValues.includes("gemini:gemini-2.5-pro"));
});

test("compare selectors enforce unique model choices with disabled taken options", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
            { provider: "zai", label: "Z.AI", default_model: "zai-chat", ui: { display_name: "Z.AI" } },
        ],
        total: 3,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "gemini", model: "gemini-2.5-flash", enabled: true },
            { provider: "zai", model: "zai-chat", enabled: true },
        ],
        total: 3,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context, elements } = createRuntime({ providersPayload, modelsPayload });

    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    const btnCompareMode = elements.get("btnCompareMode");
    const compareModel1 = elements.get("compareModel1");
    const compareModel2 = elements.get("compareModel2");
    const compareModel3 = elements.get("compareModel3");
    const compareAddModelBtn = elements.get("compareAddModelBtn");

    btnCompareMode.dispatchEvent("click");

    const slot1Value = String(compareModel1.value || "");
    assert.ok(slot1Value.length > 0);
    assert.equal(isOptionDisabled(compareModel2, slot1Value), true);

    compareModel1.value = "zai:zai-chat";
    compareModel1.dispatchEvent("change");
    assert.equal(isOptionDisabled(compareModel2, "zai:zai-chat"), true);
    assert.equal(isOptionDisabled(compareModel2, slot1Value), false);

    compareAddModelBtn.dispatchEvent("click");
    assert.ok(String(compareModel3.value || "").length > 0);

    const selected = [compareModel1.value, compareModel2.value, compareModel3.value].map(value => String(value || ""));
    assert.equal(new Set(selected).size, selected.length);
});

test("user can remove the first compare model slot", async () => {
    const { context, elements } = await createCompareRemovalRuntime();
    const before = activeCompareValues(context);
    assert.equal(before.length, 3);
    assert.equal(elements.get("compareRemoveModel1").classList.contains("hidden"), false);
    assert.equal(elements.get("compareRemoveModel2").classList.contains("hidden"), false);
    assert.equal(elements.get("compareRemoveModel3").classList.contains("hidden"), false);

    elements.get("compareRemoveModel1").dispatchEvent("click");

    assert.deepEqual(activeCompareValues(context), [before[1], before[2]]);
    assert.equal(elements.get("compareModel3Wrap").classList.contains("hidden"), true);
    assert.equal(elements.get("compareRemoveModel1").classList.contains("hidden"), true);
    assert.equal(elements.get("compareRemoveModel2").classList.contains("hidden"), true);
});

test("user can remove the second compare model slot", async () => {
    const { context, elements } = await createCompareRemovalRuntime();
    const before = activeCompareValues(context);
    assert.equal(before.length, 3);

    elements.get("compareRemoveModel2").dispatchEvent("click");

    assert.deepEqual(activeCompareValues(context), [before[0], before[2]]);
    assert.equal(elements.get("compareModel3Wrap").classList.contains("hidden"), true);
});

test("user can remove the third compare model slot", async () => {
    const { context, elements } = await createCompareRemovalRuntime();
    const before = activeCompareValues(context);
    assert.equal(before.length, 3);

    elements.get("compareRemoveModel3").dispatchEvent("click");

    assert.deepEqual(activeCompareValues(context), [before[0], before[1]]);
    assert.equal(elements.get("compareModel3Wrap").classList.contains("hidden"), true);
});

test("compare model removal cannot go below two active models", async () => {
    const { context, elements } = await createCompareRemovalRuntime();

    elements.get("compareRemoveModel3").dispatchEvent("click");
    const twoModelState = activeCompareValues(context);
    assert.equal(twoModelState.length, 2);
    assert.equal(elements.get("compareRemoveModel1").classList.contains("hidden"), true);
    assert.equal(elements.get("compareRemoveModel2").classList.contains("hidden"), true);

    elements.get("compareRemoveModel1").dispatchEvent("click");
    elements.get("compareRemoveModel2").dispatchEvent("click");

    assert.deepEqual(activeCompareValues(context), twoModelState);
});

test("compare request target construction excludes removed model slots", async () => {
    const { context, elements } = await createCompareRemovalRuntime();
    const before = activeCompareValues(context);
    assert.equal(before.length, 3);

    elements.get("compareRemoveModel2").dispatchEvent("click");

    const targets = Array.from(context.getActiveCompareSelects(), selectEl => context.parseKey(selectEl.value));
    assert.deepEqual(
        targets.map(target => `${target.provider}:${target.model}`),
        [before[0], before[2]],
    );
});

test("compare mode defaults sources on and preserves a manual off choice", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
        ],
        total: 2,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "gemini", model: "gemini-2.5-flash", enabled: true },
        ],
        total: 2,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const runtime = createRuntime({ providersPayload, modelsPayload });
    vm.createContext(runtime.context);
    vm.runInContext(source, runtime.context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    const btnSingleMode = runtime.elements.get("btnSingleMode");
    const btnCompareMode = runtime.elements.get("btnCompareMode");
    const routeResearchBtn = runtime.elements.get("routeResearchBtn");

    btnCompareMode.dispatchEvent("click");
    assert.equal(routeResearchBtn.getAttribute("aria-checked"), "true");
    assert.equal(routeResearchBtn.classList.contains("active"), true);
    assert.equal(runtime.context.getRoutingPayload().research_mode, true);

    routeResearchBtn.dispatchEvent("click");
    assert.equal(routeResearchBtn.getAttribute("aria-checked"), "false");
    assert.equal(routeResearchBtn.classList.contains("active"), false);
    assert.equal(runtime.context.getRoutingPayload().research_mode, false);

    btnSingleMode.dispatchEvent("click");
    assert.equal(routeResearchBtn.getAttribute("aria-checked"), "true");

    btnCompareMode.dispatchEvent("click");
    assert.equal(routeResearchBtn.getAttribute("aria-checked"), "false");
    assert.equal(runtime.context.getRoutingPayload().research_mode, false);
});

test("user attachment file cards preserve uploaded file metadata", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
        ],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [{ provider: "openai", model: "gpt-4o", enabled: true }],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context } = createRuntime({ providersPayload, modelsPayload });
    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    assert.equal(typeof context.normalizeUserTurnAttachmentItems, "function");
    assert.equal(typeof context.buildUserAttachmentCards, "function");

    const normalized = context.normalizeUserTurnAttachmentItems([{
        type: "file",
        payload: {
            file_id: "file_123",
            file_name: "quarterly-plan.pdf",
            file_size: 15360,
            file_type: "application/pdf",
            status: "ready",
        },
    }]);

    assert.equal(normalized[0]?.payload?.file_name, "quarterly-plan.pdf");
    assert.equal(normalized[0]?.payload?.file_type, "application/pdf");
    assert.equal(normalized[0]?.payload?.status, "ready");

    const cardHtml = context.buildUserAttachmentCards(normalized);
    assert.match(cardHtml, /quarterly-plan\.pdf/);
    assert.match(cardHtml, /Ready for analysis/);
    assert.match(cardHtml, /15\.0 KB/);
    assert.match(cardHtml, /PDF/);
    assert.match(cardHtml, /class="user-file-thumb"/);
    assert.doesNotMatch(cardHtml, /user-file-status-dot/);
    assert.doesNotMatch(cardHtml, />file-1</);

    const imageCardHtml = context.buildUserAttachmentCards([{
        file_id: "file_456",
        file_name: "scene.png",
        file_size: 4096,
        file_type: "image/png",
        status: "ready",
        preview_url: "blob:http://localhost/scene",
    }]);
    assert.match(imageCardHtml, /class="user-file-thumb-img"/);
    assert.match(imageCardHtml, /blob:http:\/\/localhost\/scene/);
});

test("upload errors are mapped to safe user-facing messages", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
        ],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [{ provider: "openai", model: "gpt-4o", enabled: true }],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context } = createRuntime({ providersPayload, modelsPayload });
    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    assert.equal(typeof context.sanitizeUploadError, "function");
    assert.equal(typeof context.getUserFriendlyUploadError, "function");
    assert.equal(typeof context.getUploadErrorMessage, "function");
    assert.equal(typeof context.getSafeAttachmentItemErrorMessage, "function");

    assert.equal(
        context.getUploadErrorMessage({
            uiErrorKind: "connection",
            message: "Failed to fetch object from s3://internal-bucket/private-key",
        }),
        "Upload failed due to a network issue. Please check your internet connection and try again.",
    );
    assert.equal(
        context.getUploadErrorMessage({
            status: 413,
            detail: "File exceeds ATTACHMENTS_MAX_FILE_BYTES (20971520).",
        }),
        "Upload failed. This file may be too large. Try a smaller file.",
    );
    assert.equal(
        context.getUploadErrorMessage({
            status: 415,
            detail: "Unsupported MIME type 'application/x-msdownload'.",
        }),
        "Upload failed. This file type is not supported. Make sure the file type is supported and try again.",
    );
    assert.equal(
        context.getUploadErrorMessage({
            uiErrorKind: "timeout",
            detail: "request timed out after 60000ms",
        }),
        "Upload failed because the request timed out. Please try again.",
    );

    const fallback = context.getUploadErrorMessage({
        detail: "storage upload failed for bucket internal-prod-uploads and key users/13/file.pdf",
    });
    assert.equal(
        fallback,
        "Upload failed. Please try again.",
    );
    assert.equal(fallback.includes("internal-prod-uploads"), false);

    const displaySafe = context.getSafeAttachmentItemErrorMessage({
        status: "error",
        error_message: "storage upload failed for bucket internal-prod-uploads and key users/13/file.pdf",
    });
    assert.equal(
        displaySafe,
        "Upload failed. Please try again.",
    );
    assert.equal(displaySafe.includes("internal-prod-uploads"), false);
});

test("provider response errors are mapped to safe user-facing messages", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
        ],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [{ provider: "gemini", model: "gemini-2.5-flash", enabled: true }],
        total: 1,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const { context } = createRuntime({ providersPayload, modelsPayload });
    vm.createContext(context);
    vm.runInContext(source, context, { filename: "frontend/app.js" });

    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));

    assert.equal(typeof context.getSafeResponseErrorMessage, "function");
    assert.equal(typeof context.getResponseErrorDisplayText, "function");

    const rawProviderMessage = (
        "Provider error: 503 UNAVAILABLE. {'error': {'message': " +
        "'This model is currently experiencing high demand. Please try again later.'}}"
    );
    const safeMessage = context.getSafeResponseErrorMessage({
        code: "provider_error",
        message: rawProviderMessage,
    });
    assert.equal(
        safeMessage,
        "This model is temporarily busy. Try again shortly or switch to another model.",
    );
    assert.equal(safeMessage.includes("UNAVAILABLE"), false);
    assert.equal(safeMessage.includes("high demand"), false);

    assert.equal(
        context.getSafeResponseErrorMessage({
            code: "provider_error",
            message: "anything",
            details: { kind: "transient_capacity" },
        }),
        "This model is temporarily busy. Try again shortly or switch to another model.",
    );
    assert.equal(
        context.getResponseErrorDisplayText({
            code: "provider_error",
            message: "anything",
            details: { kind: "transient_capacity" },
        }),
        "This model is temporarily busy. Try again shortly or switch to another model.",
    );
});
