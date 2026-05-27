import { useChatStore } from "../../store/chatStore";
import styles from "./ExampleChips.module.css";

const COMPARE_EXAMPLES = [
  "Compare OAuth2 patterns for a distributed system",
  "Benchmark API gateway options for an LLM product",
  "Find the safest approach for BYOK encryption",
];

export function ExampleChips() {
  const mode = useChatStore((s) => s.mode);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const setMode = useChatStore((s) => s.setMode);
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);

  if (responses.length > 0 || streaming) return null;
  if (mode === "single") return <AskLanding />;

  return (
    <div className={styles.section}>
      <p className={styles.title}>Try an example</p>
      <div className={styles.chips}>
        {COMPARE_EXAMPLES.map((example) => (
          <button
            key={example}
            className={styles.chip}
            onClick={() => {
              setMode("compare");
              setPrompt(example);
            }}
            title={example}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

function AskLanding() {
  const setPrompt = useChatStore((s) => s.setPrompt);

  return (
    <div className={styles.askLanding}>
      <section className={styles.hero}>
        <h2>
          How can I assist your <span>technical workflow</span> today?
        </h2>
        <p>
          Access the world's most capable large language models through a single, unified glass
          interface.
        </p>
        <div className={styles.modelPills} aria-label="Featured models">
          <button type="button" onClick={() => setPrompt("Help me design a secure API gateway")}>
            <Icon name="bolt" />
            Cortex-4 Turbo
          </button>
          <button type="button" onClick={() => setPrompt("Reason through this architecture")}>
            <Icon name="brain" />
            Logic Engine V2
          </button>
          <button type="button" onClick={() => setPrompt("Review this code snippet")}>
            <Icon name="code" />
            Code-Pilot Max
          </button>
        </div>
      </section>

      <section className={styles.askGrid} aria-label="Workspace overview">
        <article className={styles.overviewCard}>
          <div>
            <h3>Workspace Overview</h3>
            <p>Your API usage is currently within optimized limits for the Cortex-4 Turbo tier.</p>
          </div>
          <dl>
            <div>
              <dt>Total Tokens</dt>
              <dd>
                1.2M <span>/ 5M</span>
              </dd>
            </div>
            <div>
              <dt>Active Projects</dt>
              <dd>14</dd>
            </div>
            <div>
              <dt>Avg. Latency</dt>
              <dd className={styles.secondaryMetric}>240ms</dd>
            </div>
          </dl>
        </article>
        <article className={styles.integrationCard}>
          <span className={styles.integrationIcon}>
            <Icon name="terminal" />
          </span>
          <h3>Quick Integration</h3>
          <p>Copy your endpoint credentials to start building immediately.</p>
          <button type="button">Get SDK Keys</button>
        </article>
      </section>
    </div>
  );
}

function Icon({ name }: { name: "bolt" | "brain" | "code" | "terminal" }) {
  const paths = {
    bolt: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />,
    brain: (
      <>
        <path d="M9 5a3 3 0 0 0-3 3v1a3 3 0 0 0 0 6v1a3 3 0 0 0 5 2.2" />
        <path d="M15 5a3 3 0 0 1 3 3v1a3 3 0 0 1 0 6v1a3 3 0 0 1-5 2.2" />
        <path d="M12 5v14" />
      </>
    ),
    code: (
      <>
        <path d="m8 9-4 3 4 3" />
        <path d="m16 9 4 3-4 3" />
      </>
    ),
    terminal: (
      <>
        <rect x="4" y="5" width="16" height="14" rx="2" />
        <path d="m8 10 3 2-3 2" />
        <path d="M13 15h4" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
