import { useEffect, useRef, useState } from "react";
import { useChatStore } from "../../store/chatStore";
import type { ChatTurn } from "../../types";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

export function ResultsSection() {
  const turns = useChatStore((s) => s.turns);
  const sectionRef = useRef<HTMLElement | null>(null);

  if (turns.length === 0) return null;

  return (
    <section
      ref={sectionRef}
      className={styles.singleSection}
      aria-live="polite"
      aria-label="Chat transcript"
    >
      <div className={styles.singleGrid}>
        {turns.map((turn, turnIndex) =>
          turn.mode === "compare" ? (
            <CompareTurn key={turn.id} turn={turn} />
          ) : (
            <article key={turn.id} className={`${styles.turn} ${styles.singleTurn}`}>
              <div
                id={`chat-msg-${turnIndex}`}
                className={`${styles.userBubble} ${
                  turn.optimization ? styles.optimizationBubble : ""
                }`}
              >
                <span>You</span>
                {turn.optimization ? (
                  <OptimizationPrompt turn={turn} />
                ) : (
                  <p>{turn.prompt || "Analyze the attached file(s)."}</p>
                )}
                <TurnAttachments turn={turn} />
              </div>
              {turn.status !== "optimizing" &&
                turn.responses.map((response, responseIndex) => (
                  <ResponseCard
                    key={response.request_id}
                    response={response}
                    isStreaming={turn.status === "streaming"}
                    slotIndex={responseIndex}
                  />
                ))}
            </article>
          ),
        )}
      </div>
      {turns.some((turn) => turn.status === "streaming") && (
        <button
          type="button"
          className={styles.jumpButton}
          aria-label="Jump to latest"
          title="Jump to latest"
          onClick={() =>
            sectionRef.current?.scrollTo({
              top: sectionRef.current.scrollHeight,
              behavior: "smooth",
            })
          }
        >
          &#8595;
        </button>
      )}
    </section>
  );
}

function CompareTurn({ turn }: { turn: ChatTurn }) {
  return (
    <article className={`${styles.turn} ${styles.compareTurn}`} aria-label="Model comparison">
      <div className={styles.comparePrompt}>
        <div>
          <span>Prompt</span>
          {turn.optimization ? (
            <OptimizationPrompt turn={turn} />
          ) : (
            <p>{turn.prompt || "Analyze the attached file(s)."}</p>
          )}
        </div>
        <TurnAttachments turn={turn} />
      </div>

      {turn.compareSummary && (
        <div className={`${styles.compareSummary} compare-summary-card`}>
          <span>{turn.compareSummary.success_count} succeeded</span>
          <span>{turn.compareSummary.error_count} errors</span>
          <span>{turn.compareSummary.total_tokens.toLocaleString()} tokens</span>
          <span>${turn.compareSummary.total_cost.toFixed(5)}</span>
        </div>
      )}

      {turn.status !== "optimizing" && (
        <div className={`${styles.compareGrid} ${styles.compareGridTranscript}`}>
          {turn.responses.map((response, index) => (
            <ResponseCard
              key={`${turn.id}-${index}-${response.request_id}`}
              response={response}
              isStreaming={turn.status === "streaming" && !response.text && !response.error}
              slotIndex={index}
            />
          ))}
        </div>
      )}
    </article>
  );
}

const OPTIMIZATION_PROGRESS = [
  "Refining your prompt for better results",
  "Enhancing clarity",
  "Improving intent",
  "Preparing optimized version",
];

function OptimizationPrompt({ turn }: { turn: ChatTurn }) {
  const optimization = turn.optimization!;
  const pending = optimization.status === "pending";
  const [progressIndex, setProgressIndex] = useState(0);

  useEffect(() => {
    if (!pending) return;
    const intervalId = window.setInterval(() => {
      setProgressIndex((current) => (current + 1) % OPTIMIZATION_PROGRESS.length);
    }, 1650);
    return () => window.clearInterval(intervalId);
  }, [pending]);

  if (pending) {
    return (
      <p
        className={`${styles.optimizationText} optimization-user-text`}
        role="status"
        aria-live="polite"
      >
        <span className={styles.optimizationMark} aria-hidden="true">
          *
        </span>
        <span>{OPTIMIZATION_PROGRESS[progressIndex]}</span>
        <span className={styles.optimizationDots} aria-hidden="true">
          ...
        </span>
      </p>
    );
  }

  return (
    <>
      <p className={`${styles.optimizationText} optimization-user-text`}>
        {optimization.displayPrompt}
      </p>
      {optimization.note && (
        <p className={`${styles.optimizationNote} optimization-result-note`}>
          {optimization.note}
        </p>
      )}
    </>
  );
}

function TurnAttachments({ turn }: { turn: ChatTurn }) {
  if (turn.attachments.length === 0) return null;
  return (
    <ul className={styles.turnAttachments}>
      {turn.attachments.map((attachment) => (
        <li key={attachment.file_id}>{attachment.original_filename}</li>
      ))}
    </ul>
  );
}
