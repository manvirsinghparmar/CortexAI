/* ══════════════════════════════════════════════════════════════════════
   LLM Response enhancer
   --------------------------------------------------------------------
   - Wraps <pre><code> blocks into a .llm-code container with header
     and copy button (idempotent, safe to call on streamed renders).
   - Lazily loads highlight.js (CDN) to syntax-highlight code blocks.
     The page renders fine without it — highlighting is progressive.
   - Installs a single click delegate for .llm-code-copy buttons.

   No module bundler is used — this script exposes window.LLMResponse
   and is loaded as a classic script tag.
   ══════════════════════════════════════════════════════════════════════ */

(function (global) {
    "use strict";

    /* ── Highlight.js CDN config ─────────────────────────────────── */
    var HLJS_VERSION = "11.10.0";
    var HLJS_BASE = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/" + HLJS_VERSION;
    var HLJS_SCRIPT = HLJS_BASE + "/highlight.min.js";
    var HLJS_THEME_LIGHT = HLJS_BASE + "/styles/github.min.css";
    var HLJS_THEME_DARK = HLJS_BASE + "/styles/github-dark.min.css";

    var hljsLoadPromise = null;
    var hljsThemeApplied = false;

    function currentThemeIsDark() {
        var explicit = document.documentElement.getAttribute("data-theme");
        if (explicit === "dark") return true;
        if (explicit === "light") return false;
        return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    }

    function ensureHljsTheme() {
        // Insert both light & dark stylesheets up front; we toggle the
        // disabled flag based on the current theme so the swap is instant.
        if (!hljsThemeApplied) {
            ["light", "dark"].forEach(function (variant) {
                var link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = variant === "dark" ? HLJS_THEME_DARK : HLJS_THEME_LIGHT;
                link.dataset.hljsTheme = variant;
                document.head.appendChild(link);
            });
            hljsThemeApplied = true;
        }
        var dark = currentThemeIsDark();
        document.querySelectorAll("link[data-hljs-theme]").forEach(function (link) {
            link.disabled = (link.dataset.hljsTheme === "dark") !== dark;
        });
    }

    function loadHighlightJs() {
        if (global.hljs) return Promise.resolve(global.hljs);
        if (hljsLoadPromise) return hljsLoadPromise;
        hljsLoadPromise = new Promise(function (resolve) {
            ensureHljsTheme();
            var s = document.createElement("script");
            s.src = HLJS_SCRIPT;
            s.async = true;
            s.onload = function () { resolve(global.hljs || null); };
            s.onerror = function () { resolve(null); };
            document.head.appendChild(s);
        });
        return hljsLoadPromise;
    }

    /* ── Code block enhancement ──────────────────────────────────── */
    function languageOf(codeEl) {
        var match = (codeEl.className || "").match(/language-([\w-]+)/i);
        return match ? match[1].toLowerCase() : "";
    }

    function enhanceCodeBlocks(rootEl) {
        if (!rootEl) return;
        var pres = rootEl.querySelectorAll("pre");
        pres.forEach(function (pre) {
            if (pre.parentElement && pre.parentElement.classList.contains("llm-code")) return;

            var code = pre.querySelector("code");
            var lang = code ? languageOf(code) : "";

            var figure = document.createElement("figure");
            figure.className = "llm-code";

            var header = document.createElement("figcaption");
            header.className = "llm-code-header";

            var langEl = document.createElement("span");
            langEl.className = "llm-code-lang";
            langEl.textContent = lang || "text";
            header.appendChild(langEl);

            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "llm-code-copy";
            btn.setAttribute("aria-label", "Copy code to clipboard");
            btn.textContent = "Copy";
            header.appendChild(btn);

            pre.parentNode.insertBefore(figure, pre);
            figure.appendChild(header);
            figure.appendChild(pre);
        });

        if (rootEl.querySelector("pre")) {
            loadHighlightJs().then(function (hljs) {
                if (!hljs) return;
                ensureHljsTheme();
                rootEl.querySelectorAll("pre code").forEach(function (code) {
                    if (code.dataset.hljsApplied === "1") return;
                    try { hljs.highlightElement(code); } catch (_) { /* noop */ }
                    code.dataset.hljsApplied = "1";
                });
            });
        }
    }

    /* ── Copy-to-clipboard delegate ──────────────────────────────── */
    function copyText(text) {
        if (!text) return Promise.resolve(false);
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return false; });
        }
        try {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.setAttribute("readonly", "");
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            var ok = document.execCommand("copy");
            document.body.removeChild(ta);
            return Promise.resolve(ok);
        } catch (_) {
            return Promise.resolve(false);
        }
    }

    function installCopyDelegate(rootEl) {
        if (!rootEl || rootEl.dataset.llmCopyBound === "1") return;
        rootEl.dataset.llmCopyBound = "1";
        rootEl.addEventListener("click", function (event) {
            var btn = event.target.closest && event.target.closest(".llm-code-copy");
            if (!btn || !rootEl.contains(btn)) return;
            var figure = btn.closest(".llm-code");
            var code = figure && figure.querySelector("pre code");
            var text = code ? code.textContent : "";
            copyText(text).then(function (ok) {
                btn.classList.toggle("is-copied", !!ok);
                btn.textContent = ok ? "Copied" : "Copy failed";
                setTimeout(function () {
                    btn.classList.remove("is-copied");
                    btn.textContent = "Copy";
                }, 1500);
            });
        });
    }

    if (window.matchMedia) {
        try {
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
                if (hljsThemeApplied) ensureHljsTheme();
            });
        } catch (_) { /* Safari < 14 */ }
    }

    /* ── Public API ──────────────────────────────────────────────── */
    function enhanceResponseDom(rootEl) {
        if (!rootEl) return;
        enhanceCodeBlocks(rootEl);
    }

    global.LLMResponse = {
        enhanceResponseDom: enhanceResponseDom,
        installCopyDelegate: installCopyDelegate,
    };
})(window);
