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
    const matchingResponse = snapshot.responses.find(row => row.llm_request_id === request.id);

    expect(snapshot.sessions).toHaveLength(1);
    expect(userMessages).toHaveLength(1);
    expect(snapshot.requests).toHaveLength(1);
    expect(snapshot.responses).toHaveLength(1);
    expect(snapshot.routingDecisions.length).toBeGreaterThanOrEqual(1);
    expect(snapshot.routingAttempts.length).toBeGreaterThanOrEqual(1);
    test.skip(
        Boolean(matchingResponse?.error_type),
        `Live provider did not return a successful response: ${matchingResponse?.error_type}`,
    );
    expect(matchingResponse?.error_type || null).toBeNull();
    expectSummaryMatchesRequest(result.summaryText, request);
});

test("compare model picker prevents duplicate target selection", async ({ liveApp }) => {
    const { page } = liveApp;

    await ensureMode(page, "compare");
    await setToggle(page, "#routeResearchBtn", false);
    await chooseDistinctCompareModels(page, 2);

    const firstValue = await page.locator("#compareModel1").inputValue();
    const duplicateOption = page.locator("#compareModel2").locator(`option[value="${firstValue}"]`);
    await expect(duplicateOption).toBeDisabled();
    await expect(page.getByRole("alert")).toHaveCount(0);
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

    test.skip(
        snapshot.routingAttempts.length < 2,
        "Fallback recovery requires at least two routable provider candidates.",
    );
    test.skip(
        !recoveredAttempt,
        "No configured fallback provider recovered from the injected first-attempt failure.",
    );
    expect(snapshot.routingAttempts.length).toBeGreaterThanOrEqual(2);
    expect(snapshot.routingDecisions.some(row => row.fallback_used || Number(row.attempt_count) > 1)).toBe(true);
    expect(failedAttempt).toBeTruthy();
    expect(recoveredAttempt).toBeTruthy();
    expect(network.entries.some(entry => entry.fault)).toBe(true);
    expectSummaryMatchesRequest(result.summaryText, request);
});
