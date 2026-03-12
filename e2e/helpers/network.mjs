/** Browser-side request recorder used for request-id tracing and fault injection. */
function nowIso() {
    return new Date().toISOString();
}

/**
 * Capture every `/v1/*` browser request with a deterministic request id.
 * The recorder also injects optional test-only fault headers for fallback specs.
 */
export function createNetworkRecorder({ apiBaseUrl, runId, caseId }) {
    const requestMeta = new WeakMap();
    const entries = [];
    let counter = 0;
    let nextFault = null;

    function nextRequestId() {
        counter += 1;
        return `e2e-${runId}-${caseId}-${counter}`;
    }

    function shouldApplyFault(requestUrl) {
        if (!nextFault) return false;
        if (!requestUrl.startsWith(`${apiBaseUrl}/v1/`)) return false;
        if (!nextFault.pathContains) return true;
        return requestUrl.includes(nextFault.pathContains);
    }

    return {
        entries,
        /** Arm one request-scoped fault. It is consumed automatically unless configured otherwise. */
        armFault(spec, { pathContains = "/chat/stream", consume = true } = {}) {
            nextFault = { spec, pathContains, consume };
        },
        countByPath(pathFragment) {
            return entries.filter(entry => entry.url.includes(pathFragment)).length;
        },
        findByPath(pathFragment) {
            return entries.filter(entry => entry.url.includes(pathFragment));
        },
        /** Attach routing and response listeners to a Playwright browser context. */
        async attach(context) {
            await context.route(`${apiBaseUrl}/v1/**`, async route => {
                const request = route.request();
                const requestId = nextRequestId();
                const headers = {
                    ...request.headers(),
                    "X-Request-ID": requestId,
                };

                let appliedFault = null;
                if (shouldApplyFault(request.url())) {
                    appliedFault = nextFault.spec;
                    headers["X-E2E-Fault"] = appliedFault;
                    if (nextFault.consume) {
                        nextFault = null;
                    }
                }

                const entry = {
                    requestId,
                    method: request.method(),
                    url: request.url(),
                    postData: request.postData() || null,
                    startedAt: nowIso(),
                    fault: appliedFault,
                    status: null,
                    responseRequestId: null,
                    finishedAt: null,
                    durationMs: null,
                    failed: false,
                    failureText: null,
                };
                requestMeta.set(request, entry);
                entries.push(entry);

                await route.continue({ headers });
            });

            context.on("response", async response => {
                const entry = requestMeta.get(response.request());
                if (!entry) return;
                entry.status = response.status();
                entry.responseRequestId = response.headers()["x-request-id"] || null;
                entry.finishedAt = nowIso();
                entry.durationMs = Math.max(
                    0,
                    new Date(entry.finishedAt).getTime() - new Date(entry.startedAt).getTime(),
                );
            });

            context.on("requestfailed", request => {
                const entry = requestMeta.get(request);
                if (!entry) return;
                entry.failed = true;
                entry.failureText = request.failure()?.errorText || "request_failed";
                entry.finishedAt = nowIso();
                entry.durationMs = Math.max(
                    0,
                    new Date(entry.finishedAt).getTime() - new Date(entry.startedAt).getTime(),
                );
            });
        },
    };
}