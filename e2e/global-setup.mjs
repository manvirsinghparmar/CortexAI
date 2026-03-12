/**
 * Global setup for the live CortexAI E2E suite.
 *
 * Responsibilities:
 * - start the E2E-only FastAPI server bootstrap
 * - wait for API, DB, and browser readiness
 * - persist the shared run state used by fixtures and teardown
 */
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

import { chromium } from "@playwright/test";

import { getWhoAmI, getProviderCatalog, waitForJson } from "./helpers/api.mjs";
import { getE2EConfig } from "./helpers/config.mjs";
import { createDbPool, verifyDbConnection } from "./helpers/db.mjs";
import { createRunId } from "./helpers/ids.mjs";
import { ensureRuntimeDir, writeCaseRegistry, writeRunState } from "./helpers/runtime-state.mjs";
import { openApp } from "./helpers/ui.mjs";

/** Wait for the E2E server bootstrap to expose a healthy HTTP endpoint. */
async function waitForHealth(config) {
    return waitForJson(`${config.apiBaseUrl}/health`, {
        timeoutMs: config.timeouts.serverStartMs,
        intervalMs: 750,
    });
}

/**
 * Prefer the repo virtualenv when present so Playwright starts the same Python
 * environment developers use locally.
 */
function resolvePythonExecutable(config) {
    const explicit = String(process.env.E2E_PYTHON_EXECUTABLE || "").trim();
    if (explicit) {
        return explicit;
    }

    const candidates = os.platform() === "win32"
        ? [
            path.join(config.repoRoot, "venv", "Scripts", "python.exe"),
            path.join(config.repoRoot, ".venv", "Scripts", "python.exe"),
            "python",
        ]
        : [
            path.join(config.repoRoot, "venv", "bin", "python"),
            path.join(config.repoRoot, ".venv", "bin", "python"),
            "python3",
            "python",
        ];

    for (const candidate of candidates) {
        if (!candidate.includes(path.sep) || fs.existsSync(candidate)) {
            return candidate;
        }
    }
    return "python";
}

/** Spawn the dedicated E2E server bootstrap and pipe logs into the runtime folder. */
async function spawnServer(config, runId) {
    await ensureRuntimeDir(config);

    const stdoutPath = path.join(config.runtimeDir, "server.stdout.log");
    const stderrPath = path.join(config.runtimeDir, "server.stderr.log");
    const stdout = fs.openSync(stdoutPath, "a");
    const stderr = fs.openSync(stderrPath, "a");
    const pythonExecutable = resolvePythonExecutable(config);

    return spawn(
        pythonExecutable,
        ["e2e/server/run_e2e_server.py"],
        {
            cwd: config.repoRoot,
            env: {
                ...process.env,
                E2E_LIVE_ENABLED: "true",
                E2E_RUN_ID: runId,
            },
            stdio: ["ignore", stdout, stderr],
            windowsHide: true,
        },
    );
}

/** Normalize provider labels once so specs can compare UI text to persisted provider ids. */
function providerLabelMap(payload) {
    const rows = Array.isArray(payload?.providers) ? payload.providers : [];
    return Object.fromEntries(rows.map(row => [
        String(row.provider || "").trim().toLowerCase(),
        String(row?.ui?.display_name || row.label || row.provider || "").trim(),
    ]));
}

export default async function globalSetup() {
    const config = getE2EConfig();
    const runId = createRunId();
    const bootstrapSessionId = crypto.randomUUID();
    let server = null;
    let pool = null;
    let browser = null;

    await writeCaseRegistry(config, []);
    await writeRunState(config, {
        runId,
        baseUrl: config.baseUrl,
        apiBaseUrl: config.apiBaseUrl,
        ownerId: null,
        providerLabels: {},
        serverPid: null,
        startedAt: new Date().toISOString(),
    });

    try {
        server = await spawnServer(config, runId);
        await writeRunState(config, {
            runId,
            baseUrl: config.baseUrl,
            apiBaseUrl: config.apiBaseUrl,
            ownerId: null,
            providerLabels: {},
            serverPid: server.pid,
            startedAt: new Date().toISOString(),
        });

        await waitForHealth(config);
        await waitForJson(`${config.apiBaseUrl}/v1/providers`, {
            headers: { "X-API-Key": config.apiKey },
            timeoutMs: config.timeouts.discoveryMs,
            intervalMs: 500,
        });

        const [whoami, providers] = await Promise.all([
            getWhoAmI(config),
            getProviderCatalog(config),
        ]);

        if (!whoami?.user_id) {
            throw new Error("E2E bootstrap reached /v1/whoami, but user_id was null. DB mode is not active for the E2E server.");
        }

        pool = createDbPool(config);
        await verifyDbConnection(pool);

        // Open the real UI once during setup so per-test fixtures only deal with scenario logic.
        browser = await chromium.launch();
        const page = await browser.newPage();
        await page.addInitScript(({ apiBaseUrl, apiKey, activeSessionId }) => {
            window.localStorage.setItem("cortex_api_base", apiBaseUrl);
            window.localStorage.setItem("cortex_api_key", apiKey);
            window.localStorage.setItem("cortex_active_session_id", activeSessionId);
            window.localStorage.removeItem("cortex_active_session_id_single");
            window.localStorage.removeItem("cortex_active_session_id_compare");
        }, {
            apiBaseUrl: config.apiBaseUrl,
            apiKey: config.apiKey,
            activeSessionId: bootstrapSessionId,
        });
        await openApp(page, config);
        await browser.close();
        browser = null;

        await writeRunState(config, {
            runId,
            baseUrl: config.baseUrl,
            apiBaseUrl: config.apiBaseUrl,
            ownerId: whoami.user_id || null,
            providerLabels: providerLabelMap(providers),
            serverPid: server.pid,
            startedAt: new Date().toISOString(),
        });
    } catch (error) {
        if (browser) {
            await browser.close().catch(() => {});
        }
        if (pool) {
            await pool.end().catch(() => {});
        }
        if (server?.pid) {
            try {
                process.kill(server.pid);
                await delay(1_000);
            } catch (_) {
                // Best-effort cleanup only.
            }
        }
        throw error;
    } finally {
        if (pool) {
            await pool.end().catch(() => {});
        }
    }
}