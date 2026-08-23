import {
    expect,
    test,
} from "../fixtures/responsive-e2e.mjs";

test("Free Compare defaults use allowed models and keep upgraded models offered", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    await page.locator("#btnCompareMode").click();

    await expect(page.locator("#compareModel1")).toHaveValue("openai:gpt-5.1");
    await expect(page.locator("#compareModel2")).toHaveValue("deepseek:deepseek-chat");
    await expect(page.locator("#compareModel1 option")).toHaveCount(state.models.length);
    await expect(
        page.locator('#compareModel1 option[value="claude:claude-sonnet-4-5"]'),
    ).toBeDisabled();
    await expect(
        page.locator('#compareModel1 option[value="grok:grok-4"]'),
    ).toBeDisabled();
});

test("Plus Compare skips a premium fallback while retaining the full offering", async ({ responsiveApp }) => {
    const { page, state, reload } = responsiveApp;
    const providerOrder = ["openai", "grok", "claude", "deepseek", "gemini"];
    state.models = [...state.models].sort(
        (left, right) => providerOrder.indexOf(left.provider) - providerOrder.indexOf(right.provider),
    );
    state.subscriptionPlan = "plus";
    await reload();
    await page.locator("#btnCompareMode").click();

    await expect(page.locator("#compareModel1")).toHaveValue("openai:gpt-5.1");
    await expect(page.locator("#compareModel2")).toHaveValue("claude:claude-sonnet-4-5");
    await expect(page.locator("#compareModel1 option")).toHaveCount(state.models.length);
    await expect(
        page.locator('#compareModel1 option[value="grok:grok-4"]'),
    ).toBeDisabled();
});
