import { useState } from "react";
import type { ToolConnection, WorkEvent, WorkRun } from "../../types";
import { CortexIcon } from "../shared/CortexIcon";
import styles from "./Work.module.css";

interface WorkRailProps {
  run: WorkRun;
  events: WorkEvent[];
  connections: ToolConnection[];
  enabledConnectionIds: string[];
}

export function WorkRail({ run, events, connections, enabledConnectionIds }: WorkRailProps) {
  const complete = run.status === "completed";
  const terminal = ["completed", "failed", "cancelled", "budget_exhausted"].includes(run.status);
  const activityEvents = events.filter(isUserFacingEvent).slice(-8);
  const latestActivity = activityEvents.at(-1);
  const activeEventId =
    !terminal && latestActivity && isActiveEvent(latestActivity.type) ? latestActivity.id : null;
  const steps = [
    {
      label: "Review the goal and prepare a plan",
      state:
        complete || events.some((event) => event.type === "plan_created")
          ? "done"
          : terminal
            ? "todo"
            : "active",
    },
    {
      label: "Carry out the requested work",
      state: complete
        ? "done"
        : terminal
          ? "todo"
          : events.some((event) =>
                ["progress", "tool_started", "tool_completed"].includes(event.type),
              )
            ? "active"
            : "todo",
    },
    { label: "Prepare the outcome and deliverables", state: complete ? "done" : "todo" },
  ];
  const activeConnections = connections.filter((item) => enabledConnectionIds.includes(item.id));
  return (
    <aside className={styles.rail} aria-label="Work activity">
      <RailSection
        title="Plan"
        meta={`${steps.filter((step) => step.state === "done").length} of ${steps.length}`}
        defaultOpen
        locked
      >
        <ol className={styles.planList}>
          {steps.map((step) => (
            <li key={step.label} className={styles[`plan_${step.state}`]}>
              <span className={styles.planMarker}>
                {step.state === "done" && <CortexIcon name="check" size={11} />}
              </span>
              <span>{step.label}</span>
            </li>
          ))}
        </ol>
      </RailSection>
      <RailSection title="Activity" meta={`${activityEvents.length} actions`} defaultOpen>
        <ul className={styles.activityList}>
          {[...activityEvents].reverse().map((event) => {
            const active = event.id === activeEventId;
            return (
              <li key={event.id}>
                <span
                  className={active ? styles.activitySpinner : styles.activityCheck}
                  data-activity-state={active ? "active" : "done"}
                  aria-hidden="true"
                >
                  {!active && <CortexIcon name="check" size={10} />}
                </span>
                <span>{event.display_message || event.type.replaceAll("_", " ")}</span>
              </li>
            );
          })}
        </ul>
      </RailSection>
      <RailSection title="Tools" meta={`${activeConnections.length} connected`}>
        <ul className={styles.toolSummary}>
          {Boolean(run.configuration_snapshot.web_enabled) && (
            <li>
              <CortexIcon name="web" size={14} /> Web
            </li>
          )}
          {activeConnections.map((connection) => (
            <li key={connection.id}>
              <CortexIcon name="tools" size={14} /> {connection.display_name}
            </li>
          ))}
          {!run.configuration_snapshot.web_enabled && activeConnections.length === 0 && (
            <li>No connected tools</li>
          )}
        </ul>
      </RailSection>
      <RailSection title="Credits" meta={`${run.actual_credits.toLocaleString()} used`} defaultOpen>
        <div className={styles.budgetFigure}>
          <strong>{run.actual_credits.toLocaleString()}</strong>
          <span>/ {run.max_credit_budget.toLocaleString()} max</span>
        </div>
        <div
          className={styles.budgetTrack}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={run.max_credit_budget}
          aria-valuenow={Math.min(run.actual_credits, run.max_credit_budget)}
        >
          <span
            style={{
              width: `${Math.min(100, (run.actual_credits / run.max_credit_budget) * 100)}%`,
            }}
          />
        </div>
      </RailSection>
    </aside>
  );
}

function RailSection({
  title,
  meta,
  defaultOpen = false,
  locked = false,
  children,
}: {
  title: string;
  meta: string;
  defaultOpen?: boolean;
  locked?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={styles.railSection}>
      <button
        type="button"
        className={styles.railHeader}
        onClick={() => !locked && setOpen((value) => !value)}
        aria-expanded={open}
      >
        <CortexIcon
          name="chevron-down"
          size={13}
          className={open ? "" : styles.railChevronClosed}
        />
        <span>{title}</span>
        <small>{meta}</small>
      </button>
      {open && <div className={styles.railBody}>{children}</div>}
    </section>
  );
}

function isActiveEvent(type: string): boolean {
  return ["planning", "progress", "tool_started"].includes(type);
}

function isUserFacingEvent(event: WorkEvent): boolean {
  return event.type !== "progress" || Boolean(event.display_message?.trim());
}
