(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.CortexSmartRoutingState = api;
    }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    function parseKey(key) {
        const raw = String(key || "");
        const idx = raw.indexOf(":");
        if (idx < 0) return { provider: "", model: raw };
        return { provider: raw.slice(0, idx), model: raw.slice(idx + 1) };
    }

    function hasSelectedModelKey(key) {
        return !!parseKey(key).provider;
    }

    function deriveSmartModeFromSelection(key) {
        return !hasSelectedModelKey(key);
    }

    function isManualOverrideActive(mode, smartModeEnabled, key) {
        return mode === "single" && !smartModeEnabled && hasSelectedModelKey(key);
    }

    function isManualSelectionPending(mode, smartModeEnabled, key) {
        return mode === "single" && !smartModeEnabled && !hasSelectedModelKey(key);
    }

    function isModelDropdownVisible(mode, smartModeEnabled) {
        return mode === "single" && !smartModeEnabled;
    }

    function resolveManualSelection(selectedKey, fallbackKey) {
        return hasSelectedModelKey(selectedKey) ? String(selectedKey || "") : String(fallbackKey || "");
    }

    return {
        parseKey,
        hasSelectedModelKey,
        deriveSmartModeFromSelection,
        isManualOverrideActive,
        isManualSelectionPending,
        isModelDropdownVisible,
        resolveManualSelection,
    };
});
