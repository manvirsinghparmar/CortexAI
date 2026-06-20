import {
    expect,
    expectNoHorizontalOverflow,
    openMobilePanel,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("mobile navigation switches between Ask, Compare, and History", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    const mobileNav = page.getByRole("navigation", { name: "Mobile navigation" });
    const compose = page.getByRole("button", { name: "Start new chat" });

    await expect(mobileNav).toBeVisible();
    await expect(compose).toBeVisible();
    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeHidden();
    await expect(page.locator("#btnSingleMode")).toBeHidden();
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask anything . . .",
    );

    await openMobilePanel(page, "Compare");
    await expect(page.getByLabel("Compare model selectors")).toBeVisible();
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask once and compare model responses",
    );

    await openMobilePanel(page, "History");
    await expect(page.getByRole("region", { name: "History" })).toBeVisible();
    await expect(page.getByRole("region", { name: "History" }).getByText("New chat")).toHaveCount(0);
    await expect(compose).toBeVisible();
    await expect(page.locator("#promptInput")).toHaveCount(0);

    await openMobilePanel(page, "Ask");
    await expect(page.locator("#promptInput")).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("mobile compose action starts a fresh Compare session from History", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await openMobilePanel(page, "History");
    await page.getByRole("button", { name: /Architecture decision/i }).first().click();
    await expect(page.locator('article[aria-label="Model comparison"]')).toHaveCount(3);

    await openMobilePanel(page, "History");
    await page.getByRole("button", { name: "Start new chat" }).click();

    await expect(page.getByRole("region", { name: "History" })).toHaveCount(0);
    await expect(page.locator('article[aria-label="Model comparison"]')).toHaveCount(0);
    await expect(page.getByLabel("Compare model selectors")).toBeVisible();
    await expect(page.locator("#promptInput")).toHaveValue("");
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask once and compare model responses",
    );
    await expectNoHorizontalOverflow(page);
});

test("mobile compose action clears an Ask thread while preserving Ask mode", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await openMobilePanel(page, "History");
    await page.getByRole("button", { name: /Help debug a FastAPI stream/i }).click();
    await expect(page.getByText("Add a retry strategy")).toBeVisible();

    await page.locator("#promptInput").fill("Unsent follow-up");
    await page.getByRole("button", { name: "Start new chat" }).click();

    await expect(page.getByText("Add a retry strategy")).toHaveCount(0);
    await expect(page.locator("#promptInput")).toHaveValue("");
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask anything . . .",
    );
    await expectNoHorizontalOverflow(page);
});

test("mobile composer stays borderless with a soft focus state", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 390, height: 844 });

    for (const mode of ["Ask", "Compare"]) {
        await openMobilePanel(page, mode);
        const textarea = page.locator("#promptInput");
        const composer = textarea.locator("xpath=../..");
        const idle = await composer.evaluate(element => {
            const style = getComputedStyle(element);
            return {
                borderColor: style.borderColor,
                boxShadow: style.boxShadow,
            };
        });
        expect(idle.borderColor).toBe("rgba(0, 0, 0, 0)");
        expect(idle.boxShadow).not.toBe("none");

        await textarea.focus();
        const focused = await textarea.evaluate(element => ({
            outlineStyle: getComputedStyle(element).outlineStyle,
            boxShadow: getComputedStyle(element).boxShadow,
            shellShadow: getComputedStyle(element.parentElement?.parentElement).boxShadow,
        }));
        expect(focused.outlineStyle).toBe("none");
        expect(focused.boxShadow).toBe("none");
        expect(focused.shellShadow).not.toBe(idle.boxShadow);
        await expectNoHorizontalOverflow(page);
    }
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

test("small mobile keeps focused feature tooltips inside the viewport", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 320, height: 568 });

    for (const [switchName, tooltipText] of [
        ["Smart routing", "Gets you the best answer automatically"],
        ["Research mode", "Uses latest information from the web"],
        ["Prompt optimization", "Helps you ask better for better results"],
    ]) {
        const chip = page.getByRole("switch", { name: switchName });
        const tooltip = page.locator('[role="tooltip"]').filter({ hasText: tooltipText });
        await chip.focus();
        await expect(tooltip).toBeVisible();
        const bounds = await tooltip.evaluate(element => {
            const rect = element.getBoundingClientRect();
            return {
                left: rect.left,
                right: rect.right,
                viewportWidth: window.innerWidth,
            };
        });
        expect(bounds.left).toBeGreaterThanOrEqual(0);
        expect(bounds.right).toBeLessThanOrEqual(bounds.viewportWidth);
    }

    await openMobilePanel(page, "Compare");
    const sources = page.getByRole("switch", { name: "Compare with sources" });
    const sourcesTooltip = page
        .locator('[role="tooltip"]')
        .filter({ hasText: "Uses latest information from the web" });
    await expect(sources).toHaveAttribute(
        "aria-describedby",
        await sourcesTooltip.getAttribute("id"),
    );
    await expectNoHorizontalOverflow(page);
});

test("mobile tap toggles a feature chip and shows its tooltip briefly", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 390, height: 844 });

    const research = page.getByRole("switch", { name: "Research mode" });
    const tooltip = page
        .locator('[role="tooltip"]')
        .filter({ hasText: "Uses latest information from the web" });
    await expect(research).toHaveAttribute("aria-checked", "true");

    await research.evaluate(element => {
        element.dispatchEvent(
            new PointerEvent("pointerup", {
                bubbles: true,
                pointerType: "touch",
            }),
        );
        element.click();
    });

    await expect(research).toHaveAttribute("aria-checked", "false");
    await expect(tooltip).toHaveAttribute("data-touch-visible", "true");
    await expect(tooltip).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await expect(tooltip).toHaveAttribute("data-touch-visible", "false", {
        timeout: 3000,
    });
    await expect(tooltip).toBeHidden();
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
