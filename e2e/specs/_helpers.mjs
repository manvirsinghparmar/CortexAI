/** Shared polling and assertion helpers used by the browser specs. */
import { expect } from "../fixtures/live-e2e.mjs";
import { getCaseSnapshot } from "../helpers/db.mjs";

/** Poll an async loader until a predicate passes or the timeout budget is exhausted. */
export async function pollUntil(load, predicate, {
    timeoutMs = 30_000,
    intervalMs = 500,
    message = "Timed out waiting for condition.",
} = {}) {
    const deadline = Date.now() + timeoutMs;
    let lastValue = null;
    while (Date.now() < deadline) {
        lastValue = await load();
        if (await predicate(lastValue)) {
            return lastValue;
        }
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
    throw new Error(message);
}

/**
 * Read the persisted DB snapshot for the current case and remember the canonical
 * backend session id once the first request has been written.
 */
export async function waitForSnapshot(liveApp, {
    sessionId = null,
    minRequests = 1,
    timeoutMs = liveApp.config.timeouts.askMs,
    predicate = null,
} = {}) {
    const snapshot = await pollUntil(
        () => getCaseSnapshot(liveApp.dbPool, liveApp.config, liveApp.ownerId, liveApp.caseId, sessionId),
        current => {
            if (typeof predicate === "function") {
                return predicate(current);
            }
            return current.requests.length >= minRequests;
        },
        {
            timeoutMs,
            intervalMs: 750,
            message: `Timed out waiting for snapshot data for case ${liveApp.caseId}.`,
        },
    );

    const canonicalSessionId = latestRequest(snapshot)?.session_id || snapshot.requests[0]?.session_id || null;
    if (canonicalSessionId && typeof liveApp.rememberBackendSessionId === "function") {
        liveApp.rememberBackendSessionId(canonicalSessionId);
    }
    return snapshot;
}

export function latestRequest(snapshot, predicate = null) {
    const filtered = typeof predicate === "function"
        ? snapshot.requests.filter(predicate)
        : snapshot.requests;
    return filtered[filtered.length - 1] || null;
}

export function providerLabelFor(runState, provider) {
    const normalized = String(provider || "").trim().toLowerCase();
    return runState.providerLabels[normalized] || normalized;
}

/** Match the UI provider summary against the provider/model captured in persistence. */
export function expectSummaryMatchesRequest(summaryText, request, runState) {
    expect(request).toBeTruthy();
    const normalizedSummary = String(summaryText || "").toLowerCase();
    expect(normalizedSummary).toContain(providerLabelFor(runState, request.provider).toLowerCase());
    expect(normalizedSummary).toContain(String(request.model || "").toLowerCase());
}