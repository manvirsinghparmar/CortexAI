import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./PricingSection.module.css";

export function BillingNotes() {
  return (
    <div className={styles.section}>
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.disclosures}>
          <div className={styles.disclosureCard}>
            <div className={styles.disclosureHeader}>
              <CortexIcon name="cost" size={18} />
              <h4>Good to know about CortexAI Billing</h4>
            </div>
            <div className={styles.disclosureGrid}>
              <div className={styles.disclosureItem}>
                <strong>Monthly AI Credit Resets</strong>
                <p>Allowances reset each billing cycle. Input/output tokens are billed atomically with transparent reconciliation.</p>
              </div>
              <div className={styles.disclosureItem}>
                <strong>Zero Vendor Lock-In</strong>
                <p>Switch between OpenAI, Claude, Gemini, DeepSeek, and Grok seamlessly without separate vendor subscriptions.</p>
              </div>
              <div className={styles.disclosureItem}>
                <strong>Cancel Anytime</strong>
                <p>Manage and cancel subscriptions directly in the secure Stripe customer portal with no long-term contracts.</p>
              </div>
              <div className={styles.disclosureItem}>
                <strong>No Hidden Overages</strong>
                <p>Credit balances never go negative; preflight reservations protect you from surprise token bills.</p>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </div>
  );
}
