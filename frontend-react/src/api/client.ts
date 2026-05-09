/**
 * Base HTTP client. Injects the API key / session cookie automatically and
 * normalises error responses into a typed Error.
 *
 * Auth priority (mirrors the backend's dependency):
 *   1. X-API-Key header (dev / BYOK flows)
 *   2. Session cookie (Cognito OAuth — sent automatically by the browser)
 */

const getApiKey = (): string | null => {
  // runtime-config.js may inject window.__CORTEX_API_KEY at load time
  const w = window as unknown as { __CORTEX_API_KEY?: string };
  return w.__CORTEX_API_KEY ?? null;
};

function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  const key = getApiKey();
  if (key) {
    headers["X-API-Key"] = key;
  }
  return headers;
}

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as Record<string, unknown>).detail)
        : res.statusText;
    throw new ApiClientError(res.status, detail, body);
  }
  return res.json() as Promise<T>;
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    method: "GET",
    credentials: "include",
    headers: buildHeaders(),
  });
  return handleResponse<T>(res);
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    method: "DELETE",
    credentials: "include",
    headers: buildHeaders(),
  });
  return handleResponse<T>(res);
}

/** Opens a fetch stream and yields raw text lines (for SSE). */
export async function* streamPost(path: string, body: unknown): AsyncGenerator<string> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    let errBody: unknown;
    try {
      errBody = await res.json();
    } catch {
      errBody = null;
    }
    const detail =
      typeof errBody === "object" &&
      errBody !== null &&
      "detail" in errBody
        ? String((errBody as Record<string, unknown>).detail)
        : res.statusText;
    throw new ApiClientError(res.status, detail, errBody);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      yield line;
    }
  }
  if (buffer) yield buffer;
}
