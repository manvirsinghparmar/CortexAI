import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const htmlPath = path.join(process.cwd(), "frontend", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");
const appJsPath = path.join(process.cwd(), "frontend", "app.js");
const appJs = fs.readFileSync(appJsPath, "utf8");

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
    assert.match(appJs, /<span>Tokens: \$\{tokStr\}<\/span>/);
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
