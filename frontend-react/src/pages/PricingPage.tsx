import { useMemo } from "react";
import { SubscriptionPageShell } from "../components/subscription/SubscriptionPageShell";
import { CortexIcon } from "../components/shared/CortexIcon";
import { useAuth } from "../hooks/useAuth";
import {
  useSubscription,
  type CheckoutConfirmationStatus,
  type HostedBillingAction,
} from "../hooks/useSubscription";
import type { SubscriptionError } from "../subscription/subscriptionErrors";
import { getAccountMenuSubscriptionPresentation } from "../subscription/accountMenuPresentation";
import type {
  BillingPlansResponse,
  BillingSubscriptionResponse,
  EntitlementsResponse,
  SubscriptionPlanCode,
} from "../types";
import {
  isCancelled,
  isPaymentPastDue,
  resolvePlanAction,
} from "../subscription/planActions";
import {
  formatPrice,
  planFeatures,
  planSummary,
} from "../subscription/planPresentation";
import styles from "./PricingPage.module.css";

interface PricingPageContentProps {
  plans: BillingPlansResponse | null;
  subscription: BillingSubscriptionResponse | null;
  entitlements: EntitlementsResponse | null;
  loading: boolean;
  action: HostedBillingAction;
  error: SubscriptionError | null;
  checkoutConfirmation: CheckoutConfirmationStatus;
  loggedIn: boolean;
  authEnabled: boolean;
  onLogin: () => void;
  onCheckout: (planCode: SubscriptionPlanCode) => void;
  onPortal: () => void;
  onClearError: () => void;
}

export function PricingPage() {
  const { whoAmI, cognitoConfig, loading: authLoading, loggedIn, login, logout } = useAuth();
  const subscriptionState = useSubscription({ authLoading, loggedIn });
  const authEnabled = cognitoConfig?.enabled ?? false;
  const accountSubscription = getAccountMenuSubscriptionPresentation(
    subscriptionState.entitlements,
  );

  return (
    <SubscriptionPageShell
      title="Plans"
      subtitle="Choose the access and allowances that fit your work"
      authLoading={authLoading}
      authEnabled={authEnabled}
      loggedIn={loggedIn}
      whoAmI={whoAmI}
      onLogin={login}
      onLogout={logout}
      planLabel={loggedIn ? accountSubscription.planLabel : undefined}
      billingActionLabel={loggedIn ? accountSubscription.billingActionLabel : undefined}
      billingPastDue={accountSubscription.billingPastDue}
      billingDestination={accountSubscription.billingDestination}
    >
      <PricingPageContent
        plans={subscriptionState.plans}
        subscription={subscriptionState.subscription}
        entitlements={subscriptionState.entitlements}
        loading={subscriptionState.loading}
        action={subscriptionState.action}
        error={subscriptionState.error}
        checkoutConfirmation={subscriptionState.checkoutConfirmation}
        loggedIn={loggedIn}
        authEnabled={authEnabled}
        onLogin={login}
        onCheckout={(planCode) => void subscriptionState.startCheckout(planCode)}
        onPortal={() => void subscriptionState.openPortal()}
        onClearError={subscriptionState.clearError}
      />
    </SubscriptionPageShell>
  );
}

export function PricingPageContent({
  plans,
  subscription,
  entitlements,
  loading,
  action,
  error,
  checkoutConfirmation,
  loggedIn,
  authEnabled,
  onLogin,
  onCheckout,
  onPortal,
  onClearError,
}: PricingPageContentProps) {
  const currentPlanCode = entitlements?.plan.code ?? subscription?.plan_code ?? null;
  const currentStatus = entitlements?.plan.status ?? subscription?.status;
  const billingEnabled = plans?.billing_enabled ?? false;
  const orderedPlans = useMemo(
    () => [...(plans?.plans ?? [])].sort((left, right) => left.monthly_price - right.monthly_price),
    [plans],
  );

  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-labelledby="pricing-title">
        <span className={styles.eyebrow}>MONTHLY PLANS</span>
        <h1 id="pricing-title">More choice, with clear monthly limits.</h1>
        <p>
          Start free, then move up when you need more AI credits, broader model access, or
          three-model comparisons.
        </p>
      </section>

      <CheckoutNotice status={checkoutConfirmation} />

      {isPaymentPastDue(currentStatus) ? (
        <div className={`${styles.notice} ${styles.noticeWarning}`} role="alert">
          <CortexIcon name="cost" size={18} />
          <span>Your payment needs attention. Use Update payment to keep paid access.</span>
        </div>
      ) : null}

      {isCancelled(currentStatus) ? (
        <div className={styles.notice} role="status">
          <CortexIcon name="history" size={18} />
          <span>Your paid subscription has ended. You can choose a new plan at any time.</span>
        </div>
      ) : null}

      {error ? (
        <div className={`${styles.notice} ${styles.noticeError}`} role="alert">
          <span>{error.message}</span>
          <button type="button" onClick={onClearError}>
            Dismiss
          </button>
        </div>
      ) : null}

      {loading && orderedPlans.length === 0 ? (
        <div className={styles.loadingPanel} role="status">
          Loading plans…
        </div>
      ) : null}

      {!loading && orderedPlans.length === 0 ? (
        <div className={styles.loadingPanel} role="alert">
          Plan information is temporarily unavailable. Try again shortly.
        </div>
      ) : null}

      {orderedPlans.length > 0 ? (
        <section className={styles.planGrid} aria-label="Subscription plans">
          {orderedPlans.map((plan) => {
            const isCurrent = loggedIn && plan.code === currentPlanCode;
            const planAction = resolvePlanAction({
              plan,
              currentPlanCode,
              currentStatus,
              billingEnabled,
              canManage: subscription?.can_manage ?? false,
              loggedIn,
              authEnabled,
              action,
              onLogin,
              onCheckout,
              onPortal,
            });
            return (
              <article
                key={plan.code}
                className={`${styles.planCard} ${plan.recommended ? styles.planCardRecommended : ""} ${isCurrent ? styles.planCardCurrent : ""}`}
              >
                <div className={styles.badgeRow}>
                  {plan.recommended ? (
                    <span className={styles.recommendedBadge}>RECOMMENDED</span>
                  ) : (
                    <span />
                  )}
                  {isCurrent ? <span className={styles.currentBadge}>CURRENT PLAN</span> : null}
                </div>

                <div className={styles.planHeading}>
                  <div>
                    <h2>{plan.display_name}</h2>
                    <p>{planSummary(plan.code)}</p>
                  </div>
                  <div className={styles.price}>
                    <strong>{formatPrice(plan.monthly_price)}</strong>
                    <span>/ month</span>
                  </div>
                </div>

                <ul className={styles.featureList}>
                  {planFeatures(plan).map((feature) => (
                    <li key={feature}>
                      <CortexIcon name="check" size={16} strokeWidth={2.2} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  className={
                    planAction.kind === "primary" ? styles.primaryButton : styles.secondaryButton
                  }
                  disabled={planAction.disabled}
                  onClick={planAction.onClick}
                >
                  {action && !planAction.disabled ? "Opening…" : planAction.label}
                </button>
              </article>
            );
          })}
        </section>
      ) : null}

      <section className={styles.disclosure} aria-label="Plan details">
        <h2>Good to know</h2>
        <ul>
          <li>Plans are monthly subscriptions and usage resets each billing period.</li>
          <li>Model availability can change as providers update their services.</li>
          <li>Allowances are defined limits; no plan promises unlimited usage.</li>
          <li>
            Taxes may apply. Cancellation and payment details are managed in the billing portal.
          </li>
        </ul>
      </section>
    </div>
  );
}

function CheckoutNotice({ status }: { status: CheckoutConfirmationStatus }) {
  if (status === "idle") return null;
  const copy = {
    cancelled: "Checkout was cancelled. Your existing plan has not changed.",
    confirming: "Payment received. Waiting for the verified subscription update…",
    confirmed: "Your paid plan is active and ready to use.",
    pending: "Payment is still being confirmed. Your current access remains unchanged for now.",
  }[status];
  const tone =
    status === "confirmed"
      ? styles.noticeSuccess
      : status === "pending"
        ? styles.noticeWarning
        : "";
  return (
    <div className={`${styles.notice} ${tone}`} role="status">
      {copy}
    </div>
  );
}
