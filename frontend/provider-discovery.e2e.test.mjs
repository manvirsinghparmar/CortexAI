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

function createRuntime({ providersPayload, modelsPayload }) {
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
        const tagName = id.toLowerCase().includes("model") && !id.includes("Wrap")
            ? "select"
            : id === "promptInput"
                ? "textarea"
                : "div";
        elements.set(id, new FakeElement(id, tagName));
    });

    const smartChipWrap = new FakeElement("routeSmartChipWrap", "span");
    elements.get("routeSmartBtn")._closest = smartChipWrap;

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
    async function fetch(url) {
        const text = String(url || "");
        fetchCalls.push(text);
        if (text.includes("/v1/providers")) {
            return {
                ok: true,
                status: 200,
                async json() {
                    return providersPayload;
                },
            };
        }
        if (text.includes("/v1/models?enabled_only=true")) {
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
        location: {
            hash: "",
            pathname: "/",
            search: "",
            href: "http://localhost/",
        },
        history: {
            replaceState() {},
        },
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

test("third compare slot defaults to Claude Haiku when available", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "claude", label: "Claude", default_model: "claude-sonnet-4-6", ui: { display_name: "Claude" } },
        ],
        total: 3,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "gemini", model: "gemini-2.5-flash", enabled: true },
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "claude", model: "claude-haiku-4-5", enabled: true },
            { provider: "claude", model: "claude-sonnet-4-6", enabled: true },
            { provider: "claude", model: "claude-opus-4-5", enabled: true },
            { provider: "claude", model: "claude-opus-4-6", enabled: true },
        ],
        total: 6,
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
    compareAddModelBtn.dispatchEvent("click");

    assert.equal(String(compareModel3.value || ""), "claude:claude-haiku-4-5");

    const selected = [compareModel1.value, compareModel2.value, compareModel3.value].map(value => String(value || ""));
    assert.equal(new Set(selected).size, selected.length);
});

test("third compare slot still defaults to Claude Haiku when catalog omits explicit haiku rows", async () => {
    const appJsPath = path.join(process.cwd(), "frontend", "app.js");
    const source = fs.readFileSync(appJsPath, "utf8");

    const providersPayload = {
        providers: [
            { provider: "gemini", label: "Gemini", default_model: "gemini-2.5-flash", ui: { display_name: "Gemini" } },
            { provider: "openai", label: "OpenAI", default_model: "gpt-4o", ui: { display_name: "ChatGPT" } },
            { provider: "claude", label: "Claude", default_model: "claude-sonnet-4-6", ui: { display_name: "Claude" } },
        ],
        total: 3,
        timestamp: "2026-03-01T00:00:00Z",
    };

    const modelsPayload = {
        provider: null,
        enabled_only: true,
        models: [
            { provider: "gemini", model: "gemini-2.5-flash", enabled: true },
            { provider: "openai", model: "gpt-4o", enabled: true },
            { provider: "claude", model: "claude-sonnet-4-6", enabled: true },
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
    const compareModel3 = elements.get("compareModel3");
    const compareAddModelBtn = elements.get("compareAddModelBtn");

    btnCompareMode.dispatchEvent("click");
    compareAddModelBtn.dispatchEvent("click");

    assert.equal(String(compareModel3.value || ""), "claude:claude-haiku-4-5");
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
