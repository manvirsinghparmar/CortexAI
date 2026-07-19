import { get } from "./client";
import type { EntitlementsResponse } from "../types";

export function fetchEntitlements(signal?: AbortSignal): Promise<EntitlementsResponse> {
  return get<EntitlementsResponse>("/v1/entitlements", signal);
}
