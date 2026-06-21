import { useChatStore } from "../../store/chatStore";
import { CortexIcon, type CortexIconName } from "./CortexIcon";
import styles from "./ExampleChips.module.css";

type ExampleIconName = Extract<
  CortexIconName,
  | "debug"
  | "summarize"
  | "rewrite"
  | "analyze"
  | "compare"
  | "find-solution"
  | "review"
>;

interface PromptExample {
  prompt: string;
  icon: ExampleIconName;
}

const ASK_EXAMPLES = [
  {
    prompt: "Help me debug a failing FastAPI stream",
    icon: "debug" as const,
  },
  {
    prompt: "Summarize this document into key takeaways",
    icon: "summarize" as const,
  },
  {
    prompt: "Rewrite this email to sound more professional",
    icon: "rewrite" as const,
  },
  {
    prompt: "Analyze this file and highlight important findings",
    icon: "analyze" as const,
  },
];

const COMPARE_EXAMPLES = [
  {
    prompt: "Compare two approaches for this system design",
    icon: "compare" as const,
  },
  {
    prompt: "Find the strongest solution for this bug",
    icon: "find-solution" as const,
  },
  {
    prompt: "Review this answer from multiple models",
    icon: "review" as const,
  },
];

export function ExampleChips() {
  const mode = useChatStore((s) => s.mode);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const turns = useChatStore((s) => s.turns);
  const streaming = useChatStore((s) => s.streaming);

  if (turns.length > 0 || streaming) return null;
  if (mode === "single") {
    return (
      <WorkspaceLanding
        variant="ask"
        eyebrow="Your AI workspace"
        headline="Your AI workspace for answers, analysis, and model comparison"
        description="Ask questions, analyze files, generate content, and compare model responses, all from one place. Use smart routing for the best default experience, or choose a model yourself when you want more control."
        examples={ASK_EXAMPLES}
        onPick={setPrompt}
      />
    );
  }

  return (
    <WorkspaceLanding
      variant="compare"
      eyebrow="Compare mode"
      headline="Ask once. Compare answers across models."
      description="See how different AI models reason through the same prompt. Compare accuracy, depth, speed, tone, and usefulness for research, debugging, writing, architecture decisions, and second opinions."
      examples={COMPARE_EXAMPLES}
      onPick={setPrompt}
    />
  );
}

function WorkspaceLanding({
  variant,
  eyebrow,
  headline,
  description,
  examples,
  onPick,
}: {
  variant: "ask" | "compare";
  eyebrow: string;
  headline: string;
  description: string;
  examples: PromptExample[];
  onPick: (prompt: string) => void;
}) {
  return (
    <div
      className={`${styles.landing} ${
        variant === "compare" ? styles.compareLanding : styles.askLanding
      }`}
    >
      <section className={styles.hero}>
        <p className={styles.title}>{eyebrow}</p>
        <h2>{headline}</h2>
        <p>{description}</p>
        <div
          className={`${styles.modelPills} ${
            variant === "compare" ? styles.compareExamples : ""
          }`}
          aria-label={variant === "compare" ? "Compare prompt examples" : "Prompt examples"}
        >
          {examples.map((example) => (
            <button
              key={example.prompt}
              type="button"
              onClick={() => onPick(example.prompt)}
            >
              <span className={styles.exampleIcon}>
                <CortexIcon name={example.icon} />
              </span>
              <span>{example.prompt}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
