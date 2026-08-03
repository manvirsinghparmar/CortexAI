import { expect, test as base } from "@playwright/test";

const LONG_RESPONSE = Array.from(
    { length: 35 },
    (_, index) =>
        `Paragraph ${index + 1}: detailed comparison content that must remain readable inside the responsive response layout.`,
).join("\n\n");

const TABLE_RESPONSE = [
    "## Deployment comparison",
    "",
    "| Option | Delivery speed | Operational risk | Recommendation |",
    "| :--- | :---: | :---: | ---: |",
    "| Managed service | Fast | Low | Preferred |",
    "| Self-hosted | Moderate | Medium | Use for strict control |",
    "| Custom platform | Slow | High | Defer |",
].join("\n");

const MODELS = [
    model("openai", "gpt-5.1", true, "standard"),
    model("claude", "claude-sonnet-4-5", true, "advanced"),
    model("deepseek", "deepseek-chat", false, "economical"),
    model("gemini", "gemini-2.5-flash", true, "standard"),
    model("grok", "grok-4", true, "premium"),
];

export const test = base.extend({
    responsiveApp: async ({ page }, use) => {
        const state = {
            history: responsiveHistoryEntries(),
            analysisRuns: responsiveAnalysisRuns(),
            uploadedFiles: new Map(),
            models: [...MODELS],
            subscriptionPlan: "free",
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
                models: state.models,
                total: state.models.length,
                timestamp: "2026-06-12T12:00:00Z",
            });
        }
        if (url.pathname === "/v1/billing/plans" && method === "GET") {
            return json(route, {
                currency: "USD",
                billing_period: "monthly",
                billing_enabled: true,
                plans: [],
            });
        }
        if (url.pathname === "/v1/billing/subscription" && method === "GET") {
            const paid = state.subscriptionPlan !== "free";
            return json(route, {
                plan_code: state.subscriptionPlan,
                status: paid ? "active" : "free",
                provider: paid ? "stripe" : null,
                current_period_start: "2026-07-01T00:00:00Z",
                current_period_end: "2026-08-01T00:00:00Z",
                cancel_at_period_end: false,
                can_manage: paid,
            });
        }
        if (url.pathname === "/v1/entitlements" && method === "GET") {
            return json(route, entitlements(state.subscriptionPlan));
        }
        if (url.pathname === "/v1/credits/transactions" && method === "GET") {
            return json(route, creditTransactions());
        }
        if (url.pathname === "/v1/usage/summary" && method === "GET") {
            return json(route, usageSummary());
        }
        if (url.pathname === "/v1/usage/export" && method === "GET") {
            return route.fulfill({
                status: 200,
                contentType: "text/csv",
                headers: {
                    "Content-Disposition": "attachment; filename=usage_report.csv",
                },
                body: "date,requests,tokens,cost\n2026-07-01,42,189540,1.72\n",
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
            state.analysisRuns = [];
            return route.fulfill({ status: 204, body: "" });
        }
        if (url.pathname === "/v1/compare/analysis-runs" && method === "GET") {
            const sessionId = url.searchParams.get("session_id");
            const requestGroupId = url.searchParams.get("request_group_id");
            return json(
                route,
                state.analysisRuns.filter(run =>
                    (!sessionId || run.sessionId === sessionId) &&
                    (!requestGroupId || run.requestGroupId === requestGroupId),
                ),
            );
        }
        const analysisMatch = url.pathname.match(/^\/v1\/compare\/([^/]+)\/analysis$/);
        if (analysisMatch && method === "POST") {
            const requestGroupId = decodeURIComponent(analysisMatch[1]);
            const sourceRows = state.history.filter(
                entry => entry.request_group_id === requestGroupId && !entry.error_message,
            );
            if (sourceRows.length < 2) {
                return json(route, { detail: "Not enough successful responses" }, 409);
            }
            const run = makeResponsiveAnalysisRun({
                analysisId: `analysis-${state.analysisRuns.length + 1}`,
                requestGroupId,
                sessionId: sourceRows[0].session_id,
                createdAt: new Date().toISOString(),
                sourceRows,
            });
            state.analysisRuns = [run, ...state.analysisRuns];
            return json(route, run, 201);
        }
        if (url.pathname === "/v1/files/upload-batch" && method === "POST") {
            const requestBody = request.postDataBuffer();
            const multipartText = requestBody?.toString("latin1") ?? "";
            const fileNames = [...multipartText.matchAll(/filename="([^"]+)"/g)].map(
                match => match[1],
            );
            const uploadedFiles = fileNames.map((fileName, index) => {
                const uploaded = {
                    file_id: `file-${state.uploadedFiles.size + index + 1}`,
                    original_filename: fileName,
                    mime_type: "text/plain",
                    size_bytes: requestBody?.byteLength ?? 0,
                    status: "ready",
                    ingestion_meta: {},
                    created_at: "2026-06-12T12:00:00Z",
                    deduplicated: false,
                };
                state.uploadedFiles.set(uploaded.file_id, uploaded);
                return uploaded;
            });
            return json(route, { files: uploadedFiles });
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
        historyEntry({
            id: 3,
            sessionId: "dense-history-session",
            timestamp: "2026-06-12T09:30:00Z",
            prompt: "Plan a multi-region platform migration with strict recovery objectives",
            response: "Use phased regional cutovers with tested rollback and recovery procedures.",
            provider: "openai",
            modelName: "gpt-5.4-mini-enterprise-preview-with-extended-context",
        }),
        ...compareHistoryEntries(),
        ...compareTableHistoryEntries(),
        ...threeModelCompareHistoryEntries(),
    ];
}

function responsiveAnalysisRuns() {
    const history = responsiveHistoryEntries();
    const sourceRows = history.filter(
        entry => entry.request_group_id === "compare-group-1",
    );
    return [
        makeResponsiveAnalysisRun({
            analysisId: "analysis-saved-1",
            requestGroupId: "compare-group-1",
            sessionId: "compare-session",
            createdAt: "2026-06-12T10:02:00Z",
            sourceRows,
        }),
    ];
}

function makeResponsiveAnalysisRun({
    analysisId,
    requestGroupId,
    sessionId,
    createdAt,
    sourceRows,
}) {
    return {
        analysisId,
        requestGroupId,
        sessionId,
        model: "gpt-5.4-mini",
        recommendedAnswer:
            "Use a phased gateway rollout with explicit provider fallbacks and observable recovery checks.",
        agreements: [
            "Both responses favor incremental rollout over a one-time cutover.",
        ],
        disagreements: [
            "The responses assign different priorities to cost and operational control.",
        ],
        uniqueInsights: [
            {
                responseName: "ChatGPT",
                text: "One response highlights request correlation as a rollout prerequisite.",
            },
        ],
        confidence: {
            level: "moderate",
            reason: "The responses align on the main rollout shape but differ on priorities.",
        },
        verify: ["Confirm the recovery objectives for each rollout phase."],
        highStakesDomain: null,
        sourceFingerprint: `responsive-${analysisId}`,
        sourceResponses: sourceRows.map(entry => ({
            requestId: entry.request_id,
            responseVersion: entry.response_version,
            responseName: entry.provider === "openai" ? "ChatGPT" : "Claude",
        })),
        combinedResponseCount: sourceRows.length,
        failedResponseCount: 0,
        createdAt,
        isStale: false,
    };
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

function compareTableHistoryEntries() {
    return [
        historyEntry({
            id: 30,
            sessionId: "compare-table-session",
            requestGroupId: "compare-table-group",
            timestamp: "2026-06-12T11:00:00Z",
            mode: "compare",
            prompt: "Compare deployment options table",
            response: TABLE_RESPONSE,
            provider: "openai",
            modelName: "gpt-5.1",
            tokens: 640,
        }),
        historyEntry({
            id: 31,
            sessionId: "compare-table-session",
            requestGroupId: "compare-table-group",
            timestamp: "2026-06-12T11:00:01Z",
            mode: "compare",
            prompt: "Compare deployment options table",
            response: TABLE_RESPONSE,
            provider: "claude",
            modelName: "claude-sonnet-4-5",
            tokens: 670,
        }),
    ];
}

function threeModelCompareHistoryEntries() {
    return [
        ["openai", "gpt-5.1"],
        ["claude", "claude-sonnet-4-5"],
        ["deepseek", "deepseek-chat"],
    ].map(([provider, modelName], index) =>
        historyEntry({
            id: 40 + index,
            sessionId: "compare-three-model-session",
            requestGroupId: "compare-three-model-group",
            timestamp: `2026-06-12T11:30:0${index}Z`,
            mode: "compare",
            prompt: "Three model platform comparison",
            response: LONG_RESPONSE,
            provider,
            modelName,
            tokens: 900 + index * 100,
        }),
    );
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
        request_id: String(id),
        response_version: 1,
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

function model(provider, modelName, supportsImageInput, billingClass) {
    return {
        provider,
        model: modelName,
        tier: "frontier",
        billing_class: billingClass,
        access_category: billingClass,
        input_credit_multiplier: 1,
        output_credit_multiplier: 4,
        credit_usage_label: "Standard",
        credit_pricing_version: "responsive-test",
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

function entitlements(planCode = "free") {
    const plan = {
        free: {
            displayName: "Free",
            allowedBillingClasses: ["economical", "standard"],
            maxCompareModels: 2,
            allowance: 100000,
        },
        plus: {
            displayName: "Plus",
            allowedBillingClasses: ["economical", "standard", "advanced"],
            maxCompareModels: 2,
            allowance: 1000000,
        },
        pro: {
            displayName: "Pro",
            allowedBillingClasses: ["economical", "standard", "advanced", "premium"],
            maxCompareModels: 3,
            allowance: 3000000,
        },
    }[planCode] ?? {
        displayName: "Free",
        allowedBillingClasses: ["economical", "standard"],
        maxCompareModels: 2,
        allowance: 100000,
    };
    return {
        plan: {
            code: planCode,
            display_name: plan.displayName,
            status: planCode === "free" ? "free" : "active",
            source: planCode === "free" ? "default" : "stripe",
            renews_at: "2026-08-01T00:00:00Z",
            cancel_at_period_end: false,
            grace_until: null,
        },
        features: {
            compare_enabled: true,
            max_compare_models: plan.maxCompareModels,
            research_enabled: true,
            prompt_improvement_enabled: true,
            file_analysis_enabled: true,
            usage_export_enabled: false,
            saved_history_enabled: true,
            models_catalog_enabled: true,
        },
        model_access: {
            allowed_billing_classes: plan.allowedBillingClasses,
        },
        limits: {
            max_files_per_request: 1,
            max_file_bytes: 10000000,
        },
        allowances: {
            ai_credits: {
                used: 10000,
                reserved: 0,
                limit: plan.allowance,
                remaining: plan.allowance - 10000,
            },
        },
        period: {
            starts_at: "2026-07-01T00:00:00Z",
            ends_at: "2026-08-01T00:00:00Z",
        },
    };
}

function creditTransactions() {
    return {
        items: [
            {
                id: "credit-1",
                request_id: "request-1",
                activity_id: "activity-1",
                query: "How do atomic credit reservations work?",
                operation_type: "chat",
                item_type: "model",
                provider: "openai",
                model: "gpt-5.4-mini",
                input_tokens: 600,
                output_tokens: 200,
                input_credits: 1200,
                output_credits: 800,
                fixed_credits: 0,
                total_credits: 2000,
                provider_cost_usd: 0.002,
                usage_estimated: false,
                pricing_version: "2026-07-29",
                metadata: {},
                created_at: "2026-07-31T14:30:00Z",
            },
            {
                id: "credit-2",
                request_id: "request-1",
                activity_id: "activity-1",
                query: "How do atomic credit reservations work?",
                operation_type: "chat",
                item_type: "research",
                provider: "tavily",
                model: null,
                input_tokens: 0,
                output_tokens: 0,
                input_credits: 0,
                output_credits: 0,
                fixed_credits: 10000,
                total_credits: 10000,
                provider_cost_usd: 0.002,
                usage_estimated: false,
                pricing_version: "2026-07-29",
                metadata: {
                    provider_credits_used: 2,
                    cortex_credits_per_provider_credit: 5000,
                },
                created_at: "2026-07-31T14:30:00Z",
            },
            {
                id: "credit-3",
                request_id: "request-1",
                activity_id: "activity-1",
                query: "How do atomic credit reservations work?",
                operation_type: "chat",
                item_type: "adjustment",
                provider: null,
                model: null,
                input_tokens: 0,
                output_tokens: 0,
                input_credits: 0,
                output_credits: 0,
                fixed_credits: 0,
                total_credits: 0,
                provider_cost_usd: 0,
                usage_estimated: false,
                pricing_version: "2026-07-29",
                metadata: { unbilled_credits: 200 },
                created_at: "2026-07-31T14:30:00Z",
            },
            {
                id: "credit-4",
                request_id: "optimizer-request-1",
                activity_id: "activity-1",
                query: "How do atomic credit reservations work?",
                operation_type: "optimize",
                item_type: "model",
                provider: "openai",
                model: "gpt-5.4-mini",
                input_tokens: 150,
                output_tokens: 100,
                input_credits: 300,
                output_credits: 700,
                fixed_credits: 0,
                total_credits: 1000,
                provider_cost_usd: 0.001,
                usage_estimated: false,
                pricing_version: "2026-07-29",
                metadata: {},
                created_at: "2026-07-31T14:29:58Z",
            },
        ],
        limit: 20,
        offset: 0,
    };
}

function usageSummary() {
    return {
        period: {
            from: "2026-06-02",
            to: "2026-07-01",
            label: "Last 30 days",
        },
        totalTokens: 2840000,
        totalRequests: 1336,
        totalSessions: 312,
        avgLatencyMs: 4600,
        p95LatencyMs: 8100,
        minLatencyMs: 1400,
        avgCostPerRequest: 0.0091,
        totalSpend: 12.16,
        tokensDeltaPct: 18.4,
        smartRoutedTotal: 720,
        models: [
            usageModel("openai", "gpt-5.4-mini", "GPT-5.4 Mini", 512, 470),
            usageModel("anthropic", "claude-sonnet-4-5", "Claude Sonnet 4.5", 318, 88),
            usageModel("deepseek", "deepseek-chat", "DeepSeek Chat", 246, 60),
            usageModel("openai", "gpt-5.1", "GPT-5.1", 142, 64),
            usageModel("google", "gemini-2.5-flash", "Gemini 2.5", 66, 38),
            usageModel("meta", "llama-3.3-70b", "Llama 3.3 70B", 34, 0),
            usageModel("mistral", "mistral-large", "Mistral Large", 18, 0),
        ],
        sessionModes: {
            askOnly: 168,
            compareOnly: 96,
            mixed: 48,
        },
        switchedMidSession: 48,
        activityDaily: [
            activityDay("2026-06-18", 148000),
            activityDay("2026-06-19", 176000),
            activityDay("2026-06-20", 121000),
            activityDay("2026-06-21", 96000),
            activityDay("2026-06-22", 189000),
            activityDay("2026-06-23", 213000),
            activityDay("2026-06-24", 198000),
            activityDay("2026-06-25", 234000),
            activityDay("2026-06-26", 268000),
            activityDay("2026-06-27", 241000),
            activityDay("2026-06-28", 172000),
            activityDay("2026-06-29", 286000),
            activityDay("2026-06-30", 304000),
            activityDay("2026-07-01", 321000),
        ],
    };
}

function usageModel(provider, modelId, displayName, replies, viaSmart) {
    return {
        provider,
        modelId,
        displayName,
        replies,
        viaSmart,
    };
}

function activityDay(date, tokens) {
    return { date, tokens };
}

function json(route, body, status = 200) {
    return route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
    });
}
