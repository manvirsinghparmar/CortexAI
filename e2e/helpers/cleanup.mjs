/** Shared cleanup helpers for case-level and run-level E2E isolation. */
import { deleteHistoryEntry, listHistory } from "./api.mjs";
import { cleanupCaseViaDb, cleanupRunViaDb } from "./db.mjs";

function caseMarker(caseId) {
    return `case:${caseId}]`;
}

function runMarker(runId) {
    return `[e2e-run:${runId};`;
}

/**
 * Remove data created by one test attempt.
 *
 * We prefer product-level cleanup first, then fall back to direct DB cleanup for
 * telemetry rows or sessions the product history API does not fully remove.
 */
export async function cleanupCase({ config, pool, ownerId, caseId, sessionId = null }) {
    const entryIds = new Set();

    try {
        const historyEntries = await listHistory(config, { limit: 500 });
        const marker = caseMarker(caseId);
        for (const entry of historyEntries) {
            if (String(entry.prompt || "").includes(marker) && entry?.id != null) {
                entryIds.add(entry.id);
            }
        }

        for (const entryId of entryIds) {
            await deleteHistoryEntry(config, entryId);
        }
    } catch (_) {
        // DB cleanup below is the backstop for shared-DB isolation.
    }

    await cleanupCaseViaDb(pool, config, ownerId, caseId, sessionId);
}

/** Remove any leftovers from the entire suite run after all specs finish. */
export async function cleanupRun({ config, pool, ownerId, runId }) {
    try {
        const historyEntries = await listHistory(config, { limit: 500 });
        const marker = runMarker(runId);
        for (const entry of historyEntries) {
            if (String(entry.prompt || "").includes(marker)) {
                await deleteHistoryEntry(config, entry.id);
            }
        }
    } catch (_) {
        // Best effort only.
    }
    await cleanupRunViaDb(pool, config, ownerId, runId);
}