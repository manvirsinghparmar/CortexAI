import { useChatStore } from "../../store/chatStore";
import styles from "./ExampleChips.module.css";

type ExampleIconName =
  | "debug"
  | "document"
  | "write"
  | "analyze"
  | "compare"
  | "review";

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
    icon: "document" as const,
  },
  {
    prompt: "Rewrite this email to sound more professional",
    icon: "write" as const,
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
    icon: "debug" as const,
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
                <Icon name={example.icon} />
              </span>
              <span>{example.prompt}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function Icon({ name }: { name: ExampleIconName }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "debug" && (
        <>
          <path d="M9 9h6v8a3 3 0 0 1-6 0V9Z" />
          <path d="M10 5h4" />
          <path d="M12 5v4" />
          <path d="M5 12h4" />
          <path d="M15 12h4" />
        </>
      )}
      {name === "document" && (
        <>
          <path d="M6 3h8l4 4v14H6z" />
          <path d="M14 3v5h5" />
          <path d="M9 12h6" />
          <path d="M9 16h6" />
        </>
      )}
      {name === "write" && (
        <>
          <path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10Z" />
          <path d="m14 7 3 3" />
        </>
      )}
      {name === "analyze" && (
        <>
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m15.5 15.5 4 4" />
          <path d="M8 11h5" />
          <path d="M10.5 8.5v5" />
        </>
      )}
      {name === "compare" && (
        <>
          <path d="M4 5h6v14H4z" />
          <path d="M14 5h6v14h-6z" />
          <path d="M7 9h1" />
          <path d="M16 9h1" />
        </>
      )}
      {name === "review" && (
        <>
          <path d="M4 5h16v11H8l-4 4z" />
          <path d="M8 9h8" />
          <path d="M8 12h5" />
        </>
      )}
    </svg>
  );
}
