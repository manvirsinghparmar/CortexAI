/**
 * Shared prompt catalog for live E2E coverage.
 *
 * The prompts intentionally ask for multi-part answers so the UI has enough
 * streamed content to verify incremental rendering instead of a one-line burst.
 */
import { appendCaseMarker } from "./ids.mjs";

export function withMarker(prompt, { runId, caseId }) {
    return appendCaseMarker(prompt, runId, caseId);
}

export const promptLibrary = {
    smartAsk: "Explain the tradeoffs between async I/O and multithreading in Python. Use 8 bullet points grouped under four short headings, then end with a 2-sentence conclusion.",
    webResearch: "Find the latest public AI policy updates and answer with 5 dated bullet points, then 3 source-backed highlights with citations, then a short takeaway.",
    noWebFollowUp: "Now explain the same topic from memory only, without browsing or citing sources, in six clear sentences.",
    optimizer: "Turn this rough note into a polished request for a backend architect: need safer retries db consistency and fewer flaky failures.",
    refresh: "Summarize how request tracing works in a streaming API with 6 bullet points plus a short example timeline.",
    historyA: "Thread A: explain how smart routing fallback works in one paragraph.",
    historyB: "Thread B: explain how session persistence works in one paragraph.",
    historyFollowUp: "Continue thread A with one extra paragraph about why audit telemetry matters.",
    tokensOne: "Give me five bullet points on how prompt optimization affects API latency and quality.",
    tokensTwo: "Now add three more bullet points focused on observability and failure analysis.",
    compare: "Compare the pros and cons of optimistic retries versus hard fail-fast behavior in backend orchestration. Use 5 short titled sections and a final recommendation.",
    fallback: "Write an 8-point explanation of how a routing system should recover after the first provider fails, followed by a brief conclusion.",
};