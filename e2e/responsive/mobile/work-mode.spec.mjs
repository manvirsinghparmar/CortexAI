import { expect, expectNoHorizontalOverflow, test } from "../fixtures/responsive-e2e.mjs";

test("mobile Work keeps the four-item navigation and compact empty composer", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "plus";
    await page.goto("/work");

    const nav = page.getByRole("navigation", { name: "Mobile navigation" });
    await expect(nav).toBeVisible();
    await expect(nav.getByRole("button")).toHaveCount(4);
    await expect(nav.getByRole("button", { name: "Work" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name: "What should I work on?" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Work goal" })).toBeVisible();
    await expect(page.locator("aside[aria-label='Primary navigation']")).toBeHidden();
    await expectNoHorizontalOverflow(page);
});

test("mobile Work shows immediate progress while the run start is pending", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "pro";
    state.workStartDelayMs = 900;
    await page.goto("/work");

    await page.getByRole("textbox", { name: "Work goal" }).fill("Prepare a mobile launch report");
    await page.getByRole("button", { name: /Start work/ }).click();

    await expect(page.getByRole("status", { name: "Starting work" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Prepare a mobile launch report" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await expect(page.getByText("Work completed", { exact: true }).first()).toBeVisible();
});

test("mobile Work opens and interacts with the Tools menu above navigation", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "pro";
    await page.goto("/work");

    const toolsButton = page.getByRole("button", { name: /Tools/ });
    await toolsButton.click();

    const toolsDialog = page.getByRole("dialog", { name: "Tools" });
    await expect(toolsButton).toHaveAttribute("aria-expanded", "true");
    await expect(toolsDialog).toBeVisible();
    await toolsDialog.getByRole("button", { name: "Add MCP server" }).click();
    await expect(toolsDialog.getByRole("textbox", { name: "HTTPS endpoint" })).toBeVisible();
    await toolsDialog.getByRole("button", { name: "Close tools" }).click();
    await expect(toolsDialog).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
});

test("mobile completed Work shows outcome, inline activity rail, and deliverables above navigation", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "pro";
    state.workSessions = [{
        id: "work-session-1", session_id: "session-work-1", title: "Prepare a market report",
        status: "completed", agent_provider: "fake", created_at: "2026-08-20T12:00:00Z",
        updated_at: "2026-08-20T12:04:00Z", latest_run_status: "completed",
    }];
    state.workRun = {
        id: "work-run-1", work_session_id: "work-session-1", request_id: "request-1",
        instruction: "Prepare a market report", status: "completed", provider: "fake",
        max_credit_budget: 100000, reserved_credits: 100000, actual_credits: 18400,
        configuration_snapshot: { web_enabled: false, enabled_connection_ids: [] }, usage_snapshot: {},
        stop_reason: null, error_code: null, error_message: null,
        started_at: "2026-08-20T12:00:00Z", completed_at: "2026-08-20T12:04:00Z",
        created_at: "2026-08-20T12:00:00Z", updated_at: "2026-08-20T12:04:00Z",
    };
    state.workEvents = [
        { id: "event-1", sequence: 1, type: "plan_created", display_message: "Plan created", payload: {}, created_at: "2026-08-20T12:01:00Z" },
        { id: "event-2", sequence: 2, type: "agent_message", display_message: "The market report is ready.", payload: {}, created_at: "2026-08-20T12:04:00Z" },
    ];
    state.workArtifacts = [{
        id: "artifact-1", file_id: "artifact-file-1", role: "artifact", source: "agent",
        filename: "market-report.pdf", mime_type: "application/pdf", size_bytes: 4096,
        artifact_type: "report", metadata: {}, created_at: "2026-08-20T12:04:00Z",
    }];
    await page.goto("/work/work-session-1");

    await expect(page.getByText("Work completed", { exact: true }).first()).toBeVisible();
    await expect(page.locator("p", { hasText: "The market report is ready." })).toBeVisible();
    await expect(page.getByText("market-report.pdf")).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Work activity" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
});
