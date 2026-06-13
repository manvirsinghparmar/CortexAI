import {
    expect,
    expectNoHorizontalOverflow,
    openMobilePanel,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("desktop uses the sidebar and top mode navigation", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeHidden();
    await expect(page.locator("#btnSingleMode")).toBeVisible();
    await expect(page.locator("#promptInput")).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("desktop Compare picker remains visible and selectable", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.locator("#btnCompareMode").click();

    const connector = page.getByTestId("compare-connector");
    await expect(connector).toHaveCount(1);
    await expect(connector).toHaveCSS("width", "22px");
    await expect(connector).toHaveCSS("border-top-width", "1px");
    await expect(connector).toHaveCSS("border-radius", "999px");

    const connectorGeometry = await connector.evaluate(element => {
        const connectorRect = element.getBoundingClientRect();
        const firstModelRect = document.querySelector("#compareModel1Wrap")?.getBoundingClientRect();
        const secondModelRect = document.querySelector("#compareModel2Wrap")?.getBoundingClientRect();
        return {
            connectorCenter: connectorRect.left + connectorRect.width / 2,
            firstRight: firstModelRect?.right ?? 0,
            secondLeft: secondModelRect?.left ?? 0,
        };
    });
    expect(connectorGeometry.connectorCenter).toBeGreaterThan(connectorGeometry.firstRight);
    expect(connectorGeometry.connectorCenter).toBeLessThan(connectorGeometry.secondLeft);

    const select = page.locator("#compareModel2");
    const currentValue = await select.inputValue();
    const target = await select.locator("option:not(:disabled)").evaluateAll(
        (options, selectedValue) =>
            options.find(option => option.value !== selectedValue)?.value ?? "",
        currentValue,
    );
    expect(target).not.toBe("");

    await page.getByRole("button", { name: /Compare model 2:/ }).click();
    const listbox = page.getByRole("listbox", { name: "Compare model 2 options" });
    await expect(listbox).toBeVisible();
    await listbox.locator(`[role="option"]`).evaluateAll(
        (options, value) => {
            const targetOption = options.find(option => option.title?.includes(value.split(":").at(-1)));
            targetOption?.click();
        },
        target,
    );
    await expect(select).toHaveValue(target);
});

test("iPad landscape keeps the desktop workspace usable", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1024, height: 768 });

    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeVisible();
    await expect(page.locator("#btnSingleMode")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeHidden();
    const composerWidth = await page.locator("#promptInput").evaluate(element => {
        return element.parentElement?.parentElement?.getBoundingClientRect().width ?? 0;
    });
    expect(composerWidth).toBeLessThanOrEqual(860);
    await expectNoHorizontalOverflow(page);
});

test("iPad portrait switches to mobile navigation without overlap", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 820, height: 1180 });

    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    await openMobilePanel(page, "Compare");

    const metrics = await page.evaluate(() => {
        const textarea = document.querySelector("#promptInput");
        const composer = textarea?.parentElement?.parentElement?.parentElement;
        const nav = document.querySelector("nav[aria-label='Mobile navigation']");
        return {
            composerBottom: composer?.getBoundingClientRect().bottom ?? Number.POSITIVE_INFINITY,
            navTop: nav?.getBoundingClientRect().top ?? 0,
        };
    });
    expect(metrics.composerBottom).toBeLessThanOrEqual(metrics.navTop + 1);
    await expectNoHorizontalOverflow(page);
});
