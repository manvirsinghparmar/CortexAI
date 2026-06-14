import {
  Children,
  cloneElement,
  isValidElement,
  useMemo,
  useState,
} from "react";
import type {
  ComponentPropsWithoutRef,
  HTMLAttributes,
  ReactElement,
  ReactNode,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getModelPresentation } from "../../config/modelPresentation";
import type { ChatResponse } from "../../types";
import { ProviderLogo } from "../shared/ProviderLogo";
import {
  ResponseLoadingState,
  type ResponseLoadingMode,
} from "./ResponseLoadingState";
import styles from "./ResponseCard.module.css";

interface ResponseCardProps {
  response: ChatResponse;
  isStreaming?: boolean;
  slotIndex?: number;
  compact?: boolean;
  loadingMode?: ResponseLoadingMode;
  researchEnabled?: boolean;
  optimizeEnabled?: boolean;
}

export function ResponseCard({
  response,
  isStreaming,
  slotIndex = 0,
  compact = false,
  loadingMode = "ask",
  researchEnabled = false,
  optimizeEnabled = false,
}: ResponseCardProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [statsOpen, setStatsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const hasError = !!response.error;
  const softError = response.error?.details?.kind === "transient_capacity";
  const badge = getModelBadge(response.provider, response.model);
  const modelPresentation = getModelPresentation(response.provider, response.model);
  const totalTokens = response.token_usage.total_tokens;
  const responseText = hasError ? errorMessage(response) : response.text;
  const showLoading = !hasError && !responseText && !!isStreaming;
  const sourceBaseId = useMemo(() => `cite-${response.request_id.replace(/[^a-zA-Z0-9_-]/g, "")}`, [
    response.request_id,
  ]);
  const statsId = useMemo(
    () => `response-stats-${response.request_id.replace(/[^a-zA-Z0-9_-]/g, "")}`,
    [response.request_id],
  );

  const copyResponse = async () => {
    await navigator.clipboard?.writeText(responseText || "").catch(() => undefined);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <article
      className={`${styles.card} ${compact ? styles.compact : ""} ${
        hasError ? styles.errorCard : ""
      } ${
        softError ? styles.softErrorCard : ""
      }`}
    >
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <div className={styles.modelHeader}>
            <ProviderLogo
              provider={response.provider}
              logoUrl={modelPresentation.logoUrl}
              color={modelPresentation.color}
              size={26}
              className={styles.modelLogo}
            />
            <div className={styles.modelIdentity}>
              <h2>{modelPresentation.label}</h2>
              <span>{response.model || response.provider}</span>
            </div>
          </div>
          <span className={`${styles.badge} ${styles[badge.tone]}`}>{badge.label}</span>
        </div>
        <button
          type="button"
          className={styles.statsToggle}
          aria-expanded={statsOpen}
          aria-controls={statsId}
          onClick={() => setStatsOpen((open) => !open)}
        >
          <span>Details</span>
          <span
            className={`${styles.statsCaret} ${statsOpen ? styles.statsCaretOpen : ""}`}
            aria-hidden="true"
          />
        </button>
        <div
          id={statsId}
          className={`${styles.metaRow} ${statsOpen ? styles.metaRowExpanded : ""}`}
        >
          <span>
            <Icon name="bolt" />
            {response.latency_ms || 0}ms
          </span>
          <span>
            <Icon name="document" />
            {formatTokens(totalTokens)} tokens
          </span>
          {response.estimated_cost > 0 && <span>${response.estimated_cost.toFixed(5)}</span>}
        </div>
      </header>

      <div
        id={`response-text-${slotIndex}`}
        className={`${styles.body} ${isStreaming ? styles.streaming : ""}`}
      >
        {hasError ? (
          <div className={styles.errorMsg}>
            <span aria-hidden="true">!</span>
            {errorMessage(response)}
          </div>
        ) : showLoading ? (
          <ResponseLoadingState
            mode={loadingMode}
            researchEnabled={researchEnabled}
            optimizeEnabled={optimizeEnabled}
          />
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children, ...props }) => {
                const scopedHref = scopedCitationHref(href, sourceBaseId);
                return (
                  <a href={scopedHref} target={isExternal(scopedHref) ? "_blank" : undefined} rel="noreferrer" {...props}>
                    {children}
                  </a>
                );
              },
              code: CodeBlock,
              table: MarkdownTable,
            }}
          >
            {responseText}
          </ReactMarkdown>
        )}
        {isStreaming && !!responseText && <span className={styles.cursor} aria-hidden="true" />}
      </div>

      <footer className={styles.actions}>
        <button
          type="button"
          className={styles.actionButton}
          onClick={() => setSourcesOpen((open) => !open)}
          disabled={response.web_source_items.length === 0}
          aria-label="Resources"
          title="Resources"
          aria-expanded={sourcesOpen}
          aria-controls={`response-sources-${slotIndex}`}
        >
          <Icon name="resources" />
          <span>Resources</span>
        </button>
        <button
          type="button"
          className={styles.actionButton}
          aria-label={copied ? "Copied response" : "Copy response"}
          title={copied ? "Copied" : "Copy response"}
          onClick={() => void copyResponse()}
        >
          <Icon name="copy" />
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
        <button
          type="button"
          className={`${styles.iconOnly} ${feedback === "up" ? styles.selectedAction : ""}`}
          aria-label="Helpful response"
          title="Helpful response"
          onClick={() => setFeedback(feedback === "up" ? null : "up")}
        >
          <Icon name="thumbUp" />
        </button>
        <button
          type="button"
          className={`${styles.iconOnly} ${feedback === "down" ? styles.selectedAction : ""}`}
          aria-label="Not helpful response"
          title="Not helpful response"
          onClick={() => setFeedback(feedback === "down" ? null : "down")}
        >
          <Icon name="thumbDown" />
        </button>
      </footer>

      {sourcesOpen && response.web_source_items.length > 0 && (
        <div id={`response-sources-${slotIndex}`} className={styles.sources}>
          <span>Sources</span>
          <ul>
            {response.web_source_items.map((source, index) => (
              <li key={`${source.url}-${index}`} id={`${sourceBaseId}-${index + 1}`}>
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.title || source.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function MarkdownTable({
  children,
  ...props
}: ComponentPropsWithoutRef<"table">) {
  const headerLabels = tableHeaderLabels(children);
  const labelledChildren = labelTableCells(children, headerLabels);

  return (
    <div
      className={styles.tableWrap}
      role="region"
      aria-label="Response table"
      tabIndex={0}
    >
      <table {...props}>{labelledChildren}</table>
    </div>
  );
}

type MarkdownElement = ReactElement<{
  children?: ReactNode;
  "data-label"?: string;
}>;

function isMarkdownElement(
  value: ReactNode,
  type: "thead" | "tbody" | "tr" | "th" | "td",
): value is MarkdownElement {
  return isValidElement<{ children?: ReactNode }>(value) && value.type === type;
}

function tableHeaderLabels(children: ReactNode): string[] {
  const head = Children.toArray(children).find((child) =>
    isMarkdownElement(child, "thead"),
  );
  if (!head || !isMarkdownElement(head, "thead")) return [];

  const row = Children.toArray(head.props.children).find((child) =>
    isMarkdownElement(child, "tr"),
  );
  if (!row || !isMarkdownElement(row, "tr")) return [];

  return Children.toArray(row.props.children)
    .filter((cell): cell is MarkdownElement => isMarkdownElement(cell, "th"))
    .map((cell) => textContent(cell.props.children));
}

function labelTableCells(children: ReactNode, labels: string[]): ReactNode {
  return Children.map(children, (child) => {
    if (!isMarkdownElement(child, "tbody")) return child;

    return cloneElement(
      child,
      {},
      Children.map(child.props.children, (row) => {
        if (!isMarkdownElement(row, "tr")) return row;
        let cellIndex = 0;

        return cloneElement(
          row,
          {},
          Children.map(row.props.children, (cell) => {
            if (!isMarkdownElement(cell, "td")) return cell;
            const label = labels[cellIndex] || `Column ${cellIndex + 1}`;
            cellIndex += 1;
            return cloneElement(cell, { "data-label": label });
          }),
        );
      }),
    );
  });
}

function textContent(value: ReactNode): string {
  return Children.toArray(value)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") {
        return String(child);
      }
      return isValidElement<{ children?: ReactNode }>(child)
        ? textContent(child.props.children)
        : "";
    })
    .join("")
    .trim();
}

function CodeBlock({
  inline,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & {
  inline?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const code = String(children ?? "").replace(/\n$/, "");
  const language = /language-(\w+)/.exec(className ?? "")?.[1];

  if (inline) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  const copy = async () => {
    await navigator.clipboard?.writeText(code).catch(() => undefined);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div className={styles.codeBlock}>
      <div className={styles.codeHeader}>
        <span>{language ?? "code"}</span>
        <button type="button" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}

function getModelBadge(provider: string, model: string) {
  const value = `${provider} ${model}`.toLowerCase();
  if (value.includes("gemini")) return { label: "FASTEST", tone: "fastest" as const };
  if (value.includes("grok") || value.includes("xai")) return { label: "RAW", tone: "raw" as const };
  if (value.includes("claude") || value.includes("anthropic")) {
    return { label: "ADVANCED", tone: "advanced" as const };
  }
  if (value.includes("deepseek")) return { label: "DEEP", tone: "deep" as const };
  if (value.includes("smart")) return { label: "ROUTED", tone: "advanced" as const };
  return { label: "MODEL", tone: "legacy" as const };
}

function formatTokens(tokens: number) {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(tokens >= 10000 ? 0 : 1)}k`;
  return tokens.toLocaleString();
}

function errorMessage(response: ChatResponse): string {
  if (response.error?.details?.kind === "transient_capacity") {
    return "This model is temporarily busy. Try again shortly or switch to another model.";
  }
  return response.error?.message || response.text || "The model returned an error.";
}

function scopedCitationHref(href: string | undefined, sourceBaseId: string): string | undefined {
  if (!href?.startsWith("#cite-")) return href;
  const index = Number(href.match(/(\d+)$/)?.[1] ?? "0");
  return index > 0 ? `#${sourceBaseId}-${index}` : href;
}

function isExternal(href: string | undefined): boolean {
  return !!href && /^https?:\/\//i.test(href);
}

function Icon({ name }: { name: "bolt" | "document" | "resources" | "copy" | "thumbUp" | "thumbDown" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "bolt" && <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />}
      {name === "document" && (
        <>
          <path d="M7 3h7l4 4v14H7z" />
          <path d="M14 3v5h4" />
          <path d="M9 13h6" />
          <path d="M9 17h6" />
        </>
      )}
      {name === "resources" && (
        <>
          <path d="M5 5h14v14H5z" />
          <path d="M8 9h8" />
          <path d="M8 13h5" />
        </>
      )}
      {name === "copy" && (
        <>
          <path d="M8 8h11v11H8z" />
          <path d="M5 16V5h11" />
        </>
      )}
      {name === "thumbUp" && (
        <>
          <path d="M7 10v10" />
          <path d="M11 10 13 4a2 2 0 0 1 2 2v4h5l-2 10H9a2 2 0 0 1-2-2v-8z" />
        </>
      )}
      {name === "thumbDown" && (
        <>
          <path d="M7 14V4" />
          <path d="M11 14 13 20a2 2 0 0 0 2-2v-4h5L18 4H9a2 2 0 0 0-2 2v8z" />
        </>
      )}
    </svg>
  );
}
