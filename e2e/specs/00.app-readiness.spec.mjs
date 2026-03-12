/**
 * Tier A readiness smoke checks.
 *
 * This spec intentionally stays small: if this fails, the richer live scenarios are
 * not worth running because the app is not even ready for user interaction.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";

test("app load and readiness", async ({ liveApp }) => {
    const { page } = liveApp;

    await expect(page.locator("#promptInput")).toBeVisible();
    await expect(page.locator("#historySidebar")).toBeVisible();
    await expect(page.locator("#btnSingleMode")).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#errorBanner")).toBeHidden();

    const singleOptions = await page.locator("#singleModel option").count();
    const compareOptions = await page.locator("#compareModel1 option").count();
    expect(singleOptions).toBeGreaterThan(0);
    expect(compareOptions).toBeGreaterThan(0);
});
