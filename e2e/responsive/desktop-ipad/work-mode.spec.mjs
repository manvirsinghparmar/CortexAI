import { expect, expectNoHorizontalOverflow, test } from "../fixtures/responsive-e2e.mjs";

test("desktop Work empty state starts a real mocked run and renders its deliverable", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "pro";
    await page.goto("/work");

    await expect(page.getByRole("heading", { name: "What should I work on?" })).toBeVisible();
    await expect(page.locator("aside[aria-label='Primary navigation']").getByRole("button", { name: "Work", exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Work goal" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("textbox", { name: "Work goal" }).fill("Analyze these files and create a report");
    await page.getByRole("button", { name: /Start work/ }).click();

    await expect(page.getByText("Work completed", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("work-report.pdf")).toBeVisible();
    await expect(page.getByRole("link", { name: "Download work-report.pdf" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
});

test("desktop Work binds the inline approval card and clears it after approve", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.subscriptionPlan = "pro";
    state.workSessions = [workSession("waiting_for_approval")];
    state.workRun = workRun("waiting_for_approval");
    state.workApproval = {
        id: "approval-1",
        work_run_id: "work-run-1",
        tool_call_id: "tool-call-1",
        connection_id: "connection-1",
        action_type: "WRITE",
        tool_name: "open_pull_request",
        description: "The report needs a pull request in the selected repository.",
        request_payload: { repository: "cortex/example", branch: "work/report" },
        status: "pending",
        requested_at: "2026-08-20T12:03:00Z",
        decided_at: null,
    };
    state.workEvents = [
        workEvent(1, "plan_created", "Plan created"),
        workEvent(2, "approval_required", "Your approval is required", { approval_ids: ["approval-1"] }),
    ];
    await page.goto("/work/work-session-1");

    await expect(page.getByText("Approval needed")).toBeVisible();
    await expect(page.getByText("cortex/example")).toBeVisible();
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Approval needed")).toHaveCount(0);
    expect(state.workApproval.status).toBe("approved");
});

function workSession(status) {
    return {
        id: "work-session-1", session_id: "session-work-1", title: "Prepare a market report",
        status, agent_provider: "fake", created_at: "2026-08-20T12:00:00Z",
        updated_at: "2026-08-20T12:03:00Z", latest_run_status: status,
    };
}

function workRun(status) {
    return {
        id: "work-run-1", work_session_id: "work-session-1", request_id: "request-1",
        instruction: "Prepare a market report", status, provider: "fake",
        max_credit_budget: 100000, reserved_credits: 100000, actual_credits: 6400,
        configuration_snapshot: { web_enabled: false, enabled_connection_ids: [] }, usage_snapshot: {},
        stop_reason: null, error_code: null, error_message: null,
        started_at: "2026-08-20T12:00:00Z", completed_at: null,
        created_at: "2026-08-20T12:00:00Z", updated_at: "2026-08-20T12:03:00Z",
    };
}

function workEvent(sequence, type, message, payload = {}) {
    return { id: `event-${sequence}`, sequence, type, display_message: message, payload, created_at: "2026-08-20T12:03:00Z" };
}
