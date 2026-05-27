import ReactMarkdown from "react-markdown";
import type { ChatResponse } from "../../types";

interface ResponseCardProps {
  response: ChatResponse;
  isStreaming?: boolean;
  streamingText?: string;
}

function getModelBadge(provider: string): { label: string; className: string } {
  const p = provider.toLowerCase();
  if (p.includes("openai") || p.includes("gpt")) {
    return { label: "LEGACY", className: "bg-zinc-100 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400" };
  }
  if (p.includes("gemini") || p.includes("google")) {
    return { label: "FASTEST", className: "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400" };
  }
  if (p.includes("grok") || p.includes("xai")) {
    return { label: "RAW", className: "bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400" };
  }
  if (p.includes("claude") || p.includes("anthropic")) {
    return { label: "ADVANCED", className: "bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400" };
  }
  if (p.includes("deepseek")) {
    return { label: "DEEP", className: "bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400" };
  }
  return { label: "AI", className: "bg-zinc-100 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400" };
}

export function ResponseCard({ response, isStreaming, streamingText }: ResponseCardProps) {
  const text = isStreaming ? (streamingText ?? "") : response.text;
  const hasError = !!response.error;
  const badge = getModelBadge(response.provider);

  return (
    <article className={`bg-white dark:bg-zinc-800 rounded-xl border ${hasError ? "border-red-200 dark:border-red-800" : "border-zinc-200 dark:border-zinc-700"} shadow-sm flex flex-col overflow-hidden`}>
      {/* Card header */}
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-3 border-b border-zinc-100 dark:border-zinc-700">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 truncate">
              {response.model || response.provider}
            </span>
            <span className={`text-[10px] font-semibold tracking-wider px-1.5 py-0.5 rounded uppercase shrink-0 ${badge.className}`}>
              {badge.label}
            </span>
          </div>
          <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5 truncate">
            {response.provider}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className={`flex-1 px-4 py-3 text-sm overflow-auto ${isStreaming ? "min-h-[4rem]" : ""}`}>
        {hasError ? (
          <div className="flex items-start gap-2 text-red-600 dark:text-red-400">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{response.error!.message}</span>
          </div>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1.5 prose-headings:mt-3">
            <ReactMarkdown>{text}</ReactMarkdown>
            {isStreaming && (
              <span
                className="inline-block w-0.5 h-4 bg-zinc-600 dark:bg-zinc-400 animate-pulse ml-0.5 align-text-bottom"
                aria-hidden="true"
              />
            )}
          </div>
        )}
      </div>

      {/* Footer meta */}
      {!isStreaming && !hasError && (
        <div className="flex items-center gap-3 px-4 py-2.5 border-t border-zinc-100 dark:border-zinc-700 text-xs text-zinc-400 dark:text-zinc-500">
          <span>{response.latency_ms}ms</span>
          <span className="text-zinc-300 dark:text-zinc-600">·</span>
          <span>{response.token_usage.total_tokens.toLocaleString()} tokens</span>
          {response.estimated_cost > 0 && (
            <>
              <span className="text-zinc-300 dark:text-zinc-600">·</span>
              <span>${response.estimated_cost.toFixed(4)}</span>
            </>
          )}
        </div>
      )}

      {/* Web sources */}
      {!isStreaming && response.web_source_items.length > 0 && (
        <div className="px-4 pb-3">
          <div className="text-xs font-medium text-zinc-400 dark:text-zinc-500 mb-1.5">Sources</div>
          <ul className="space-y-1">
            {response.web_source_items.map((s, i) => (
              <li key={i}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline truncate block"
                >
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
