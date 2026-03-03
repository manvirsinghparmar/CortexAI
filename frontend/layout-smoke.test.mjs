import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const htmlPath = path.join(process.cwd(), "frontend", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");
const appJsPath = path.join(process.cwd(), "frontend", "app.js");
const appJs = fs.readFileSync(appJsPath, "utf8");
const styleCssPath = path.join(process.cwd(), "frontend", "style.css");
const styleCss = fs.readFileSync(styleCssPath, "utf8");

test("dedicated smart routing card is removed", () => {
    assert.doesNotMatch(html, /routing-card/);
    assert.doesNotMatch(html, /singleRoutingSubtitle/);
    assert.doesNotMatch(html, /id="panelSingle"/);
});

test("checkbox-based manual model opt-in is removed", () => {
    assert.doesNotMatch(html, /singleModelOptIn/);
});

test("compact composer toolbar contains smart, manual, and inline compare controls", () => {
    assert.match(html, /id="composerToolbar"/);
    assert.match(html, /id="routeSmartBtn"/);
    assert.match(html, /id="routeSmartBtn"[\s\S]*role="switch"/);
    assert.match(html, /id="singleModelWrap"/);
    assert.match(html, /id="singleModel"/);
    assert.match(html, /id="singleModelLabel"/);
    assert.match(html, /class="toolbar-model-group hidden"/);
    assert.match(html, /id="compareModelWrap"/);
    assert.match(html, /id="compareModel1"/);
    assert.match(html, /id="compareModel2"/);
    assert.match(html, /id="compareModel3"/);
    assert.match(html, /id="compareAddModelBtn"/);
});

test("composer send button is inside the input area, not in the feature-chip row", () => {
    assert.match(
        html,
        /<div class="prompt-input-wrap">[\s\S]*id="promptInput"[\s\S]*btn-submit-inline[\s\S]*id="submitBtn"/,
    );
    assert.doesNotMatch(html, /class="prompt-footer-right"/);
});

test("composer chip row does not render optimization debug/status labels", () => {
    assert.doesNotMatch(html, /id="optViewBtn"/);
    assert.doesNotMatch(html, /id="optPanel"/);
    assert.doesNotMatch(html, /Optimization Off \(server\)/);
    assert.doesNotMatch(appJs, /Optimization Off \(server\)/);
    assert.doesNotMatch(appJs, /optViewBtn\.textContent/);
});

test("top mode tabs use Ask and Compare labels", () => {
    assert.match(html, /id="btnSingleMode"[\s\S]*>\s*Ask\s*</);
    assert.match(html, /id="btnCompareMode"[\s\S]*>\s*Compare\s*</);
});

test("toolbar keeps compact auto, web, and rewrite feature chips", () => {
    assert.doesNotMatch(html, /route-pill-group/);
    assert.match(html, /id="routeOptimizeBtn"/);
    assert.match(html, /id="routeResearchBtn"/);
    assert.match(html, /id="routeSmartBtn"[\s\S]*Auto \(Recommended\)/);
    assert.match(html, /id="routeResearchBtn"[\s\S]*chip-icon/);
    assert.match(html, /id="routeResearchBtn"[\s\S]*>\s*<span>Web<\/span>/);
    assert.match(html, /id="routeOptimizeBtn"[\s\S]*Rewrite/);
});

test("composer chips have premium motion and visual-state styling without status text", () => {
    assert.match(appJs, /function triggerChipToggleFeedback\(button\) \{/);
    assert.match(styleCss, /\.feature-chip:hover:not\(:disabled\) \{/);
    assert.match(styleCss, /transform:\s*translateY\(-1px\);/);
    assert.match(styleCss, /\.feature-chip\.active,/);
    assert.match(styleCss, /\.feature-chip:disabled \{/);
    assert.match(styleCss, /\.feature-chip\.is-toggling \{/);
    assert.match(styleCss, /@keyframes chipTogglePulse \{/);
    assert.match(styleCss, /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*\.feature-chip\.is-toggling \{/);
});

test("feature chips expose concise tooltip copy and compact active hint container", () => {
    assert.match(html, /Automatically selects the best model based on quality, speed, and cost\./);
    assert.match(html, /Searches the internet and includes citations\./);
    assert.match(html, /Improves your prompt before sending\./);
    assert.doesNotMatch(html, /Automatically picks the best model for your prompt\./);
    assert.match(html, /id="workspaceTagline"/);
});

test("compare mode is inline and no longer uses separate model-selection card", () => {
    assert.doesNotMatch(html, /id="panelCompare"/);
    assert.doesNotMatch(html, /Model Selection/);
    assert.doesNotMatch(html, /id="btn2Models"/);
    assert.doesNotMatch(html, /id="btn3Models"/);
    assert.match(html, /Compare:\s*<\/span>/);
    assert.match(html, /id="compareAddModelBtn"[\s\S]*\+ Add Model/);
});

test("compare transcript renders turn-based side-by-side columns with model headers", () => {
    assert.match(appJs, /function buildCompareModelHeader\(providerRaw, modelRaw\)/);
    assert.match(appJs, /class="compare-model-header"/);
    assert.match(appJs, /function buildCompareStreamingTurn\(promptText, targets, indexMap\)/);
    assert.match(appJs, /function buildCompareTurn\(promptText, responses, startIndex = 0\)/);
    assert.match(appJs, /<section class="compare-turn/);
    assert.match(appJs, /const gridClass = getCompareGridClass\(targets\.length\);/);
    assert.match(appJs, /const gridClass = getCompareGridClass\(safeResponses\.length\);/);
    assert.match(appJs, /buildStreamingCard\(target, cardIndex, offset \* 35, false, \{ compareView: true \}\)/);
    assert.match(appJs, /buildResponseCard\(resp, index, false, \{ compareView: true \}\)/);
});

test("compare mode sends session context and preserves prompt history between turns", () => {
    assert.match(appJs, /async function doCompare\(prompt\) \{[\s\S]*const sessionId = ensureActiveSessionId\(\);/);
    assert.match(appJs, /await callAPIStream\("\/v1\/compare\/stream", \{[\s\S]*context: \{[\s\S]*session_id: sessionId,[\s\S]*conversation_history: conversationHistory,[\s\S]*new_session: pendingNewSession,/);
    assert.match(appJs, /const compareAssistantContext = buildCompareAssistantContext\(compareResponsesForContext\);/);
    assert.match(appJs, /renderCompareSummary\(comparePayload\);[\s\S]*conversationHistory\.push\(\{ role: "user", content: prompt \}\);[\s\S]*if \(compareAssistantContext\) \{[\s\S]*conversationHistory\.push\(\{ role: "assistant", content: compareAssistantContext \}\);/);
});

test("compare history hydration keeps prior user prompts without duplicating per-model assistant turns", () => {
    assert.match(appJs, /function buildConversationHistoryFromEntries\(entries\) \{[\s\S]*const flushCompareTurn = \(\) => \{/);
    assert.match(appJs, /const assistantContext = buildCompareAssistantContext\(activeCompareTurn\.responses\);/);
    assert.match(appJs, /if \(assistantContext\) \{[\s\S]*rebuilt\.push\(\{ role: "assistant", content: assistantContext \}\);/);
});

test("mode-scoped session ids are persisted separately for Ask and Compare", () => {
    assert.match(appJs, /const SESSION_STORAGE_KEY_BY_MODE = \{/);
    assert.match(appJs, /single:\s*"cortex_active_session_id_single"/);
    assert.match(appJs, /compare:\s*"cortex_active_session_id_compare"/);
    assert.match(appJs, /const activeSessionIdByMode = \{/);
    assert.match(appJs, /function historyModeForUiMode\(mode = currentMode\)/);
});

test("history threads are grouped by mode and session to avoid cross-mode merging", () => {
    assert.match(appJs, /function buildHistoryThreads\(data\) \{[\s\S]*const modeLabel = normalizeHistoryModeLabel\(entry\.mode\);/);
    assert.match(appJs, /const key = sessionId \? `session:\$\{modeLabel\}:\$\{sessionId\}` : `entry:\$\{modeLabel\}:\$\{entry\.id\}`;/);
    assert.match(appJs, /const isActive = thread\.modeLabel === historyModeForUiMode\(currentMode\)/);
});

test("header keeps only slim nav links without subtitle block", () => {
    assert.match(html, /<button class="top-nav-link" type="button">History<\/button>/);
    assert.match(html, /<button class="top-nav-link" type="button">Settings<\/button>/);
    assert.match(html, /<button class="top-nav-link" type="button">Profile<\/button>/);
    assert.doesNotMatch(html, /header-intro-sub/);
});

test("brand uses typography-first wordmark without AI badge icon", () => {
    assert.match(html, /<span class="logo-text">CortexAI<\/span>/);
    assert.match(html, /<span class="compact-logo-text">CortexAI<\/span>/);
    assert.doesNotMatch(html, /class="logo-icon"/);
    assert.doesNotMatch(html, /class="compact-logo-icon"/);
});

test("response cards and history hide price and latency metadata", () => {
    assert.doesNotMatch(appJs, /Est\. Cost/);
    assert.doesNotMatch(appJs, /response-cost-/);
    assert.doesNotMatch(appJs, /response-latency-/);
    assert.doesNotMatch(appJs, /Latency:/);
    assert.match(appJs, /<span class="history-token-text">Tokens: \$\{tokStr\}<\/span>/);
    assert.match(appJs, /history-cost-text/);
});

test("ask mode defaults Web toggle to enabled", () => {
    assert.match(appJs, /let askResearchModeEnabled = true;/);
    assert.match(appJs, /function isResearchEnabledForCurrentMode\(\)/);
    assert.match(appJs, /research_mode: isResearchEnabledForCurrentMode\(\),/);
});

test("response cards provide copy, like, and dislike actions", () => {
    assert.match(appJs, /function buildResponseActionButtons\(index\)/);
    assert.match(appJs, /data-action="copy"/);
    assert.match(appJs, /data-action="like"/);
    assert.match(appJs, /data-action="dislike"/);
    assert.match(appJs, /function handleCopyAction\(button\)/);
    assert.match(appJs, /function handleReactionAction\(button, action\)/);
    assert.match(appJs, /el\.resultsGrid\.addEventListener\("click", event =>/);
});

test("streaming placeholder shows Thinking label with animated dots and reduced-motion fallback", () => {
    assert.match(appJs, /class="typing-indicator"/);
    assert.match(appJs, /class="typing-indicator-label" aria-hidden="true">Thinking<\/span>/);
    assert.match(appJs, /class="typing-indicator-dot">\.<\/span>/);
    assert.match(appJs, /role="status" aria-live="polite"/);
    assert.match(styleCss, /\.typing-indicator-label \{/);
    assert.match(styleCss, /\.typing-indicator-dot \{/);
    assert.match(styleCss, /@keyframes thinkingDot \{/);
    assert.match(styleCss, /@media \(prefers-reduced-motion: reduce\) \{/);
    assert.match(styleCss, /\.chat-message-ai\.is-streaming \.message-footer \{/);
    assert.match(styleCss, /display: none;/);
    assert.doesNotMatch(styleCss, /@keyframes typingPulse \{/);
});

test("chat action controls use persistent premium footer layout", () => {
    assert.match(appJs, /response-action-group-copy/);
    assert.match(appJs, /response-action-group-feedback/);
    assert.match(appJs, /class="message-footer"/);
    assert.match(appJs, /buildResponseFooter\(index, summary, resp\.token_usage, webSources\)/);
    assert.doesNotMatch(appJs, /message-details/);
    assert.match(styleCss, /\.message-footer \{/);
    assert.match(styleCss, /\.message-footer-meta \{/);
    assert.match(styleCss, /\.response-token-usage \{/);
    assert.doesNotMatch(styleCss, /\.chat-bubble-ai:hover \.response-actions,/);
    assert.match(styleCss, /width: 38px;/);
    assert.match(styleCss, /height: 38px;/);
    assert.match(styleCss, /width: 19px;/);
    assert.match(styleCss, /\.response-action-group \+ \.response-action-group \{/);
    assert.match(styleCss, /margin-left: 13px;/);
});

test("history thread selection restores transcript instead of reusing last prompt text", () => {
    assert.match(appJs, /function renderConversationFromEntries\(entries\)/);
    assert.match(appJs, /renderConversationFromEntries\(sessionEntries\);/);
    assert.match(appJs, /el\.promptInput\.value = "";/);
    assert.doesNotMatch(
        appJs,
        /el\.promptInput\.value = !isPromptPlaceholder\(thread\.latestPrompt\) \? thread\.latestPrompt : "";/,
    );
});

test("history sidebar titles use the first prompt in a thread", () => {
    assert.match(appJs, /function pickFirstPrompt\(entries\)/);
    assert.match(appJs, /const firstPrompt = pickFirstPrompt\(entries\);/);
    assert.match(appJs, /const rawPrompt = thread\.firstPrompt \|\| "\[prompt not stored\]";/);
    assert.doesNotMatch(appJs, /const rawPrompt = thread\.latestPrompt \|\| "\[prompt not stored\]";/);
});

test("history sidebar items do not render provider/model labels", () => {
    assert.doesNotMatch(appJs, /history-provider-model/);
});

test("provider and model selectors are loaded from discovery APIs", () => {
    assert.match(appJs, /async function loadDynamicProviderModelCatalog\(\)/);
    assert.match(appJs, /fetchCatalogJson\("\/v1\/providers"\)/);
    assert.match(appJs, /fetchCatalogJson\("\/v1\/models\?enabled_only=true"\)/);
    assert.match(appJs, /applyCatalogData\(providers, models\);/);
});

test("history thread selection scrolls to the bottom of restored messages", () => {
    assert.match(appJs, /function scrollResultsToBottom\(behavior = "auto"\) \{/);
    assert.match(appJs, /function scheduleScrollResultsToBottom\(options = \{\}\) \{/);
    assert.match(
        appJs,
        /if \(!el\.resultsSection\.classList\.contains\("hidden"\)\) \{[\s\S]*scheduleScrollResultsToBottom\(\{ behavior: "smooth", followUpDelayMs: 96 \}\);/,
    );
});

test("new streaming turns auto-scroll to Thinking and keep following streamed text", () => {
    assert.match(appJs, /function maybeAutoScrollDuringStream\(\) \{/);
    assert.match(appJs, /scheduleScrollResultsToBottom\(\{ behavior: "smooth", followUpDelayMs: 96 \}\);/);
    assert.match(appJs, /function appendStreamLine\(index, text\) \{[\s\S]*maybeAutoScrollDuringStream\(\);/);
    assert.match(appJs, /streamAutoScrollEnabled = true;/);
    assert.match(appJs, /streamAutoScrollEnabled = false;/);
});

test("historical transcripts render persisted web source citations", () => {
    assert.match(appJs, /const webSourceItems = normalizeWebSources\(entry\.web_source_items \|\| \[\]\);/);
    assert.match(appJs, /const webSources = normalizeWebSources\(resp\.web_source_items \|\| \[\]\);/);
    assert.match(appJs, /class="web-source-strip\$\{webSources\.length > 0 \? "" : " hidden"\}" id="response-sources-\$\{index\}" aria-label="Web sources"/);
});

test("compare layout styles support equal-width columns and responsive stacking", () => {
    assert.match(styleCss, /\.results-grid\.compare-transcript \{/);
    assert.match(styleCss, /\.compare-grid \{/);
    assert.match(styleCss, /\.compare-grid\.compare-grid-2 \{/);
    assert.match(styleCss, /\.compare-grid\.compare-grid-3 \{/);
    assert.match(styleCss, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
    assert.match(styleCss, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
    assert.match(styleCss, /@media \(max-width: 980px\) \{[\s\S]*\.compare-grid\.compare-grid-2,[\s\S]*\.compare-grid\.compare-grid-3 \{[\s\S]*grid-template-columns: minmax\(0, 1fr\);/);
});
