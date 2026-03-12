/** Resolve and cache E2E-only configuration from env files. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const e2eRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(e2eRoot, "..");

let loaded = false;
let cachedConfig = null;

function loadEnvFile(filePath) {
    if (!fs.existsSync(filePath)) return;
    dotenv.config({ path: filePath });
}

/** Load E2E-local env files once so every helper sees the same resolved values. */
export function loadE2EEnv() {
    if (loaded) return;

    loadEnvFile(path.join(e2eRoot, ".env"));
    loadEnvFile(path.join(e2eRoot, ".env.local"));
    loaded = true;
}

function readBool(name, defaultValue = false) {
    const raw = process.env[name];
    if (raw == null || raw === "") return defaultValue;
    return ["1", "true", "yes", "on"].includes(String(raw).trim().toLowerCase());
}

function readInt(name, defaultValue) {
    const raw = process.env[name];
    if (raw == null || raw === "") return defaultValue;
    const value = Number.parseInt(String(raw), 10);
    return Number.isFinite(value) ? value : defaultValue;
}

function requireEnv(name) {
    const value = String(process.env[name] || "").trim();
    if (!value) {
        throw new Error(`Missing required E2E environment variable: ${name}`);
    }
    return value;
}

function normalizeUrl(value) {
    return String(value || "").trim().replace(/\/+$/, "");
}

/**
 * Return the shared config object used across setup, fixtures, helpers, and teardown.
 * The object is cached intentionally so every part of the suite uses one consistent view.
 */
export function getE2EConfig() {
    if (cachedConfig) return cachedConfig;

    loadE2EEnv();

    const liveEnabled = readBool("E2E_LIVE_ENABLED", false);
    if (!liveEnabled) {
        throw new Error("E2E_LIVE_ENABLED must be true to run the live CortexAI E2E suite.");
    }

    const host = String(process.env.E2E_HOST || "127.0.0.1").trim();
    const port = readInt("E2E_PORT", 8010);
    const baseUrl = normalizeUrl(process.env.E2E_BASE_URL || `http://${host}:${port}`);
    const apiBaseUrl = baseUrl;
    const apiKey = requireEnv("E2E_API_KEY");
    const databaseUrl = requireEnv("E2E_DATABASE_URL");
    const dbSchema = String(process.env.E2E_DB_SCHEMA || "public").trim() || "public";

    cachedConfig = {
        repoRoot,
        e2eRoot,
        runtimeDir: path.join(e2eRoot, ".runtime"),
        host,
        port,
        baseUrl,
        apiBaseUrl,
        apiKey,
        databaseUrl,
        dbSchema,
        loadRootDotenv: readBool("E2E_LOAD_ROOT_DOTENV", true),
        enableFaultInjection: readBool("E2E_ENABLE_FAULT_INJECTION", true),
        timeouts: {
            serverStartMs: readInt("E2E_SERVER_START_TIMEOUT_MS", 90_000),
            discoveryMs: readInt("E2E_DISCOVERY_TIMEOUT_MS", 30_000),
            frontendReadyMs: readInt("E2E_FRONTEND_READY_TIMEOUT_MS", 30_000),
            firstContentMs: readInt("E2E_FIRST_CONTENT_TIMEOUT_MS", 45_000),
            askMs: readInt("E2E_ASK_TIMEOUT_MS", 180_000),
            compareMs: readInt("E2E_COMPARE_TIMEOUT_MS", 240_000),
            historyRestoreMs: readInt("E2E_HISTORY_RESTORE_TIMEOUT_MS", 20_000),
            fallbackMs: readInt("E2E_FALLBACK_TIMEOUT_MS", 120_000),
        },
    };

    return cachedConfig;
}