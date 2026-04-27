// Copy this file to runtime-config.js for static-only hosting (e.g. scripts/serve_frontend.py).
// When frontend is served by FastAPI (SERVE_FRONTEND=true), /runtime-config.js is generated dynamically.
window.CORTEX_RUNTIME_CONFIG = {
    apiBase: "http://127.0.0.1:8000",
    enableDevSessionLogin: true,
    // devSessionLoginToken: "optional-local-dev-token",
};
