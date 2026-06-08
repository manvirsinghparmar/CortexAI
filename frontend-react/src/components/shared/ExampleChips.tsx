import { useChatStore } from "../../store/chatStore";
import styles from "./ExampleChips.module.css";

const ASK_EXAMPLES = [
  "Help me debug a failing FastAPI stream",
  "Summarize the tradeoffs in this architecture",
  "Write a safer prompt for a customer support workflow",
];

const COMPARE_EXAMPLES = [
  "Compare OAuth2 patterns for a distributed system",
  "Benchmark API gateway options for an LLM product",
  "Find the safest approach for BYOK encryption",
];

export function ExampleChips() {
  const mode = useChatStore((s) => s.mode);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const setMode = useChatStore((s) => s.setMode);
  const turns = useChatStore((s) => s.turns);
  const streaming = useChatStore((s) => s.streaming);

  if (turns.length > 0 || streaming) return null;
  if (mode === "single") return <AskLanding examples={ASK_EXAMPLES} onPick={setPrompt} />;

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

function AskLanding({
  examples,
  onPick,
}: {
  examples: string[];
  onPick: (prompt: string) => void;
}) {
  return (
    <div className={styles.askLanding}>
      <section className={styles.hero}>
        <p className={styles.title}>Try an example</p>
        <h2>
          Ask across <span>your model gateway</span>
        </h2>
        <p>
          Use smart routing for the default path, switch to manual model selection when needed, and
          attach supported files for analysis.
        </p>
        <div className={styles.modelPills} aria-label="Prompt examples">
          {examples.map((example) => (
            <button key={example} type="button" onClick={() => onPick(example)}>
              <Icon />
              {example}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Icon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />
    </svg>
  );
}
