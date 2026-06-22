import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { SparkleIcon } from "../common/SparkleIcon";
import { getModelPresentation } from "../../config/modelPresentation";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import { useChat } from "../../hooks/useChat";
import { useChatStore } from "../../store/chatStore";
import type { ChatTurn } from "../../types";
import { CortexIcon } from "../shared/CortexIcon";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

export function ResultsSection() {
  const turns = useChatStore((s) => s.turns);
  const { regenerate } = useChat();
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
              onRegenerate={regenerate}
            />
          ) : (
            <article
              key={turn.id}
              ref={(node) => registerTurn(turn.id, node)}
              data-turn-id={turn.id}
              className={`${styles.turn} ${styles.singleTurn}`}
            >
              <TurnPrompt turn={turn} turnIndex={turnIndex} />
              {turn.responses.map((response, responseIndex) => (
                <ResponseCard
                  key={response.request_id}
                  response={response}
                  isStreaming={isResponseLoading(turn, response)}
                  slotIndex={responseIndex}
                  loadingMode="ask"
                  researchEnabled={turn.researchEnabled}
                  optimizeEnabled={turn.optimizeEnabled ?? !!turn.optimization}
                  onRegenerate={() => void regenerate(turn.id, responseIndex)}
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
          <CortexIcon name="scroll-down" />
        </button>
      )}
    </section>
  );
}

function CompareTurn({
  turn,
  turnIndex,
  registerTurn,
  onRegenerate,
}: {
  turn: ChatTurn;
  turnIndex: number;
  registerTurn: (turnId: string, node: HTMLElement | null) => void;
  onRegenerate: (turnId: string, responseIndex: number) => Promise<void>;
}) {
  const [activeResponseIndex, setActiveResponseIndex] = useState(0);
  const compareGridClass =
    turn.responses.length >= 3
      ? styles.compareGridThree
      : turn.responses.length === 2
        ? styles.compareGridTwo
        : styles.compareGridOne;
  const hasResponseTabs = turn.responses.length > 1;
  const metricHighlights = resolveCompareMetricHighlights(turn.responses);

  useEffect(() => {
    if (activeResponseIndex >= turn.responses.length) {
      setActiveResponseIndex(Math.max(0, turn.responses.length - 1));
    }
  }, [activeResponseIndex, turn.responses.length]);

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
          <span className={`${styles.summaryPill} ${styles.summarySuccess}`}>
            {turn.compareSummary.success_count} succeeded
          </span>
          <span className={`${styles.summaryPill} ${styles.summaryNeutral}`}>
            {turn.compareSummary.error_count} errors
          </span>
          <span className={`${styles.summaryPill} ${styles.summaryMono}`}>
            {turn.compareSummary.total_tokens.toLocaleString()} tok
          </span>
          <span className={`${styles.summaryPill} ${styles.summaryMono}`}>
            ${turn.compareSummary.total_cost.toFixed(5)}
          </span>
        </div>
      )}

      {turn.responses.length > 0 && (
        <>
          {hasResponseTabs && (
            <div
              className={styles.mobileResponseTabs}
              role="tablist"
              aria-label="Compare model responses"
            >
              {turn.responses.map((response, index) => {
                const presentation = getModelPresentation(
                  response.provider,
                  response.model,
                );
                const selected = index === activeResponseIndex;
                return (
                  <button
                    key={`${turn.id}-tab-${response.request_id}`}
                    type="button"
                    role="tab"
                    id={`${turn.id}-response-tab-${index}`}
                    aria-selected={selected}
                    aria-controls={`${turn.id}-response-panel-${index}`}
                    tabIndex={selected ? 0 : -1}
                    className={selected ? styles.mobileResponseTabActive : undefined}
                    onClick={() => setActiveResponseIndex(index)}
                  >
                    {presentation.label}
                  </button>
                );
              })}
            </div>
          )}

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
                  id={`${turn.id}-response-panel-${index}`}
                  className={`${styles.compareResponsePanel} ${
                    index === activeResponseIndex ? styles.mobileResponsePanelActive : ""
                  }`}
                  role={hasResponseTabs ? "tabpanel" : "region"}
                  aria-labelledby={
                    hasResponseTabs ? `${turn.id}-response-tab-${index}` : undefined
                  }
                  aria-label={hasResponseTabs ? undefined : `${presentation.label} response`}
                  data-response-panel
                >
                  <ResponseCard
                    response={response}
                    isStreaming={isResponseLoading(turn, response)}
                    slotIndex={index}
                    compact
                    loadingMode="compare"
                    researchEnabled={turn.researchEnabled}
                    optimizeEnabled={turn.optimizeEnabled ?? !!turn.optimization}
                    onRegenerate={() => void onRegenerate(turn.id, index)}
                    compareHighlights={metricHighlights[index]}
                  />
                </div>
              );
            })}
          </div>
        </>
      )}
    </article>
  );
}

function resolveCompareMetricHighlights(responses: ChatTurn["responses"]) {
  const durations = responses.map((response) =>
    response.error || response.ui_status === "failed"
      ? null
      : responseDurationMs(response),
  );
  const costs = responses.map((response) =>
    response.error || response.ui_status === "failed"
      ? null
      : positiveNumber(response.estimated_cost),
  );
  const fastestDuration = minMetric(durations);
  const cheapestCost = minMetric(costs);

  return responses.map((_, index) => ({
    fastest: fastestDuration !== null && durations[index] === fastestDuration,
    cheapest: cheapestCost !== null && costs[index] === cheapestCost,
  }));
}

function responseDurationMs(response: ChatTurn["responses"][number]) {
  const startedAtMs = parseTimestamp(response.started_at);
  const completedAtMs = parseTimestamp(response.completed_at);
  if (startedAtMs !== null && completedAtMs !== null) {
    return Math.max(0, completedAtMs - startedAtMs);
  }
  return positiveNumber(response.latency_ms);
}

function positiveNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : null;
}

function minMetric(values: Array<number | null>) {
  const usableValues = values.filter((value): value is number => value !== null);
  return usableValues.length > 0 ? Math.min(...usableValues) : null;
}

function parseTimestamp(value: string | undefined): number | null {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? parsed : null;
}

function isResponseLoading(turn: ChatTurn, response: ChatTurn["responses"][number]) {
  if (response.error || response.ui_status === "complete" || response.ui_status === "failed") {
    return false;
  }
  return turn.status === "optimizing" || turn.status === "streaming";
}

function TurnPrompt({ turn, turnIndex }: { turn: ChatTurn; turnIndex: number }) {
  const [originalVisible, setOriginalVisible] = useState(false);
  const optimization = turn.optimization;
  const promptText = optimization
    ? optimization.displayPrompt
    : turn.prompt || "Analyze the attached file(s).";

  return (
    <div className={styles.promptRow}>
      <div className={styles.promptGroup}>
        <div id={`chat-msg-${turnIndex}`} className={styles.userBubble}>
          <span className={styles.userLabel}>You</span>
          <p className={styles.userPromptText}>{promptText}</p>
          <TurnAttachments turn={turn} />
        </div>
        {optimization && (
          <OptimizationStatus
            optimization={optimization}
            originalVisible={originalVisible}
            onViewOriginal={() => setOriginalVisible(true)}
          />
        )}
      </div>
    </div>
  );
}

const OPTIMIZATION_LIVE_MESSAGE = "Improving your prompt";
const OPTIMIZATION_PENDING_MESSAGE = "Improving your prompt";

function OptimizationStatus({
  optimization,
  originalVisible,
  onViewOriginal,
}: {
  optimization: NonNullable<ChatTurn["optimization"]>;
  originalVisible: boolean;
  onViewOriginal: () => void;
}) {
  const pending = optimization.status === "pending";
  const reducedMotion = useReducedMotion();

  if (pending) {
    return (
      <div
        className={`${styles.optimizationStatus} ${styles.optimizationStatusPending}`}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span className={`${styles.visuallyHidden} optimization-live-message`}>
          {OPTIMIZATION_LIVE_MESSAGE}
        </span>
        <OptimizationMark animated />
        <span
          className={`${styles.optimizationMessage} optimization-visible-message`}
          aria-hidden="true"
        >
          {OPTIMIZATION_PENDING_MESSAGE}
        </span>
        {!reducedMotion && (
          <span
            className={`${styles.optimizationDots} optimization-pending-dots`}
            aria-hidden="true"
          >
            ...
          </span>
        )}
      </div>
    );
  }

  if (optimization.status === "optimized") {
    return (
      <div className={styles.optimizationStatusStack}>
        <div
          className={`${styles.optimizationStatus} ${styles.optimizationStatusOptimized} ${styles.optimizationReveal} optimization-reveal`}
        >
          <OptimizationMark />
          <span className="optimization-result-message">Prompt optimized</span>
          {!originalVisible && (
            <button
              type="button"
              className={styles.optimizationToggle}
              aria-expanded={originalVisible}
              onClick={onViewOriginal}
            >
              View original
            </button>
          )}
        </div>
        {originalVisible && (
          <p
            className={`${styles.optimizationOriginalText} ${styles.optimizationReveal} optimization-reveal`}
          >
            {optimization.originalPrompt}
          </p>
        )}
      </div>
    );
  }

  if (optimization.status === "kept_original") {
    return (
      <div
        className={`${styles.optimizationStatus} ${styles.optimizationStatusClear} ${styles.optimizationReveal} optimization-result-note optimization-reveal`}
      >
        <span className={styles.optimizationCheck} aria-hidden="true">
          <CortexIcon name="check" />
        </span>
        <span>Already clear — sent as-is</span>
      </div>
    );
  }

  if (optimization.status === "cancelled") {
    return null;
  }

  return (
    <div
      className={`${styles.optimizationStatus} ${styles.optimizationStatusOptimized} ${styles.optimizationReveal} optimization-reveal`}
    >
      <OptimizationMark />
      <span className="optimization-result-message">{optimization.displayPrompt}</span>
    </div>
  );
}

function OptimizationMark({ animated = false }: { animated?: boolean }) {
  return (
    <span
      className={`${styles.optimizationMark} optimization-mark ${
        animated ? styles.optimizationMarkAnimated : ""
      }`}
      aria-hidden="true"
    >
      <SparkleIcon />
    </span>
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
