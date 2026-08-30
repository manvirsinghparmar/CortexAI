import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./PricingSection.module.css";

interface PlanTier {
  id: "free" | "plus" | "pro";
  name: string;
  monthlyPrice: number;
  annualMonthlyPrice: number;
  tagline: string;
  recommended?: boolean;
  credits: string;
  compareModels: number;
  modelAccess: string;
  filesLimit: string;
  rateLimit: string;
  features: string[];
  ctaLabel: string;
  ctaKind: "primary" | "secondary";
}

const TIERS: PlanTier[] = [
  {
    id: "free",
    name: "Free",
    monthlyPrice: 0,
    annualMonthlyPrice: 0,
    tagline: "For exploring CortexAI and daily tasks",
    credits: "100,000 AI credits / mo",
    compareModels: 2,
    modelAccess: "Economical & Standard models (GPT-4o-mini, Flash)",
    filesLimit: "1 file per request (up to 10 MB)",
    rateLimit: "5 requests / minute",
    features: [
      "100,000 AI credits per month",
      "Compare up to 2 models simultaneously",
      "Economical & Standard model access",
      "Full conversation history & model catalogue",
    ],
    ctaLabel: "Start Free",
    ctaKind: "secondary",
  },
  {
    id: "plus",
    name: "Plus",
    monthlyPrice: 6.99,
    annualMonthlyPrice: 5.59,
    tagline: "For regular research, coding, and production work",
    recommended: true,
    credits: "1,000,000 AI credits / mo",
    compareModels: 2,
    modelAccess: "Economical, Standard & Advanced models (Sonnet 4.6)",
    filesLimit: "3 files per request (up to 20 MB each)",
    rateLimit: "15 requests / minute",
    features: [
      "1,000,000 AI credits per month",
      "Advanced model access (incl. Claude Sonnet 4.6)",
      "Advanced Web Search & Citations",
      "Priority streaming throughput",
    ],
    ctaLabel: "Get Plus",
    ctaKind: "primary",
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 12.99,
    annualMonthlyPrice: 10.39,
    tagline: "For frontier-model power users and engineering teams",
    credits: "3,000,000 AI credits / mo",
    compareModels: 3,
    modelAccess: "All models including Premium (Opus 4.5/4.6, Terra)",
    filesLimit: "5 files per request (up to 20 MB each)",
    rateLimit: "30 requests / minute",
    features: [
      "3,000,000 AI credits per month",
      "Compare up to 3 models simultaneously",
      "Cortex Deep Analysis & Attribution Engine",
      "Premium frontier access (Claude Opus, GPT-5.6 Terra)",
    ],
    ctaLabel: "Get Pro Access",
    ctaKind: "secondary",
  },
];

interface PricingSectionProps {
  onSelectPlan?: (planId: "free" | "plus" | "pro") => void;
}

export function PricingSection({ onSelectPlan }: PricingSectionProps) {
  const navigate = useNavigate();
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");

  const handlePlanClick = (tier: PlanTier) => {
    if (onSelectPlan) {
      onSelectPlan(tier.id);
    } else {
      navigate("/pricing");
    }
  };

  return (
    <section id="pricing" className={styles.section} aria-labelledby="pricing-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>TRANSPARENT SUBSCRIPTION TIERS</span>
          <h2 id="pricing-title" className={styles.title}>
            Simple, Predictable Monthly Pricing
          </h2>
          <p className={styles.subtitle}>
            Start for free, then scale up when you need higher AI credits, advanced frontier models,
            or 3-model comparison with Cortex deep synthesis.
          </p>

          {/* Billing Cycle Toggle */}
          <div className={styles.toggleWrapper}>
            <div className={styles.toggleContainer} role="radiogroup" aria-label="Billing cycle">
              <button
                type="button"
                role="radio"
                aria-checked={billingCycle === "monthly"}
                className={`${styles.toggleButton} ${billingCycle === "monthly" ? styles.toggleActive : ""}`}
                onClick={() => setBillingCycle("monthly")}
              >
                Monthly billing
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={billingCycle === "annual"}
                className={`${styles.toggleButton} ${billingCycle === "annual" ? styles.toggleActive : ""}`}
                onClick={() => setBillingCycle("annual")}
              >
                <span>Annual billing</span>
                <span className={styles.discountBadge}>SAVE 20%</span>
              </button>
            </div>
          </div>
        </ScrollReveal>

        {/* Pricing Cards Grid */}
        <div className={styles.grid}>
          {TIERS.map((tier, idx) => {
            const price =
              billingCycle === "annual" ? tier.annualMonthlyPrice : tier.monthlyPrice;
            const priceDisplay = price === 0 ? "$0" : `$${price.toFixed(2)}`;

            return (
              <ScrollReveal
                key={tier.id}
                variant="fade-up"
                delay={idx * 100}
                className={`${styles.card} ${tier.recommended ? styles.recommendedCard : ""}`}
              >
                <div className={styles.cardTopRow}>
                  {tier.recommended ? (
                    <span className={styles.recommendedBadge}>MOST POPULAR • RECOMMENDED</span>
                  ) : (
                    <span className={styles.tierNameBadge}>{tier.name.toUpperCase()} PLAN</span>
                  )}
                </div>

                <div className={styles.cardHeader}>
                  <h3 className={styles.tierName}>{tier.name}</h3>
                  <p className={styles.tierTagline}>{tier.tagline}</p>
                </div>

                <div className={styles.priceBlock}>
                  <div className={styles.priceRow}>
                    <span className={styles.priceAmount}>{priceDisplay}</span>
                    <span className={styles.pricePeriod}>/ month</span>
                  </div>
                  {billingCycle === "annual" && tier.monthlyPrice > 0 && (
                    <span className={styles.annualNote}>
                      Billed annually ($
                      {(tier.annualMonthlyPrice * 12).toFixed(2)}/yr)
                    </span>
                  )}
                </div>

                <div className={styles.creditsHighlight}>
                  <CortexIcon name="tokens" size={16} />
                  <strong>{tier.credits}</strong>
                </div>

                <ul className={styles.featureList}>
                  {tier.features.map((feature) => (
                    <li key={feature} className={styles.featureItem}>
                      <CortexIcon name="check" size={16} strokeWidth={2.2} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  className={
                    tier.ctaKind === "primary" ? styles.primaryButton : styles.secondaryButton
                  }
                  onClick={() => handlePlanClick(tier)}
                >
                  <span>{tier.ctaLabel}</span>
                  <CortexIcon name="chevron-right" size={15} strokeWidth={2.5} />
                </button>
              </ScrollReveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
