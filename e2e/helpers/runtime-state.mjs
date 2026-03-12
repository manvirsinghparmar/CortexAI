/** Persist shared run metadata inside `e2e/.runtime` for setup, fixtures, and teardown. */
import fs from "node:fs/promises";
import path from "node:path";

export function getRunStatePath(config) {
    return path.join(config.runtimeDir, "run-state.json");
}

export function getCaseRegistryPath(config) {
    return path.join(config.runtimeDir, "case-registry.json");
}

export async function ensureRuntimeDir(config) {
    await fs.mkdir(config.runtimeDir, { recursive: true });
}

/** Store worker-shared run metadata such as run id, owner id, and server pid. */
export async function writeRunState(config, payload) {
    await ensureRuntimeDir(config);
    await fs.writeFile(getRunStatePath(config), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

export async function readRunState(config) {
    const raw = await fs.readFile(getRunStatePath(config), "utf8");
    return JSON.parse(raw);
}

/** Store per-case runtime facts so teardown can clean up even after a crash. */
export async function writeCaseRegistry(config, payload) {
    await ensureRuntimeDir(config);
    await fs.writeFile(getCaseRegistryPath(config), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

export async function readCaseRegistry(config) {
    try {
        const raw = await fs.readFile(getCaseRegistryPath(config), "utf8");
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

/** Upsert one case entry instead of appending duplicates for retries or reruns. */
export async function recordCaseRuntime(config, payload) {
    const existing = await readCaseRegistry(config);
    const next = [
        ...existing.filter(entry => !(entry.caseId === payload.caseId && entry.seededSessionId === payload.seededSessionId)),
        payload,
    ];
    await writeCaseRegistry(config, next);
}