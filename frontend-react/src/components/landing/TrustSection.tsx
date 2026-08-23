import { CortexIcon } from "../shared/CortexIcon";
import { ProviderLogo } from "../shared/ProviderLogo";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./TrustSection.module.css";

const TRUST_PILLARS = [
  {
    title: "BYOK Tenant Key Security",
    desc: "Bring your own API keys encrypted-at-rest using AES-256 master key derivation with complete credential isolation.",
    badge: "AES-256 ENCRYPTION",
  },
  {
    title: "Zero-Retention Privacy Controls",
    desc: "Deploy in metadata-only persistence mode with optional PII redaction so prompt text never touches persistent storage.",
    badge: "DATA PRIVACY",
  },
  {
    title: "PostgreSQL ACID Durability",
    desc: "Every token reserve, settlement, and comparison run is backed by robust PostgreSQL relational integrity and immutable ledgers.",
    badge: "IMMUTABLE LEDGER",
  },
  {
    title: "99.9% High-Availability Gateway",
    desc: "Per-provider circuit breakers, streaming keepalive heartbeats, and automatic tier escalations eliminate downtime.",
    badge: "CIRCUIT BREAKER",
  },
];

const TESTIMONIALS = [
  {
    quote:
      "CortexAI replaced 4 separate subscriptions on our engineering team with one transparent AI credit wallet. Comparing Claude Sonnet and GPT-5 side-by-side with Cortex synthesis cut our evaluation time by 70%.",
    author: "Elena Rostova",
    role: "Head of AI Engineering, Veloce Labs",
  },
  {
    quote:
      "The autonomous smart router is incredible. It saves us thousands of dollars by routing low-complexity tasks to DeepSeek and reserving Claude Opus only for hard reasoning proofs.",
    author: "Marcus Chen",
    role: "Principal Systems Architect, HyperScale Cloud",
  },
  {
    quote:
      "Cortex Analysis synthesis is the killer feature. Having an unbiased cross-model consensus that flags subtle hallucinations gives our team supreme confidence before deploying prompts.",
    author: "Sarah Jenkins",
    role: "Staff Machine Learning Engineer, Synapse Data",
  },
];

const PROVIDER_LIST = [
  { id: "openai" as const, name: "OpenAI", status: "Active • 99.98% uptime" },
  { id: "claude" as const, name: "Anthropic Claude", status: "Active • 99.95% uptime" },
  { id: "gemini" as const, name: "Google Gemini", status: "Active • 99.99% uptime" },
  { id: "deepseek" as const, name: "DeepSeek AI", status: "Active • 99.92% uptime" },
  { id: "grok" as const, name: "xAI Grok", status: "Active • 99.90% uptime" },
];

export function TrustSection() {
  return (
    <section id="trust" className={styles.section} aria-labelledby="trust-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>TRUST, SECURITY & RELIABILITY</span>
          <h2 id="trust-title" className={styles.title}>
            Enterprise-Grade Orchestration & Security
          </h2>
          <p className={styles.subtitle}>
            Architected from the ground up for strict confidentiality, bulletproof reliability,
            and complete observability.
          </p>
        </ScrollReveal>

        {/* Security Pillars */}
        <div className={styles.pillarsGrid}>
          {TRUST_PILLARS.map((p, idx) => (
            <ScrollReveal
              key={p.title}
              variant="fade-up"
              delay={idx * 70}
              className={styles.pillarCard}
            >
              <span className={styles.pillarBadge}>{p.badge}</span>
              <h3 className={styles.pillarTitle}>{p.title}</h3>
              <p className={styles.pillarDesc}>{p.desc}</p>
            </ScrollReveal>
          ))}
        </div>

        {/* Provider Live Status Bar */}
        <ScrollReveal variant="zoom-in" delay={150} className={styles.providersBar}>
          <div className={styles.providersBarHeader}>
            <CortexIcon name="smart" size={16} />
            <span>Multi-Provider Gateway Health & Integrations</span>
          </div>
          <div className={styles.providersGrid}>
            {PROVIDER_LIST.map((p) => (
              <div key={p.id} className={styles.providerStatusItem}>
                <ProviderLogo provider={p.id} size={22} />
                <div>
                  <strong>{p.name}</strong>
                  <span>{p.status}</span>
                </div>
              </div>
            ))}
          </div>
        </ScrollReveal>

        {/* Testimonials Grid */}
        <div className={styles.testimonialsGrid}>
          {TESTIMONIALS.map((t, idx) => (
            <ScrollReveal
              key={t.author}
              variant="fade-up"
              delay={idx * 100}
              className={styles.testimonialCard}
            >
              <div className={styles.quoteIcon}>“</div>
              <p className={styles.quoteText}>{t.quote}</p>
              <div className={styles.authorMeta}>
                <strong>{t.author}</strong>
                <span>{t.role}</span>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
