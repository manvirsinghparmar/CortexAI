import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getModelPresentation } from "../../config/modelPresentation";
import { useChatStore } from "../../store/chatStore";
import type { ChatTurn } from "../../types";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

export function ResultsSection() {
  const turns = useChatStore((s) => s.turns);
  const sectionRef = useRef<HTMLElement | null>(null);
  const turnRefs = useRef(new Map<string, HTMLElement>());
  const previousTurnsRef = useRef({ count: 0, lastId: "" });
  const hasMultipleTurns = turns.length > 1;
  const hasCompareTurns = turns.some((turn) => turn.mode === "compare");
  const latestTurnId = turns[turns.length - 1]?.id ?? "";
  const turnCount = turns.length;

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const previousTurns = previousTurnsRef.current;
    const latestTurnChanged = !!latestTurnId && latestTurnId !== previousTurns.lastId;
    let frameId: number | null = null;
    let followUpTimer: number | null = null;

    const revealLatestTurn = () => {
      if (!section || !latestTurnId) return;
      const target = turnRefs.current.get(latestTurnId);
      if (!target) return;
      const sectionRect = section.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const targetTop = section.scrollTop + targetRect.top - sectionRect.top;
      const top = Math.max(0, targetTop);
      if (typeof section.scrollTo === "function") {
        section.scrollTo({ top, behavior: "smooth" });
      } else {
        section.scrollTop = top;
      }
    };

    if (latestTurnChanged) {
      frameId = window.requestAnimationFrame(revealLatestTurn);
      followUpTimer = window.setTimeout(revealLatestTurn, 96);
    }

    previousTurnsRef.current = {
      count: turnCount,
      lastId: latestTurnId,
    };

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      if (followUpTimer !== null) window.clearTimeout(followUpTimer);
    };
  }, [latestTurnId, turnCount]);

  if (turns.length === 0) return null;

  const registerTurn = (turnId: string, node: HTMLElement | null) => {
    if (node) {
      turnRefs.current.set(turnId, node);
    } else {
      turnRefs.current.delete(turnId);
    }
  };

  return (
    <section
      ref={sectionRef}
      className={styles.singleSection}
      aria-live="polite"
      aria-label="Chat transcript"
    >
      <div
        className={`${styles.singleGrid} ${
          hasMultipleTurns ? styles.multiTurnGrid : styles.oneTurnGrid
        } ${hasCompareTurns ? styles.compareTranscriptGrid : ""}`}
      >
        {turns.map((turn, turnIndex) =>
          turn.mode === "compare" ? (
            <CompareTurn
              key={turn.id}
              turn={turn}
              turnIndex={turnIndex}
              registerTurn={registerTurn}
            />
          ) : (
            <article
              key={turn.id}
              ref={(node) => registerTurn(turn.id, node)}
              data-turn-id={turn.id}
              className={`${styles.turn} ${styles.singleTurn}`}
            >
              <TurnPrompt turn={turn} turnIndex={turnIndex} />
              {turn.status !== "optimizing" &&
                turn.responses.map((response, responseIndex) => (
                  <ResponseCard
                    key={response.request_id}
                    response={response}
                    isStreaming={turn.status === "streaming"}
                    slotIndex={responseIndex}
                    loadingMode="ask"
                    researchEnabled={turn.researchEnabled}
                    optimizeEnabled={turn.optimizeEnabled ?? !!turn.optimization}
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

function CompareTurn({
  turn,
  turnIndex,
  registerTurn,
}: {
  turn: ChatTurn;
  turnIndex: number;
  registerTurn: (turnId: string, node: HTMLElement | null) => void;
}) {
  const compareGridClass =
    turn.responses.length >= 3
      ? styles.compareGridThree
      : turn.responses.length === 2
        ? styles.compareGridTwo
        : styles.compareGridOne;

  return (
    <article
      ref={(node) => registerTurn(turn.id, node)}
      data-turn-id={turn.id}
      className={`${styles.turn} ${styles.compareTurn}`}
      aria-label="Model comparison"
    >
      <TurnPrompt turn={turn} turnIndex={turnIndex} />

      {turn.compareSummary && (
        <div className={`${styles.compareSummary} compare-summary-card`}>
          <span>{turn.compareSummary.success_count} succeeded</span>
          <span>{turn.compareSummary.error_count} errors</span>
          <span>{turn.compareSummary.total_tokens.toLocaleString()} tokens</span>
          <span>${turn.compareSummary.total_cost.toFixed(5)}</span>
        </div>
      )}

      {turn.status !== "optimizing" && (
        <div
          className={`${styles.compareGrid} ${styles.compareGridTranscript} ${compareGridClass}`}
        >
          {turn.responses.map((response, index) => {
            const presentation = getModelPresentation(
              response.provider,
              response.model,
            );
            return (
              <div
                key={`${turn.id}-${index}-${response.request_id}`}
                className={styles.compareResponsePanel}
                role="region"
                aria-label={`${presentation.label} response`}
                data-response-panel
              >
                <ResponseCard
                  response={response}
                  isStreaming={
                    turn.status === "streaming" && !response.text && !response.error
                  }
                  slotIndex={index}
                  compact
                  loadingMode="compare"
                  researchEnabled={turn.researchEnabled}
                  optimizeEnabled={turn.optimizeEnabled ?? !!turn.optimization}
                />
              </div>
            );
          })}
        </div>
      )}
    </article>
  );
}

function TurnPrompt({ turn, turnIndex }: { turn: ChatTurn; turnIndex: number }) {
  return (
    <div className={styles.promptRow}>
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
    </div>
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
