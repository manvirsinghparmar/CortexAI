const DIAGNOSTICS_STORAGE_KEY = "cortex_client_diagnostics";
const LAST_UNLOAD_STORAGE_KEY = "cortex_last_page_unload";
const MAX_BUFFERED_EVENTS = 40;
const LONG_TASK_THRESHOLD_MS = 750;
const LONG_TASK_REPORT_INTERVAL_MS = 5000;
const PAGE_INSTANCE_ID = makePageInstanceId();

type DiagnosticDetails = Record<string, unknown>;

interface BufferedDiagnosticEvent {
  event: string;
  timestamp: string;
  page_instance_id: string;
  details: DiagnosticDetails;
}

// Attributes each app boot so production "blink/refresh" reports can be
// traced to a cause: user reload, Chrome tab discard, bfcache restore, or a
// plain navigation. `document.wasDiscarded` is the definitive discard signal.
export function logBootDiagnostics(): void {
  try {
    const navigation = performance.getEntriesByType("navigation")[0] as
      | PerformanceNavigationTiming
      | undefined;
    const wasDiscarded =
      (document as Document & { wasDiscarded?: boolean }).wasDiscarded ?? false;
    const lastUnload = readLastUnloadMarker();

    recordClientDiagnostic("boot", {
      navigationType: navigation?.type ?? "unknown",
      wasDiscarded,
      path: window.location.pathname,
      hasSearch: window.location.search.length > 0,
      searchKeys: Array.from(new URLSearchParams(window.location.search).keys()),
      referrerOrigin: safeOrigin(document.referrer),
      lastUnload,
    }, { flush: true });

    window.addEventListener("visibilitychange", () => {
      recordClientDiagnostic(
        "visibilitychange",
        { visibilityState: document.visibilityState },
        { flush: document.visibilityState === "hidden" },
      );
    });

    window.addEventListener("pageshow", (event) => {
      recordClientDiagnostic("pageshow", { persisted: event.persisted }, {
        flush: event.persisted,
      });
    });

    window.addEventListener("pagehide", (event) => {
      recordUnloadMarker("pagehide", { persisted: event.persisted });
      recordClientDiagnostic("pagehide", { persisted: event.persisted }, { flush: true });
    });

    window.addEventListener("beforeunload", () => {
      recordUnloadMarker("beforeunload", {});
      recordClientDiagnostic("beforeunload", {}, { flush: true });
    });

    window.addEventListener("error", (event) => {
      recordClientDiagnostic("error", {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      }, { flush: true });
    });

    window.addEventListener("unhandledrejection", (event) => {
      recordClientDiagnostic("unhandledrejection", {
        reason: reasonToString(event.reason),
      }, { flush: true });
    });

    installLongTaskObserver();
  } catch {
    // Diagnostics must never affect app startup.
  }
}

export function recordClientDiagnostic(
  event: string,
  details: DiagnosticDetails = {},
  options: { flush?: boolean } = {},
): void {
  try {
    const entry: BufferedDiagnosticEvent = {
      event,
      timestamp: new Date().toISOString(),
      page_instance_id: PAGE_INSTANCE_ID,
      details: sanitizeDetails(details),
    };
    const next = [...readBufferedEvents(), entry].slice(-MAX_BUFFERED_EVENTS);
    writeBufferedEvents(next);
    console.info("[cortex] diagnostic", entry);
    if (options.flush) {
      flushClientDiagnostics(event);
    }
  } catch {
    // Diagnostics must never affect app behavior.
  }
}

function flushClientDiagnostics(reason: string): void {
  const events = readBufferedEvents();
  if (events.length === 0) return;

  const payload = JSON.stringify({
    source: "react",
    reason,
    page_instance_id: PAGE_INSTANCE_ID,
    events,
  });

  const clearSent = () => {
    try {
      window.localStorage.removeItem(DIAGNOSTICS_STORAGE_KEY);
    } catch {
      // Ignore storage failures.
    }
  };

  try {
    if (navigator.sendBeacon) {
      const accepted = navigator.sendBeacon(
        "/v1/client-diagnostics",
        new Blob([payload], { type: "application/json" }),
      );
      if (accepted) clearSent();
      return;
    }

    void fetch("/v1/client-diagnostics", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).then((response) => {
      if (response.ok) clearSent();
    }).catch(() => undefined);
  } catch {
    // Keep the buffer for the next boot attempt.
  }
}

function installLongTaskObserver(): void {
  const PerformanceObserverCtor = window.PerformanceObserver;
  if (!PerformanceObserverCtor) return;
  const supported = PerformanceObserverCtor.supportedEntryTypes ?? [];
  if (!supported.includes("longtask")) return;

  let lastReportAt = 0;
  const observer = new PerformanceObserverCtor((list) => {
    const longTasks = list
      .getEntries()
      .filter((entry) => entry.duration >= LONG_TASK_THRESHOLD_MS);
    if (longTasks.length === 0) return;

    const now = Date.now();
    if (now - lastReportAt < LONG_TASK_REPORT_INTERVAL_MS) return;
    lastReportAt = now;
    const maxDurationMs = Math.round(
      Math.max(...longTasks.map((entry) => entry.duration)),
    );
    recordClientDiagnostic("longtask", {
      count: longTasks.length,
      maxDurationMs,
    });
  });

  observer.observe({ entryTypes: ["longtask"] });
}

function readBufferedEvents(): BufferedDiagnosticEvent[] {
  try {
    const raw = window.localStorage.getItem(DIAGNOSTICS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter(isBufferedEvent) : [];
  } catch {
    return [];
  }
}

function writeBufferedEvents(events: BufferedDiagnosticEvent[]): void {
  try {
    window.localStorage.setItem(DIAGNOSTICS_STORAGE_KEY, JSON.stringify(events));
  } catch {
    // Ignore storage quota or privacy-mode failures.
  }
}

function isBufferedEvent(value: unknown): value is BufferedDiagnosticEvent {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.event === "string" &&
    typeof record.timestamp === "string" &&
    typeof record.page_instance_id === "string" &&
    typeof record.details === "object" &&
    record.details !== null
  );
}

function recordUnloadMarker(event: string, details: DiagnosticDetails): void {
  try {
    window.localStorage.setItem(
      LAST_UNLOAD_STORAGE_KEY,
      JSON.stringify({
        event,
        timestamp: new Date().toISOString(),
        page_instance_id: PAGE_INSTANCE_ID,
        details: sanitizeDetails(details),
      }),
    );
  } catch {
    // Ignore storage failures.
  }
}

function readLastUnloadMarker(): unknown {
  try {
    const raw = window.localStorage.getItem(LAST_UNLOAD_STORAGE_KEY);
    window.localStorage.removeItem(LAST_UNLOAD_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function sanitizeDetails(details: DiagnosticDetails): DiagnosticDetails {
  return sanitizeValue(details, 0) as DiagnosticDetails;
}

function sanitizeValue(value: unknown, depth: number): unknown {
  if (depth > 3) return "[truncated]";
  if (value === null || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") return value.slice(0, 500);
  if (Array.isArray(value)) {
    return value.slice(0, 10).map((item) => sanitizeValue(item, depth + 1));
  }
  if (typeof value === "object") {
    const output: DiagnosticDetails = {};
    for (const [key, item] of Object.entries(value).slice(0, 25)) {
      output[key.slice(0, 80)] = sanitizeValue(item, depth + 1);
    }
    return output;
  }
  return String(value).slice(0, 200);
}

function makePageInstanceId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function safeOrigin(url: string): string {
  if (!url) return "";
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

function reasonToString(reason: unknown): string {
  if (reason instanceof Error) {
    return `${reason.name}: ${reason.message}`;
  }
  if (typeof reason === "string") return reason;
  return String(reason);
}
