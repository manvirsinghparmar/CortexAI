import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const htmlPath = path.join(process.cwd(), "frontend", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");
const appJsPath = path.join(process.cwd(), "frontend", "app.js");
const appJs = fs.readFileSync(appJsPath, "utf8");
const styleCssPath = path.join(process.cwd(), "frontend", "style.css");
const styleCss = fs.readFileSync(styleCssPath, "utf8");
const llmResponseJsPath = path.join(process.cwd(), "frontend", "llm-response.js");
const llmResponseJs = fs.readFileSync(llmResponseJsPath, "utf8");
const llmResponseCssPath = path.join(process.cwd(), "frontend", "llm-response.css");
const llmResponseCss = fs.readFileSync(llmResponseCssPath, "utf8");

test("runtime config script loads before app bootstrap", () => {
    const runtimeConfigScriptIndex = html.indexOf('src="runtime-config.js');
    const appScriptIndex = html.indexOf('src="app.js');

    assert.notEqual(runtimeConfigScriptIndex, -1);
    assert.notEqual(appScriptIndex, -1);
    assert.ok(runtimeConfigScriptIndex < appScriptIndex);
});

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
    assert.match(html, /id="compareRemoveModel1"/);
    assert.match(html, /id="compareRemoveModel2"/);
    assert.match(html, /id="compareRemoveModel3"/);
});

test("composer send button is inside the input area, not in the feature-chip row", () => {
    assert.match(
        html,
        /<div class="prompt-input-wrap"[^>]*>[\s\S]*id="promptInput"[\s\S]*btn-submit-inline[\s\S]*id="submitBtn"/,
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

test("improve flow renders optimization progress without response-card ids", () => {
    assert.match(appJs, /function appendOptimizationPendingTurn\(promptText, options = \{\}\) \{/);
    assert.match(appJs, /function buildOptimizationUserBubble\(turnId, options = \{\}\) \{/);
    assert.match(appJs, /Refining your prompt for better results/);
    assert.match(appJs, /Enhancing clarity/);
    assert.match(appJs, /Improving intent/);
    assert.match(appJs, /Preparing optimized version/);
    assert.match(appJs, /OPTIMIZE_REQUEST_TIMEOUT_MS\s*=\s*5500/);
    assert.match(appJs, /function buildOptimizeContextPayload\(prompt, options = \{\}\) \{/);
    assert.match(appJs, /hasAttachments: Boolean\(options\?\.hasAttachments\)/);
    assert.match(appJs, /function isLikelyFollowUpPrompt\(prompt\) \{/);
    assert.match(appJs, /the second one/);
    assert.match(appJs, /make\|rewrite\|improve\|modify/);
    assert.match(appJs, /OPTIMIZE_CONTEXT_MESSAGE_LIMIT\s*=\s*4/);
    assert.match(appJs, /OPTIMIZE_REFERENCE_CONTEXT_MESSAGE_LIMIT\s*=\s*10/);
    assert.match(appJs, /OPTIMIZE_CONTEXT_TOTAL_LIMIT\s*=\s*2000/);
    assert.match(appJs, /OPTIMIZE_REFERENCE_CONTEXT_TOTAL_LIMIT\s*=\s*4000/);
    assert.match(appJs, /OPTIMIZE_CONTEXT_MESSAGE_LIMIT_CHARS\s*=\s*500/);
    assert.match(appJs, /possessiveReferencePattern/);
    assert.match(appJs, /priorOfferPattern/);
    assert.match(appJs, /\.slice\(-OPTIMIZE_REFERENCE_CONTEXT_MESSAGE_LIMIT\);/);
    assert.match(appJs, /const selected = recentMessages\.slice\(-messageLimit\);/);
    assert.match(appJs, /context_hint/);
    assert.match(appJs, /optimization_status/);
    assert.match(appJs, /startOptimizationProgressStates\(turnId\);/);
    assert.match(appJs, /Your prompt was already clear\. CortexAI sent the original version\./);
    assert.doesNotMatch(appJs, /Could not refine this time\. Sent your original prompt\./);
    assert.match(appJs, /chat-message chat-message-user optimization-message is-pending/);
    assert.match(appJs, /skipUserBubble: renderedUserBeforeRequest/);
    assert.match(appJs, /id="optimization-turn-\$\{turnId\}"/);
    assert.match(appJs, /id="optimization-note-\$\{turnId\}"/);
    assert.doesNotMatch(appJs, /id="response-text-\$\{turnId\}"/);
    assert.match(styleCss, /\.optimization-message \{/);
    assert.match(styleCss, /\.optimization-user-text \{/);
    assert.match(styleCss, /\.optimization-result-note \{/);
    assert.match(styleCss, /\.optimization-result-note \{[\s\S]*font-size:\s*\.66rem;[\s\S]*font-weight:\s*500;[\s\S]*color:\s*#3F6F5E;[\s\S]*background:\s*#F3FAF6;[\s\S]*border:\s*1px solid #CFE8DA;/);
    assert.match(styleCss, /@keyframes optimizationBubbleShimmer \{/);
    assert.match(styleCss, /@keyframes optimizationSparkleGlow \{/);
    assert.match(styleCss, /@keyframes optimizationDotFloat \{/);
    assert.match(styleCss, /\.optimization-message\.is-pending \.optimization-user-text \{[\s\S]*font-size:\s*\.82rem;[\s\S]*font-weight:\s*700;[\s\S]*color:\s*#0F3A6D;/);
});

test("optimize reference follow-up context payload uses expanded mixed-message window", () => {
    const constantsMatch = appJs.match(
        /const OPTIMIZE_CONTEXT_MESSAGE_LIMIT\s*=\s*\d+;\s*[\s\S]*?const OPTIMIZE_CONTEXT_MESSAGE_LIMIT_CHARS\s*=\s*\d+;/,
    );
    assert.ok(constantsMatch);

    const snippetStart = appJs.indexOf("function normalizeOptimizeContextText");
    const snippetEnd = appJs.indexOf("async function callOptimize", snippetStart);
    assert.ok(snippetStart > 0);
    assert.ok(snippetEnd > snippetStart);

    const sandbox = {
        conversationHistory: [
            { role: "user", content: "root marker: compare OpenAI, Gemini, and Claude" },
            { role: "assistant", content: "root answer marker: second one is Gemini" },
            { role: "user", content: "follow-up one marker" },
            { role: "assistant", content: "follow-up one answer marker" },
            { role: "user", content: "follow-up two marker" },
            { role: "assistant", content: "follow-up two answer marker" },
            { role: "user", content: "follow-up three marker" },
            { role: "assistant", content: "follow-up three answer marker" },
            { role: "user", content: "follow-up four marker" },
            { role: "assistant", content: "follow-up four answer marker" },
        ],
        activeSessionId: "session-long-chat",
        pendingNewSession: false,
    };
    vm.createContext(sandbox);
    vm.runInContext(
        `${constantsMatch[0]}
${appJs.slice(snippetStart, snippetEnd)}
globalThis.__payload = buildOptimizeContextPayload("make the second one more suitable", {});
globalThis.__possessiveFollowUp = isLikelyFollowUpPrompt("How many of their cadres were actually killed?");
globalThis.__priorOfferFollowUp = isLikelyFollowUpPrompt("Give me the detailed range of estimates.");`,
        sandbox,
    );

    const payload = sandbox.__payload;
    assert.equal(sandbox.__possessiveFollowUp, true);
    assert.equal(sandbox.__priorOfferFollowUp, true);
    assert.equal(payload.context.session_id, "session-long-chat");
    assert.deepEqual(
        payload.context.conversation_history.map(item => item.content),
        [
            "root marker: compare OpenAI, Gemini, and Claude",
            "root answer marker: second one is Gemini",
            "follow-up one marker",
            "follow-up one answer marker",
            "follow-up two marker",
            "follow-up two answer marker",
            "follow-up three marker",
            "follow-up three answer marker",
            "follow-up four marker",
            "follow-up four answer marker",
        ],
    );
    assert.match(payload.context_hint, /root answer marker/);
    assert.match(payload.context_hint, /follow-up three marker/);
    assert.match(payload.context_hint, /follow-up four answer marker/);
});

test("top mode tabs use Ask and Compare labels", () => {
    assert.match(html, /id="btnSingleMode"[\s\S]*>\s*Ask\s*</);
    assert.match(html, /id="btnCompareMode"[\s\S]*>\s*Compare\s*</);
});

test("toolbar uses Smart, With sources, and Improve chip labels", () => {
    assert.doesNotMatch(html, /route-pill-group/);
    assert.match(html, /id="routeOptimizeBtn"/);
    assert.match(html, /id="routeResearchBtn"/);
    assert.match(html, /id="routeSmartBtn"[\s\S]*chip-icon/);
    assert.match(html, /id="routeSmartBtn"[\s\S]*>\s*<span class="chip-label">Smart<\/span>/);
    assert.match(html, /id="routeResearchBtn"[\s\S]*>\s*<span class="chip-label">With sources<\/span>/);
    assert.match(html, /id="routeOptimizeBtn"[\s\S]*>\s*<span class="chip-label">Improve<\/span>/);
});

test("composer chips have premium motion and visual-state styling without status text", () => {
    assert.match(appJs, /function triggerChipToggleFeedback\(button\) \{/);
    assert.match(appJs, /setRoutingButtonState\(el\.routeSmartBtn, "Smart", smartAllowed && smartModeEnabled\);/);
    assert.match(appJs, /setRoutingButtonState\(el\.routeResearchBtn, "With sources", isResearchEnabledForCurrentMode\(\)\);/);
    assert.match(appJs, /setRoutingButtonState\(el\.routeOptimizeBtn, "Improve", optimizeEnabled\);/);
    assert.match(styleCss, /\.feature-chip:hover:not\(:disabled\) \{/);
    assert.match(styleCss, /transform:\s*translateY\(-1px\);/);
    assert.match(styleCss, /transform:\s*scale\(1\.02\);/);
    assert.match(styleCss, /\.feature-chip\.active,/);
    assert.match(styleCss, /\.feature-chip:disabled \{/);
    assert.match(styleCss, /\.feature-chip\.is-toggling \{/);
    assert.match(styleCss, /@keyframes chipTogglePulse \{/);
    assert.match(styleCss, /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*\.feature-chip\.is-toggling \{/);
});

test("feature chips expose premium tooltip copy and compact active hint container", () => {
    assert.match(html, /Gets you the best answer automatically/);
    assert.match(html, /Uses latest information from the web/);
    assert.match(html, /Helps you ask better for better results/);
    assert.doesNotMatch(html, /Automatically selects the best model based on quality, speed, and cost\./);
    assert.doesNotMatch(html, /Searches the internet and includes citations\./);
    assert.doesNotMatch(html, /Automatically selects the best model for your request based on cost, latency, and token efficiency\./);
    assert.doesNotMatch(html, /Searches the web and injects relevant up-to-date information into the prompt so the response can use the latest available context\./);
    assert.doesNotMatch(html, /Optimizes your prompt before sending it so the model can generate a clearer and better response\./);
    assert.doesNotMatch(html, /Rewrites your prompt for better results/);
    assert.match(html, /id="workspaceTagline"/);
});

test("composer chips use natural auto-width layout with premium spacing", () => {
    assert.match(styleCss, /\.feature-strip \{[\s\S]*gap:\s*11px;[\s\S]*justify-content:\s*flex-start;[\s\S]*flex-wrap:\s*nowrap;/);
    assert.match(styleCss, /\.composer-footer-features \{[\s\S]*width:\s*100%;[\s\S]*justify-content:\s*flex-start;[\s\S]*flex-wrap:\s*nowrap;/);
    assert.match(styleCss, /\.feature-chip-wrap \{[^}]*display:\s*inline-flex;[^}]*flex:\s*0 0 auto;/);
    assert.match(styleCss, /\.feature-chip \{[^}]*justify-content:\s*center;/);
    assert.match(styleCss, /\.feature-chip \{[^}]*width:\s*auto;/);
    assert.match(styleCss, /\.chip-label \{[\s\S]*text-overflow:\s*ellipsis;/);
    assert.match(styleCss, /\.chip-tooltip \{[\s\S]*top:\s*auto;[\s\S]*bottom:\s*calc\(100%\s*\+\s*8px\);[\s\S]*max-width:\s*360px;[\s\S]*padding:\s*10px 12px;[\s\S]*border-radius:\s*12px;/);
    assert.doesNotMatch(styleCss, /\.feature-chip-wrap \{[^}]*flex:\s*1 1 0;/);
    assert.doesNotMatch(styleCss, /\.feature-chip \{[^}]*width:\s*100%;/);
});

test("compare mode is inline and no longer uses separate model-selection card", () => {
    assert.doesNotMatch(html, /id="panelCompare"/);
    assert.doesNotMatch(html, /Model Selection/);
    assert.doesNotMatch(html, /id="btn2Models"/);
    assert.doesNotMatch(html, /id="btn3Models"/);
    assert.match(html, /Compare:\s*<\/span>/);
    assert.match(html, /id="compareAddModelBtn"[\s\S]*\+ Add Model/);
    assert.doesNotMatch(html, />\s*- Remove Model\s*</);
    assert.match(html, /class="compare-remove-model-btn"[\s\S]*id="compareRemoveModel1"/);
    assert.match(html, /data-compare-slot="1"[\s\S]*aria-label="Remove model 2 from comparison"/);
});

test("compare payload is built from active removable selector slots", () => {
    assert.match(appJs, /function removeCompareSlot\(slotIndexRaw\) \{[\s\S]*remainingValues = selects[\s\S]*filter\(\(_, index\) => index !== slotIndex\);/);
    assert.match(appJs, /const selects = getActiveCompareSelects\(\);\s*const targets = selects\.map\(sel => parseKey\(sel\.value\)\);/);
});

test("compare transcript renders turn-based side-by-side columns with model headers", () => {
    assert.match(appJs, /function buildCompareModelHeader\(providerRaw, modelRaw\)/);
    assert.match(appJs, /class="compare-model-header"/);
    assert.match(appJs, /function buildCompareStreamingTurn\(promptText, targets, indexMap(?:, options = \{\})?\)/);
    assert.match(appJs, /function buildCompareTurn\(promptText, responses, startIndex = 0(?:, options = \{\})?\)/);
    assert.match(appJs, /<section class="compare-turn/);
    assert.match(appJs, /const gridClass = getCompareGridClass\(targets\.length\);/);
    assert.match(appJs, /const gridClass = getCompareGridClass\(safeResponses\.length\);/);
    assert.match(appJs, /buildStreamingCard\(target, cardIndex, offset \* 35, false, \{ compareView: true \}\)/);
    assert.match(appJs, /buildResponseCard\(resp, index, false, \{ compareView: true \}\)/);
});

test("compare response cards use compact icon-only footers", () => {
    assert.match(appJs, /function buildResponseFooter\(index, summary, tokenUsage, webSources = \[\], options = \{\}\) \{/);
    assert.match(appJs, /const compact = Boolean\(options\.compact\);/);
    assert.match(appJs, /const providerMetaHtml = compact \? "" : buildResponseProviderMeta\(summary, index\);/);
    assert.match(appJs, /const tokenUsageHtml = compact \? "" : buildTokenUsageText\(tokenUsage, index\);/);
    assert.match(appJs, /class="message-footer\$\{compactClass\}"/);
    assert.match(appJs, /buildResponseFooter\(index, summary, null, \[\], \{ compact: compareView \}\)/);
    assert.match(appJs, /buildResponseFooter\(index, summary, resp\.token_usage, webSources, \{ compact: compareView \}\)/);
    assert.match(appJs, /function buildCompareResponseTooltip\(resp, summary, webSources = \[\]\) \{/);
    assert.match(appJs, /<span>Usage: \$\{escHtml\(usageLabel\)\}<\/span>/);
    assert.match(appJs, /<div class="response-action-rail" role="group" aria-label="Response actions">/);
    assert.match(appJs, /aria-label="Resources"[\s\S]*title="Resources"/);
    assert.doesNotMatch(appJs, /aria-label="Toggle Sources"/);
    assert.match(styleCss, /\.message-footer\.is-compare-compact \{/);
    assert.match(styleCss, /\.message-footer\.is-compare-compact \.response-action-rail \{[\s\S]*--response-action-size: 30px;/);
    assert.match(styleCss, /\.response-action-rail \.web-source-toggle-text,[\s\S]*\.response-action-rail \.web-source-toggle-icon \{[\s\S]*display: none;/);
    assert.match(styleCss, /\.message-footer\.is-compare-compact \.response-action-group \{[\s\S]*gap: 12px;/);
});

test("compare mode sends session context and preserves prompt history between turns", () => {
    assert.match(
        appJs,
        /async function doCompare\(prompt, \{[\s\S]*streamRequest = null,[\s\S]*attachments = \[\],[\s\S]*const sessionId = ensureActiveSessionId\(\);/,
    );
    assert.match(appJs, /await callAPIStream\("\/v1\/compare\/stream", \{[\s\S]*context: \{[\s\S]*session_id: sessionId,[\s\S]*conversation_history: conversationHistory,[\s\S]*new_session: pendingNewSession,/);
    assert.match(appJs, /const compareAssistantContext = buildCompareAssistantContext\(compareResponsesForContext\);/);
    assert.match(appJs, /renderCompareSummary\(comparePayload\);[\s\S]*conversationHistory\.push\(\{ role: "user", content: prompt \}\);[\s\S]*if \(compareAssistantContext\) \{[\s\S]*conversationHistory\.push\(\{ role: "assistant", content: compareAssistantContext \}\);/);
});

test("stream requests send correlation ids and log read failures", () => {
    assert.match(appJs, /const REQUEST_ID_HEADER = "X-Request-ID";/);
    assert.match(appJs, /function createClientRequestId\(\) \{[\s\S]*return `web-\$\{timestamp\}-\$\{random\}`;/);
    assert.match(appJs, /async function callAPIStream\(path, body, onEvent, options = \{\}\) \{[\s\S]*const requestId = createClientRequestId\(\);[\s\S]*\[REQUEST_ID_HEADER\]: requestId,/);
    assert.match(appJs, /serverRequestId = getResponseHeader\(resp, REQUEST_ID_HEADER\);/);
    assert.match(appJs, /eventsReceived \+= 1;/);
    assert.match(appJs, /console\.error\("CortexAI stream request failed", \{[\s\S]*request_id:[\s\S]*server_request_id:[\s\S]*elapsed_ms:[\s\S]*classified_kind:[\s\S]*events_received:[\s\S]*api_base: API_BASE,/);
});

test("compare history hydration keeps prior user prompts without duplicating per-model assistant turns", () => {
    assert.match(appJs, /function buildConversationHistoryFromEntries\(entries\) \{[\s\S]*const flushCompareTurn = \(\) => \{/);
    assert.match(appJs, /const assistantContext = buildCompareAssistantContext\(activeCompareTurn\.responses\);/);
    assert.match(appJs, /if \(assistantContext\) \{[\s\S]*rebuilt\.push\(\{ role: "assistant", content: assistantContext \}\);/);
});

test("a single shared session id is reused across Ask and Compare", () => {
    assert.match(appJs, /const ACTIVE_SESSION_STORAGE_KEY = "cortex_active_session_id";/);
    assert.match(appJs, /const LEGACY_MODE_SESSION_STORAGE_KEYS = \[/);
    assert.match(appJs, /function setActiveSessionId\(sessionId, \{ persist = true \} = \{\}\)/);
    assert.match(appJs, /function ensureActiveSessionId\(\) \{[\s\S]*const existing = normalizeSessionId\(activeSessionId \|\| loadActiveSessionId\(\)\);/);
    assert.doesNotMatch(appJs, /const activeSessionIdByMode = \{/);
});

test("fresh login starts a new active thread instead of restoring the previous session", () => {
    assert.match(appJs, /const FRESH_LOGIN_PENDING_STORAGE_KEY = "cortex_fresh_login_pending";/);
    assert.match(appJs, /const FRESH_LOGIN_QUERY_PARAM = "fresh_login";/);
    assert.match(appJs, /function consumeFreshLoginSessionReset\(\) \{[\s\S]*params\.get\(FRESH_LOGIN_QUERY_PARAM\) === "1"[\s\S]*window\.history\.replaceState/);
    assert.match(appJs, /function startFreshSessionForLogin\(\) \{[\s\S]*startNewChatSession\(\);[\s\S]*\}/);
    assert.match(appJs, /if \(consumeFreshLoginSessionReset\(\)\) \{[\s\S]*startFreshSessionForLogin\(\);[\s\S]*\}/);
    assert.match(appJs, /wrap\.querySelector\("#cognitoSignInBtn"\)\.addEventListener\("click", function \(\) \{[\s\S]*requestFreshLoginSessionReset\(\);[\s\S]*window\.location\.href = url;/);
    assert.match(appJs, /async function reconcileAuthenticatedSession\(\{ forceFresh = false \} = \{\}\) \{[\s\S]*if \(forceFresh \|\| !priorUserId \|\| \(userId && priorUserId !== userId\)\) \{[\s\S]*startFreshSessionForLogin\(\);/);
    assert.match(appJs, /if \(!activeSessionId && !pendingNewSession\) \{[\s\S]*const mostRecentWithSession = _historyData\.find/);
});

test("initial history load waits for auth bootstrap", () => {
    assert.match(
        appJs,
        /async function initializeAuthAndCatalog\(\) \{[\s\S]*await initCognitoAuth\(\);[\s\S]*await Promise\.all\(\[[\s\S]*loadHistory\(\{ restoreActiveTranscript: true \}\),[\s\S]*\]\);[\s\S]*\}/,
    );
    assert.doesNotMatch(
        appJs,
        /historyEl\.search\.addEventListener\("input"[\s\S]*\}\);\s*loadHistory\(\{ restoreActiveTranscript: true \}\);/,
    );
});

test("mode switches preserve a pending new session until it has history", () => {
    assert.match(appJs, /function setMode\(mode\) \{[\s\S]*const sessionEntries = getSessionEntries\(_historyData, activeSessionId\);[\s\S]*if \(sessionEntries\.length > 0\) \{[\s\S]*pendingNewSession = false;/);
    assert.doesNotMatch(appJs, /renderSessionTranscript\(activeSessionId, _historyData\);\s*pendingNewSession = false;/);
});

test("history threads are grouped by shared session id and can surface mixed-mode turns", () => {
    assert.match(appJs, /function buildHistoryThreads\(data\) \{[\s\S]*const key = sessionId \? `session:\$\{sessionId\}` : `entry:\$\{entry\.id\}`;/);
    assert.match(appJs, /const normalizedModes = new Set\(entries\.map\(entry => normalizeHistoryModeLabel\(entry\.mode\)\)\);/);
    assert.match(appJs, /const modeLabel = normalizedModes\.size > 1[\s\S]*\? "mixed"/);
    assert.match(appJs, /function getHistoryThreadBadgeLabel\(modeLabel\) \{[^}]*if \(modeLabel === "compare"\) return "Compare";[^}]*if \(modeLabel === "mixed"\) return "Hybrid";[^}]*return "Ask";[^}]*\}/);
    assert.doesNotMatch(appJs, /function getHistoryThreadBadgeLabel\(modeLabel\) \{[^}]*return "Chat";/);
    assert.doesNotMatch(appJs, /function getHistoryThreadBadgeLabel\(modeLabel\) \{[^}]*return "Mixed";/);
    assert.match(appJs, /const isActive = thread\.sessionId[\s\S]*thread\.sessionId === activeSessionId;/);
});

test("header removes static nav links and subtitle block", () => {
    assert.doesNotMatch(html, /<button class="top-nav-link" type="button">History<\/button>/);
    assert.doesNotMatch(html, /<button class="top-nav-link" type="button">Settings<\/button>/);
    assert.doesNotMatch(html, /<button class="top-nav-link" type="button">Profile<\/button>/);
    assert.doesNotMatch(html, /header-intro-sub/);
});

test("brand uses typography-first wordmark without AI badge icon", () => {
    assert.match(html, /<span class="logo-text">CortexAI<\/span>/);
    assert.doesNotMatch(html, /class="logo-icon"/);
});

test("floating compact header bar is removed from html, css, and script logic", () => {
    assert.doesNotMatch(html, /id="compactBar"/);
    assert.doesNotMatch(html, /id="compactModelInfo"/);
    assert.doesNotMatch(html, /id="cBtnSingle"/);
    assert.doesNotMatch(html, /id="cBtnCompare"/);
    assert.doesNotMatch(html, /id="compactSendBtn"/);

    assert.doesNotMatch(appJs, /compactBar/);
    assert.doesNotMatch(appJs, /compactModelInfo/);
    assert.doesNotMatch(appJs, /cBtnSingle/);
    assert.doesNotMatch(appJs, /cBtnCompare/);
    assert.doesNotMatch(appJs, /compactSendBtn/);
    assert.doesNotMatch(appJs, /updateCompactBar/);
    assert.doesNotMatch(appJs, /getCompactBadges/);

    assert.doesNotMatch(styleCss, /\.compact-bar/);
    assert.doesNotMatch(styleCss, /\.compact-model-info/);
    assert.doesNotMatch(styleCss, /\.compact-mode-btn/);
    assert.doesNotMatch(styleCss, /\.compact-send-btn/);
});

test("response cards hide price and latency while history keeps cost only", () => {
    assert.doesNotMatch(appJs, /Est\. Cost/);
    assert.doesNotMatch(appJs, /Est\. cost/);
    assert.doesNotMatch(appJs, /response-cost-/);
    assert.doesNotMatch(appJs, /response-latency-/);
    assert.doesNotMatch(appJs, /Latency:/);
    assert.doesNotMatch(appJs, /history-token-text/);
    assert.doesNotMatch(appJs, /Tokens: \$\{tokStr\}/);
    assert.match(appJs, /history-cost-text/);
});

test("history sidebar cards render compact timestamp and cost metadata", () => {
    assert.match(appJs, /function formatHistoryDateTime\(value, now = new Date\(\)\) \{/);
    assert.match(appJs, /Today, \$\{timeLabel\}/);
    assert.match(appJs, /Yesterday, \$\{timeLabel\}/);
    assert.match(appJs, /class="history-timestamp"/);
    assert.match(appJs, /<span class="history-cost-text">Usage: \$\{escHtml\(totalCostLabel \|\| "-"\)\}<\/span>/);
    assert.match(styleCss, /\.history-entry \{[\s\S]*padding: 8px 10px 7px;[\s\S]*margin-bottom: 6px;/);
    assert.match(styleCss, /\.history-prompt \{[\s\S]*-webkit-line-clamp: 2;/);
    assert.match(styleCss, /\.history-entry\.is-active-session \{[^}]*background: rgba\(255, 255, 255, \.96\);[^}]*box-shadow: none;/);
    assert.doesNotMatch(styleCss, /\.history-entry\.is-active-session \{[^}]*linear-gradient/);
    assert.match(styleCss, /\.history-list::-webkit-scrollbar \{[\s\S]*width: 6px;/);
});

test("ask and compare modes default Web toggle to enabled", () => {
    assert.match(appJs, /let askResearchModeEnabled = true;/);
    assert.match(appJs, /let compareResearchModeEnabled = true;/);
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

test("composer shows explicit stop control during streaming", () => {
    assert.match(appJs, /function handlePrimaryComposerAction\(\) \{/);
    assert.match(appJs, /stopActiveGeneration\(\);/);
    assert.match(appJs, /setComposerRequestState\("connecting"\)/);
    assert.match(appJs, /const streamRequest = beginActiveStreamRequest\(\);/);
    assert.match(
        appJs,
        /function setComposerRequestState\(nextState\) \{[\s\S]*renderComposerActionButtons\(\);[\s\S]*updateSendButtonState\(\);[\s\S]*\}/,
    );
    assert.match(appJs, /Stop generating/);
    assert.match(styleCss, /\.btn-submit\.is-stop \{/);
    assert.match(styleCss, /\.stop-icon \{/);
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
    assert.match(appJs, /class="message-footer\$\{compactClass\}"/);
    assert.match(appJs, /buildResponseFooter\(index, summary, resp\.token_usage, webSources, \{ compact: compareView \}\)/);
    assert.doesNotMatch(appJs, /message-details/);
    assert.match(styleCss, /\.message-footer \{/);
    assert.match(styleCss, /\.message-footer-meta \{/);
    assert.match(styleCss, /\.response-token-usage \{/);
    assert.doesNotMatch(styleCss, /\.chat-bubble-ai:hover \.response-actions,/);
    assert.match(styleCss, /\.response-action-rail \{[\s\S]*--response-action-size: 32px;[\s\S]*gap: 12px;[\s\S]*padding: 0;[\s\S]*border: 0;[\s\S]*background: transparent;[\s\S]*box-shadow: none;/);
    assert.match(styleCss, /\.response-action-btn \{[\s\S]*width: var\(--response-action-size, 32px\);[\s\S]*height: var\(--response-action-size, 32px\);/);
    assert.match(styleCss, /\.response-action-btn svg \{[\s\S]*width: var\(--response-action-icon-size, 17px\);/);
    assert.match(styleCss, /\.response-action-rail \.web-source-toggle \{[\s\S]*background: transparent;/);
    assert.match(styleCss, /\.response-action-btn:active \{[\s\S]*transform: scale\(\.96\);/);
    assert.match(styleCss, /\.response-action-group \+ \.response-action-group \{/);
    assert.match(styleCss, /margin-left: 0;/);
    assert.doesNotMatch(styleCss, /\.response-action-rail \{[\s\S]*background: rgba\(248, 250, 252, \.86\);/);
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

test("new streaming turns reveal only from latest position and do not auto-follow streamed text", () => {
    assert.match(appJs, /function syncStreamViewportDuringStream\(\) \{/);
    assert.match(appJs, /const shouldRevealLatest = el\.resultsSection\.classList\.contains\("hidden"\) \|\| isNearStreamingBottom\(\);/);
    assert.match(appJs, /if \(shouldRevealLatest\) \{[\s\S]*scheduleScrollResultsToBottom\(\{ behavior: "smooth", followUpDelayMs: 96 \}\);/);
    assert.match(appJs, /function appendStreamLine\(index, text\) \{[\s\S]*renderStreamingMarkdown\(key\);/);
    assert.match(appJs, /function renderStreamingMarkdown\(index\) \{[\s\S]*syncStreamViewportDuringStream\(\);/);
    assert.match(appJs, /setStreamAutoScrollPaused\(!streamState\.shouldRevealLatest && !isNearStreamingBottom\(\)\);/);
    assert.match(appJs, /streamAutoScrollEnabled = true;/);
    const syncStart = appJs.indexOf("function syncStreamViewportDuringStream()");
    const syncEnd = appJs.indexOf("function finishStreamingViewportControls", syncStart);
    assert.ok(syncStart > 0);
    assert.ok(syncEnd > syncStart);
    assert.doesNotMatch(appJs.slice(syncStart, syncEnd), /scrollResultsToBottom/);
});

test("streaming keeps the floating jump control removed", () => {
    assert.doesNotMatch(html, /id="jumpToLatestBtn"/);
    assert.doesNotMatch(html, /class="jump-to-latest/);
    assert.doesNotMatch(html, /aria-label="Jump to latest"/);
    assert.doesNotMatch(styleCss, /\.jump-to-latest\b/);
    assert.doesNotMatch(appJs, /jumpToLatestBtn/);
    assert.doesNotMatch(appJs, /updateJumpToLatestVisibility/);
    assert.match(appJs, /let streamAutoScrollPausedByUser = false;/);
    assert.match(appJs, /const STREAM_USER_SCROLL_INTENT_MS = 900;/);
    assert.match(appJs, /function markStreamUserScrollIntent\(event = null\) \{/);
    assert.match(appJs, /function isNearStreamingBottom\(\) \{[\s\S]*isDocumentNearBottom\(\) && isResultsSectionNearBottom\(\);/);
    assert.match(appJs, /function handleUserScrollDuringStream\(\) \{[\s\S]*streamScrollProgrammatic && !hasRecentStreamUserScrollIntent\(\)[\s\S]*const latestBelowViewport = !isNearStreamingBottom\(\);[\s\S]*setStreamAutoScrollPaused\(latestBelowViewport\);/);
    assert.match(appJs, /window\.addEventListener\("wheel", markStreamUserScrollIntent, \{ passive: true \}\);/);
    assert.match(appJs, /function finishStreamingViewportControls\(\) \{[\s\S]*if \(!streamAutoScrollPausedByUser\) \{/);
    assert.match(appJs, /function renderCompareSummary\(data\) \{[\s\S]*syncStreamViewportDuringStream\(\);/);
});

test("historical transcripts render persisted web source citations", () => {
    assert.match(appJs, /const webSourceItems = normalizeWebSources\(entry\.web_source_items \|\| \[\]\);/);
    assert.match(appJs, /const webSources = normalizeWebSources\(resp\.web_source_items \|\| \[\]\);/);
    assert.match(appJs, /class="web-source-strip\$\{safeSources\.length > 0 \? "" : " hidden"\}" id="response-sources-\$\{index\}" aria-label="Resources"/);
});

test("composer supports attachment upload chips and request wiring", () => {
    assert.match(html, /id="attachmentInput"/);
    assert.match(html, /id="attachmentStrip"/);
    assert.match(html, /id="attachmentList"/);
    assert.match(html, /id="attachmentHint"/);
    assert.match(appJs, /function ensureComposerInputsInteractive\(\) \{/);
    assert.match(appJs, /el\.promptAddBtn\.disabled = false;/);
    assert.match(appJs, /const hasAnyAttachments = attachmentItems\.length > 0;/);
    assert.match(appJs, /const disabled = stopMode \? false : !\(hasPrompt \|\| hasAnyAttachments\);/);
    assert.match(appJs, /if \(!rawPrompt && !hasAnyAttachments\) \{/);
    assert.match(appJs, /const clearComposerAttachments = \(\) => \{/);
    assert.match(appJs, /onBeforeRequestSend: clearComposerAttachments,/);
    assert.match(appJs, /buildRequestAttachmentPayload\(\)/);
    assert.match(appJs, /\/v1\/files\/upload/);
    assert.match(appJs, /\.\.\.\(attachments\.length \? \{ attachments \} : \{\}\),/);
    assert.match(appJs, /function getUserFriendlyUploadError\(error\) \{/);
    assert.match(appJs, /function sanitizeUploadError\(apiError\) \{/);
    assert.match(appJs, /const safeErrorMessage = isFailed \? getSafeAttachmentItemErrorMessage\(item\) : "";/);
    assert.doesNotMatch(appJs, /escHtml\(String\(item\.error_message \|\| ""\)\)/);
});

test("composer enter key submits while shift+enter keeps newline", () => {
    assert.match(
        appJs,
        /el\.promptInput\.addEventListener\("keydown", e => \{[\s\S]*if \(e\.key !== "Enter"\) return;[\s\S]*if \(e\.isComposing \|\| e\.keyCode === 229\) return;[\s\S]*if \(e\.shiftKey\) return;[\s\S]*e\.preventDefault\(\);[\s\S]*handlePrimaryComposerAction\(\);[\s\S]*\}\);/,
    );
    assert.doesNotMatch(appJs, /if \(e\.key === "Enter" && \(e\.ctrlKey \|\| e\.metaKey\)\)/);
});

test("user transcript can render file cards for sent attachments", () => {
    assert.match(appJs, /function buildUserAttachmentCards\(attachments\) \{/);
    assert.match(appJs, /const source = item\?\.payload && typeof item\.payload === "object" \? item\.payload : item;/);
    assert.match(appJs, /class="chat-user-files"/);
    assert.match(appJs, /class="user-file-card is-\$\{escHtml\(status\)\}"/);
    assert.match(appJs, /class="\$\{thumbClass\}"/);
    assert.match(appJs, /class="user-file-thumb-img"/);
    assert.match(appJs, /getAttachmentCardStatusLabel\(status\)/);
    assert.match(styleCss, /\.chat-user-files \{/);
    assert.match(styleCss, /\.user-file-card \{/);
    assert.match(styleCss, /\.user-file-card:hover \{/);
    assert.match(styleCss, /\.user-file-thumb \{/);
    assert.match(styleCss, /\.user-file-status \{/);
});

test("attachment compatibility treats text-extractable files as model-agnostic", () => {
    assert.match(appJs, /const TEXT_MATERIALIZED_ATTACHMENT_MIME_TYPES = new Set\(\[/);
    assert.match(
        appJs,
        /if \(binaryAttachments\.length === 0\) \{[\s\S]*return true;[\s\S]*\}/,
    );
    assert.match(appJs, /maxCount !== null && binaryAttachments\.length > maxCount/);
    assert.match(
        appJs,
        /binaryAttachments\.every\(item => supportedMimeTypes\.has\(normalizeAttachmentMimeType\(item\.mime_type\)\)\)/,
    );
});

test("composer remains interactive when submit button is disabled", () => {
    assert.match(appJs, /function ensureComposerInputsInteractive\(\) \{/);
    assert.match(
        appJs,
        /function ensureComposerInputsInteractive\(\) \{[\s\S]*el\.promptInput\.disabled = false;[\s\S]*el\.promptInput\.readOnly = false;[\s\S]*el\.promptAddBtn\.disabled = false;/,
    );
    assert.match(styleCss, /\.btn-submit:disabled \{[\s\S]*pointer-events:\s*none;/);
    assert.match(styleCss, /#promptAddBtn \{[\s\S]*pointer-events:\s*auto !important;/);
    assert.match(styleCss, /#promptInput \{[\s\S]*pointer-events:\s*auto !important;/);
    assert.match(styleCss, /\.prompt-card \{[\s\S]*z-index:\s*320;/);
});

test("model picker options show internal model names without capability badges", () => {
    assert.match(appJs, /model-picker-option-secondary/);
    assert.match(styleCss, /\.model-picker-option-secondary \{/);
    assert.doesNotMatch(appJs, /model-picker-option-badge/);
    assert.doesNotMatch(styleCss, /\.model-picker-option-badge \{/);
    assert.doesNotMatch(appJs, /Vision/);
});

test("compare model picker dropdowns use wide clamped smart positioning", () => {
    assert.match(appJs, /const COMPARE_MODEL_PICKER_DESKTOP_WIDTH = 400;/);
    assert.match(appJs, /const MODEL_PICKER_VIEWPORT_PADDING = 16;/);
    assert.match(appJs, /function getCompareModelPickerAlignment\(selectEl\) \{/);
    assert.match(appJs, /function positionCompareModelPickerMenu\(picker, buttonRect, viewportWidth\) \{/);
    assert.match(appJs, /wrapper\.classList\.add\("compare-model-picker"\);/);
    assert.match(
        styleCss,
        /\.model-picker\.compare-model-picker \.model-picker-menu \{[\s\S]*width:\s*min\(400px,\s*calc\(100vw - 32px\)\);/,
    );
    assert.match(styleCss, /\.model-picker-option-label \{[\s\S]*white-space:\s*normal;/);
});

test("compare model remove controls are compact circular icon buttons", () => {
    assert.match(styleCss, /\.toolbar-compare-slot \{[\s\S]*display:\s*inline-flex;[\s\S]*position:\s*relative;/);
    assert.match(styleCss, /\.compare-remove-model-btn \{[\s\S]*position:\s*absolute;[\s\S]*top:\s*-5px;[\s\S]*right:\s*-5px;[\s\S]*width:\s*19px;[\s\S]*height:\s*19px;[\s\S]*border-radius:\s*50%;/);
    assert.match(styleCss, /\.compare-remove-model-btn \{[\s\S]*background-color:\s*rgba\(255, 255, 255, \.96\);[\s\S]*color:\s*rgba\(71, 85, 105, \.66\);/);
    assert.match(styleCss, /\.compare-remove-model-btn \{[\s\S]*opacity:\s*0;[\s\S]*pointer-events:\s*none;[\s\S]*transform:\s*scale\(\.94\);/);
    assert.match(styleCss, /\.toolbar-compare-slot:hover \.compare-remove-model-btn:not\(:disabled\),[\s\S]*\.toolbar-compare-slot:focus-within \.compare-remove-model-btn:not\(:disabled\),[\s\S]*\.compare-remove-model-btn:focus-visible \{[\s\S]*opacity:\s*\.86;[\s\S]*transform:\s*scale\(1\);/);
    assert.match(styleCss, /\.compare-remove-model-btn:hover:not\(:disabled\) \{[\s\S]*background-color:\s*rgba\(255, 241, 242, \.98\);[\s\S]*color:\s*#BE123C;[\s\S]*transform:\s*scale\(1\.05\);/);
    assert.match(styleCss, /\.compare-remove-model-btn:focus-visible \{[\s\S]*box-shadow:\s*0 0 0 3px rgba\(244, 63, 94, \.18\)/);
    assert.match(styleCss, /\.compare-remove-model-btn:disabled \{[\s\S]*cursor:\s*default;[\s\S]*opacity:\s*0;/);
    assert.match(styleCss, /\.toolbar-compare-slot\.is-removing \{[\s\S]*opacity:\s*0;[\s\S]*transform:\s*scale\(\.98\);/);
    assert.match(appJs, /const isVisible = Boolean\(selectEl\) && canRemove;/);
    assert.match(appJs, /function animateCompareRemoval\(button, slotIndex\) \{[\s\S]*slotEl\.classList\.add\("is-removing"\);[\s\S]*removeCompareSlot\(slotIndex\);/);
});

test("assistant markdown pipeline supports gfm tables with wide-table handling", () => {
    assert.match(appJs, /const GFM_TABLE_DELIMITER_RE =/);
    assert.match(appJs, /function renderMarkdownToHtml\(markdownText, options = \{\}\) \{/);
    assert.match(appJs, /function renderMarkdownTable\(lines, startIndex, options = \{\}\) \{/);
    assert.match(appJs, /function applyWideTableLayout\(containerEl\) \{/);
    assert.match(appJs, /const responseHtml = hasError[\s\S]*renderResponseErrorHtml\(resp\.error\)[\s\S]*renderMarkdownToHtml\(text, \{ citationPrefix: responseCitationPrefix\(index\) \}\);/);
    assert.match(appJs, /renderResponseMarkdown\(textEl, text, \{ hasError, error: resp\.error \}\);/);
    assert.match(appJs, /<div class="response-text hidden" id="response-text-\$\{index\}" data-empty="true"><\/div>/);
    assert.match(appJs, /<div class="response-text \$\{responseClasses\}" id="response-text-\$\{index\}">\$\{responseHtml\}<\/div>/);
});

test("response enhancer assets are loaded and wired", () => {
    assert.match(html, /<link rel="stylesheet" href="llm-response\.css\?v=/);
    assert.match(html, /<script src="llm-response\.js\?v=/);
    assert.doesNotMatch(html, /id="themeToggle"/);
    assert.doesNotMatch(appJs, /installThemeToggle/);
    assert.match(appJs, /window\.LLMResponse\.installCopyDelegate\(el\.resultsGrid\);/);
    assert.match(appJs, /window\.LLMResponse\.enhanceResponseDom\(targetEl\);/);
    assert.match(llmResponseJs, /global\.LLMResponse = \{/);
    assert.doesNotMatch(llmResponseJs, /installThemeToggle/);
    assert.match(llmResponseCss, /\.response-text \.llm-code-copy \{/);
    assert.doesNotMatch(llmResponseCss, /\.theme-toggle/);
});

test("assistant markdown preserves explicit ordered-list numbering", () => {
    assert.match(appJs, /const itemMatch = \/\^\(\\d\+\)\\\.\\s\+\(\.\*\)\$\/\.exec\(current\);/);
    assert.match(appJs, /const startAttr = Number\.isSafeInteger\(firstValue\) && firstValue !== 1[\s\S]*start="\$\{firstValue\}"/);
    assert.match(appJs, /const valueAttr = Number\.isSafeInteger\(item\.value\) \? ` value="\$\{item\.value\}"` : "";/);
    assert.match(appJs, /<span class="llm-ol-num" aria-hidden="true">\$\{num\}<\/span><span class="llm-ol-text">\$\{renderInlineMarkdown\(item\.text, options\)\}<\/span>/);
});

test("inline citations map to response-scoped source chip targets", () => {
    assert.match(appJs, /function responseCitationPrefix\(index\) \{/);
    assert.match(appJs, /function responseCitationTargetId\(index, citationNumber\) \{/);
    assert.match(appJs, /id="\$\{escHtml\(citationId\)\}"/);
    assert.match(appJs, /buildWebSourceChipsHtml\(safeSources, index\)/);
    assert.match(appJs, /renderMarkdownToHtml\(text, \{ citationPrefix: responseCitationPrefix\(index\) \}\)/);
    assert.match(appJs, /citationPrefix: citationPrefixFromResponseElement\(targetEl\)/);
    assert.match(appJs, /const citationLink = event\.target\.closest\("\.llm-cite"\);/);
    assert.match(appJs, /setSourceStripExpanded\(sourceStrip, true\);/);
});

test("final markdown rendering clears streaming cursor before success or error output", () => {
    assert.match(appJs, /function renderResponseMarkdown\(targetEl, text, \{ hasError = false, error = null \} = \{\}\) \{[\s\S]*targetEl\.removeAttribute\("data-streaming"\);[\s\S]*if \(hasError\) \{/);
});

test("assistant markdown renderer preserves loose ordered-list indexes at runtime", () => {
    const snippetStart = appJs.indexOf("function escHtml");
    const snippetEnd = appJs.indexOf("function shouldStackTableForChat", snippetStart);
    assert.ok(snippetStart > 0);
    assert.ok(snippetEnd > snippetStart);

    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(
        `${appJs.slice(snippetStart, snippetEnd)}
globalThis.__html = renderMarkdownToHtml([
    "1. First cited point [1].",
    "Context after the first point.",
    "",
    "2. Second cited point [2].",
    "Context after the second point.",
    "",
    "4. Fourth cited point [4].",
].join("\\n"));`,
        sandbox,
    );

    assert.match(sandbox.__html, /<ol><li value="1"><span class="llm-ol-num" aria-hidden="true">1<\/span><span class="llm-ol-text">First cited point<a href="#cite-1" class="llm-cite" data-cite="1" aria-label="Citation 1">1<\/a>\.<\/span><\/li><\/ol>/);
    assert.match(sandbox.__html, /<ol start="2"><li value="2"><span class="llm-ol-num" aria-hidden="true">2<\/span><span class="llm-ol-text">Second cited point<a href="#cite-2" class="llm-cite" data-cite="2" aria-label="Citation 2">2<\/a>\.<\/span><\/li><\/ol>/);
    assert.match(sandbox.__html, /<ol start="4"><li value="4"><span class="llm-ol-num" aria-hidden="true">4<\/span><span class="llm-ol-text">Fourth cited point<a href="#cite-4" class="llm-cite" data-cite="4" aria-label="Citation 4">4<\/a>\.<\/span><\/li><\/ol>/);
});

test("assistant markdown renderer supports citation groups and callouts", () => {
    const snippetStart = appJs.indexOf("function escHtml");
    const snippetEnd = appJs.indexOf("function shouldStackTableForChat", snippetStart);
    assert.ok(snippetStart > 0);
    assert.ok(snippetEnd > snippetStart);

    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(
        `${appJs.slice(snippetStart, snippetEnd)}
globalThis.__html = renderMarkdownToHtml([
    "Evidence [1] [2].",
    "",
    "> [!TIP] Review",
    "> Use the source list [1].",
].join("\\n"), { citationPrefix: "response-7" });`,
        sandbox,
    );

    assert.match(sandbox.__html, /Evidence<a href="#cite-response-7-1" class="llm-cite" data-cite="1" aria-label="Citation 1">1<\/a><a href="#cite-response-7-2" class="llm-cite" data-cite="2" aria-label="Citation 2">2<\/a>\./);
    assert.match(sandbox.__html, /<aside class="llm-callout llm-callout-tip" role="note">/);
    assert.match(sandbox.__html, /<div class="llm-callout-title">Review<\/div>/);
    assert.match(sandbox.__html, /Use the source list<a href="#cite-response-7-1" class="llm-cite" data-cite="1" aria-label="Citation 1">1<\/a>\./);
});

test("streaming uses a buffered progressive markdown render before final cleanup", () => {
    assert.match(appJs, /const streamResponseBuffers = new Map\(\);/);
    assert.match(appJs, /const STREAM_MARKDOWN_RENDER_DEBOUNCE_MS = 120;/);
    assert.match(appJs, /function normalizeStreamingMarkdownPreview\(rawText\) \{/);
    assert.match(appJs, /function scheduleStreamingMarkdownRender\(index\) \{/);
    assert.match(appJs, /function renderStreamingMarkdown\(index\) \{[\s\S]*renderMarkdownToHtml\(previewText, \{[\s\S]*citationPrefix: citationPrefixFromResponseElement\(textEl\),/);
    assert.match(appJs, /function appendStreamLine\(index, text\) \{[\s\S]*streamResponseBuffers\.set\(key, previousText \+ chunk\);[\s\S]*scheduleStreamingMarkdownRender\(key\);/);
    assert.doesNotMatch(appJs, /textEl\.textContent \+= text;/);
    assert.match(appJs, /function readStreamedResponseText\(index\) \{[\s\S]*streamResponseBuffers\.has\(key\)/);
    assert.match(appJs, /function clearStreamingRenderState\(index\) \{/);
    assert.match(appJs, /function finalizeStreamCard\(index, resp\) \{[\s\S]*renderResponseMarkdown\(textEl, text, \{ hasError, error: resp\.error \}\);/);
    assert.match(appJs, /function finalizeStreamCard\(index, resp\) \{[\s\S]*clearStreamingRenderState\(index\);[\s\S]*renderResponseMarkdown\(textEl, text, \{ hasError, error: resp\.error \}\);/);
    assert.match(appJs, /const text = explicitText\.trim\(\) \|\| \(hasError \? getResponseErrorDisplayText\(resp\.error\) : "\(empty response\)"\);/);
    assert.match(appJs, /applyResponseErrorClasses\(textEl, resp\.error\);/);
});

test("model response errors use soft amber model-down styling", () => {
    assert.match(styleCss, /\.model-soft-error \{[\s\S]*margin: 24px 16px;[\s\S]*padding: 16px 18px;[\s\S]*border-radius: 16px;[\s\S]*border: 1px solid #FDE68A;[\s\S]*background: linear-gradient\(180deg, #FFFBEB 0%, #FEF3C7 100%\);[\s\S]*color: #92400E;[\s\S]*font-size: \.92rem;[\s\S]*line-height: 1\.55;[\s\S]*font-style: normal;/);
    assert.match(styleCss, /\.model-soft-error-title \{[\s\S]*font-weight: 650;[\s\S]*margin-bottom: 4px;/);
    assert.match(styleCss, /\.model-soft-error-body \{[\s\S]*color: #A16207;/);
    assert.match(appJs, /function getModelSoftErrorParts\(errorLike\) \{/);
    assert.match(appJs, /title: "This model is temporarily busy\.",/);
    assert.match(appJs, /body: "Try again shortly or switch to another model\.",/);
    assert.match(styleCss, /\.chat-message-ai\.is-error \.chat-bubble-ai \{[\s\S]*background: #FFFFFF;[\s\S]*box-shadow: none;/);
});

test("markdown table css adds overflow wrapper, cell wrapping, and stacked layout", () => {
    assert.match(styleCss, /\.response-table-wrap \{/);
    assert.match(styleCss, /overflow-x: auto;/);
    assert.match(styleCss, /\.response-text table \{/);
    assert.match(styleCss, /\.response-text thead \{/);
    assert.match(styleCss, /\.response-text th,[\s\S]*\.response-text td \{/);
    assert.match(styleCss, /word-break: break-word;/);
    assert.match(styleCss, /\.response-text table\.is-stacked td::before \{/);
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
