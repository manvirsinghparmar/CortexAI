/** Small helpers for stable run ids, retry-aware case ids, and prompt markers. */
import crypto from "node:crypto";

/** Create one suite-level id that is readable in logs and unique across runs. */
export function createRunId() {
    const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
    return `${stamp}-${crypto.randomUUID().slice(0, 8)}`;
}

export function slugifyTitle(value) {
    return String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 48) || "case";
}

/** Encode the test title plus retry/repeat indexes so every attempt has a unique case id. */
export function createCaseId(runId, testInfo) {
    const titleSlug = slugifyTitle(testInfo.title);
    const retry = Number.isInteger(testInfo.retry) ? testInfo.retry : 0;
    const repeat = Number.isInteger(testInfo.repeatEachIndex) ? testInfo.repeatEachIndex : 0;
    return `${runId}-${titleSlug}-try${retry}-rep${repeat}`;
}

/** Seed localStorage before the UI creates or restores the canonical backend session id. */
export function createSeededSessionId() {
    return crypto.randomUUID();
}

export function buildCaseMarker(runId, caseId) {
    return `[e2e-run:${runId};case:${caseId}]`;
}

/** Append a lightweight marker so DB queries can correlate persisted prompts to the test attempt. */
export function appendCaseMarker(prompt, runId, caseId) {
    const marker = buildCaseMarker(runId, caseId);
    const rawPrompt = String(prompt || "").trim();
    return `${rawPrompt}\n\n${marker}`;
}