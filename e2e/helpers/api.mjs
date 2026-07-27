/** Thin HTTP helpers for the live E2E suite. */
import { setTimeout as delay } from "node:timers/promises";

const sessionCookies = new Map();

/** Wrap fetches in an AbortController so retries fail fast with clear timeout errors. */
function withTimeout(signal, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error(`Timed out after ${timeoutMs}ms`)), timeoutMs);
    if (signal) {
        signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
    }
    return {
        signal: controller.signal,
        dispose() {
            clearTimeout(timer);
        },
    };
}

/** Fetch JSON-like data and surface response bodies in thrown errors for easier debugging. */
export async function fetchJson(url, { method = "GET", headers = {}, body, timeoutMs = 15_000 } = {}) {
    const timeout = withTimeout(null, timeoutMs);
    try {
        const response = await fetch(url, {
            method,
            headers,
            body,
            signal: timeout.signal,
        });
        const text = await response.text();
        let parsed = null;
        try {
            parsed = text ? JSON.parse(text) : null;
        } catch (_) {
            parsed = text;
        }
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} for ${url}: ${typeof parsed === "string" ? parsed : JSON.stringify(parsed)}`);
        }
        return parsed;
    } finally {
        timeout.dispose();
    }
}

/** Poll an endpoint until it becomes healthy or the configured budget expires. */
export async function waitForJson(url, { headers = {}, timeoutMs = 30_000, intervalMs = 500 } = {}) {
    const deadline = Date.now() + timeoutMs;
    let lastError = null;
    while (Date.now() < deadline) {
        try {
            return await fetchJson(url, { headers, timeoutMs: Math.min(intervalMs * 2, 5_000) });
        } catch (error) {
            lastError = error;
            await delay(intervalMs);
        }
    }
    throw lastError || new Error(`Timed out waiting for ${url}`);
}

/** Mint and cache the local-only session cookie required by browser-scoped routes. */
export async function getSessionCookie(config) {
    const cacheKey = config.apiBaseUrl;
    const cached = sessionCookies.get(cacheKey);
    if (cached) return cached;

    const timeout = withTimeout(null, config.timeouts.discoveryMs);
    try {
        const response = await fetch(`${config.apiBaseUrl}/v1/auth/dev-login`, {
            method: "POST",
            headers: {
                "X-Dev-Login-Token": config.devSessionLoginToken,
            },
            signal: timeout.signal,
        });
        const body = await response.text();
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} for /v1/auth/dev-login: ${body}`);
        }

        const setCookie = response.headers.get("set-cookie") || "";
        const match = setCookie.match(/cortex_session=([^;]+)/i);
        if (!match) {
            throw new Error("Dev login succeeded without returning a cortex_session cookie.");
        }

        const cookie = `cortex_session=${match[1]}`;
        sessionCookies.set(cacheKey, cookie);
        return cookie;
    } finally {
        timeout.dispose();
    }
}

/** Return headers for routes that require identity-backed session auth. */
export async function getSessionHeaders(config) {
    return { Cookie: await getSessionCookie(config) };
}

/** Resolve the stable E2E owner identity created by the dev session. */
export async function getWhoAmI(config) {
    return fetchJson(`${config.apiBaseUrl}/v1/whoami`, {
        headers: await getSessionHeaders(config),
        timeoutMs: config.timeouts.discoveryMs,
    });
}

export async function getProviderCatalog(config) {
    return fetchJson(`${config.apiBaseUrl}/v1/providers`, {
        headers: await getSessionHeaders(config),
        timeoutMs: config.timeouts.discoveryMs,
    });
}

/** List history entries, optionally narrowed to a single backend session. */
export async function listHistory(config, { limit = 500, sessionId = null } = {}) {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (sessionId) {
        params.set("session_id", String(sessionId));
    }
    return fetchJson(`${config.apiBaseUrl}/v1/history?${params.toString()}`, {
        headers: await getSessionHeaders(config),
        timeoutMs: config.timeouts.discoveryMs,
    });
}

/** Best-effort delete used during E2E cleanup. Missing rows are treated as already-clean. */
export async function deleteHistoryEntry(config, entryId) {
    const response = await fetch(`${config.apiBaseUrl}/v1/history/${entryId}`, {
        method: "DELETE",
        headers: await getSessionHeaders(config),
    });
    if (!response.ok && response.status !== 404) {
        throw new Error(`Failed to delete history entry ${entryId}: HTTP ${response.status}`);
    }
}
