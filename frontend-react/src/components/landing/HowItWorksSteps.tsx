import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./HowItWorksSteps.module.css";

const STEPS = [
  {
    step: "01",
    title: "Ingest & Optional Prompt Rewrite",
    description:
      "Submit complex prompts, codebases, or multi-file attachments (PDF, DOCX, CSV, Images). Optional prompt optimization refines context clarity, and Tavily search retrieves real-time web evidence when needed.",
    icon: "improve" as const,
    telemetry: "Optimized prompt • 0ms cold start",
    badge: "INGESTION & RESEARCH",
  },
  {
    step: "02",
    title: "Autonomous Tier Decider (T0–T3)",
    description:
      "CortexAI classifies query complexity into tiers: T0 (Fast/Economical), T1 (Standard/Code), T2 (Advanced Reasoning), and T3 (Frontier Synthesis). It enforces cost caps and latency bounds automatically.",
    icon: "smart" as const,
    telemetry: "Tier T2 selected • Cost ceiling $0.004",
    badge: "DYNAMIC ROUTER",
  },
  {
    step: "03",
    title: "Synchronous Multi-Provider Execution",
    description:
      "Execute single ask or compare mode across 2 or 3 frontier models (OpenAI, Claude, Gemini, DeepSeek, Grok) concurrently with resilient chunk streaming and circuit-breaker fault tolerance.",
    icon: "compare" as const,
    telemetry: "3 streams connected • Heartbeat 15s",
    badge: "PARALLEL GATEWAY",
  },
  {
    step: "04",
    title: "Cortex Synthesis & Atomic Settlement",
    description:
      "Anonymized outputs are evaluated for agreements and disagreements with qualitative confidence attribution. Credits are atomically settled against actual input/output usage with zero billing surprises.",
    icon: "analyze" as const,
    telemetry: "Consensus generated • Settled 18 cr",
    badge: "SYNTHESIS & AUDIT",
  },
];

export function HowItWorksSteps() {
  return (
    <section id="how-it-works" className={styles.section} aria-labelledby="how-it-works-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>ARCHITECTURE & FLOW</span>
          <h2 id="how-it-works-title" className={styles.title}>
            The Intelligent Orchestration Pipeline
          </h2>
          <p className={styles.subtitle}>
            From initial prompt ingestion to cross-model consensus and itemized credit reconciliation,
            every request travels through our resilient 4-stage gateway pipeline.
          </p>
        </ScrollReveal>

        <div className={styles.pipeline}>
          <div className={styles.connectingLine} aria-hidden="true" />

          <div className={styles.stepsGrid}>
            {STEPS.map((step, idx) => (
              <ScrollReveal
                key={step.step}
                variant="fade-up"
                delay={idx * 140}
                className={styles.stepCard}
              >
                <div className={styles.stepHeader}>
                  <div className={styles.stepNumberBadge}>
                    <span>{step.step}</span>
                  </div>
                  <div className={styles.iconBox}>
                    <CortexIcon name={step.icon} size={20} />
                  </div>
                  <span className={styles.stepBadge}>{step.badge}</span>
                </div>

                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDesc}>{step.description}</p>

                <div className={styles.telemetryTag}>
                  <CortexIcon name="latency" size={13} />
                  <span>{step.telemetry}</span>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
