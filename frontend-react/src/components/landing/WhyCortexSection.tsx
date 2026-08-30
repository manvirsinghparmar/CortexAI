import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./WhyCortexSection.module.css";

const PILLARS = [
  {
    icon: "cost" as const,
    title: "One Wallet, Every Model",
    blurb:
      "Stop paying for idle seats across separate subscriptions. One AI credit wallet covers OpenAI, Claude, Gemini, DeepSeek, and Grok — billed transparently for what you actually use.",
    tag: "COST TRANSPARENCY",
  },
  {
    icon: "smart" as const,
    title: "Routes to the Right Model",
    blurb:
      "Cortex classifies every prompt automatically and sends it to the fastest, cheapest model that can handle it — no manual picking, no wasted tokens.",
    tag: "SMART ROUTING",
  },
  {
    icon: "compare" as const,
    title: "Compare, Don't Guess",
    blurb:
      "Run any prompt across models side-by-side and get an unbiased synthesis of where they agree — and where they don't.",
    tag: "UNBIASED COMPARE",
  },
];

export function WhyCortexSection() {
  return (
    <section id="why-cortex" className={styles.section} aria-labelledby="why-cortex-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>WHY CORTEXAI</span>
          <h2 id="why-cortex-title" className={styles.title}>
            Everything Frontier AI, <span className={styles.highlight}>Nothing Extra.</span>
          </h2>
        </ScrollReveal>

        <div className={styles.grid}>
          {PILLARS.map((p, idx) => (
            <ScrollReveal
              key={p.title}
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

              <h3 className={styles.cardTitle}>{p.title}</h3>
              <p className={styles.blurb}>{p.blurb}</p>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
