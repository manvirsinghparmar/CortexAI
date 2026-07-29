/**
 * Shared Playwright fixtures for the live CortexAI E2E suite.
 *
 * The `liveApp` fixture owns one case lifecycle: browser setup, request-id
 * recording, prompt tagging, cleanup, and optional artifact persistence.
 */
import fs from "node:fs/promises";

import { expect, test as base } from "@playwright/test";

import { cleanupCase } from "../helpers/cleanup.mjs";
import { getE2EConfig } from "../helpers/config.mjs";
import { createDbPool } from "../helpers/db.mjs";
import { appendCaseMarker, createCaseId, createSeededSessionId } from "../helpers/ids.mjs";
import { createNetworkRecorder } from "../helpers/network.mjs";
import { readRunState, recordCaseRuntime } from "../helpers/runtime-state.mjs";
import { openApp, startNewChat } from "../helpers/ui.mjs";

/** Keep detailed request logs only for failures and the specs that debug persistence paths. */
function shouldPersistNetworkLog(testInfo) {
    if (testInfo.status !== testInfo.expectedStatus) return true;
    return /persistence|fallback/i.test(testInfo.title);
}

export const test = base.extend({
    config: [async ({}, use) => {
        await use(getE2EConfig());
    }, { scope: "worker" }],

    runState: [async ({ config }, use) => {
        await use(await readRunState(config));
    }, { scope: "worker" }],

    dbPool: [async ({ config }, use) => {
        const pool = createDbPool(config);
        try {
            await use(pool);
        } finally {
            await pool.end();
        }
    }, { scope: "worker" }],

    liveApp: async ({ page, config, runState, dbPool }, use, testInfo) => {
        const caseId = createCaseId(runState.runId, testInfo);
        let seededSessionId = createSeededSessionId();
        const network = createNetworkRecorder({
            apiBaseUrl: config.apiBaseUrl,
            runId: runState.runId,
            caseId,
        });
        await network.attach(page.context());

        await page.addInitScript(({ apiBaseUrl, apiKey, activeSessionId }) => {
            window.localStorage.setItem("cortex_api_base", apiBaseUrl);
            window.localStorage.setItem("cortex_api_key", apiKey);
            // Preserve the runtime-selected active session across reloads.
            if (!window.localStorage.getItem("cortex_active_session_id")) {
                window.localStorage.setItem("cortex_active_session_id", activeSessionId);
            }
            window.localStorage.removeItem("cortex_active_session_id_single");
            window.localStorage.removeItem("cortex_active_session_id_compare");
        }, {
            apiBaseUrl: config.apiBaseUrl,
            apiKey: config.apiKey,
            activeSessionId: seededSessionId,
        });

        if (!runState.ownerId) {
            throw new Error("E2E run state is missing ownerId. Check global setup readiness.");
        }

        await cleanupCase({
            config,
            pool: dbPool,
            ownerId: runState.ownerId,
            caseId,
        });

        await openApp(page, config);
        // Force a fresh frontend thread so live tests do not inherit whatever thread history restored.
        await startNewChat(page);
        seededSessionId = await page.evaluate(() => window.localStorage.getItem("cortex_active_session_id") || "");
        await recordCaseRuntime(config, {
            caseId,
            seededSessionId,
            title: testInfo.title,
            startedAt: new Date().toISOString(),
        });

        const liveApp = {
            page,
            config,
            runState,
            dbPool,
            network,
            ownerId: runState.ownerId,
            caseId,
            seededSessionId,
            backendSessionId: null,
            /** Remember the canonical backend session id once persistence has confirmed it. */
            rememberBackendSessionId(sessionId) {
                const normalized = String(sessionId || "").trim();
                if (!normalized) return this.backendSessionId;
                this.backendSessionId = normalized;
                return this.backendSessionId;
            },
            /** Attach the case marker expected by DB lookups and cleanup helpers. */
            withPromptMarker(prompt) {
                return appendCaseMarker(prompt, runState.runId, caseId);
            },
        };

        try {
            await use(liveApp);
        } finally {
            if (shouldPersistNetworkLog(testInfo)) {
                const networkPath = testInfo.outputPath("network-log.json");
                await fs.writeFile(networkPath, `${JSON.stringify({
                    runId: runState.runId,
                    caseId,
                    seededSessionId,
                    backendSessionId: liveApp.backendSessionId,
                    entries: network.entries,
                }, null, 2)}\n`, "utf8");
            }
            await cleanupCase({
                config,
                pool: dbPool,
                ownerId: runState.ownerId,
                caseId,
                sessionId: liveApp.backendSessionId || seededSessionId || null,
            });
        }
    },
});

export { expect };
