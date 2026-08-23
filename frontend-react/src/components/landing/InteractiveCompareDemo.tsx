import { useState } from "react";
import { CortexIcon } from "../shared/CortexIcon";
import { ProviderLogo } from "../shared/ProviderLogo";
import { ScrollReveal } from "./ScrollReveal";
import styles from "./InteractiveCompareDemo.module.css";

interface DemoScenario {
  id: string;
  title: string;
  tag: string;
  prompt: string;
  models: Array<{
    provider: "openai" | "claude" | "deepseek";
    name: string;
    modelId: string;
    speed: string;
    tokens: string;
    credits: string;
    snippet: string;
    highlight: string;
  }>;
  synthesis: {
    consensus: string;
    agreements: string[];
    disagreements: Array<{ model: string; note: string }>;
    confidence: "High" | "Medium" | "Limited";
  };
}

const SCENARIOS: DemoScenario[] = [
  {
    id: "distributed-raft",
    title: "Distributed Raft Consensus & Split-Brain",
    tag: "SYSTEMS ARCHITECTURE",
    prompt:
      "Explain how Raft prevents split-brain during asymmetric network partitions and provide a resilient term lease verification snippet in Go.",
    models: [
      {
        provider: "openai",
        name: "OpenAI",
        modelId: "gpt-5.4-luna",
        speed: "185 tok/s",
        tokens: "340 tokens",
        credits: "14 credits",
        highlight: "Clear quorum & pre-vote architecture",
        snippet: `// Pre-Vote prevents disrupted node term inflation
func (r *Raft) handlePreVote(req *PreVoteReq) *PreVoteResp {
    r.mu.Lock()
    defer r.mu.Unlock()
    // Deny if active leader lease is valid
    if r.leaderLeaseValid() {
        return &PreVoteResp{Granted: false}
    }
    return &PreVoteResp{Granted: r.isLogUpToDate(req.LogIndex)}
}`,
      },
      {
        provider: "claude",
        name: "Claude",
        modelId: "claude-sonnet-4-6",
        speed: "145 tok/s",
        tokens: "390 tokens",
        credits: "18 credits",
        highlight: "Edge cases & formal invariant proof",
        snippet: `// Strict majority lease check before committed write
func (n *Node) processWrite(cmd Command) error {
    if !n.isLeader.Load() {
        return ErrNotLeader
    }
    // Asymmetric isolation guard: verify majority heartbeat quorum
    if time.Since(n.lastQuorumAck) > n.leaseTimeout {
        n.stepDown(n.currentTerm)
        return ErrLeaseExpired
    }
    return n.replicate(cmd)
}`,
      },
      {
        provider: "deepseek",
        name: "DeepSeek",
        modelId: "deepseek-v4-flash",
        speed: "220 tok/s",
        tokens: "310 tokens",
        credits: "6 credits",
        highlight: "Compact & high-throughput concurrency",
        snippet: `// Atomic term fence with monotonic barrier
func (rf *Raft) RequestVote(args *RequestVoteArgs, reply *RequestVoteReply) {
    rf.mu.Lock()
    defer rf.mu.Unlock()
    if args.Term > rf.currentTerm {
        rf.currentTerm = args.Term
        rf.state = Follower
    }
    reply.VoteGranted = (args.Term == rf.currentTerm && rf.canVote(args))
}`,
      },
    ],
    synthesis: {
      consensus:
        "All 3 models agree that Pre-Vote and majority leader leases are necessary to prevent stale leader writes during asymmetric network partitions.",
      agreements: [
        "Pre-vote phase prevents partitioned node from incrementing term unconditionally.",
        "Leader lease expiration prevents split-brain reads without full consensus roundtrips.",
      ],
      disagreements: [
        {
          model: "Claude (Sonnet 4.6)",
          note: "Emphasizes strict clock drift tolerances on leader leases and explicit monotonic step-down barriers.",
        },
        {
          model: "OpenAI (GPT-5.4 Luna)",
          note: "Prefers election timeout randomization with jitter over static monotonic leases.",
        },
      ],
      confidence: "High",
    },
  },
  {
    id: "fast-sql-cte",
    title: "Recursive CTE & Window Retention",
    tag: "DATA ENGINEERING",
    prompt:
      "Write a high-performance PostgreSQL query for multi-touch attribution with 30-day lookback decay across customer touchpoints.",
    models: [
      {
        provider: "openai",
        name: "OpenAI",
        modelId: "gpt-5.4-luna",
        speed: "190 tok/s",
        tokens: "280 tokens",
        credits: "12 credits",
        highlight: "Optimized partition filters",
        snippet: `WITH touchpoint_weights AS (
  SELECT user_id, conversion_id, channel,
         EXP(-0.05 * (EXTRACT(EPOCH FROM (conv_time - touch_time))/86400)) AS weight
  FROM user_touchpoints
  WHERE touch_time >= conv_time - INTERVAL '30 days'
)
SELECT channel, SUM(weight) / SUM(SUM(weight)) OVER (PARTITION BY conversion_id)
FROM touchpoint_weights GROUP BY channel, conversion_id;`,
      },
      {
        provider: "claude",
        name: "Claude",
        modelId: "claude-sonnet-4-6",
        speed: "150 tok/s",
        tokens: "310 tokens",
        credits: "15 credits",
        highlight: "Half-life decay function with index hints",
        snippet: `WITH ranked_touches AS (
  SELECT user_id, channel, conv_id,
         POW(0.5, EXTRACT(EPOCH FROM (conv_date - touch_date))/ (86400 * 7)) AS half_life_w
  FROM touches t
  JOIN conversions c USING (user_id)
  WHERE t.touch_date BETWEEN c.conv_date - INTERVAL '30 days' AND c.conv_date
)
SELECT channel, SUM(half_life_w) AS attributed_conversions
FROM ranked_touches GROUP BY 1;`,
      },
      {
        provider: "deepseek",
        name: "DeepSeek",
        modelId: "deepseek-v4-flash",
        speed: "230 tok/s",
        tokens: "260 tokens",
        credits: "5 credits",
        highlight: "Lowest cost & fast vector decay",
        snippet: `SELECT channel,
       SUM(1.0 - (EXTRACT(DAY FROM conv_time - touch_time) / 30.0)) AS linear_weight
FROM touchpoints
WHERE touch_time >= conv_time - INTERVAL '30 days'
GROUP BY 1;`,
      },
    ],
    synthesis: {
      consensus:
        "All models formulate the 30-day window query with CTEs; Claude implements half-life exponential decay while DeepSeek implements linear decay and OpenAI uses continuous exponential.",
      agreements: [
        "Filtering within CTE before window aggregation significantly reduces scan cost.",
        "Partitioning by conversion ID handles repeat purchasing without cross-talk.",
      ],
      disagreements: [
        {
          model: "Claude (Sonnet 4.6)",
          note: "Uses standard 7-day half-life decay formula, which is common in ad-tech.",
        },
        {
          model: "DeepSeek (V4 Flash)",
          note: "Chooses linear weighting for reduced CPU overhead on massive datasets.",
        },
      ],
      confidence: "High",
    },
  },
];

export function InteractiveCompareDemo() {
  const [selectedId, setSelectedId] = useState(SCENARIOS[0].id);
  const activeScenario = SCENARIOS.find((s) => s.id === selectedId) || SCENARIOS[0];

  return (
    <section id="compare-demo" className={styles.section} aria-labelledby="compare-demo-title">
      <div className={styles.container}>
        <ScrollReveal variant="fade-up" className={styles.header}>
          <span className={styles.eyebrow}>LIVE DEMO SIMULATION</span>
          <h2 id="compare-demo-title" className={styles.title}>
            Multi-Model Compare & Cortex Synthesis in Action
          </h2>
          <p className={styles.subtitle}>
            See how CortexAI executes side-by-side frontier models simultaneously and synthesizes an
            unbiased consensus highlighting agreements and subtle differences.
          </p>
        </ScrollReveal>

        {/* Scenario Switcher Tabs */}
        <ScrollReveal variant="fade-up" delay={100} className={styles.tabsWrapper}>
          <div className={styles.tabsList} role="tablist">
            {SCENARIOS.map((scenario) => {
              const isSelected = scenario.id === activeScenario.id;
              return (
                <button
                  key={scenario.id}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  className={`${styles.tabButton} ${isSelected ? styles.tabActive : ""}`}
                  onClick={() => setSelectedId(scenario.id)}
                >
                  <span className={styles.tabTag}>{scenario.tag}</span>
                  <span className={styles.tabTitle}>{scenario.title}</span>
                </button>
              );
            })}
          </div>
        </ScrollReveal>

        {/* Active Prompt Box */}
        <ScrollReveal variant="fade-up" delay={150} className={styles.promptBox}>
          <div className={styles.promptHeader}>
            <CortexIcon name="ask" size={16} />
            <span>Shared Query (Sent simultaneously to 3 frontier providers):</span>
          </div>
          <p className={styles.promptText}>"{activeScenario.prompt}"</p>
        </ScrollReveal>

        {/* 3 Side-by-Side Model Response Cards */}
        <div className={styles.modelsGrid}>
          {activeScenario.models.map((m, idx) => (
            <ScrollReveal
              key={m.modelId}
              variant="fade-up"
              delay={200 + idx * 80}
              className={styles.modelCard}
            >
              <div className={styles.modelCardHeader}>
                <div className={styles.modelMeta}>
                  <ProviderLogo provider={m.provider} size={18} />
                  <div>
                    <strong>{m.name}</strong>
                    <span>{m.modelId}</span>
                  </div>
                </div>
                <div className={styles.creditPill}>
                  <CortexIcon name="tokens" size={13} />
                  <span>{m.credits}</span>
                </div>
              </div>

              <div className={styles.telemetryBar}>
                <span className={styles.statItem}>⚡ {m.speed}</span>
                <span className={styles.statItem}>📊 {m.tokens}</span>
                <span className={styles.highlightPill}>{m.highlight}</span>
              </div>

              <pre className={styles.codeSnippet}>
                <code>{m.snippet}</code>
              </pre>
            </ScrollReveal>
          ))}
        </div>

        {/* Cortex Synthesis Section */}
        <ScrollReveal variant="zoom-in" delay={300} className={styles.synthesisZone}>
          <div className={styles.synthesisHeader}>
            <div className={styles.synthesisTitle}>
              <CortexIcon name="sparkle" size={20} />
              <div>
                <h3>Cortex Analysis & Attribution Engine</h3>
                <span>Cross-model evidence synthesis • Shuffled blinded evaluation</span>
              </div>
            </div>
            <div className={styles.confidenceBadge}>
              <span>Confidence:</span>
              <strong>{activeScenario.synthesis.confidence}</strong>
            </div>
          </div>

          <div className={styles.consensusBody}>
            <p className={styles.consensusText}>{activeScenario.synthesis.consensus}</p>

            <div className={styles.synthesisColumns}>
              <div className={styles.agreementsColumn}>
                <div className={styles.columnHeading}>
                  <CortexIcon name="check" size={15} strokeWidth={2.5} />
                  <span>Consensus Agreements</span>
                </div>
                <ul className={styles.bulletList}>
                  {activeScenario.synthesis.agreements.map((ag) => (
                    <li key={ag}>{ag}</li>
                  ))}
                </ul>
              </div>

              <div className={styles.differencesColumn}>
                <div className={styles.columnHeading}>
                  <CortexIcon name="compare" size={15} />
                  <span>Attributed Differences</span>
                </div>
                <ul className={styles.differencesList}>
                  {activeScenario.synthesis.disagreements.map((dis) => (
                    <li key={dis.model}>
                      <strong>{dis.model}:</strong> {dis.note}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
