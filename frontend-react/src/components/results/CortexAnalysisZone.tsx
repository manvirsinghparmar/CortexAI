import { useEffect, useId, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import type { ChatResponse, ChatTurn, CortexAnalysisRun } from "../../types";
import {
  currentSuccessfulResponses,
  isCortexAnalysisRunStale,
} from "../../analysis/cortexAnalysisStaleness";
import styles from "./CortexAnalysisZone.module.css";

interface CortexAnalysisZoneProps {
  turn: ChatTurn;
  onAnalyze: (turnId: string) => Promise<void>;
}

const PROCESSING_STEPS = [
  "Reading the responses",
  "Comparing agreements and differences",
  "Building your combined answer",
];

export function CortexAnalysisZone({ turn, onAnalyze }: CortexAnalysisZoneProps) {
  const successfulResponses = useMemo(
    () => currentSuccessfulResponses(turn.responses),
    [turn.responses],
  );
  const runs = turn.analysisRuns ?? [];
  const newestRunId = runs[0]?.analysisId ?? "";
  const [selectedRunId, setSelectedRunId] = useState(newestRunId);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousStatusRef = useRef(turn.analysisStatus ?? "idle");

  useEffect(() => {
    if (newestRunId) setSelectedRunId(newestRunId);
  }, [newestRunId]);

  useEffect(() => {
    const previous = previousStatusRef.current;
    const current = turn.analysisStatus ?? "idle";
    if (previous === "processing" && current === "idle" && newestRunId) {
      resultHeadingRef.current?.focus();
    }
    previousStatusRef.current = current;
  }, [newestRunId, turn.analysisStatus]);

  if (
    successfulResponses.length < 2 &&
    runs.length === 0 &&
    turn.analysisStatus !== "processing" &&
    turn.analysisStatus !== "failed"
  ) {
    return null;
  }

  const selectedRun = runs.find((run) => run.analysisId === selectedRunId) ?? runs[0];
  const savedResult = selectedRun ? (
    <AnalysisResult
      run={selectedRun}
      runs={runs}
      responses={turn.responses}
      headingRef={resultHeadingRef}
      onSelectRun={setSelectedRunId}
      onAnalyze={() => void onAnalyze(turn.id)}
      announceReady={turn.analysisStatus !== "processing" && turn.analysisStatus !== "failed"}
    />
  ) : null;

  if (turn.analysisStatus === "processing") {
    return <ProcessingState responseCount={successfulResponses.length} />;
  }

  if (turn.analysisStatus === "failed") {
    return (
      <>
        <FailureState message={turn.analysisError} onRetry={() => void onAnalyze(turn.id)} />
        {savedResult}
      </>
    );
  }

  if (savedResult) return savedResult;

  return (
    <ReadyState
      responseCount={successfulResponses.length}
      onAnalyze={() => void onAnalyze(turn.id)}
    />
  );
}

function ReadyState({
  responseCount,
  onAnalyze,
}: {
  responseCount: number;
  onAnalyze: () => void;
}) {
  return (
    <section className={`${styles.zoneCard} ${styles.readyCard}`}>
      <TriColourSeam />
      <div className={styles.readyContent}>
        <ConvergenceMark />
        <div className={styles.readyCopy}>
          <h3>Get one better-informed answer</h3>
          <p>
            Cortex will analyze what the models agree on, where they differ, and what each response
            may have missed.
          </p>
        </div>
        <div className={styles.readyAction}>
          <button type="button" className={styles.primaryButton} onClick={onAnalyze}>
            Combine these answers
          </button>
          <span className={styles.modelLine}>From your {responseCount} answers</span>
        </div>
      </div>
    </section>
  );
}

function ProcessingState({ responseCount }: { responseCount: number }) {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStep((current) => Math.min(current + 1, PROCESSING_STEPS.length - 1));
    }, 900);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section
      className={`${styles.zoneCard} ${styles.processingCard}`}
      aria-live="polite"
      aria-atomic="true"
    >
      <TriColourSeam />
      <div className={styles.processingHeader}>
        <span className={styles.spinner} aria-hidden="true" />
        <div>
          <h3>Analyzing responses…</h3>
          <p>Comparing {responseCount} answers · usually a few seconds</p>
        </div>
      </div>
      <ol className={styles.processingSteps}>
        {PROCESSING_STEPS.map((step, index) => {
          const state = index < activeStep ? "done" : index === activeStep ? "active" : "pending";
          return (
            <li key={step} className={styles[`step${capitalize(state)}`]}>
              <span className={styles.stepDot} aria-hidden="true">
                {state === "done" ? "✓" : ""}
              </span>
              <span>{step}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function FailureState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <section className={`${styles.zoneCard} ${styles.failureCard}`} role="alert">
      <TriColourSeam />
      <span className={styles.failureIcon} aria-hidden="true">
        !
      </span>
      <div>
        <h3>Cortex couldn&apos;t combine these answers</h3>
        <p>{message ?? "Your model responses are safe above. Nothing was lost."}</p>
      </div>
      <button type="button" className={styles.secondaryButton} onClick={onRetry}>
        Try again
      </button>
    </section>
  );
}

function AnalysisResult({
  run,
  runs,
  responses,
  headingRef,
  onSelectRun,
  onAnalyze,
  announceReady,
}: {
  run: CortexAnalysisRun;
  runs: CortexAnalysisRun[];
  responses: ChatResponse[];
  headingRef: RefObject<HTMLHeadingElement>;
  onSelectRun: (analysisId: string) => void;
  onAnalyze: () => void;
  announceReady: boolean;
}) {
  const [explanationOpen, setExplanationOpen] = useState(false);
  const stale = run.isStale || isCortexAnalysisRunStale(run, responses);
  const strongDisagreement = run.disagreements.length > 0 && run.confidence.level === "limited";
  const sectionOrder = strongDisagreement
    ? (["disagreements", "agreements"] as const)
    : (["agreements", "disagreements"] as const);

  return (
    <section className={`${styles.zoneCard} ${styles.resultCard}`}>
      {announceReady && (
        <span className={styles.screenReaderStatus} role="status">
          Combined answer ready
        </span>
      )}
      <TriColourSeam />
      {stale && (
        <div className={styles.staleBanner}>
          <span className={styles.staleIcon} aria-hidden="true">
            !
          </span>
          <p>
            <strong>One answer changed after this analysis</strong>
            <span> — the combined answer below may be out of date.</span>
          </p>
          <button type="button" onClick={onAnalyze}>
            Update combined answer
          </button>
        </div>
      )}

      <header className={styles.resultHeader}>
        <ConvergenceMark compact />
        <div className={styles.resultTitleGroup}>
          <div className={styles.resultTitleLine}>
            <h3 ref={headingRef} tabIndex={-1}>
              Cortex Analysis
            </h3>
            <span className={styles.resultBadge}>Better-informed answer</span>
          </div>
          <p>Combined from your {run.combinedResponseCount} answers</p>
          {run.failedResponseCount > 0 && (
            <p className={styles.partialNote}>
              Combined the successful answers; {run.failedResponseCount} response was unavailable.
            </p>
          )}
        </div>
        <div className={styles.resultActions}>
          <button
            type="button"
            className={styles.explanationButton}
            onClick={() => setExplanationOpen(true)}
          >
            How Cortex made this
          </button>
          <button
            type="button"
            className={styles.regenerateButton}
            aria-label="Run Cortex Analysis again"
            title="Run Cortex Analysis again"
            onClick={onAnalyze}
          >
            ↻
          </button>
        </div>
      </header>

      {runs.length > 1 && (
        <div className={styles.runHistory}>
          <label htmlFor={`analysis-history-${run.requestGroupId}`}>Analysis history</label>
          <select
            id={`analysis-history-${run.requestGroupId}`}
            value={run.analysisId}
            onChange={(event) => onSelectRun(event.target.value)}
          >
            {runs.map((item, index) => (
              <option key={item.analysisId} value={item.analysisId}>
                {index === 0 ? "Latest · " : ""}
                {formatRunDate(item.createdAt)}
                {item.isStale || isCortexAnalysisRunStale(item, responses) ? " · out of date" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className={styles.resultBody}>
        <div className={styles.recommendedColumn}>
          <span className={styles.microLabel}>Recommended answer</span>
          <p className={styles.recommendedAnswer}>{run.recommendedAnswer}</p>
          {run.uniqueInsights.length > 0 && (
            <Collapsible storageKey="cortex-analysis-unique-insights" title="Unique insights">
              <ul className={styles.uniqueInsightList}>
                {run.uniqueInsights.map((insight, index) => (
                  <li key={`${insight.responseName}-${index}`}>
                    <span>{insight.responseName}</span>
                    <p>{insight.text}</p>
                  </li>
                ))}
              </ul>
            </Collapsible>
          )}
        </div>

        <div className={styles.comparisonColumn}>
          {sectionOrder.map((section) => {
            const items = section === "agreements" ? run.agreements : run.disagreements;
            if (items.length === 0) return null;
            return (
              <Collapsible
                key={section}
                storageKey={`cortex-analysis-${section}`}
                title={section === "agreements" ? "What the models agree on" : "Where they differ"}
                tone={section}
              >
                <BulletList items={items} tone={section} />
              </Collapsible>
            );
          })}
        </div>
      </div>

      <footer className={styles.resultFooter}>
        <ConfidenceBlock run={run} />
        {run.verify.length > 0 && <VerifyBlock run={run} />}
      </footer>

      {explanationOpen && <ExplanationDialog onClose={() => setExplanationOpen(false)} />}
    </section>
  );
}

function ConfidenceBlock({ run }: { run: CortexAnalysisRun }) {
  const filledBars =
    run.confidence.level === "high" ? 3 : run.confidence.level === "moderate" ? 2 : 1;
  return (
    <section className={styles.confidenceBlock}>
      <span className={styles.microLabel}>Confidence</span>
      <div className={styles.confidenceHeading}>
        <strong>{capitalize(run.confidence.level)}</strong>
        <span className={styles.confidenceBars} aria-hidden="true">
          {[0, 1, 2].map((index) => (
            <i key={index} className={index < filledBars ? styles.barFilled : ""} />
          ))}
        </span>
      </div>
      <p>{run.confidence.reason}</p>
    </section>
  );
}

function VerifyBlock({ run }: { run: CortexAnalysisRun }) {
  const domain = run.highStakesDomain?.toUpperCase();
  return (
    <Collapsible
      storageKey="cortex-analysis-verify"
      title={`Worth verifying${domain ? ` · ${domain}` : ""}`}
      defaultOpen={!!run.highStakesDomain}
      tone="verify"
      footer
    >
      <BulletList items={run.verify} tone="verify" />
    </Collapsible>
  );
}

function Collapsible({
  storageKey,
  title,
  children,
  defaultOpen = false,
  tone = "neutral",
  footer = false,
}: {
  storageKey: string;
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  tone?: "neutral" | "agreements" | "disagreements" | "verify";
  footer?: boolean;
}) {
  const [open, setOpen] = usePersistentBoolean(storageKey, defaultOpen);
  const reactId = useId().replace(/:/g, "");
  const panelId = `${storageKey}-${reactId}-panel`;
  return (
    <section
      className={`${styles.collapsible} ${styles[`tone${capitalize(tone)}`]} ${
        footer ? styles.footerCollapsible : ""
      }`}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
      >
        <span className={styles.sectionIcon} aria-hidden="true">
          {tone === "agreements"
            ? "✓"
            : tone === "disagreements"
              ? "↔"
              : tone === "verify"
                ? "◇"
                : "＋"}
        </span>
        <span>{title}</span>
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ""}`}>⌄</span>
      </button>
      {open && (
        <div id={panelId} className={styles.collapsiblePanel}>
          {children}
        </div>
      )}
    </section>
  );
}

function BulletList({
  items,
  tone,
}: {
  items: string[];
  tone: "agreements" | "disagreements" | "verify";
}) {
  return (
    <ul className={`${styles.bulletList} ${styles[`bullet${capitalize(tone)}`]}`}>
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>
          <span aria-hidden="true">
            {tone === "agreements" ? "✓" : tone === "disagreements" ? "•" : "◇"}
          </span>
          <p>{item}</p>
        </li>
      ))}
    </ul>
  );
}

function ExplanationDialog({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);
  return (
    <div className={styles.dialogBackdrop} role="presentation" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cortex-analysis-explanation-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <h3 id="cortex-analysis-explanation-title">How Cortex made this</h3>
        <p>
          Cortex shuffled and anonymized the successful responses before identifying agreements,
          differences, unique observations, and points that may require verification.
        </p>
        <p>
          This is a combined analysis based on the responses, not an independent source of truth.
        </p>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

function ConvergenceMark({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`${styles.convergenceMark} ${compact ? styles.convergenceMarkCompact : ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 32 32">
        <path d="M7 7h5l8 9M7 16h13M7 25h5l8-9" />
        <circle cx="6" cy="7" r="2" />
        <circle cx="6" cy="16" r="2" />
        <circle cx="6" cy="25" r="2" />
        <circle cx="23" cy="16" r="3.5" />
      </svg>
    </span>
  );
}

function TriColourSeam() {
  return <span className={styles.triColourSeam} aria-hidden="true" />;
}

function usePersistentBoolean(key: string, defaultValue: boolean) {
  const [value, setValue] = useState(() => {
    try {
      const stored = window.localStorage.getItem(key);
      return stored === null ? defaultValue : stored === "true";
    } catch {
      return defaultValue;
    }
  });
  const update = (next: boolean) => {
    setValue(next);
    try {
      window.localStorage.setItem(key, String(next));
    } catch {
      // Local storage can be unavailable in privacy-restricted contexts.
    }
  };
  return [value, update] as const;
}

function formatRunDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Saved analysis";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function capitalize<T extends string>(value: T) {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}
