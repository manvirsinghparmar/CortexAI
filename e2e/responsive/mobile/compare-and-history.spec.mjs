import {
    expect,
    expectNoHorizontalOverflow,
    openMobilePanel,
    restoreHistoryThread,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("mobile Compare opens the visible model picker and updates its selection", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await openMobilePanel(page, "Compare");

    const connector = page.getByTestId("compare-connector");
    await expect(connector).toHaveCount(1);
    await expect(connector).toBeVisible();
    await expect(connector).toHaveCSS("border-top-width", "0px");
    await expect(connector).toHaveCSS("pointer-events", "none");

    const nativeSelect = page.locator("#compareModel1");
    const currentValue = await nativeSelect.inputValue();
    const target = await nativeSelect.locator("option:not(:disabled)").evaluateAll(
        (options, selectedValue) => {
            const option = options.find(candidate => candidate.value !== selectedValue);
            if (!option) return null;
            const separator = option.value.indexOf(":");
            return {
                value: option.value,
                modelId: separator >= 0 ? option.value.slice(separator + 1) : option.value,
            };
        },
        currentValue,
    );
    expect(target).not.toBeNull();

    const trigger = page.getByRole("button", { name: /Compare model 1:/ });
    await trigger.click();
    const listbox = page.getByRole("listbox", { name: "Compare model 1 options" });
    await expect(listbox).toBeVisible();
    expect(await listbox.evaluate(element => element.parentElement === document.body)).toBe(true);

    const geometry = await listbox.evaluate(element => {
        const rect = element.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + 24, rect.top + 24);
        return {
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            left: rect.left,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            hitInside: Boolean(hit && element.contains(hit)),
        };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(0);
    expect(geometry.top).toBeGreaterThanOrEqual(0);
    expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth);
    expect(geometry.bottom).toBeLessThanOrEqual(geometry.viewportHeight);
    expect(geometry.hitInside).toBe(true);

    const targetOption = listbox
        .locator('[role="option"]')
        .filter({ hasText: target.modelId })
        .first();
    await targetOption.click();
    await expect(nativeSelect).toHaveValue(target.value);
    await expect(listbox).toBeHidden();
});

test("mobile Compare adds and removes a third model without page overflow", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await openMobilePanel(page, "Compare");

    await page.getByRole("button", { name: "Add model to comparison" }).click();
    await expect(page.locator("#compareModel3Wrap")).toBeVisible();
    await expect(page.getByTestId("compare-connector")).toHaveCount(2);

    const scrollMetrics = await page.locator("#compareModel1Wrap").evaluate(element => {
        const chips = element.parentElement?.parentElement;
        return {
            clientWidth: chips?.clientWidth ?? 0,
            scrollWidth: chips?.scrollWidth ?? 0,
            overflowX: chips ? getComputedStyle(chips).overflowX : "",
        };
    });
    expect(scrollMetrics.scrollWidth).toBeGreaterThan(scrollMetrics.clientWidth);
    expect(scrollMetrics.overflowX).toBe("auto");
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /Remove DeepSeek Chat/i }).click();
    await expect(page.locator("#compareModel3Wrap")).toHaveCount(0);
    await expect(page.getByTestId("compare-connector")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "Add model to comparison" })).toBeVisible();
});

test("small mobile keeps the Compare connector inside the model scroller", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 320, height: 568 });
    await openMobilePanel(page, "Compare");

    const metrics = await page.evaluate(() => {
        const first = document.querySelector("#compareModel1Wrap")?.getBoundingClientRect();
        const second = document.querySelector("#compareModel2Wrap")?.getBoundingClientRect();
        const connector = document.querySelector("[data-testid='compare-connector']");
        const connectorRect = connector?.getBoundingClientRect();
        const chips = connector?.parentElement?.parentElement;
        return {
            ordered:
                Boolean(first && connectorRect && second)
                && first.right <= connectorRect.left
                && connectorRect.right <= second.left,
            connectorWidth: connectorRect?.width ?? 0,
            overflowX: chips ? getComputedStyle(chips).overflowX : "",
            scrollWidth: chips?.scrollWidth ?? 0,
            clientWidth: chips?.clientWidth ?? 0,
        };
    });

    expect(metrics.ordered).toBe(true);
    expect(metrics.connectorWidth).toBe(16);
    expect(metrics.overflowX).toBe("auto");
    expect(metrics.scrollWidth).toBeGreaterThan(metrics.clientWidth);
    await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("mobile History search restores a grouped Compare session", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await openMobilePanel(page, "History");

    const search = page.getByRole("textbox", { name: "Search history" });
    await search.fill("Architecture decision");
    const thread = page.getByRole("button", { name: /Architecture decision/i });
    await expect(thread).toHaveCount(1);
    await thread.click();

    await expect(page.locator('article[aria-label="Model comparison"]')).toHaveCount(3);
    await expect(page.locator("#promptInput")).toHaveAttribute(
        "placeholder",
        "Ask once and compare model responses",
    );
    await expectNoHorizontalOverflow(page);
});

test("mobile Compare stacks Markdown table rows with visible column labels", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await restoreHistoryThread(page, "Compare deployment options table");

    const responseTabs = page.getByRole("tablist", { name: "Compare model responses" });
    await expect(responseTabs).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(1);
    const metrics = await page
        .getByRole("region", { name: "Response table" })
        .evaluate(wrapper => {
            const table = wrapper.querySelector("table");
            const head = table?.querySelector("thead");
            const body = table?.querySelector("tbody");
            const firstCell = table?.querySelector("tbody td");
            return {
                wrapperOverflow: getComputedStyle(wrapper).overflowX,
                tableDisplay: table ? getComputedStyle(table).display : "",
                headPosition: head ? getComputedStyle(head).position : "",
                bodyDisplay: body ? getComputedStyle(body).display : "",
                cellDisplay: firstCell ? getComputedStyle(firstCell).display : "",
                cellLabel: firstCell?.getAttribute("data-label") ?? "",
                pseudoLabel: firstCell
                    ? getComputedStyle(firstCell, "::before").content.replaceAll('"', "")
                    : "",
            };
        });

    expect(metrics.wrapperOverflow).toBe("visible");
    expect(metrics.tableDisplay).toBe("block");
    expect(metrics.headPosition).toBe("absolute");
    expect(metrics.bodyDisplay).toBe("grid");
    expect(metrics.cellDisplay).toBe("grid");
    expect(metrics.cellLabel).toBe("Option");
    expect(metrics.pseudoLabel).toBe("Option");

    await responseTabs.getByRole("tab", { name: "Claude Sonnet" }).click();
    await expect(responseTabs.getByRole("tab", { name: "Claude Sonnet" })).toHaveAttribute(
        "aria-selected",
        "true",
    );
    await expect(page.getByRole("table")).toHaveCount(1);
    await expectNoHorizontalOverflow(page);
});

test("mobile multi-turn Compare switches one natural-height response card at a time", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await restoreHistoryThread(page, "Architecture decision");

    const firstTurn = page.locator('article[aria-label="Model comparison"]').first();
    const tabs = firstTurn.getByRole("tablist", { name: "Compare model responses" });
    const gptTab = tabs.getByRole("tab", { name: "GPT-5.1" });
    const claudeTab = tabs.getByRole("tab", { name: "Claude Sonnet" });
    const panels = firstTurn.locator('[role="tabpanel"]');

    await expect(panels).toHaveCount(2);
    await expect(gptTab).toHaveAttribute("aria-selected", "true");
    await expect(panels.nth(0)).toBeVisible();
    await expect(panels.nth(1)).toBeHidden();

    const details = panels.nth(0).getByRole("button", { name: "Show run details" });
    await expect(details).toHaveAttribute("aria-expanded", "false");
    await expect(details).not.toContainText("Details");
    await details.click();
    const hideDetails = panels.nth(0).getByRole("button", { name: "Hide run details" });
    await expect(hideDetails).toHaveAttribute("aria-expanded", "true");
    const runDetails = panels.nth(0).locator('[id^="response-stats-"]');
    await expect(runDetails).toBeVisible();
    await expect(runDetails).toContainText("0.90 sec");
    await expect(runDetails).toContainText("tokens");

    const activeBodyMetrics = await panels.nth(0).locator("[id^='response-text-']").evaluate(body => {
        return {
            clientHeight: body.clientHeight,
            scrollHeight: body.scrollHeight,
            overflowY: getComputedStyle(body).overflowY,
        };
    });
    expect(activeBodyMetrics.clientHeight).toBe(activeBodyMetrics.scrollHeight);
    expect(activeBodyMetrics.overflowY).toBe("visible");

    await claudeTab.click();
    await expect(claudeTab).toHaveAttribute("aria-selected", "true");
    await expect(panels.nth(0)).toBeHidden();
    await expect(panels.nth(1)).toBeVisible();
    await expectNoHorizontalOverflow(page);
});
