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

    console.info("[cortex] boot", {
      navigationType: navigation?.type ?? "unknown",
      wasDiscarded,
    });

    window.addEventListener("pageshow", (event) => {
      if (event.persisted) {
        console.info("[cortex] restored from back/forward cache");
      }
    });
  } catch {
    // Diagnostics must never affect app startup.
  }
}
