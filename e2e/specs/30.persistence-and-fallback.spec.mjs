/**
 * Persistence-contract and deterministic fallback coverage.
 *
 * These scenarios are the bridge between browser-visible success and backend truth:
 * they verify that the request was stored correctly and that fallback telemetry was recorded.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { promptLibrary } from "../helpers/prompts.mjs";
import { chooseDistinctCompareModels, ensureMode, setToggle, submitAskPrompt } from "../helpers/ui.mjs";
import { expectSummaryMatchesRequest, latestRequest, waitForSnapshot } from "./_helpers.mjs";

test("successful ask persistence contract is recorded end to end", async ({ liveApp }) => {
    const { page, config, runState, caseId } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    const result = await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.smartAsk), config);
    const snapshot = await waitForSnapshot(liveApp, { minRequests: 1 });
    const request = latestRequest(snapshot);
    const userMessages = snapshot.messages.filter(row => row.role === "user" && String(row.content || "").includes(`case:${caseId}]`));
    const assistantMessages = snapshot.messages.filter(row => row.role === "assistant");
    const matchingResponse = snapshot.responses.find(row => row.llm_request_id === request.id);

    expect(snapshot.sessions).toHaveLength(1);
    expect(userMessages).toHaveLength(1);
    expect(assistantMessages).toHaveLength(1);
    expect(snapshot.requests).toHaveLength(1);
    expect(snapshot.responses).toHaveLength(1);
    expect(snapshot.routingDecisions.length).toBeGreaterThanOrEqual(1);
    expect(snapshot.routingAttempts.length).toBeGreaterThanOrEqual(1);
    expect(matchingResponse?.error_type || null).toBeNull();
    expectSummaryMatchesRequest(result.summaryText, request, runState);
});

test("real compare validation error shows user-facing UI and skips the compare request", async ({ liveApp }) => {
    const { page, network } = liveApp;

    await ensureMode(page, "compare");
    await setToggle(page, "#routeResearchBtn", false);
    await chooseDistinctCompareModels(page, 2);

    const compareCallsBefore = network.countByPath("/v1/compare/stream");
    await page.evaluate(() => {
        const first = document.getElementById("compareModel1");
        const second = document.getElementById("compareModel2");
        if (!first || !second) {
            throw new Error("Compare selects not found");
        }
        second.value = first.value;
    });

    await page.locator("#promptInput").fill(liveApp.withPromptMarker(promptLibrary.compare));
    await page.locator("#submitBtn").click();

    await expect(page.locator("#errorBanner")).toBeVisible();
    await expect(page.locator("#errorMsg")).toContainText("Please select different models for each slot.");
    await expect.poll(() => network.countByPath("/v1/compare/stream")).toBe(compareCallsBefore);
});

test("smart routing fallback records failed first attempt plus a successful recovery", async ({ liveApp }) => {
    const { page, config, network, runState } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    network.armFault("type=fail_attempt;attempt=0", { pathContains: "/chat/stream" });
    const result = await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.fallback), config);

    const snapshot = await waitForSnapshot(liveApp, {
        minRequests: 1,
        timeoutMs: config.timeouts.fallbackMs,
    });
    const request = latestRequest(snapshot);
    const failedAttempt = snapshot.routingAttempts.find(row => row.error_type || row.error_message);
    const recoveredAttempt = snapshot.routingAttempts.find(row => !row.error_type && !row.error_message);

    expect(snapshot.routingAttempts.length).toBeGreaterThanOrEqual(2);
    expect(snapshot.routingDecisions.some(row => row.fallback_used || Number(row.attempt_count) > 1)).toBe(true);
    expect(failedAttempt).toBeTruthy();
    expect(recoveredAttempt).toBeTruthy();
    expect(network.entries.some(entry => entry.fault)).toBe(true);
    expectSummaryMatchesRequest(result.summaryText, request, runState);
});
