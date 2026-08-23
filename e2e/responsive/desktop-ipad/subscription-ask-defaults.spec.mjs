import {
    expect,
    test,
} from "../fixtures/responsive-e2e.mjs";

for (const expectation of [
    { planCode: "free", expectedKey: "openai:gpt-5.6-luna" },
    { planCode: "plus", expectedKey: "claude:claude-sonnet-4-6" },
    { planCode: "pro", expectedKey: "openai:gpt-5.6-terra" },
]) {
    test(`${expectation.planCode} Ask shows its plan default after Smart is turned off`, async ({
        responsiveApp,
    }) => {
        const { page, state, reload } = responsiveApp;
        state.models = withAskDefaultModels(state.models);
        state.subscriptionPlan = expectation.planCode;
        await reload();

        const smartSwitch = page.getByRole("switch", { name: "Smart routing" });
        await expect(smartSwitch).toHaveAttribute("aria-checked", "true");
        await smartSwitch.click();

        await expect(smartSwitch).toHaveAttribute("aria-checked", "false");
        await expect(page.locator("#singleModel")).toHaveValue(expectation.expectedKey);
        await expect(page.locator("#singleModel option")).toHaveCount(state.models.length);
        await expect(
            page.locator(`#singleModel option[value="${expectation.expectedKey}"]`),
        ).toBeEnabled();
    });
}

function withAskDefaultModels(models) {
    const openai = models.find(model => model.provider === "openai");
    const claude = models.find(model => model.provider === "claude");
    if (!openai || !claude) throw new Error("Responsive model fixture is incomplete.");

    return [
        {
            ...openai,
            model: "gpt-5.6-luna",
            billing_class: "economical",
            access_category: "economical",
        },
        {
            ...claude,
            model: "claude-sonnet-4-6",
            billing_class: "advanced",
            access_category: "advanced",
        },
        {
            ...openai,
            model: "gpt-5.6-terra",
            billing_class: "advanced",
            access_category: "advanced",
        },
        ...models,
    ];
}
