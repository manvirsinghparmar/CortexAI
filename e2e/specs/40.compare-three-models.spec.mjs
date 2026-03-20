/**
 * Compare-mode coverage for a 3-model run using the live fixtures and UI helpers.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { ensureMode, startNewChat, submitComparePrompt } from "../helpers/ui.mjs";

const PROMPT = "Explain Python virtual environments in 3 short bullet points.";

async function addGrokAsThirdModel(page) {
    await expect(page.locator("#compareModel1")).toBeVisible();
    await expect(page.locator("#compareModel2")).toBeVisible();

    const selectedOne = await page.locator("#compareModel1").inputValue();
    const selectedTwo = await page.locator("#compareModel2").inputValue();
    expect(selectedOne).toMatch(/:/);
    expect(selectedTwo).toMatch(/:/);
    expect(selectedOne).not.toBe(selectedTwo);

    await page.locator("#compareAddModelBtn").click();
    await expect(page.locator("#compareModel3Wrap")).toBeVisible();

    const thirdValue = await page.locator("#compareModel3 option").evaluateAll((options, selected) => {
        const selectedValues = Array.isArray(selected) ? selected : [];
        const matches = options
            .map(option => {
                const value = String(option.value || "");
                const lowerValue = value.toLowerCase();
                const lowerLabel = String(option.textContent || "").toLowerCase();
                return { value, lowerValue, lowerLabel };
            })
            .filter(option => option.value.includes(":") && !selectedValues.includes(option.value));

        const grokMatch = matches.find(option => option.lowerValue.includes("grok") || option.lowerLabel.includes("grok"));
        return (grokMatch || matches[0] || { value: "" }).value;
    }, [selectedOne, selectedTwo]);

    expect(thirdValue).toBeTruthy();
    await page.locator("#compareModel3").selectOption(thirdValue);
    await expect(page.locator("#compareModel3")).toHaveValue(thirdValue);
}

test("compare mode with three selected models renders exactly three non-empty cards", async ({ liveApp }) => {
    const { page, config } = liveApp;

    await startNewChat(page);
    await ensureMode(page, "compare");
    await expect(page.locator("#errorBanner")).toBeHidden();

    await addGrokAsThirdModel(page);

    const cardsBefore = await page.locator("[id^='response-text-']").count();
    const result = await submitComparePrompt(page, PROMPT, config, 3);
    const cardsAfter = await page.locator("[id^='response-text-']").count();

    expect(result.indices).toHaveLength(3);
    expect(cardsAfter - cardsBefore).toBe(3);

    for (const index of result.indices) {
        await expect(page.locator(`#chat-msg-${index}`)).toBeVisible();

        const summaryText = String(await page.locator(`#response-provider-summary-${index}`).textContent() || "").trim();
        expect(summaryText.length).toBeGreaterThan(0);

        const responseText = String(await page.locator(`#response-text-${index}`).textContent() || "").trim();
        expect(responseText.length).toBeGreaterThan(20);
    }

    await expect(page.locator("#errorBanner")).toBeHidden();
});
