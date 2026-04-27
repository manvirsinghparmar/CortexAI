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

test("compare mode sends session context and preserves prompt history between turns", () => {
    assert.match(
        appJs,
        /async function doCompare\(prompt, \{[\s\S]*streamRequest = null,[\s\S]*attachments = \[\],[\s\S]*const sessionId = ensureActiveSessionId\(\);/,
    );
    assert.match(appJs, /await callAPIStream\("\/v1\/compare\/stream", \{[\s\S]*context: \{[\s\S]*session_id: sessionId,[\s\S]*conversation_history: conversationHistory,[\s\S]*new_session: pendingNewSession,/);
    assert.match(appJs, /const compareAssistantContext = buildCompareAssistantContext\(compareResponsesForContext\);/);
    assert.match(appJs, /renderCompareSummary\(comparePayload\);[\s\S]*conversationHistory\.push\(\{ role: "user", content: prompt \}\);[\s\S]*if \(compareAssistantContext\) \{[\s\S]*conversationHistory\.push\(\{ role: "assistant", content: compareAssistantContext \}\);/);
});

test("third compare slot prefers Claude Haiku defaults before generic fallback", () => {
    assert.match(appJs, /const COMPARE_THIRD_SLOT_PREFERRED_KEYS = \[/);
    assert.match(appJs, /"claude:claude-haiku-4-5"/);
    assert.match(appJs, /"claude:claude-sonnet-4-6"/);
    assert.match(appJs, /"claude:claude-sonnet-4-5"/);
    assert.match(appJs, /function appendPreferredCompareModels\(byKey, allowedProviders\) \{/);
    assert.match(appJs, /function pickCompareFallbackKey\(slotIndex, availableKeys, used\) \{/);
    assert.match(appJs, /return resolved\.map\(value => String\(value \|\| ""\)\);/);
    assert.match(appJs, /if \(slotIndex === 2\) \{[\s\S]*key\.startsWith\("claude:"\)/);
    assert.match(appJs, /el\.compareModel3\.value = pickCompareFallbackKey\(2, availableKeys, used\);/);
    assert.match(appJs, /const fallback = pickCompareFallbackKey\(index, availableKeys, used\);/);
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

test("history threads are grouped by shared session id and can surface mixed-mode turns", () => {
    assert.match(appJs, /function buildHistoryThreads\(data\) \{[\s\S]*const key = sessionId \? `session:\$\{sessionId\}` : `entry:\$\{entry\.id\}`;/);
    assert.match(appJs, /const normalizedModes = new Set\(entries\.map\(entry => normalizeHistoryModeLabel\(entry\.mode\)\)\);/);
    assert.match(appJs, /const modeLabel = normalizedModes\.size > 1[\s\S]*\? "mixed"/);
    assert.match(appJs, /const isActive = thread\.sessionId[\s\S]*thread\.sessionId === activeSessionId;/);
});

test("header keeps only slim nav links without subtitle block", () => {
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

test("model errors are sanitized before rendering on response cards", () => {
    assert.match(appJs, /function hasUnsafeModelErrorPayload\(rawMessage\)/);
    assert.match(appJs, /function fallbackModelErrorMessage\(error = \{\}\)/);
    assert.match(appJs, /function getModelErrorDisplayText\(resp\)/);
    assert.match(appJs, /const text = hasError \? getModelErrorDisplayText\(resp\) : \(resp\.text \|\| "\(empty response\)"\);/);
    assert.match(appJs, /const text = hasError[\s\S]*\? getModelErrorDisplayText\(resp\)/);
    assert.doesNotMatch(appJs, /Error: \$\{resp\.error\.message\}/);
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
    assert.match(appJs, /class="chat-user-files"/);
    assert.match(appJs, /class="user-file-card is-\$\{escHtml\(status\)\}"/);
    assert.match(appJs, /const statusLabel = status === "uploading"/);
    assert.match(styleCss, /\.chat-user-files \{/);
    assert.match(styleCss, /\.user-file-card \{/);
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

test("model picker options can render capability badges", () => {
    assert.match(appJs, /model-picker-option-badge/);
    assert.match(styleCss, /\.model-picker-option-badge \{/);
});

test("assistant markdown pipeline supports gfm tables with wide-table handling", () => {
    assert.match(appJs, /const GFM_TABLE_DELIMITER_RE =/);
    assert.match(appJs, /function renderMarkdownToHtml\(markdownText\) \{/);
    assert.match(appJs, /function renderMarkdownTable\(lines, startIndex\) \{/);
    assert.match(appJs, /function applyWideTableLayout\(containerEl\) \{/);
    assert.match(appJs, /const findNextNonEmptyLineIndex = \(startIndex\) => \{/);
    assert.match(
        appJs,
        /if \(!current\) \{[\s\S]*const nextIndex = findNextNonEmptyLineIndex\(index \+ 1\);[\s\S]*index = nextIndex;[\s\S]*continue;[\s\S]*\}/,
    );
    assert.match(appJs, /const startAttr = startNumber > 1 \? ` start="\$\{startNumber\}"` : "";/);
    assert.match(appJs, /const responseHtml = hasError \? escHtml\(text\) : renderMarkdownToHtml\(text\);/);
    assert.match(appJs, /renderResponseMarkdown\(textEl, text, \{ hasError \}\);/);
    assert.match(appJs, /<div class="response-text hidden" id="response-text-\$\{index\}" data-empty="true"><\/div>/);
    assert.match(appJs, /<div class="response-text \$\{hasError \? "error-text" : ""\}" id="response-text-\$\{index\}">\$\{responseHtml\}<\/div>/);
});

test("streaming still appends raw chunks before final markdown rendering", () => {
    assert.match(appJs, /function appendStreamLine\(index, text\) \{[\s\S]*textEl\.textContent \+= text;/);
    assert.match(appJs, /function finalizeStreamCard\(index, resp\) \{[\s\S]*renderResponseMarkdown\(textEl, text, \{ hasError \}\);/);
    assert.match(appJs, /const text = hasError[\s\S]*\? getModelErrorDisplayText\(resp\)[\s\S]*: \(explicitText\.trim\(\) \|\| "\(empty response\)"\);/);
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
