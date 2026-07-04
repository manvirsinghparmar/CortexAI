import { beforeEach, describe, expect, it } from "vitest";
import {
  ACTIVE_SESSION_STORAGE_KEY,
  FRESH_LOGIN_PENDING_STORAGE_KEY,
  clearActiveSessionId,
  consumeFreshLoginSessionReset,
  loadActiveSessionId,
  markFreshLoginPending,
  persistActiveSessionId,
} from "../session/activeSession";

describe("active session persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("persists, normalizes, and clears the active session id", () => {
    persistActiveSessionId("  SESSION-ABC  ");

    expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe("session-abc");
    expect(loadActiveSessionId()).toBe("session-abc");

    clearActiveSessionId();

    expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBeNull();
    expect(loadActiveSessionId()).toBeNull();
  });

  it("migrates a single legacy mode-specific active session id", () => {
    window.localStorage.setItem("cortex_active_session_id_single", "SESSION-LEGACY");
    window.localStorage.setItem("cortex_active_session_id_compare", "session-legacy");

    expect(loadActiveSessionId()).toBe("session-legacy");

    persistActiveSessionId(loadActiveSessionId());

    expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe("session-legacy");
    expect(window.localStorage.getItem("cortex_active_session_id_single")).toBeNull();
    expect(window.localStorage.getItem("cortex_active_session_id_compare")).toBeNull();
  });

  it("clears the active session only for an explicit fresh-login callback", () => {
    persistActiveSessionId("session-1");
    markFreshLoginPending();
    window.history.replaceState({}, "", "/?fresh_login=1");

    expect(consumeFreshLoginSessionReset()).toBe(true);

    expect(loadActiveSessionId()).toBeNull();
    expect(window.localStorage.getItem(FRESH_LOGIN_PENDING_STORAGE_KEY)).toBeNull();
    expect(window.location.search).toBe("");
  });

  it("keeps the active session for a callback marker without explicit login intent", () => {
    persistActiveSessionId("session-1");
    window.history.replaceState({}, "", "/?fresh_login=1");

    expect(consumeFreshLoginSessionReset()).toBe(false);

    expect(loadActiveSessionId()).toBe("session-1");
    expect(window.location.search).toBe("");
  });
});
