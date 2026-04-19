/**
 * Playwright configuration for the live Cortex E2E suite.
 *
 * The suite is intentionally serial and resource-heavy because it talks to the
 * real FastAPI app, shared Postgres state, and live model providers.
 */
import { defineConfig } from "@playwright/test";

import { getE2EConfig } from "./helpers/config.mjs";

const config = getE2EConfig();
const reporters = process.env.CI
    ? [
        ["github"],
        ["list"],
        ["junit", { outputFile: "test-results/junit.xml" }],
        ["html", { open: "never", outputFolder: "playwright-report" }],
    ]
    : [
        ["list"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
    ];

export default defineConfig({
    testDir: "./specs",
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 2 : 0,
    timeout: Math.max(config.timeouts.compareMs, config.timeouts.askMs) + 60_000,
    expect: {
        timeout: process.env.CI ? 15_000 : 8_000,
    },
    globalSetup: "./global-setup.mjs",
    globalTeardown: "./global-teardown.mjs",
    reporter: reporters,
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
