import { expect, expectNoHorizontalOverflow, test } from "../fixtures/responsive-e2e.mjs";

test("mobile Usage route renders the compact dashboard and footer navigation", async ({
    responsiveApp,
}) => {
    const { page } = responsiveApp;

    await page.goto("/usage");
    await expect(page.getByRole("heading", { name: "Usage & insights" })).toBeVisible();

    const visibleTitle = await page.locator("main h1").evaluate(element =>
        Array.from(element.children)
            .filter(child => window.getComputedStyle(child).display !== "none")
            .map(child => child.textContent?.trim())
            .join(""),
    );
    expect(visibleTitle).toBe("Usage");

    await expect(page.getByText("TOKENS", { exact: true })).toBeVisible();
    await expect(page.getByText("TOTAL TOKENS", { exact: true })).toBeHidden();
    await expect(page.getByText("AVG COST", { exact: true })).toBeVisible();
    await expect(page.getByText("$12.16 total", { exact: true })).toBeVisible();
    await expect(page.getByText("720 via Smart", { exact: true })).toBeVisible();
    await expect(page.getByText("1,336 total", { exact: true })).toBeHidden();
    await expect(page.getByText(/top Smart pick/)).toBeVisible();
    await expect(page.getByText("GPT-5.4 Mini").first()).toBeVisible();
    await expect(page.locator("#usage-activity-title")).toBeHidden();

    const modelList = page.locator('[aria-label="Models that replied list"]');
    const modelListMetrics = await modelList.evaluate(element => {
        const style = window.getComputedStyle(element);
        return {
            overflowX: style.overflowX,
            overflowY: style.overflowY,
            scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight,
        };
    });
    expect(modelListMetrics.overflowX).toBe("hidden");
    expect(modelListMetrics.overflowY).toBe("auto");
    expect(modelListMetrics.scrollHeight).toBeGreaterThan(modelListMetrics.clientHeight);

    const mobileNav = page.getByRole("navigation", { name: "Mobile navigation" });
    await expect(mobileNav).toBeVisible();
    await expect(mobileNav.getByRole("button", { name: "Ask" })).toBeVisible();
    await expect(mobileNav.getByRole("button", { name: "Compare" })).toBeVisible();
    await expect(mobileNav.getByRole("button", { name: "History" })).toBeVisible();

    await expectNoHorizontalOverflow(page);
});

test("mobile account menu exposes the Usage entry point", async ({ responsiveApp }) => {
    const { page } = responsiveApp;

    await page.goto("/");
    await page.getByRole("button", { name: "Guest account" }).click();
    await expect(page.getByRole("menuitem", { name: "Usage & insights" })).toBeVisible();
    await page.getByRole("menuitem", { name: "Usage & insights" }).click();

    await expect(page).toHaveURL(/\/usage$/);
    await expect(page.getByRole("heading", { name: "Usage & insights" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
});
