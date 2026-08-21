import { useRef, useState, type KeyboardEvent } from "react";
import type { AttachmentUploadTask } from "../../store/attachmentUploadStore";
import type { ToolCatalogItem, ToolConnection } from "../../types";
import { CortexIcon } from "../shared/CortexIcon";
import styles from "./Work.module.css";

interface WorkComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onFiles: (files: File[]) => void;
  onRemoveFile: (clientId: string) => void;
  onRetryFile: (clientId: string) => void;
  tasks: AttachmentUploadTask[];
  connections: ToolConnection[];
  catalog: ToolCatalogItem[];
  enabledConnectionIds: string[];
  onToggleConnection: (id: string) => void;
  onConnect: (connectorKey: string) => void;
  onAddMcp: (name: string, url: string) => Promise<void>;
  webEnabled: boolean;
  onWebChange: (enabled: boolean) => void;
  maxCreditBudget: number;
  maxPlanBudget: number;
  onBudgetChange: (value: number) => void;
  busy?: boolean;
  disabled?: boolean;
  followup?: boolean;
}

export function WorkComposer({
  value,
  onChange,
  onSubmit,
  onFiles,
  onRemoveFile,
  onRetryFile,
  tasks,
  connections,
  catalog,
  enabledConnectionIds,
  onToggleConnection,
  onConnect,
  onAddMcp,
  webEnabled,
  onWebChange,
  maxCreditBudget,
  maxPlanBudget,
  onBudgetChange,
  busy,
  disabled,
  followup,
}: WorkComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mcpOpen, setMcpOpen] = useState(false);
  const [mcpName, setMcpName] = useState("");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpBusy, setMcpBusy] = useState(false);
  const ready = tasks.every((task) => task.state === "ready" || task.state === "cancelled");
  const canSubmit = Boolean(value.trim()) && ready && !busy && !disabled;
  const connectedCount = enabledConnectionIds.length;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) onSubmit();
    }
  };

  return (
    <div className={`${styles.composer} ${followup ? styles.composerFollowup : styles.composerStart}`}>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={followup ? "Ask Cortex to refine the work..." : "Describe what you want Cortex to accomplish..."}
        aria-label={followup ? "Refine this work" : "Work goal"}
        disabled={disabled || busy}
      />
      {tasks.length > 0 && (
        <div className={styles.attachmentStrip} aria-label="Work attachments">
          {tasks.map((task) => (
            <span className={styles.attachmentItem} key={task.clientId}>
              <CortexIcon name="attach" size={14} />
              <span>{task.filename}</span>
              <small>{task.state === "uploading" ? `${task.progress}%` : task.state}</small>
              {task.state === "failed" && <button type="button" onClick={() => onRetryFile(task.clientId)}>Retry</button>}
              <button type="button" aria-label={`Remove ${task.filename}`} onClick={() => onRemoveFile(task.clientId)}>×</button>
            </span>
          ))}
        </div>
      )}
      <div className={styles.composerFooter}>
        <div className={styles.chipRow}>
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            onChange={(event) => {
              onFiles(Array.from(event.target.files || []));
              event.target.value = "";
            }}
          />
          <button type="button" className={styles.workChip} onClick={() => inputRef.current?.click()} disabled={disabled}>
            <CortexIcon name="attach" size={15} /> Files {tasks.length > 0 && <b>{tasks.length}</b>}
          </button>
          <button type="button" className={`${styles.workChip} ${webEnabled ? styles.workChipActive : ""}`} onClick={() => onWebChange(!webEnabled)} disabled={disabled} aria-pressed={webEnabled}>
            <CortexIcon name="web" size={15} /> Web
          </button>
          <div className={styles.popoverAnchor}>
            <button type="button" className={`${styles.workChip} ${connectedCount ? styles.workChipActive : ""}`} onClick={() => { setToolsOpen((open) => !open); setSettingsOpen(false); }} aria-haspopup="dialog" aria-expanded={toolsOpen} disabled={disabled}>
              <CortexIcon name="tools" size={15} /> Tools {connectedCount > 0 && <b>{connectedCount}</b>} <CortexIcon name="chevron-down" size={12} />
            </button>
            {toolsOpen && (
              <div className={styles.toolsPopover} role="dialog" aria-label="Tools">
                <div className={styles.popoverHeader}><strong>Tools</strong><button type="button" aria-label="Close tools" onClick={() => setToolsOpen(false)}>×</button></div>
                <p className={styles.popoverEyebrow}>Connected</p>
                {connections.length === 0 ? <p className={styles.popoverEmpty}>No connected apps yet.</p> : connections.map((connection) => (
                  <label className={styles.toolRow} key={connection.id}>
                    <span className={styles.toolTile}>{connection.display_name.slice(0, 1)}</span>
                    <span><strong>{connection.display_name}</strong><small>{connection.status}</small></span>
                    <input type="checkbox" checked={enabledConnectionIds.includes(connection.id)} onChange={() => onToggleConnection(connection.id)} />
                  </label>
                ))}
                <p className={styles.popoverEyebrow}>Available apps</p>
                {catalog.filter((item) => !["cortex_files", "cortex_web", "custom_mcp"].includes(item.connector_key) && !connections.some((connection) => connection.connector_key === item.connector_key)).map((item) => (
                  <div className={styles.toolRow} key={item.connector_key}>
                    <span className={styles.toolTile}>{item.display_name.slice(0, 1)}</span>
                    <span><strong>{item.display_name}</strong><small>{item.configuration_required ? "Setup required" : item.description}</small></span>
                    <button type="button" className={styles.connectButton} onClick={() => onConnect(item.connector_key)} disabled={item.configuration_required}>Connect</button>
                  </div>
                ))}
                {mcpOpen ? (
                  <form className={styles.mcpForm} onSubmit={(event) => { event.preventDefault(); setMcpBusy(true); void onAddMcp(mcpName, mcpUrl).then(() => { setMcpName(""); setMcpUrl(""); setMcpOpen(false); }).finally(() => setMcpBusy(false)); }}>
                    <label>Name<input value={mcpName} onChange={(event) => setMcpName(event.target.value)} required maxLength={120} /></label>
                    <label>HTTPS endpoint<input value={mcpUrl} onChange={(event) => setMcpUrl(event.target.value)} required type="url" placeholder="https://mcp.example.com/mcp" /></label>
                    <button type="submit" className={styles.inkButton} disabled={mcpBusy}>Add server</button>
                  </form>
                ) : (
                  <button type="button" className={styles.mcpLink} onClick={() => setMcpOpen(true)}><CortexIcon name="plus" size={14} /> Add MCP server</button>
                )}
              </div>
            )}
          </div>
        </div>
        <div className={styles.composerActions}>
          <div className={styles.popoverAnchor}>
            <button type="button" className={styles.settingsButton} aria-label="Work settings" onClick={() => { setSettingsOpen((open) => !open); setToolsOpen(false); }} aria-haspopup="dialog" aria-expanded={settingsOpen} disabled={disabled}>
              <CortexIcon name="settings" size={17} />
            </button>
            {settingsOpen && (
              <div className={`${styles.settingsPopover} ${styles.popoverRight}`} role="dialog" aria-label="Work settings">
                <div className={styles.popoverHeader}><strong>Work settings</strong><button type="button" aria-label="Close settings" onClick={() => setSettingsOpen(false)}>×</button></div>
                <p className={styles.popoverEyebrow}>Agent</p>
                <label className={styles.agentChoice}><input type="radio" checked readOnly /><span><strong>Cortex Auto</strong><small>Picks the right model for each step</small></span></label>
                <p className={styles.popoverEyebrow}>Maximum task budget</p>
                <div className={styles.budgetOptions}>
                  {[25_000, 100_000, 250_000, 1_000_000].filter((option) => option <= maxPlanBudget).map((option) => (
                    <button type="button" key={option} className={option === maxCreditBudget ? styles.budgetOptionActive : ""} onClick={() => onBudgetChange(option)}>{formatBudget(option)}</button>
                  ))}
                </div>
                <p className={styles.settingsNote}>Cortex stops before it would exceed this budget.</p>
              </div>
            )}
          </div>
          <button type="button" className={followup ? styles.followupSend : styles.startButton} onClick={onSubmit} disabled={!canSubmit}>
            {followup ? <CortexIcon name="send" size={17} /> : <>Start work <CortexIcon name="send" size={16} /></>}
          </button>
        </div>
      </div>
    </div>
  );
}

function formatBudget(value: number): string {
  return value >= 1_000_000 ? `${value / 1_000_000}m` : `${value / 1_000}k`;
}
