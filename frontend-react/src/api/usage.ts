import { get } from "./client";
import type { UsageSummary } from "../types";

export interface UsageSummaryParams {
  from?: string;
  to?: string;
}

export async function fetchUsageSummary(
  params: UsageSummaryParams = {},
  signal?: AbortSignal,
): Promise<UsageSummary> {
  const query = new URLSearchParams();
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);

  const suffix = query.toString();
  return get<UsageSummary>(`/v1/usage/summary${suffix ? `?${suffix}` : ""}`, signal);
}
