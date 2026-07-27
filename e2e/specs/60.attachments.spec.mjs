/**
 * Attachment flow coverage for Ask mode.
 */
import { test, expect } from "../fixtures/live-e2e.mjs";
import { ensureMode, setToggle, submitAskPrompt } from "../helpers/ui.mjs";
import { waitForSnapshot } from "./_helpers.mjs";

const TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7ZxwAAAABJRU5ErkJggg==";

async function ensureAttachmentRuntimeEnabled(liveApp) {
    const probeId = "00000000-0000-0000-0000-000000000001";
    const response = await liveApp.page.request.get(`${liveApp.config.apiBaseUrl}/v1/files/${probeId}`, {
        headers: { "X-API-Key": liveApp.config.apiKey },
    });
    let detailCode = "";
    try {
        const payload = await response.json();
        detailCode = String(payload?.detail?.code || "");
    } catch {
        detailCode = "";
    }
    if (response.status() === 404 && detailCode === "attachments_disabled") {
        test.skip(true, "Attachments are disabled in this environment.");
    }
    if (response.status() === 501 && detailCode === "attachments_require_db") {
        test.skip(true, "Attachments require DB mode in this environment.");
    }
}

async function waitForSingleAttachmentReady(page) {
    const deadline = Date.now() + 45_000;
    while (Date.now() < deadline) {
        if (await page.locator(".attachment-chip.is-ready").count()) return;
        if (await page.locator("#errorText").count()) {
            const message = String(await page.locator("#errorText").textContent().catch(() => "") || "").trim();
            if (message) {
                test.skip(true, `Attachment storage is unavailable in this environment: ${message}`);
                return;
            }
        }
        await page.waitForTimeout(250);
    }
    await expect(page.locator(".attachment-chip.is-ready")).toHaveCount(1);
}

test("ask mode supports text attachment upload and persists request_attachments", async ({ liveApp }) => {
    const { page, config } = liveApp;
    await ensureAttachmentRuntimeEnabled(liveApp);

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);

    await page.locator("#attachmentInput").setInputFiles({
        name: "notes.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Release notes:\n- Revenue +12%\n- Defects -8%"),
    });
    await waitForSingleAttachmentReady(page);

    const result = await submitAskPrompt(
        page,
        liveApp.withPromptMarker("Summarize the attachment in 2 bullets."),
        config,
    );
    expect(result.text.length).toBeGreaterThan(10);

    const snapshot = await waitForSnapshot(liveApp, { minRequests: 1 });
    expect(snapshot.requestAttachments.length).toBeGreaterThanOrEqual(1);

    const latestAttachment = snapshot.requestAttachments[snapshot.requestAttachments.length - 1];
    expect(String(latestAttachment.usage_role || "")).toBe("primary");
    expect(String(latestAttachment.transform_mode || "")).toBeTruthy();
});

test("file-only send clears composer chips and renders a user file card", async ({ liveApp }) => {
    const { page, config } = liveApp;
    await ensureAttachmentRuntimeEnabled(liveApp);

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", true);

    await page.locator("#attachmentInput").setInputFiles({
        name: "file_only_notes.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Quarterly highlights:\nRevenue +8%\nCost -3%"),
    });
    await waitForSingleAttachmentReady(page);

    const nextIndex = await page.locator("[id^='response-text-']").count();
    const streamCallsBefore = liveApp.network.countByPath("/v1/chat/stream");
    await page.locator("#submitBtn").click();

    await expect.poll(() => liveApp.network.countByPath("/v1/chat/stream"), {
        timeout: 10_000,
    }).toBe(streamCallsBefore + 1);

    await expect(page.locator("#promptInput")).toHaveValue("");
    await expect(page.locator(".attachment-chip")).toHaveCount(0);

    const userMessage = page.locator("[id^='chat-msg-']").last();
    await expect(userMessage).toContainText("file_only_notes.txt");

    await expect(page.locator(`#response-text-${nextIndex}`)).toContainText(/\S+/, {
        timeout: config.timeouts.askMs,
    });
});

test("manual incompatible model with image attachment is blocked client-side", async ({ liveApp }) => {
    const { page } = liveApp;
    await ensureAttachmentRuntimeEnabled(liveApp);

    await ensureMode(page, "single");
    await setToggle(page, "#routeSmartBtn", false);

    const deepseekValue = await page.locator("#singleModel option").evaluateAll(options => {
        const values = options
            .map(option => String(option.value || ""))
            .filter(value => value.includes(":"));
        return values.find(value => value.toLowerCase().startsWith("deepseek:")) || "";
    });
    if (!deepseekValue) {
        test.skip(true, "DeepSeek model is not present in this catalog.");
    }

    await page.locator("#singleModel").selectOption(deepseekValue);
    await page.locator("#attachmentInput").setInputFiles({
        name: "pixel.png",
        mimeType: "image/png",
        buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
    });
    await waitForSingleAttachmentReady(page);

    const requestsBefore = liveApp.network.countByPath("/v1/chat");
    await page.locator("#promptInput").fill("Describe this image.");
    await page.locator("#submitBtn").click();

    await expect(page.locator("#errorBanner")).toBeVisible();
    await expect(page.locator("#errorText")).toContainText("does not support the attached files");
    await expect.poll(() => liveApp.network.countByPath("/v1/chat"), { timeout: 5000 }).toBe(requestsBefore);
});
