/**
 * Tier A readiness smoke checks.
 *
 * This spec intentionally stays small: if this fails, the richer live scenarios are
 * not worth running because the app is not even ready for user interaction.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { ensureMode, setToggle } from "../helpers/ui.mjs";

test("app load and readiness", async ({ liveApp }) => {
    const { page } = liveApp;

    await expect(page.locator("#promptInput")).toBeVisible();
    await expect(page.locator("#desktopSidebar")).toBeVisible();
    await expect(page.locator("#btnSingleMode")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("alert")).toHaveCount(0);

    await setToggle(page, "#routeSmartBtn", false);
    const singleOptions = await page.locator("#singleModel option").count();
    await ensureMode(page, "compare");
    const compareOptions = await page.locator("#compareModel1 option").count();
    expect(singleOptions).toBeGreaterThan(0);
    expect(compareOptions).toBeGreaterThan(0);
});
