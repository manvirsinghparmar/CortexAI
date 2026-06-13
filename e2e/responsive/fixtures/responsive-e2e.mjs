import { expect, test as base } from "@playwright/test";

const LONG_RESPONSE = Array.from(
    { length: 35 },
    (_, index) =>
        `Paragraph ${index + 1}: detailed comparison content that must remain readable inside the responsive response layout.`,
).join("\n\n");

const MODELS = [
    model("openai", "gpt-5.1", true),
    model("claude", "claude-sonnet-4-5", true),
    model("deepseek", "deepseek-chat", false),
    model("gemini", "gemini-2.5-flash", true),
    model("grok", "grok-4", true),
];

export const test = base.extend({
    responsiveApp: async ({ page }, use) => {
        const state = {
            history: responsiveHistoryEntries(),
            uploadedFiles: new Map(),
        };
        const pageErrors = [];
        page.on("pageerror", error => pageErrors.push(error));

        await installResponsiveRoutes(page, state);
        await page.goto("/");
        await expect(page.locator("#promptInput")).toBeVisible();

        await use({
            page,
            state,
            async reload() {
                await page.reload();
                await expect(page.locator("#promptInput")).toBeVisible();
            },
        });

        expect(pageErrors, "uncaught browser errors").toEqual([]);
    },
});

export { expect };

export async function openMobilePanel(page, name) {
    await page
        .getByRole("navigation", { name: "Mobile navigation" })
        .getByRole("button", { name })
        .click();
}

export async function restoreHistoryThread(page, title) {
    const desktopHistory = page.locator("aside[aria-label='Primary navigation']");
    if (await desktopHistory.isVisible()) {
        await page.getByRole("button", { name: new RegExp(title, "i") }).first().click();
    } else {
        await openMobilePanel(page, "History");
        await page.getByRole("button", { name: new RegExp(title, "i") }).first().click();
    }
    await expect(page.locator('section[aria-label="Chat transcript"]')).toBeVisible();
}

export async function expectNoHorizontalOverflow(page) {
    const metrics = await page.evaluate(() => ({
        viewportWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        bodyWidth: document.body.scrollWidth,
    }));
    expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth);
    expect(metrics.bodyWidth).toBeLessThanOrEqual(metrics.viewportWidth);
}

async function installResponsiveRoutes(page, state) {
    await page.route("**/runtime-config.js", route =>
        route.fulfill({
            status: 200,
            contentType: "application/javascript",
            body: "window.CORTEX_RUNTIME_CONFIG = { enableDevSessionLogin: false };",
        }),
    );

    await page.route("**/v1/**", async route => {
        const request = route.request();
        const url = new URL(request.url());
        const method = request.method();

        if (url.pathname === "/v1/auth/cognito-config") {
            return json(route, { enabled: false });
        }
        if (url.pathname === "/v1/whoami") {
            return json(route, whoAmI());
        }
        if (url.pathname === "/v1/models") {
            return json(route, {
                enabled_only: true,
                models: MODELS,
                total: MODELS.length,
                timestamp: "2026-06-12T12:00:00Z",
            });
        }
        if (url.pathname === "/v1/history" && method === "GET") {
            const sessionId = url.searchParams.get("session_id");
            return json(
                route,
                sessionId
                    ? state.history.filter(entry => entry.session_id === sessionId)
                    : state.history,
            );
        }
        if (url.pathname === "/v1/history" && method === "DELETE") {
            state.history = [];
            return route.fulfill({ status: 204, body: "" });
        }
        if (url.pathname === "/v1/files/upload" && method === "POST") {
            const fileName = request.headers()["x-file-name"] || "attachment.txt";
            const uploaded = {
                file_id: `file-${state.uploadedFiles.size + 1}`,
                original_filename: fileName,
                mime_type: request.headers()["x-file-content-type"] || "text/plain",
                size_bytes: request.postDataBuffer()?.byteLength ?? 0,
                status: "ready",
                ingestion_meta: {},
                created_at: "2026-06-12T12:00:00Z",
                deduplicated: false,
            };
            state.uploadedFiles.set(uploaded.file_id, uploaded);
            return json(route, uploaded);
        }
        if (url.pathname.startsWith("/v1/files/") && method === "GET") {
            const fileId = url.pathname.split("/").at(-1);
            const uploaded = state.uploadedFiles.get(fileId);
            return uploaded
                ? json(route, uploaded)
                : json(route, { detail: "File not found" }, 404);
        }

        return json(route, { detail: `Unhandled responsive test route: ${method} ${url.pathname}` }, 404);
    });
}

function responsiveHistoryEntries() {
    return [
        historyEntry({
            id: 1,
            sessionId: "ask-session",
            timestamp: "2026-06-12T09:00:00Z",
            prompt: "Help debug a FastAPI stream",
            response: "Check disconnect handling, response iteration, and request correlation.",
            provider: "openai",
            modelName: "gpt-5.1",
        }),
        historyEntry({
            id: 2,
            sessionId: "ask-session",
            timestamp: "2026-06-12T09:05:00Z",
            prompt: "Add a retry strategy",
            response: "Retry only transient failures and preserve the request identifier.",
            provider: "openai",
            modelName: "gpt-5.1",
        }),
        ...compareHistoryEntries(),
    ];
}

function compareHistoryEntries() {
    const entries = [];
    let id = 10;
    for (let turn = 1; turn <= 3; turn += 1) {
        const prompt =
            turn === 1
                ? "Architecture decision for an LLM gateway"
                : `Architecture follow-up ${turn}`;
        for (const [provider, modelName] of [
            ["openai", "gpt-5.1"],
            ["claude", "claude-sonnet-4-5"],
        ]) {
            entries.push(
                historyEntry({
                    id,
                    sessionId: "compare-session",
                    requestGroupId: `compare-group-${turn}`,
                    timestamp: `2026-06-12T10:0${turn}:${provider === "openai" ? "00" : "01"}Z`,
                    mode: "compare",
                    prompt,
                    response: LONG_RESPONSE,
                    provider,
                    modelName,
                    tokens: 1800 + id,
                }),
            );
            id += 1;
        }
    }
    return entries;
}

function historyEntry({
    id,
    sessionId,
    requestGroupId,
    timestamp,
    mode = "single",
    prompt,
    response,
    provider,
    modelName,
    tokens = 320,
}) {
    return {
        id,
        session_id: sessionId,
        request_group_id: requestGroupId,
        timestamp,
        mode,
        prompt,
        provider,
        model: modelName,
        response,
        latency_ms: 900,
        tokens,
        cost: 0.001,
        web_source_items: [],
    };
}

function model(provider, modelName, supportsImageInput) {
    return {
        provider,
        model: modelName,
        tier: "frontier",
        input_cost_per_1m: 0,
        output_cost_per_1m: 0,
        context_limit: 128000,
        tags: [],
        enabled: true,
        supports_image_input: supportsImageInput,
        supported_attachment_mime_types: [],
    };
}

function whoAmI() {
    return {
        api_key_id: "responsive-test-key",
        user_id: "responsive-test-user",
        plan_tier: "test",
        storage_policy: "full",
        redact_pii: false,
        baseline: {
            provider: "openai",
            model: "gpt-5.1",
            source: "test",
        },
        rate_limits: {
            requests_per_minute: 60,
            daily_cap_scope: "user",
        },
        breakers: {
            failure_threshold: 5,
            window_seconds: 60,
            cooldown_seconds: 120,
            scope: "provider_model",
        },
    };
}

function json(route, body, status = 200) {
    return route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
    });
}
