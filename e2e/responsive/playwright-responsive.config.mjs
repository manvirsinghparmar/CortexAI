import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const e2eRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function createResponsiveConfig({
    name,
    testDir,
    port,
    viewport,
}) {
    const baseURL = `http://127.0.0.1:${port}`;
    return defineConfig({
        testDir,
        fullyParallel: true,
        workers: process.env.CI ? 2 : undefined,
        retries: process.env.CI ? 1 : 0,
        timeout: 30_000,
        expect: {
            timeout: 8_000,
        },
        globalSetup: path.join(e2eRoot, "responsive", "global-setup.mjs"),
        metadata: {
            responsivePort: port,
        },
        outputDir: path.join(e2eRoot, "test-results", name),
        reporter: [
            ["list"],
            [
                "html",
                {
                    open: "never",
                    outputFolder: path.join(e2eRoot, "playwright-report", name),
                },
            ],
        ],
        use: {
            baseURL,
            viewport,
            screenshot: "only-on-failure",
            trace: "retain-on-failure",
            video: "retain-on-failure",
        },
    });
}
