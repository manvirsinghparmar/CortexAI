/**
 * Global teardown for the live CortexAI E2E suite.
 *
 * The teardown pass replays case-aware cleanup before it shuts down the shared
 * server process so failed runs do not leave noisy rows behind in the dev DB.
 */
import { execFileSync } from "node:child_process";
import os from "node:os";

import { cleanupCase, cleanupRun } from "./helpers/cleanup.mjs";
import { getE2EConfig } from "./helpers/config.mjs";
import { createDbPool } from "./helpers/db.mjs";
import { readCaseRegistry, readRunState } from "./helpers/runtime-state.mjs";

/** Use platform-appropriate process termination so the uvicorn tree shuts down cleanly. */
async function stopServer(pid) {
    if (!pid) return;
    if (os.platform() === "win32") {
        execFileSync("taskkill", ["/pid", String(pid), "/t", "/f"], { stdio: "ignore" });
        return;
    }
    process.kill(pid, "SIGTERM");
}

export default async function globalTeardown() {
    const config = getE2EConfig();
    let state = null;
    try {
        state = await readRunState(config);
    } catch (_) {
        return;
    }

    const pool = createDbPool(config);
    try {
        if (state.ownerId) {
            const recordedCases = await readCaseRegistry(config);
            for (const entry of recordedCases) {
                await cleanupCase({
                    config,
                    pool,
                    ownerId: state.ownerId,
                    caseId: entry.caseId,
                    sessionId: entry.seededSessionId || null,
                }).catch(() => {});
            }
        }

        if (state.ownerId && state.runId) {
            await cleanupRun({
                config,
                pool,
                ownerId: state.ownerId,
                runId: state.runId,
            });
        }
    } finally {
        await pool.end().catch(() => {});
    }

    try {
        await stopServer(state.serverPid);
    } catch (_) {
        // Best effort shutdown only.
    }
}