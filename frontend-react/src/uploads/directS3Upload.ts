import type { PresignedPost } from "../types";

export type S3UploadFailureKind = "aborted" | "network" | "http";

export class S3UploadError extends Error {
  constructor(
    public readonly kind: S3UploadFailureKind,
    public readonly status?: number,
  ) {
    super(
      kind === "aborted"
        ? "Upload cancelled."
        : kind === "network"
          ? "Storage upload could not be reached. Check S3 CORS and network access."
          : "Storage rejected the upload.",
    );
    this.name = "S3UploadError";
  }
}

interface DirectS3UploadOptions {
  signal?: AbortSignal;
  onProgress?: (percent: number) => void;
  xhrFactory?: () => XMLHttpRequest;
}

export function uploadFileDirectlyToS3(
  file: File,
  upload: PresignedPost,
  options: DirectS3UploadOptions = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = options.xhrFactory?.() ?? new XMLHttpRequest();
    let settled = false;

    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      options.signal?.removeEventListener("abort", abortUpload);
      callback();
    };
    const abortUpload = () => xhr.abort();

    xhr.open("POST", upload.url, true);
    xhr.withCredentials = false;
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) return;
      const percent = Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100)));
      options.onProgress?.(percent);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        finish(resolve);
        return;
      }
      finish(() => reject(new S3UploadError("http", xhr.status)));
    };
    xhr.onerror = () => finish(() => reject(new S3UploadError("network")));
    xhr.onabort = () => finish(() => reject(new S3UploadError("aborted")));

    if (options.signal?.aborted) {
      abortUpload();
      return;
    }
    options.signal?.addEventListener("abort", abortUpload, { once: true });

    const form = new FormData();
    for (const [name, value] of Object.entries(upload.fields)) {
      form.append(name, value);
    }
    form.append("file", file, file.name || "file");
    xhr.send(form);
  });
}
