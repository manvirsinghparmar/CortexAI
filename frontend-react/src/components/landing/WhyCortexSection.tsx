import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./WhyCortexSection.module.css";

const PILLARS = [
  {
    icon: "cost" as const,
    problemTitle: "Subscription Sprawl & Idling Costs",
    problemText:
      "Subscribing separately to ChatGPT, Claude Pro, and Gemini Pro costs $60+/month. You pay full price for idle seats, juggle disconnected browser tabs, and receive unaligned token invoices.",
    solutionTitle: "One Unified AI Credit Wallet",
    solutionText:
      "One single monthly subscription ($0 Free, $6.99 Plus, $12.99 Pro) unlocks all frontier models. Transparent itemized reconciliation ensures you pay only for actual input and output tokens.",
    tag: "100% COST TRANSPARENCY",
  },
  {
    icon: "smart" as const,
    problemTitle: "Blind Model Selection & Token Burn",
    problemText:
      "Developers overpay by using expensive flagship models for simple tasks, or risk silent code bugs by routing complex distributed reasoning to basic lightweight models.",
    solutionTitle: "Autonomous Smart Routing (T0–T3)",
    solutionText:
      "Dynamic tier decider classifies prompt intent, context size, latency constraints, and cost limits. Automatically escalates or falls back across 5 frontier providers with circuit breaker resilience.",
    tag: "DYNAMIC INTENT ROUTING",
  },
  {
    icon: "compare" as const,
    problemTitle: "Single-Model Hallucinations & Bias",
    problemText:
      "Relying on one isolated model leaves you vulnerable to hallucinated APIs, architectural blind spots, and vendor-specific training biases.",
    solutionTitle: "Side-by-Side Compare & Synthesis",
    solutionText:
      "Stream 2 or 3 models simultaneously. Cortex Analysis automatically anonymizes outputs, compares evidence, identifies agreements, and flags critical disagreements with zero vendor bias.",
    tag: "UNBIASED CONSENSUS",
  },
];

export function WhyCortexSection() {
  return (
    <section id="why-cortex" className={styles.section} aria-labelledby="why-cortex-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>WHY CORTEXAI MATTERS</span>
          <h2 id="why-cortex-title" className={styles.title}>
            Engineered for Developers Who Demand <br className={styles.desktopBr} />
            <span className={styles.highlight}>Power, Precision, and Control.</span>
          </h2>
          <p className={styles.subtitle}>
            Stop switching between disjointed AI subscriptions and guessing which model to trust.
            CortexAI brings multi-provider orchestration, intelligent cost governance, and deep cross-model synthesis under one unified roof.
          </p>
        </ScrollReveal>

        <div className={styles.grid}>
          {PILLARS.map((p, idx) => (
            <ScrollReveal
              key={p.problemTitle}
              variant="fade-up"
              delay={idx * 120}
              className={styles.card}
            >
              <div className={styles.cardTop}>
                <div className={styles.iconCircle}>
                  <CortexIcon name={p.icon} size={22} strokeWidth={1.8} />
                </div>
                <span className={styles.cardTag}>{p.tag}</span>
              </div>

              <div className={styles.problemBox}>
                <div className={styles.boxLabel}>
                  <span className={styles.crossIcon}>✕</span>
                  <strong>The Old Way</strong>
                </div>
                <h3 className={styles.problemHeading}>{p.problemTitle}</h3>
                <p className={styles.problemDesc}>{p.problemText}</p>
              </div>

              <div className={styles.divider}>
                <span className={styles.dividerBadge}>VS</span>
              </div>

              <div className={styles.solutionBox}>
                <div className={styles.boxLabel}>
                  <span className={styles.checkIcon}>✓</span>
                  <strong>The CortexAI Way</strong>
                </div>
                <h3 className={styles.solutionHeading}>{p.solutionTitle}</h3>
                <p className={styles.solutionDesc}>{p.solutionText}</p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
