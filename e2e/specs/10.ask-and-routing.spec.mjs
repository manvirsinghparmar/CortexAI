/**
 * Tier A and Tier B Ask-mode routing coverage.
 *
 * These scenarios exercise the main smart-routing controls through the live UI and
 * then verify the backend's persisted routing choice instead of trusting the DOM alone.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { promptLibrary } from "../helpers/prompts.mjs";
import { ensureMode, expandSourcesForCard, setToggle, startNewChat, submitAskPrompt } from "../helpers/ui.mjs";
import { routingBoundaryScenarios } from "../test-data/routing-outcomes.mjs";
import { expectSummaryMatchesRequest, latestRequest, waitForSnapshot } from "./_helpers.mjs";

test("ask mode with smart routing returns streamed response and persisted selection", async ({ liveApp }) => {
    const { page, config, runState } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    const result = await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.smartAsk), config);
    expect(result.stream.distinctSnapshots).toBeGreaterThanOrEqual(2);
    expect(result.text.length).toBeGreaterThan(20);

    const snapshot = await waitForSnapshot(liveApp, { minRequests: 1 });
    const request = latestRequest(snapshot);

    expect(snapshot.responses).toHaveLength(1);
    expect(snapshot.routingDecisions.length).toBeGreaterThanOrEqual(1);
    expect(snapshot.routingAttempts.length).toBeGreaterThanOrEqual(1);
    expect(new Set(snapshot.requests.map(row => row.session_id)).size).toBe(1);
    expectSummaryMatchesRequest(result.summaryText, request, runState);
});

test("web on then off in the same session changes source behavior", async ({ liveApp }) => {
    const { page, config } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeOptimizeBtn", false);
    await setToggle(page, "#routeResearchBtn", true);

    const first = await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.webResearch), config);
    const firstCardText = await page.locator(`#chat-msg-${first.index}`).innerText();
    const firstSnapshot = await waitForSnapshot(liveApp, { minRequests: 1 });

    expect(firstSnapshot.requests).toHaveLength(1);
    expect(firstSnapshot.routingDecisions).toHaveLength(1);
    expect(firstSnapshot.routingDecisions[0].research_mode).toBe("on");

    const firstSourcesStrip = page.locator(`#response-sources-${first.index}`);
    if (await firstSourcesStrip.isVisible()) {
        const sourceLinks = await expandSourcesForCard(page, first.index);
        expect(await sourceLinks.count()).toBeGreaterThan(0);
    } else {
        expect(firstCardText.toLowerCase()).not.toMatch(
            /can't browse|cannot browse|do not have access to real-time|don't have access to real-time|real-time web browsing capabilities/,
        );
    }

    await setToggle(page, "#routeResearchBtn", false);
    const second = await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.noWebFollowUp), config);
    await expect(page.locator(`#response-sources-${second.index}`)).toBeHidden();

    const snapshot = await waitForSnapshot(liveApp, { minRequests: 2 });
    expect(snapshot.requests).toHaveLength(2);
    expect(snapshot.routingDecisions).toHaveLength(2);
    expect(snapshot.routingDecisions.map(row => row.research_mode)).toEqual(["on", "off"]);
    expect(new Set(snapshot.requests.map(row => row.session_id)).size).toBe(1);
    expect(snapshot.requests[0].session_id).toBe(snapshot.requests[1].session_id);
});

test("prompt optimizer on then off in the same session changes request flow", async ({ liveApp }) => {
    const { page, config, network } = liveApp;

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", true);

    const optimizeCallsBefore = network.countByPath("/v1/optimize");
    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.optimizer), config);
    const optimizeCallsAfterFirst = network.countByPath("/v1/optimize");
    expect(optimizeCallsAfterFirst).toBeGreaterThan(optimizeCallsBefore);

    await setToggle(page, "#routeOptimizeBtn", false);
    const optimizeCallsBeforeSecond = network.countByPath("/v1/optimize");
    await submitAskPrompt(page, liveApp.withPromptMarker(promptLibrary.tokensTwo), config);
    expect(network.countByPath("/v1/optimize")).toBe(optimizeCallsBeforeSecond);

    const snapshot = await waitForSnapshot(liveApp, {
        minRequests: 2,
        predicate: current => current.requests.length >= 2,
    });
    expect(snapshot.requests.length).toBeGreaterThanOrEqual(2);
    const sessionId = snapshot.requests[0].session_id;
    expect(snapshot.requests.every(row => row.session_id === sessionId)).toBe(true);
});

test("routing policy boundary coverage uses allowed outcomes and varies across prompt classes", async ({ liveApp }) => {
    const { page, config, runState } = liveApp;
    const seenRequestIds = new Set();
    const outcomes = [];

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);
    await setToggle(page, "#routeResearchBtn", false);
    await setToggle(page, "#routeOptimizeBtn", false);

    for (let index = 0; index < routingBoundaryScenarios.length; index += 1) {
        const scenario = routingBoundaryScenarios[index];
        if (index > 0) {
            await startNewChat(page);
        }

        const result = await submitAskPrompt(page, liveApp.withPromptMarker(scenario.prompt), config);
        const snapshot = await waitForSnapshot(liveApp, {
            sessionId: null,
            predicate: current => current.requests.length > seenRequestIds.size,
            timeoutMs: config.timeouts.askMs,
        });

        const newRequests = snapshot.requests.filter(row => !seenRequestIds.has(row.id));
        expect(newRequests).toHaveLength(1);

        const request = newRequests[0];
        seenRequestIds.add(request.id);
        outcomes.push(`${request.provider}:${request.model}`);

        expect(scenario.allowedProviders).toContain(request.provider);
        expectSummaryMatchesRequest(result.summaryText, request, runState);
    }

    expect(new Set(outcomes).size).toBeGreaterThanOrEqual(2);
});
