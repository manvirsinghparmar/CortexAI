import {
    expect,
    expectNoHorizontalOverflow,
    openMobilePanel,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("mobile navigation switches between Ask, Compare, and History", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    const mobileNav = page.getByRole("navigation", { name: "Mobile navigation" });

    await expect(mobileNav).toBeVisible();
    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeHidden();
    await expect(page.locator("#btnSingleMode")).toBeHidden();
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "What would you like help with today?",
    );

    await openMobilePanel(page, "Compare");
    await expect(page.getByLabel("Compare model selectors")).toBeVisible();
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask once and compare model responses",
    );

    await openMobilePanel(page, "History");
    await expect(page.getByRole("region", { name: "History" })).toBeVisible();
    await expect(page.locator("#promptInput")).toHaveCount(0);

    await openMobilePanel(page, "Ask");
    await expect(page.locator("#promptInput")).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

for (const viewport of [
    { width: 320, height: 568 },
    { width: 390, height: 844 },
]) {
    test(`mobile composer clears bottom navigation at ${viewport.width}px`, async ({ responsiveApp }) => {
        const { page } = responsiveApp;
        await page.setViewportSize(viewport);

        const metrics = await composerMetrics(page);
        expect(metrics.composerBottom).toBeLessThanOrEqual(metrics.navTop + 1);
        expect(metrics.sendVisible).toBe(true);
        expect(metrics.textareaFontSize).toBeGreaterThanOrEqual(16);
        expect(metrics.textareaHeight).toBeGreaterThanOrEqual(44);
        await expectNoHorizontalOverflow(page);
    });
}

test("mobile composer auto-grows and keeps Send accessible", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    const textarea = page.locator("#promptInput");
    await textarea.fill(Array.from({ length: 18 }, (_, index) => `Line ${index + 1}`).join("\n"));

    await expect.poll(async () => {
        return textarea.evaluate(element => ({
            height: element.getBoundingClientRect().height,
            overflowY: getComputedStyle(element).overflowY,
        }));
    }).toMatchObject({
        height: 160,
        overflowY: "auto",
    });

    const metrics = await composerMetrics(page);
    expect(metrics.composerBottom).toBeLessThanOrEqual(metrics.navTop + 1);
    expect(metrics.sendVisible).toBe(true);
    await expectNoHorizontalOverflow(page);
});

test("mobile attachment chips stay inside the composer without narrowing input", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    const textarea = page.locator("#promptInput");
    const widthBefore = await textarea.evaluate(element => element.getBoundingClientRect().width);

    await page.locator("#attachmentInput").setInputFiles({
        name: "very-long-mobile-product-design-reference-document.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Responsive attachment fixture"),
    });

    const fileName = page.getByText("very-long-mobile-product-design-reference-document.txt");
    await expect(fileName).toBeVisible();
    const widthAfter = await textarea.evaluate(element => element.getBoundingClientRect().width);
    expect(Math.abs(widthAfter - widthBefore)).toBeLessThanOrEqual(1);
    await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page
        .getByRole("button", {
            name: "Remove very-long-mobile-product-design-reference-document.txt",
        })
        .click();
    await expect(fileName).toHaveCount(0);
});

test("mobile Ask examples stack and populate the composer", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 320, height: 568 });

    const examples = page.getByLabel("Prompt examples").getByRole("button");
    await expect(examples).toHaveCount(4);
    const rects = await examples.evaluateAll(buttons =>
        buttons.map(button => {
            const rect = button.getBoundingClientRect();
            return { left: rect.left, top: rect.top, bottom: rect.bottom };
        }),
    );
    expect(rects[1].top).toBeGreaterThan(rects[0].bottom);

    await examples.first().click();
    await expect(page.locator("#promptInput")).not.toHaveValue("");
    await expectNoHorizontalOverflow(page);
});

async function composerMetrics(page) {
    return page.evaluate(() => {
        const textarea = document.querySelector("#promptInput");
        const card = textarea?.parentElement?.parentElement;
        const composer = card?.parentElement;
        const nav = document.querySelector("nav[aria-label='Mobile navigation']");
        const send = document.querySelector("#submitBtn");
        const textareaRect = textarea?.getBoundingClientRect();
        const sendRect = send?.getBoundingClientRect();
        return {
            composerBottom: composer?.getBoundingClientRect().bottom ?? Number.POSITIVE_INFINITY,
            navTop: nav?.getBoundingClientRect().top ?? 0,
            sendVisible:
                !!sendRect
                && sendRect.width >= 40
                && sendRect.height >= 40
                && sendRect.right <= window.innerWidth,
            textareaFontSize: Number.parseFloat(
                textarea ? getComputedStyle(textarea).fontSize : "0",
            ),
            textareaHeight: textareaRect?.height ?? 0,
        };
    });
}
