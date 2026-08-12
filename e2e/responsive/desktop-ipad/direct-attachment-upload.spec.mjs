import { test, expect } from "../fixtures/responsive-e2e.mjs";

test("direct attachment upload shows progress, completes, and enables Send", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.s3DelayMs = 250;

    await page.locator("#attachmentInput").setInputFiles({
        name: "direct-report.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("direct browser to storage payload"),
    });

    const chip = attachmentChip(page, "direct-report.txt");
    await expect(chip).toBeVisible();
    await expect(chip.getByRole("progressbar", { name: /uploading/i })).toBeVisible();
    await expect(chip).toContainText("Ready");
    await expect(page.locator("#submitBtn")).toBeEnabled();

    expect(state.directUploadIntentRequests).toHaveLength(1);
    expect(state.directUploadIntentRequests[0]).toMatchObject({
        files: [{
            filename: "direct-report.txt",
            mime_type: "text/plain",
            size_bytes: 33,
        }],
    });
    expect(JSON.stringify(state.directUploadIntentRequests[0])).not.toContain(
        "direct browser to storage payload",
    );
    expect(state.s3UploadRequests).toHaveLength(1);
    expect(state.completeUploadRequests).toHaveLength(1);
    const s3Request = state.s3UploadRequests[0];
    expect(s3Request.headers.authorization).toBeUndefined();
    expect(s3Request.headers["x-api-key"]).toBeUndefined();
    expect(s3Request.body.indexOf('name="policy"')).toBeGreaterThanOrEqual(0);
    expect(s3Request.body.indexOf('name="file"')).toBeGreaterThan(
        s3Request.body.indexOf('name="policy"'),
    );
});

test("failed S3 upload exposes Retry and obtains a fresh intent", async ({ responsiveApp }) => {
    const { page, state } = responsiveApp;
    state.s3FailuresByFilename.set("retry-notes.txt", 2);

    await page.locator("#attachmentInput").setInputFiles({
        name: "retry-notes.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("retry payload"),
    });

    const chip = attachmentChip(page, "retry-notes.txt");
    const retry = chip.getByRole("button", { name: "Retry retry-notes.txt" });
    await expect(retry).toBeVisible();
    expect(state.completeUploadRequests).toHaveLength(0);

    await retry.click();

    await expect(chip).toContainText("Ready");
    expect(state.directUploadIntentRequests).toHaveLength(2);
    expect(state.s3UploadRequests).toHaveLength(3);
    expect(state.completeUploadRequests).toHaveLength(1);
});

test("one failed file does not remove ready siblings in a multi-file batch", async ({ responsiveApp }) => {
    const { page, state, reload } = responsiveApp;
    state.maxFilesPerRequest = 3;
    state.s3FailuresByFilename.set("bad.txt", 2);
    await reload();

    await page.locator("#attachmentInput").setInputFiles([
        { name: "good-a.txt", mimeType: "text/plain", buffer: Buffer.from("a") },
        { name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("b") },
        { name: "good-c.txt", mimeType: "text/plain", buffer: Buffer.from("c") },
    ]);

    await expect(attachmentChip(page, "good-a.txt")).toContainText("Ready");
    await expect(attachmentChip(page, "good-c.txt")).toContainText("Ready");
    const failed = attachmentChip(page, "bad.txt");
    await expect(failed.getByRole("button", { name: "Retry bad.txt" })).toBeVisible();
    expect(state.completeUploadRequests).toHaveLength(2);

    await failed.getByRole("button", { name: "Remove bad.txt" }).click();
    await expect(failed).toHaveCount(0);
    await page.locator("#promptInput").fill("Use the two ready files");
    await expect(page.locator("#submitBtn")).toBeEnabled();
});

function attachmentChip(page, filename) {
    return page.getByRole("listitem").filter({ hasText: filename });
}
