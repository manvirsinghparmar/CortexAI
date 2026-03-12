/**
 * Playwright configuration for the live Cortex E2E suite.
 *
 * The suite is intentionally serial and resource-heavy because it talks to the
 * real FastAPI app, shared Postgres state, and live model providers.
 */
import { defineConfig } from "@playwright/test";

import { getE2EConfig } from "./helpers/config.mjs";

const config = getE2EConfig();

export default defineConfig({
    testDir: "./specs",
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    timeout: Math.max(config.timeouts.compareMs, config.timeouts.askMs) + 60_000,
    globalSetup: "./global-setup.mjs",
    globalTeardown: "./global-teardown.mjs",
    reporter: [
        ["list"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
    ],
    use: {
        baseURL: config.baseUrl,
        viewport: null,
        launchOptions: {
            // Running headed with a maximized window makes local debugging match
            // the real desktop layout more closely than a fixed viewport.
            args: ["--start-maximized"],
        },
        screenshot: "only-on-failure",
        trace: "retain-on-failure",
        video: "retain-on-failure",
    },
});
