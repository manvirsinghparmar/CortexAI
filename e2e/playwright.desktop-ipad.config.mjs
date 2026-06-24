import { createResponsiveConfig } from "./responsive/playwright-responsive.config.mjs";

export default createResponsiveConfig({
    name: "desktop-ipad",
    testDir: "./responsive/desktop-ipad",
    port: 4174,
    viewport: { width: 1440, height: 900 },
});
