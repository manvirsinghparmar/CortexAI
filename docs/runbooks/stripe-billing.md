# Stripe Hosted Billing Sessions

This runbook covers WP7 server-side Stripe Customer, Checkout, and Customer Portal session creation. It does not cover webhook-driven paid access; keep production billing disabled until the WP8 verified webhook lifecycle is deployed and validated.

## Safety invariants

- Stripe secret keys stay in the backend environment and must never appear in frontend runtime config, logs, source control, or Postman variables.
- The browser submits only `plan_code` and `billing_period`. Price IDs, amounts, currencies, Customer IDs, and all redirect URLs are server-owned.
- `config/subscription_plans.yaml` maps each paid plan to an environment-variable name; the environment supplies the actual recurring Stripe Price ID.
- Hosted Checkout and Portal URLs are short-lived responses and are never stored as account state.
- Checkout/Portal creation does not grant paid access. Only verified Stripe webhook state may do so.

## Required configuration

Install `requirements.txt`, configure Stripe products and recurring monthly Prices in the Stripe Dashboard, and set:

```ini
BILLING_ENABLED=true
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PLUS_MONTHLY_PRICE_ID=price_...
STRIPE_PRO_MONTHLY_PRICE_ID=price_...
STRIPE_CHECKOUT_SUCCESS_URL=https://app.example.com/settings/billing?checkout=success
STRIPE_CHECKOUT_CANCEL_URL=https://app.example.com/plans?checkout=canceled
STRIPE_PORTAL_RETURN_URL=https://app.example.com/settings/billing
```

`STRIPE_API_VERSION` is optional. Leave it unset to use the version pinned by the installed Stripe SDK unless a reviewed webhook/API compatibility test requires an override. `STRIPE_WEBHOOK_SECRET` is reserved for WP8 and is not read by these session routes. Configure and activate the Stripe Customer Portal in the Dashboard before testing Portal sessions.

HTTP loopback redirect URLs are accepted only for `localhost`, `127.0.0.1`, or `::1` development. Non-loopback URLs must use HTTPS. Startup fails conservatively when billing is enabled and any required value is missing or malformed.

## Safe validation

1. Start with Stripe test-mode keys and Prices only.
2. Run `python -m pytest tests/test_stripe_billing.py tests/test_billing_repository.py -q`. These tests inject mock clients and make no Stripe calls.
3. Start the API and authenticate through a signed session or Cognito bearer token. API-key-only auth is intentionally rejected.
4. Request Plus and Pro Checkout separately. Confirm the Stripe-hosted page shows the expected server-configured recurring Price.
5. Confirm a Customer ID is persisted once on the correct `billing_accounts` row.
6. For an account with a provider-live subscription snapshot, confirm Checkout returns `destination: "portal"` and no second Checkout subscription is created.
7. Request the Portal endpoint and confirm the return action uses `STRIPE_PORTAL_RETURN_URL`.

Do not complete a real-money Checkout as part of automated tests. WP7 has no webhook authority, so a completed Stripe Checkout alone must not change `/v1/entitlements`.

## Disable and troubleshoot

Set `BILLING_ENABLED=false` to stop new hosted-session creation. The app continues to start, users resolve to Free under the existing lifecycle policy, and both hosted-session endpoints return `503 billing_not_configured` without initializing Stripe.

- `409 stripe_customer_required`: the account has no persisted Customer; use Checkout for first purchase or reconcile reviewed provider state.
- `502 billing_provider_unavailable`: Stripe rejected or could not complete the request; use request correlation logs and the Stripe Dashboard request log without exposing raw provider errors to the client.
- Startup configuration error: verify every required variable, ensure paid plan values begin with `price_`, use a backend `sk_test_`/`sk_live_` secret, and verify redirect URL schemes.

Do not manually insert paid subscription rows to compensate for Checkout issues. Until WP8 is live, leave billing disabled in production.
