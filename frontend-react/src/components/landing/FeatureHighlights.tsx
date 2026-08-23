import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./FeatureHighlights.module.css";

const FEATURES = [
  {
    icon: "smart" as const,
    title: "Autonomous Smart Routing (T0–T3)",
    description:
      "Dynamically analyzes query complexity, context limits, and cost constraints. Automatically routes to the optimal model and handles transparent provider failover.",
    badge: "ROUTING & GOVERNANCE",
    points: [
      "Sub-millisecond intent and reasoning classification",
      "Dynamic cost ceilings and latency deadlines",
      "Automatic circuit breaker with 99.9% uptime fallback",
    ],
  },
  {
    icon: "compare" as const,
    title: "Side-by-Side Multi-Model Compare",
    description:
      "Send queries to 2 or 3 frontier models simultaneously. Compare reasoning strategies, code quality, speed, and cost side-by-side in real-time.",
    badge: "EVALUATION ENGINE",
    points: [
      "Synchronous chunk streaming across providers",
      "Unified prompt and conversation history",
      "Per-model latency, token count, and credit telemetry",
    ],
  },
  {
    icon: "analyze" as const,
    title: "Cortex Analysis & Synthesis",
    description:
      "Anonymizes and shuffles competing model outputs to produce an unbiased qualitative synthesis with agreement highlights and attributed disagreements.",
    badge: "CROSS-MODEL CONSENSUS",
    points: [
      "Blinded multi-model synthesis with zero vendor bias",
      "Identifies edge-case differences and unique insights",
      "Qualitative confidence rating (High / Medium / Limited)",
    ],
  },
  {
    icon: "tokens" as const,
    title: "Unified AI Credit Wallet & Ledger",
    description:
      "One monthly subscription covers all models. Atomic reserve and settle transitions ensure you pay only for actual input/output tokens with complete audit visibility.",
    badge: "TRANSPARENT METERING",
    points: [
      "100k, 1M, and 3M monthly credits with rollover protection",
      "Itemized transaction reconciliation ledger",
      "No sudden overages or unexpected cloud invoices",
    ],
  },
  {
    icon: "web" as const,
    title: "Live Web Search & Multimodal Files",
    description:
      "Ground your queries with real-time web retrieval via Tavily and upload multi-file attachments (PDF, DOCX, CSV, Code, Images) up to 20MB per file.",
    badge: "RESEARCH & ATTACHMENTS",
    points: [
      "Real-time search citations and domain verification",
      "Direct S3 upload for fast multimodal analysis",
      "Optional Prompt Optimizer for refined context clarity",
    ],
  },
  {
    icon: "user" as const,
    title: "Enterprise BYOK & Privacy Controls",
    description:
      "Bring Your Own Keys with AES-256 encrypted storage, metadata-only persistence policy, and automated PII redaction for privacy-sensitive workflows.",
    badge: "SECURITY & PRIVACY",
    points: [
      "Encrypted-at-rest tenant API secrets",
      "Metadata-only logging & optional PII redaction",
      "PostgreSQL ACID durability & Stripe billing integration",
    ],
  },
];

export function FeatureHighlights() {
  return (
    <section id="features" className={styles.section} aria-labelledby="features-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>FEATURE HIGHLIGHTS</span>
          <h2 id="features-title" className={styles.title}>
            Built for High-Velocity AI Workflows
          </h2>
          <p className={styles.subtitle}>
            Everything you need to orchestrate, evaluate, and scale frontier language models without
            the friction of multiple vendors or unpredictable costs.
          </p>
        </ScrollReveal>

        <div className={styles.grid}>
          {FEATURES.map((f, idx) => (
            <ScrollReveal
              key={f.title}
              variant="fade-up"
              delay={idx * 80}
              className={styles.card}
            >
              <div className={styles.cardHeader}>
                <div className={styles.iconCircle}>
                  <CortexIcon name={f.icon} size={22} />
                </div>
                <span className={styles.featureBadge}>{f.badge}</span>
              </div>

              <h3 className={styles.cardTitle}>{f.title}</h3>
              <p className={styles.cardDesc}>{f.description}</p>

              <ul className={styles.pointList}>
                {f.points.map((pt) => (
                  <li key={pt}>
                    <CortexIcon name="check" size={15} strokeWidth={2.5} />
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
