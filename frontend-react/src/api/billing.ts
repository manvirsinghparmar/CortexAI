import { get, post } from "./client";
import type {
  BillingPlansResponse,
  BillingSubscriptionResponse,
  CheckoutSessionResponse,
  PortalSessionResponse,
  SubscriptionPlanCode,
} from "../types";

export function fetchPlans(signal?: AbortSignal): Promise<BillingPlansResponse> {
  return get<BillingPlansResponse>("/v1/billing/plans", signal);
}

export function fetchSubscription(signal?: AbortSignal): Promise<BillingSubscriptionResponse> {
  return get<BillingSubscriptionResponse>("/v1/billing/subscription", signal);
}

export function createCheckoutSession(
  planCode: SubscriptionPlanCode,
  signal?: AbortSignal,
): Promise<CheckoutSessionResponse> {
  return post<CheckoutSessionResponse>(
    "/v1/billing/checkout-session",
    { plan_code: planCode, billing_period: "monthly" },
    signal,
  );
}

export function createPortalSession(signal?: AbortSignal): Promise<PortalSessionResponse> {
  return post<PortalSessionResponse>("/v1/billing/portal-session", {}, signal);
}
