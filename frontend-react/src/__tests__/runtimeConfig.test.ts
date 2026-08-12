import { afterEach, describe, expect, it } from "vitest";
import { getAttachmentUploadMode } from "../config/runtimeConfig";

describe("attachment runtime config", () => {
  afterEach(() => {
    delete (
      window as unknown as {
        CORTEX_RUNTIME_CONFIG?: Record<string, unknown>;
      }
    ).CORTEX_RUNTIME_CONFIG;
  });

  it("selects direct mode only when the backend exposes it", () => {
    setRuntimeConfig({ directAttachmentUploads: true, legacyAttachmentUploads: true });
    expect(getAttachmentUploadMode()).toBe("direct");
  });

  it("falls back to legacy mode during rollout and can disable both paths", () => {
    setRuntimeConfig({ directAttachmentUploads: false, legacyAttachmentUploads: true });
    expect(getAttachmentUploadMode()).toBe("legacy");

    setRuntimeConfig({ directAttachmentUploads: false, legacyAttachmentUploads: false });
    expect(getAttachmentUploadMode()).toBe("disabled");
  });

  it("keeps legacy behavior for older runtime-config responses", () => {
    setRuntimeConfig({});
    expect(getAttachmentUploadMode()).toBe("legacy");
  });
});

function setRuntimeConfig(value: Record<string, unknown>): void {
  (
    window as unknown as {
      CORTEX_RUNTIME_CONFIG?: Record<string, unknown>;
    }
  ).CORTEX_RUNTIME_CONFIG = value;
}
