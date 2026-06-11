/**
 * Compare transcript layout regression coverage.
 *
 * These cases restore multiple persisted Compare turns so the browser exercises
 * the same request_group_id reconstruction path as a real History selection.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";

const LONG_RESPONSE = Array.from(
    { length: 35 },
    (_, index) =>
        `Paragraph ${index + 1}: detailed comparison content that must remain readable inside its own scrollable response area.`,
).join("\n\n");

function historyEntries() {
    return [
        compareEntry(1, "group-1", "First compare prompt", "openai", "gpt-5.1"),
        compareEntry(2, "group-1", "First compare prompt", "claude", "claude-sonnet-4-5"),
        compareEntry(3, "group-2", "Second compare prompt", "openai", "gpt-5.1"),
        compareEntry(4, "group-2", "Second compare prompt", "claude", "claude-sonnet-4-5"),
        compareEntry(5, "group-3", "Third compare prompt", "openai", "gpt-5.1"),
        compareEntry(6, "group-3", "Third compare prompt", "claude", "claude-sonnet-4-5"),
    ];
}

function compareEntry(id, requestGroupId, prompt, provider, model) {
    return {
        id,
        session_id: "compare-layout-session",
        request_group_id: requestGroupId,
        timestamp: `2026-06-09T10:0${id}:00Z`,
        mode: "compare",
        prompt,
        provider,
        model,
        response: LONG_RESPONSE,
        latency_ms: 900 + id * 100,
        tokens: 1800 + id * 100,
        cost: 0.01 + id * 0.001,
        web_source_items: [],
    };
}

async function restoreMockedHistory(page, mobile = false) {
    await page.route("**/v1/history?**", route =>
        route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(historyEntries()),
        }),
    );
    await page.reload({ waitUntil: "networkidle" });

    if (mobile) {
        await page.getByRole("button", { name: "History" }).click();
    }

    const thread = page.getByRole("button", { name: /First compare prompt/i }).first();
    await expect(thread).toBeVisible();
    await thread.click();
    await expect(page.locator('article[aria-label="Model comparison"]')).toHaveCount(3);
}

test("desktop multi-turn Compare keeps readable panels and scrolls the transcript", async ({ liveApp }) => {
    const { page } = liveApp;
    await page.setViewportSize({ width: 1440, height: 900 });
    await restoreMockedHistory(page);

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

test("mobile multi-turn Compare retains stacked natural-height cards", async ({ liveApp }) => {
    const { page } = liveApp;
    await page.setViewportSize({ width: 390, height: 844 });
    await restoreMockedHistory(page, true);

    const metrics = await page.evaluate(() => {
        const firstTurn = document.querySelector('article[aria-label="Model comparison"]');
        const cards = [...(firstTurn?.querySelectorAll(":scope > div:last-child > article") ?? [])];
        const rects = cards.map(card => card.getBoundingClientRect());
        const bodies = cards.map(card => card.querySelector("[id^='response-text-']"));
        return {
            stacked:
                rects.length === 2 &&
                Math.abs(rects[0].left - rects[1].left) <= 2 &&
                rects[1].top > rects[0].bottom,
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
