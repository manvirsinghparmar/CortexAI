import { describe, expect, it, vi } from "vitest";
import {
  S3UploadError,
  uploadFileDirectlyToS3,
} from "../uploads/directS3Upload";

describe("uploadFileDirectlyToS3", () => {
  it("posts every signed field followed by the file without Cortex headers", async () => {
    const xhr = new FakeXMLHttpRequest();
    const progress = vi.fn();
    const file = new File(["report"], "report.pdf", { type: "application/pdf" });
    const promise = uploadFileDirectlyToS3(
      file,
      {
        url: "https://bucket.s3.us-east-1.amazonaws.com/",
        fields: {
          key: "attachments/users/u/report.pdf",
          policy: "opaque-policy",
          "x-amz-signature": "opaque-signature",
        },
        expires_at: "2026-08-12T00:00:00Z",
      },
      {
        onProgress: progress,
        xhrFactory: () => xhr as unknown as XMLHttpRequest,
      },
    );

    xhr.emitProgress(1, 10);
    xhr.emitProgress(5, 10);
    xhr.emitProgress(10, 10);
    xhr.succeed(204);
    await promise;

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("https://bucket.s3.us-east-1.amazonaws.com/");
    expect(xhr.withCredentials).toBe(false);
    expect(xhr.headers).toEqual([]);
    expect(progress.mock.calls.map(([value]) => value)).toEqual([10, 50, 100]);

    const entries = Array.from((xhr.body as FormData).entries());
    expect(entries.slice(0, -1)).toEqual([
      ["key", "attachments/users/u/report.pdf"],
      ["policy", "opaque-policy"],
      ["x-amz-signature", "opaque-signature"],
    ]);
    expect(entries.at(-1)?.[0]).toBe("file");
    const appendedFile = entries.at(-1)?.[1] as File;
    expect(appendedFile).toMatchObject({
      name: "report.pdf",
      size: file.size,
      type: "application/pdf",
    });
  });

  it("reports storage network failures without exposing an S3 response body", async () => {
    const xhr = new FakeXMLHttpRequest();
    const promise = uploadFileDirectlyToS3(
      new File(["x"], "notes.txt", { type: "text/plain" }),
      {
        url: "https://bucket.s3.us-east-1.amazonaws.com/",
        fields: { key: "notes.txt" },
        expires_at: "2026-08-12T00:00:00Z",
      },
      { xhrFactory: () => xhr as unknown as XMLHttpRequest },
    );

    xhr.failNetwork();

    await expect(promise).rejects.toMatchObject({
      name: "S3UploadError",
      kind: "network",
    });
  });

  it("aborts the active XMLHttpRequest when its signal is cancelled", async () => {
    const xhr = new FakeXMLHttpRequest();
    const controller = new AbortController();
    const promise = uploadFileDirectlyToS3(
      new File(["x"], "notes.txt", { type: "text/plain" }),
      {
        url: "https://bucket.s3.us-east-1.amazonaws.com/",
        fields: { key: "notes.txt" },
        expires_at: "2026-08-12T00:00:00Z",
      },
      {
        signal: controller.signal,
        xhrFactory: () => xhr as unknown as XMLHttpRequest,
      },
    );

    controller.abort();

    await expect(promise).rejects.toBeInstanceOf(S3UploadError);
    expect(xhr.aborted).toBe(true);
  });
});

class FakeXMLHttpRequest {
  method = "";
  url = "";
  async = true;
  status = 0;
  withCredentials = true;
  body: Document | XMLHttpRequestBodyInit | null = null;
  aborted = false;
  headers: Array<[string, string]> = [];
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  open(method: string, url: string, async = true) {
    this.method = method;
    this.url = url;
    this.async = async;
  }

  setRequestHeader(name: string, value: string) {
    this.headers.push([name, value]);
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body;
  }

  abort() {
    this.aborted = true;
    this.onabort?.();
  }

  emitProgress(loaded: number, total: number) {
    this.upload.onprogress?.(
      new ProgressEvent("progress", {
        lengthComputable: true,
        loaded,
        total,
      }),
    );
  }

  succeed(status: number) {
    this.status = status;
    this.onload?.();
  }

  failNetwork() {
    this.onerror?.();
  }
}
