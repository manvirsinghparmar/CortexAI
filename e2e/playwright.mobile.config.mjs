import { createResponsiveConfig } from "./responsive/playwright-responsive.config.mjs";

export default createResponsiveConfig({
    name: "mobile",
    testDir: "./responsive/mobile",
    port: 4173,
    viewport: { width: 390, height: 844 },
});
