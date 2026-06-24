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

test("desktop sidebar collapses to an icon rail and expands again", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    const sidebar = page.locator("aside[aria-label='Primary navigation']");
    await expect(sidebar).toBeVisible();
    await expect(sidebar).toHaveAttribute("data-collapsed", "false");

    const expandedWidth = await sidebar.evaluate(element => element.getBoundingClientRect().width);
    await page.getByRole("button", { name: "Collapse sidebar" }).click();

    await expect(sidebar).toHaveAttribute("data-collapsed", "true");
    await expect(sidebar.getByRole("textbox", { name: "Search history" })).toBeHidden();
    await expect.poll(
        () => sidebar.evaluate(element => element.getBoundingClientRect().width),
    ).toBeLessThanOrEqual(90);
    const collapsedWidth = await sidebar.evaluate(element => element.getBoundingClientRect().width);
    expect(collapsedWidth).toBeLessThan(expandedWidth);

    await sidebar.getByRole("button", { name: "Compare" }).click();
    await expect(page.locator("#btnCompareMode")).toHaveClass(/activeTab/);

    await page.getByRole("button", { name: "Expand sidebar" }).click();
    await expect(sidebar).toHaveAttribute("data-collapsed", "false");
    await expect(sidebar.getByRole("textbox", { name: "Search history" })).toBeVisible();

    await page.setViewportSize({ width: 820, height: 1180 });
    await expect(sidebar).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("desktop history keeps compact title, mode, and date rows", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 520 });

    const sidebar = page.locator("aside[aria-label='Primary navigation']");
    const rows = sidebar.locator("button[data-history-thread]");
    await expect(rows).toHaveCount(5);

    const rowMetrics = await rows.evaluateAll(elements =>
        elements.map(element => {
            const title = element.querySelector("[data-history-title]");
            return {
                height: element.getBoundingClientRect().height,
                titleWhiteSpace: title ? getComputedStyle(title).whiteSpace : "",
                titleOverflow: title ? getComputedStyle(title).textOverflow : "",
            };
        }),
    );
    for (const row of rowMetrics) {
        expect(row.height).toBeLessThanOrEqual(60);
        expect(row.titleWhiteSpace).toBe("nowrap");
        expect(row.titleOverflow).toBe("ellipsis");
    }

    const longRow = sidebar.getByRole("button", {
        name: /Plan a multi-region platform migration/,
    });
    await expect(longRow).toHaveAttribute(
        "aria-label",
        /Ask,/,
    );
    const truncation = await longRow.evaluate(element => {
        const title = element.querySelector("[data-history-title]");
        return {
            titleTruncated: Boolean(title && title.scrollWidth > title.clientWidth),
            hasModel: element.textContent?.includes(
                "gpt-5.4-mini-enterprise-preview-with-extended-context",
            ),
            hasTurnCount: element.textContent?.includes("1 turn"),
        };
    });
    expect(truncation.titleTruncated).toBe(true);
    expect(truncation.hasModel).toBe(false);
    expect(truncation.hasTurnCount).toBe(false);

    const historyList = sidebar.locator("ul").first();
    const listMetrics = await historyList.evaluate(element => ({
        overflowY: getComputedStyle(element).overflowY,
        scrollHeight: element.scrollHeight,
        clientHeight: element.clientHeight,
    }));
    expect(listMetrics.overflowY).toBe("auto");
    expect(listMetrics.scrollHeight).toBeGreaterThan(listMetrics.clientHeight);

    await longRow.hover();
    await expect(longRow).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await longRow.click();
    await expect(longRow).toHaveAttribute("aria-current", "page");

    const search = sidebar.getByRole("textbox", { name: "Search history" });
    await search.fill("multi-region");
    await expect(rows).toHaveCount(1);
    await expect(longRow).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("desktop composer uses the refresh hairline shell and soft textarea focus state", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    await expectSoftComposerShell(page);
    await page.locator("#btnCompareMode").click();
    await expectSoftComposerShell(page);
});

test("desktop feature chips show accessible tooltips in Ask and Compare", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    await expectChipTooltip(
        page,
        "Smart routing",
        "Gets you the best answer automatically",
    );
    await expectChipTooltip(
        page,
        "Research mode",
        "Uses latest information from the web",
    );
    await expectChipTooltip(
        page,
        "Prompt optimization",
        "Helps you ask better for better results",
    );

    await page.locator("#btnCompareMode").click();
    await expectChipTooltip(
        page,
        "Compare with sources",
        "Uses latest information from the web",
    );
    await expectChipTooltip(
        page,
        "Prompt optimization",
        "Helps you ask better for better results",
    );
    await expectNoHorizontalOverflow(page);
});

test("dark theme gives enabled Ask feature chips a distinct accent state", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.getByRole("button", { name: "Account" }).click();
    await page.getByRole("menuitem", { name: "Switch to dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    const switches = [
        page.getByRole("switch", { name: "Smart routing" }),
        page.getByRole("switch", { name: "Research mode" }),
        page.getByRole("switch", { name: "Prompt optimization" }),
    ];
    for (const featureSwitch of switches) {
        if ((await featureSwitch.getAttribute("aria-checked")) !== "true") {
            await featureSwitch.click();
        }
        await page.getByRole("heading", { level: 2 }).hover();
        await expect(featureSwitch).toHaveCSS("background-color", "rgb(52, 52, 103)");
        await expect(featureSwitch).toHaveCSS("color", "rgb(255, 255, 255)");
        await expect(featureSwitch).toHaveCSS("box-shadow", /rgb\(139, 139, 240\)/);
    }

    await switches[0].click();
    await expect(switches[0]).not.toHaveCSS("background-color", "rgb(52, 52, 103)");
    await expect(switches[0]).not.toHaveCSS("color", "rgb(255, 255, 255)");
});

test("dark theme keeps the top Ask and Compare tabs legible", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.getByRole("button", { name: "Account" }).click();
    await page.getByRole("menuitem", { name: "Switch to dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    const modeNavigation = page.getByRole("navigation", { name: "Chat mode" });
    const askTab = modeNavigation.getByRole("button", { name: "Ask" });
    const compareTab = modeNavigation.getByRole("button", { name: "Compare" });

    await expect(askTab).toHaveCSS("color", "rgb(241, 243, 246)");
    await expect(askTab).toHaveCSS("border-bottom-color", "rgb(139, 139, 240)");
    await expect(compareTab).toHaveCSS("color", "rgb(174, 182, 194)");

    await compareTab.click();
    await expect(compareTab).toHaveCSS("color", "rgb(241, 243, 246)");
    await expect(compareTab).toHaveCSS("border-bottom-color", "rgb(139, 139, 240)");
    await expect(askTab).toHaveCSS("color", "rgb(174, 182, 194)");
});

test("Compare sources and Improve use the same styling for matching states", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.locator("#btnCompareMode").click();

    const sources = page.getByRole("switch", { name: "Compare with sources" });
    const improve = page.getByRole("switch", { name: "Prompt optimization" });
    const promptInput = page.locator("#promptInput");

    await sources.click();
    await promptInput.hover();
    await expectMatchingChipStyles(sources, improve);

    await sources.click();
    await improve.click();
    await promptInput.hover();
    await expectMatchingChipStyles(sources, improve);

    await page.getByRole("button", { name: "Account" }).click();
    await page.getByRole("menuitem", { name: "Switch to dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expectMatchingChipStyles(sources, improve);

    await sources.click();
    await improve.click();
    await promptInput.hover();
    await expectMatchingChipStyles(sources, improve);
});

test("Improve keeps response cards hidden until optimization resolves", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });

    let releaseOptimization;
    const optimizationGate = new Promise(resolve => {
        releaseOptimization = resolve;
    });
    await page.route("**/v1/optimize", async route => {
        await optimizationGate;
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                original_prompt: "rough browser prompt",
                optimized_prompt: "Clear browser prompt",
                was_optimized: true,
                server_optimization_enabled: true,
                optimization_status: "optimized",
            }),
        });
    });
    await page.route("**/v1/chat/stream", route => route.fulfill({
        status: 200,
        headers: { "content-type": "application/x-ndjson" },
        body: [
            JSON.stringify({ type: "start", provider: "openai", model: "gpt-5.1" }),
            JSON.stringify({ type: "line", text: "Optimized browser answer." }),
            JSON.stringify({
                type: "response_done",
                response: {
                    provider: "openai",
                    model: "gpt-5.1",
                    text: "Optimized browser answer.",
                    latency_ms: 300,
                    estimated_cost: 0.001,
                    token_usage: {
                        prompt_tokens: 10,
                        completion_tokens: 10,
                        total_tokens: 20,
                    },
                    web_source_items: [],
                },
            }),
            JSON.stringify({ type: "done", session_id: "optimized-session" }),
            "",
        ].join("\n"),
    }));

    await page.getByRole("switch", { name: "Prompt optimization" }).click();
    await page.locator("#promptInput").fill("rough browser prompt");
    await page.locator("#submitBtn").click();

    const pendingTurn = page.locator("[data-turn-id]").last();
    await expect(pendingTurn.getByRole("status")).toContainText("Improving your prompt");
    await expect(pendingTurn.locator("article")).toHaveCount(0);
    await expect(page.getByRole("tablist", { name: "Compare model responses" })).toHaveCount(0);

    releaseOptimization();

    await expect(pendingTurn.locator("article")).toHaveCount(1);
    await expect(pendingTurn).toContainText("Optimized browser answer.");
});

test("desktop Compare picker remains visible and selectable", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.locator("#btnCompareMode").click();

    const connector = page.getByTestId("compare-connector");
    await expect(connector).toHaveCount(1);
    await expect(connector).toHaveCSS("width", "26px");
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

async function expectChipTooltip(page, switchName, tooltipText) {
    const chip = page.getByRole("switch", { name: switchName });
    const tooltip = page.locator('[role="tooltip"]').filter({ hasText: tooltipText });
    await expect(tooltip).toHaveAttribute("id", await chip.getAttribute("aria-describedby"));
    await chip.hover();
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toHaveCSS("opacity", "1");
}

async function chipVisualStyle(chip) {
    return chip.evaluate(element => {
        const style = getComputedStyle(element);
        return {
            backgroundColor: style.backgroundColor,
            borderColor: style.borderColor,
            boxShadow: style.boxShadow,
            color: style.color,
        };
    });
}

async function expectMatchingChipStyles(first, second) {
    await expect.poll(async () => {
        const firstStyle = await chipVisualStyle(first);
        const secondStyle = await chipVisualStyle(second);
        return JSON.stringify(firstStyle) === JSON.stringify(secondStyle);
    }).toBe(true);
}

async function expectSoftComposerShell(page) {
    const textarea = page.locator("#promptInput");
    const composer = textarea.locator("xpath=../..");
    const idle = await composer.evaluate(element => ({
        borderColor: getComputedStyle(element).borderColor,
        boxShadow: getComputedStyle(element).boxShadow,
    }));
    expect(idle.borderColor).toBe("rgb(235, 237, 240)");
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
}

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
