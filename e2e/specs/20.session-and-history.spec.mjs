/**
 * Session continuity and history restoration coverage.
 *
 * These tests deliberately treat backend session ids as the source of truth because
 * a restored-looking UI is not enough if the server silently forked the conversation.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { promptLibrary } from "../helpers/prompts.mjs";
import { sumTokensForSession } from "../helpers/db.mjs";
import {
    chooseDistinctCompareModels,
    ensureMode,
    openHistoryThread,
    setToggle,
    startNewChat,
    submitAskPrompt,
    submitComparePrompt,
    waitForComposerReady,
} from "../helpers/ui.mjs";
import { latestRequest, waitForSnapshot } from "./_helpers.mjs";

test("ask to compare switch in one active session reuses the same backend session", async ({ liveApp }) => {
    const { page, config } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);
    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.smartAsk), config);

    const askSnapshot = await waitForSnapshot(liveApp, { minRequests: 1 });
    const askRequest = latestRequest(askSnapshot);

    await ensureMode(page, "compare");
    await setToggle(page, "#routeResearchBtn", false);
    await chooseDistinctCompareModels(page, 2);
    await submitComparePrompt(page, liveApp.withPromptMarker(promptLibrary.compare), config, 2);

    const snapshot = await waitForSnapshot(liveApp, {
        sessionId: null,
        predicate: current => current.requests.length >= 3,
        timeoutMs: config.timeouts.compareMs,
    });

    const compareRequests = snapshot.requests.filter(row => row.request_group_id);
    expect(compareRequests).toHaveLength(2);
    expect(new Set(compareRequests.map(row => row.request_group_id)).size).toBe(1);
    expect(compareRequests.every(row => row.session_id === askRequest.session_id)).toBe(true);
});

test("mid-session browser refresh restores the active thread and continues the same backend session", async ({ liveApp }) => {
    const { page, config } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.refresh), config);
    const firstSnapshot = await waitForSnapshot(liveApp, { minRequests: 1 });
    const firstRequest = latestRequest(firstSnapshot);

    await expect(page.locator(".chat-user-text", { hasText: "request tracing works" })).toBeVisible({
        timeout: config.timeouts.historyRestoreMs,
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForComposerReady(page, config);
    await expect(page.locator(".chat-user-text", { hasText: "request tracing works" })).toBeVisible({
        timeout: config.timeouts.historyRestoreMs,
    });

    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.tokensTwo), config);
    const secondSnapshot = await waitForSnapshot(liveApp, {
        minRequests: 2,
        predicate: current => current.requests.length >= 2,
    });

    expect(secondSnapshot.requests).toHaveLength(2);
    expect(secondSnapshot.requests.every(row => row.session_id === firstRequest.session_id)).toBe(true);
});

test("reopening an old history thread restores it and continues the same backend session", async ({ liveApp }) => {
    const { page, config } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.historyA), config);
    const afterA = await waitForSnapshot(liveApp, { sessionId: null, minRequests: 1 });
    const sessionA = afterA.requests[0].session_id;

    await startNewChat(page);
    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.historyB), config);
    const afterB = await waitForSnapshot(liveApp, {
        sessionId: null,
        predicate: current => current.requests.length >= 2,
    });
    expect(new Set(afterB.requests.map(row => row.session_id)).size).toBe(2);

    await openHistoryThread(page, "Thread A:");
    await expect(page.locator(".chat-user-text", { hasText: "Thread A:" })).toBeVisible({
        timeout: config.timeouts.historyRestoreMs,
    });

    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.historyFollowUp), config);
    const finalSnapshot = await waitForSnapshot(liveApp, {
        sessionId: null,
        predicate: current => current.requests.length >= 3,
    });

    expect(finalSnapshot.requests[2].session_id).toBe(sessionA);
    expect(finalSnapshot.requests[1].session_id).not.toBe(sessionA);
});

test("history restores every persisted turn with persistence-backed token totals", async ({ liveApp }) => {
    const { page, config, dbPool, ownerId } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.tokensOne), config);
    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.tokensTwo), config);

    const snapshot = await waitForSnapshot(liveApp, {
        minRequests: 2,
        predicate: current => current.requests.length >= 2,
    });
    const sessionId = snapshot.requests[0].session_id;
    expect(snapshot.requests.every(row => row.session_id === sessionId)).toBe(true);

    const persistedTokens = await sumTokensForSession(dbPool, config, ownerId, sessionId);
    expect(Number.isFinite(persistedTokens)).toBe(true);
    expect(persistedTokens).toBeGreaterThanOrEqual(0);

    await startNewChat(page);
    await openHistoryThread(page, "Give me five bullet points");
    await expect(page.locator(".chat-user-text", { hasText: "Give me five bullet points" })).toBeVisible({
        timeout: config.timeouts.historyRestoreMs,
    });
    await expect(page.locator(".chat-user-text", { hasText: "Now add three more bullet points" })).toBeVisible({
        timeout: config.timeouts.historyRestoreMs,
    });
});
