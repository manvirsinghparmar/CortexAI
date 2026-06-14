import {
    expect,
    expectNoHorizontalOverflow,
    restoreHistoryThread,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("desktop multi-turn Compare keeps readable panels and scrolls the transcript", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await restoreHistoryThread(page, "Architecture decision");

    const metrics = await page.evaluate(() => {
        const transcript = document.querySelector('section[aria-label="Chat transcript"]');
        const turns = [...document.querySelectorAll('article[aria-label="Model comparison"]')];
        return {
            transcriptClientHeight: transcript?.clientHeight ?? 0,
            transcriptScrollHeight: transcript?.scrollHeight ?? 0,
            turns: turns.map(turn => {
                const cards = [...turn.querySelectorAll(":scope > div:last-child > article")];
                const bodies = cards.map(card => card.querySelector("[id^='response-text-']"));
                return {
                    height: Math.round(turn.getBoundingClientRect().height),
                    cardHeights: cards.map(card => Math.round(card.getBoundingClientRect().height)),
                    bodies: bodies.map(body => ({
                        clientHeight: body?.clientHeight ?? 0,
                        scrollHeight: body?.scrollHeight ?? 0,
                        overflowY: body ? getComputedStyle(body).overflowY : "",
                    })),
                };
            }),
        };
    });

    expect(metrics.transcriptScrollHeight).toBeGreaterThan(metrics.transcriptClientHeight);
    for (const turn of metrics.turns) {
        expect(turn.height).toBeGreaterThanOrEqual(480);
        expect(turn.height).toBeLessThanOrEqual(620);
        expect(Math.max(...turn.cardHeights) - Math.min(...turn.cardHeights)).toBeLessThanOrEqual(2);
        for (const body of turn.bodies) {
            expect(body.clientHeight).toBeGreaterThanOrEqual(280);
            expect(body.scrollHeight).toBeGreaterThan(body.clientHeight);
            expect(body.overflowY).toBe("auto");
        }
    }
});

test("desktop Compare renders Markdown tables inside each response scroller", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await restoreHistoryThread(page, "Compare deployment options table");

    const tables = page.getByRole("table");
    await expect(tables).toHaveCount(2);
    await expect(page.getByRole("columnheader", { name: "Recommendation" }).first()).toBeVisible();

    const metrics = await page
        .getByRole("region", { name: "Response table" })
        .first()
        .evaluate(wrapper => {
            const table = wrapper.querySelector("table");
            const header = table?.querySelector("thead");
            return {
                overflowX: getComputedStyle(wrapper).overflowX,
                tableDisplay: table ? getComputedStyle(table).display : "",
                tableMinWidth: table ? getComputedStyle(table).minWidth : "",
                headerPosition: header ? getComputedStyle(header).position : "",
            };
        });

    expect(metrics.overflowX).toBe("auto");
    expect(metrics.tableDisplay).toBe("table");
    expect(metrics.tableMinWidth).toBe("520px");
    expect(metrics.headerPosition).toBe("static");
    await expectNoHorizontalOverflow(page);
});

test("iPad portrait stacks Compare cards in natural page flow", async ({ responsiveApp }) => {
    const { page } = responsiveApp;
    await page.setViewportSize({ width: 820, height: 1180 });
    await restoreHistoryThread(page, "Architecture decision");

    const metrics = await page.evaluate(() => {
        const firstTurn = document.querySelector('article[aria-label="Model comparison"]');
        const cards = [...(firstTurn?.querySelectorAll(":scope > div:last-child > article") ?? [])];
        const rects = cards.map(card => card.getBoundingClientRect());
        return {
            stacked:
                rects.length === 2
                && Math.abs(rects[0].left - rects[1].left) <= 2
                && rects[1].top > rects[0].bottom,
        };
    });
    expect(metrics.stacked).toBe(true);
    await expectNoHorizontalOverflow(page);
});
