import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const htmlPath = path.join(process.cwd(), "frontend", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");

test("dedicated smart routing card is removed", () => {
    assert.doesNotMatch(html, /routing-card/);
    assert.doesNotMatch(html, /singleRoutingSubtitle/);
    assert.doesNotMatch(html, /id="panelSingle"/);
});

test("checkbox-based manual model opt-in is removed", () => {
    assert.doesNotMatch(html, /singleModelOptIn/);
});

test("compact composer toolbar contains smart and model controls", () => {
    assert.match(html, /id="composerToolbar"/);
    assert.match(html, /id="routeSmartBtn"/);
    assert.match(html, /id="singleModelWrap"/);
    assert.match(html, /id="singleModel"/);
    assert.match(html, /class="toolbar-model-group hidden"/);
});

test("toolbar keeps compact research and optimizer controls", () => {
    assert.doesNotMatch(html, /route-pill-group/);
    assert.match(html, /id="routeOptimizeBtn"/);
    assert.match(html, /id="routeResearchBtn"/);
});
