import { useChatStore } from "../../store/chatStore";
import styles from "./ExampleChips.module.css";

const EXAMPLES = [
  "Explain quantum computing in simple terms",
  "Write a haiku about artificial intelligence",
  "What are the pros and cons of remote work?",
  "Explain the difference between SQL and NoSQL databases",
  "What is the best way to learn a new programming language?",
];

export function ExampleChips() {
  const setPrompt = useChatStore((s) => s.setPrompt);
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);

  // Hide once results are visible
  if (responses.length > 0 || streaming) return null;

  return (
    <div className={styles.section}>
      <p className={styles.title}>TRY AN EXAMPLE</p>
      <div className={styles.chips}>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            className={styles.chip}
            onClick={() => setPrompt(ex)}
            title={ex}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
