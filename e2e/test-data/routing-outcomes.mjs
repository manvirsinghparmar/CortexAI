/**
 * Allowed routing envelopes for the live routing-boundary spec.
 *
 * These are intentionally provider-level rather than exact model snapshots so the
 * test stays resilient when routing policy evolves or a provider rotates models.
 */
export const routingBoundaryScenarios = [
    {
        id: "coding",
        prompt: "Review this backend bug: an async retry loop duplicates writes. Explain the root cause, propose a safer design, and include a short corrected Python example.",
        allowedProviders: ["openai", "claude", "deepseek"],
    },
    {
        id: "analysis",
        prompt: "Compare the tradeoffs between fast response time, model quality, and operating cost in a smart-routing system. Use short headings and concrete recommendations.",
        allowedProviders: ["openai", "claude", "gemini", "grok"],
    },
    {
        id: "creative",
        prompt: "Write a short launch note that makes a complex developer tool sound approachable without losing technical credibility.",
        allowedProviders: ["grok", "gemini", "claude", "openai"],
    },
];
