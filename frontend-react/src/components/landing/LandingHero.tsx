import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CortexIcon } from "../shared/CortexIcon";
import { ProviderLogo } from "../shared/ProviderLogo";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./LandingHero.module.css";

const PROVIDERS = [
  { provider: "openai" as const, name: "OpenAI", models: "GPT-5.4 / 4o" },
  { provider: "claude" as const, name: "Claude", models: "Sonnet 4.6 / Opus" },
  { provider: "gemini" as const, name: "Gemini", models: "3.5 Pro / Flash" },
  { provider: "deepseek" as const, name: "DeepSeek", models: "V4 Flash / Reasoner" },
  { provider: "grok" as const, name: "Grok", models: "Grok 3" },
];

const HERO_EXAMPLES = [
  {
    query: "Architect a resilient real-time streaming pipeline with Redis & Kafka",
    tier: "T2 (Advanced Reasoning)",
    provider: "claude" as const,
    model: "Claude Sonnet 4.6",
    credits: "24 credits",
    latency: "380ms",
    savings: "42% saved vs baseline",
    synthesis: "Synthesized consensus from 3 frontier models with zero vendor lock-in.",
  },
  {
    query: "Generate high-throughput SQL CTE with recursive window aggregation",
    tier: "T1 (Coding & Speed)",
    provider: "deepseek" as const,
    model: "DeepSeek V4 Flash",
    credits: "8 credits",
    latency: "190ms",
    savings: "76% saved vs baseline",
    synthesis: "Optimal query plan confirmed across OpenAI & DeepSeek simultaneously.",
  },
  {
    query: "Deep competitive market analysis with live web search retrieval",
    tier: "T3 (Frontier + Web)",
    provider: "openai" as const,
    model: "GPT-5.4 Luna + Tavily",
    credits: "45 credits",
    latency: "610ms",
    savings: "35% saved vs baseline",
    synthesis: "Real-time research grounded with 6 cited verified web sources.",
  },
];

export function LandingHero() {
  const navigate = useNavigate();
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % HERO_EXAMPLES.length);
    }, 4500);
    return () => clearInterval(timer);
  }, []);

  const activeDemo = HERO_EXAMPLES[activeIdx];

  const scrollToPricing = () => {
    const el = document.getElementById("pricing");
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToDemo = () => {
    const el = document.getElementById("compare-demo");
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className={styles.heroSection} aria-label="Hero">
      <div className={styles.backgroundGlow} aria-hidden="true" />

      <div className={styles.container}>
        <ScrollReveal variant="fade-up" delay={50} className={styles.heroContent}>
          <div className={styles.badgePill}>
            <span className={styles.sparkleDot} />
            <span>MULTI-PROVIDER AI ORCHESTRATION GATEWAY</span>
          </div>

          <h1 className={styles.headline}>
            One Gateway for Every Frontier Model. <br />
            <span className={styles.gradientText}>Zero Vendor Lock-In.</span>
          </h1>

          <p className={styles.subheadline}>
            Intelligently route, compare, and synthesize responses across{" "}
            <strong>OpenAI</strong>, <strong>Claude</strong>, <strong>Gemini</strong>,{" "}
            <strong>DeepSeek</strong>, and <strong>Grok</strong> — backed by transparent monthly AI credits
            and unified API telemetry.
          </p>

          <div className={styles.ctaGroup}>
            <button
              type="button"
              className={styles.primaryCta}
              onClick={() => navigate("/")}
            >
              <span>Get Started Free</span>
              <CortexIcon name="chevron-right" size={16} strokeWidth={2.5} />
            </button>

            <button
              type="button"
              className={styles.secondaryCta}
              onClick={scrollToPricing}
            >
              <span>Explore Plans ($0 – $12.99)</span>
            </button>

            <button
              type="button"
              className={styles.tertiaryCta}
              onClick={scrollToDemo}
            >
              <CortexIcon name="compare" size={16} />
              <span>Interactive Compare Demo</span>
            </button>
          </div>

          <div className={styles.providersRibbon} aria-label="Supported Providers">
            <span className={styles.ribbonLabel}>ORCHESTRATING FRONTIER PROVIDERS:</span>
            <div className={styles.providerPills}>
              {PROVIDERS.map((p) => (
                <div key={p.provider} className={styles.providerPill}>
                  <ProviderLogo provider={p.provider} size={18} />
                  <span className={styles.providerName}>{p.name}</span>
                  <span className={styles.providerModels}>{p.models}</span>
                </div>
              ))}
            </div>
          </div>
        </ScrollReveal>

        {/* Hero Interactive Terminal & Telemetry Card */}
        <ScrollReveal variant="zoom-in" delay={200} className={styles.visualWrapper}>
          <div className={styles.interactiveCard}>
            <div className={styles.cardHeader}>
              <div className={styles.trafficLights}>
                <span className={`${styles.light} ${styles.red}`} />
                <span className={`${styles.light} ${styles.yellow}`} />
                <span className={`${styles.light} ${styles.green}`} />
              </div>
              <div className={styles.windowTitle}>
                <CortexIcon name="smart" size={14} />
                <span>Cortex Smart Router • Live Telemetry</span>
              </div>
              <span className={styles.liveIndicator}>
                <span className={styles.pulseDot} />
                LIVE
              </span>
            </div>

            <div className={styles.cardBody}>
              <div className={styles.promptBar}>
                <span className={styles.promptLabel}>Prompt:</span>
                <span className={styles.promptText}>"{activeDemo.query}"</span>
              </div>

              <div className={styles.routingGrid}>
                <div className={styles.routingItem}>
                  <span className={styles.routeKey}>Tier Decider</span>
                  <strong className={styles.routeVal}>{activeDemo.tier}</strong>
                </div>
                <div className={styles.routingItem}>
                  <span className={styles.routeKey}>Optimal Model</span>
                  <div className={styles.modelVal}>
                    <ProviderLogo provider={activeDemo.provider} size={16} />
                    <strong>{activeDemo.model}</strong>
                  </div>
                </div>
                <div className={styles.routingItem}>
                  <span className={styles.routeKey}>AI Credits</span>
                  <strong className={styles.routeVal}>{activeDemo.credits}</strong>
                </div>
                <div className={styles.routingItem}>
                  <span className={styles.routeKey}>Latency</span>
                  <strong className={styles.routeVal}>{activeDemo.latency}</strong>
                </div>
              </div>

              <div className={styles.synthesisBar}>
                <div className={styles.synthesisHeader}>
                  <CortexIcon name="sparkle" size={15} />
                  <span>Cortex Cross-Model Synthesis</span>
                  <span className={styles.savingsBadge}>{activeDemo.savings}</span>
                </div>
                <p className={styles.synthesisText}>{activeDemo.synthesis}</p>
              </div>

              <div className={styles.demoTabRow}>
                {HERO_EXAMPLES.map((ex, i) => (
                  <button
                    key={ex.model}
                    type="button"
                    className={`${styles.demoTab} ${i === activeIdx ? styles.demoTabActive : ""}`}
                    onClick={() => setActiveIdx(i)}
                  >
                    <span>{ex.model.split(" ")[0]} Flow</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
