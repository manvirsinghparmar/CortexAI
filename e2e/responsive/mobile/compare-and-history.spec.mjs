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

    await expect(page.getByRole("table")).toHaveCount(2);
    const metrics = await page
        .getByRole("region", { name: "Response table" })
        .first()
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
    await expectNoHorizontalOverflow(page);
});

test("mobile multi-turn Compare retains stacked natural-height cards", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await restoreHistoryThread(page, "Architecture decision");

    const metrics = await page.evaluate(() => {
        const firstTurn = document.querySelector('article[aria-label="Model comparison"]');
        const cards = [...(firstTurn?.querySelectorAll(":scope > div:last-child > article") ?? [])];
        const rects = cards.map(card => card.getBoundingClientRect());
        const bodies = cards.map(card => card.querySelector("[id^='response-text-']"));
        return {
            stacked:
                rects.length === 2
                && Math.abs(rects[0].left - rects[1].left) <= 2
                && rects[1].top > rects[0].bottom,
            bodies: bodies.map(body => ({
                clientHeight: body?.clientHeight ?? 0,
                scrollHeight: body?.scrollHeight ?? 0,
                overflowY: body ? getComputedStyle(body).overflowY : "",
            })),
        };
    });

    expect(metrics.stacked).toBe(true);
    for (const body of metrics.bodies) {
        expect(body.clientHeight).toBe(body.scrollHeight);
        expect(body.overflowY).toBe("visible");
    }
});
