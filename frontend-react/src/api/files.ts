import { ApiClientError, buildHeaders, get } from "./client";
import type { FileUploadResponse } from "../types";

export async function uploadFile(file: File): Promise<FileUploadResponse> {
  const res = await fetch("/v1/files/upload", {
    method: "POST",
    credentials: "include",
    headers: buildHeaders({
      "Content-Type": file.type || "application/octet-stream",
      "X-File-Name": file.name || "file",
      "X-File-Content-Type": file.type || "application/octet-stream",
    }),
    body: await file.arrayBuffer(),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as Record<string, unknown>).detail
        : null;
    const message =
      typeof detail === "object" && detail !== null && "message" in detail
        ? String((detail as Record<string, unknown>).message)
        : typeof detail === "string"
          ? detail
          : res.statusText;
    throw new ApiClientError(res.status, message, body);
  }

  return res.json() as Promise<FileUploadResponse>;
}

export interface FileUploadTarget {
  provider: string;
  model: string;
}

export async function uploadFiles(
  files: File[],
  target?: FileUploadTarget,
): Promise<FileUploadResponse[]> {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name || "file");
  const headers = buildHeaders({
    "X-Provider": target?.provider,
    "X-Model": target?.model,
  });
  delete headers["Content-Type"];
  const res = await fetch("/v1/files/upload-batch", {
    method: "POST",
    credentials: "include",
    headers,
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as Record<string, unknown>).detail
        : null;
    const message =
      typeof detail === "object" && detail !== null && "message" in detail
        ? String((detail as Record<string, unknown>).message)
        : typeof detail === "string"
          ? detail
          : res.statusText;
    throw new ApiClientError(res.status, message, body);
  }
  const payload = (await res.json()) as { files: FileUploadResponse[] };
  return payload.files;
}

export async function fetchFileStatus(fileId: string): Promise<FileUploadResponse> {
  return get<FileUploadResponse>(`/v1/files/${encodeURIComponent(fileId)}`);
}

export async function deleteFile(fileId: string): Promise<void> {
  void fileId;
  // The backend has no DELETE /v1/files/{id} contract. Removing a chip is local-only.
}
