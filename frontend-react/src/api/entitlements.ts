import { get } from "./client";
import type { CreditTransactionsResponse, EntitlementsResponse } from "../types";

export function fetchEntitlements(signal?: AbortSignal): Promise<EntitlementsResponse> {
  return get<EntitlementsResponse>("/v1/entitlements", signal);
}

export function fetchCreditTransactions(
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<CreditTransactionsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return get<CreditTransactionsResponse>(`/v1/credits/transactions?${params}`, signal);
}
