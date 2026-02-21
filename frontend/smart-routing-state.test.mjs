import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const SmartRoutingState = require("./smart-routing-state.js");

test("smart routing defaults to on when no model is selected", () => {
    const smartOn = SmartRoutingState.deriveSmartModeFromSelection("");
    assert.equal(smartOn, true);
    assert.equal(SmartRoutingState.isModelDropdownVisible("single", smartOn), false);
    assert.equal(
        SmartRoutingState.isManualOverrideActive("single", smartOn, ""),
        false
    );
});

test("smart off shows model dropdown and defaults to chatgpt when empty", () => {
    const fallback = "openai:gpt-4o";
    assert.equal(SmartRoutingState.isModelDropdownVisible("single", false), true);
    assert.equal(
        SmartRoutingState.resolveManualSelection("", fallback),
        fallback
    );
});

test("selecting a model switches into manual override", () => {
    const key = "openai:gpt-4o";
    const smartOn = SmartRoutingState.deriveSmartModeFromSelection(key);
    assert.equal(smartOn, false);
    assert.equal(
        SmartRoutingState.isManualOverrideActive("single", smartOn, key),
        true
    );
    assert.equal(
        SmartRoutingState.isManualSelectionPending("single", smartOn, key),
        false
    );
    assert.equal(
        SmartRoutingState.resolveManualSelection(key, "openai:gpt-4o"),
        key
    );
});

test("compare mode never enters single manual override states", () => {
    const key = "gemini:gemini-2.5-flash";
    assert.equal(
        SmartRoutingState.isModelDropdownVisible("compare", false),
        false
    );
    assert.equal(
        SmartRoutingState.isManualOverrideActive("compare", false, key),
        false
    );
    assert.equal(
        SmartRoutingState.isManualSelectionPending("compare", false, ""),
        false
    );
});
