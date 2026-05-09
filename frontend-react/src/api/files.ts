import { ApiClientError } from "./client";
import type { FileUploadResponse } from "../types";

const getApiKey = (): string | null => {
  const w = window as unknown as { __CORTEX_API_KEY?: string };
  return w.__CORTEX_API_KEY ?? null;
};

export async function uploadFile(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;

  const res = await fetch("/v1/files/upload", {
    method: "POST",
    credentials: "include",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as Record<string, unknown>).detail)
        : res.statusText;
    throw new ApiClientError(res.status, detail, body);
  }

  return res.json() as Promise<FileUploadResponse>;
}

export async function deleteFile(fileId: string): Promise<void> {
  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;

  await fetch(`/v1/files/${fileId}`, {
    method: "DELETE",
    credentials: "include",
    headers,
  });
}
