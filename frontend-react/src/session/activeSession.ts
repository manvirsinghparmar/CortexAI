export const ACTIVE_SESSION_STORAGE_KEY = "cortex_active_session_id";
export const FRESH_LOGIN_PENDING_STORAGE_KEY = "cortex_fresh_login_pending";
export const FRESH_LOGIN_QUERY_PARAM = "fresh_login";

const LEGACY_MODE_SESSION_STORAGE_KEYS = [
  "cortex_active_session_id_single",
  "cortex_active_session_id_compare",
];

export function normalizeSessionId(value: unknown): string | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  return normalized || null;
}

export function loadActiveSessionId(): string | null {
  const storage = getLocalStorage();
  if (!storage) return null;

  const current = normalizeSessionId(readStorageValue(storage, ACTIVE_SESSION_STORAGE_KEY));
  if (current) return current;

  const legacyValues = LEGACY_MODE_SESSION_STORAGE_KEYS.map((key) =>
    normalizeSessionId(readStorageValue(storage, key)),
  ).filter(Boolean);
  const uniqueLegacyValues = [...new Set(legacyValues)];
  return uniqueLegacyValues.length === 1 ? uniqueLegacyValues[0]! : null;
}

export function persistActiveSessionId(sessionId: string | null | undefined): void {
  const storage = getLocalStorage();
  if (!storage) return;

  const normalized = normalizeSessionId(sessionId);
  if (!normalized) {
    removeStorageValue(storage, ACTIVE_SESSION_STORAGE_KEY);
    LEGACY_MODE_SESSION_STORAGE_KEYS.forEach((key) => removeStorageValue(storage, key));
    return;
  }

  writeStorageValue(storage, ACTIVE_SESSION_STORAGE_KEY, normalized);
  LEGACY_MODE_SESSION_STORAGE_KEYS.forEach((key) => removeStorageValue(storage, key));
}

export function clearActiveSessionId(): void {
  persistActiveSessionId(null);
}

export function markFreshLoginPending(): void {
  const storage = getLocalStorage();
  if (!storage) return;
  writeStorageValue(storage, FRESH_LOGIN_PENDING_STORAGE_KEY, "1");
}

export function clearFreshLoginPending(): void {
  const storage = getLocalStorage();
  if (!storage) return;
  removeStorageValue(storage, FRESH_LOGIN_PENDING_STORAGE_KEY);
}

export function consumeFreshLoginSessionReset(): boolean {
  const marker = readFreshLoginMarker();
  if (!marker) return false;

  clearFreshLoginQueryParam();
  const pending = isFreshLoginPending();
  clearFreshLoginPending();

  if (pending) {
    clearActiveSessionId();
    return true;
  }

  return false;
}

function isFreshLoginPending(): boolean {
  const storage = getLocalStorage();
  if (!storage) return false;
  return readStorageValue(storage, FRESH_LOGIN_PENDING_STORAGE_KEY) === "1";
}

function readFreshLoginMarker(): boolean {
  if (typeof window === "undefined") return false;

  try {
    const url = new URL(window.location.href);
    return url.searchParams.get(FRESH_LOGIN_QUERY_PARAM) === "1";
  } catch {
    return false;
  }
}

function clearFreshLoginQueryParam(): void {
  if (typeof window === "undefined") return;

  try {
    const url = new URL(window.location.href);
    url.searchParams.delete(FRESH_LOGIN_QUERY_PARAM);
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState(window.history.state, document.title, nextUrl || "/");
  } catch {
    // Query cleanup is a UX nicety; session state has already been resolved.
  }
}

function getLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readStorageValue(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorageValue(storage: Storage, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // The app still works for this page view if storage is unavailable.
  }
}

function removeStorageValue(storage: Storage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    // The app still works for this page view if storage is unavailable.
  }
}
