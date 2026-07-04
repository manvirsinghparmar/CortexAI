import { useChatStore } from "../store/chatStore";

// Applying every SSE delta to the store re-renders the transcript and
// re-parses markdown per token, which can saturate the main thread on long
// responses. Batch deltas and flush at the same ~8/sec cadence the legacy
// UI used (STREAM_MARKDOWN_RENDER_DEBOUNCE_MS in frontend/app.js).
const FLUSH_INTERVAL_MS = 120;

export class StreamDeltaBuffer {
  private pending = new Map<number, string>();
  private timer: number | null = null;

  constructor(private readonly turnId: string) {}

  append(index: number, text: string): void {
    this.pending.set(index, (this.pending.get(index) ?? "") + text);
    if (this.timer === null) {
      this.timer = window.setTimeout(() => this.flush(), FLUSH_INTERVAL_MS);
    }
  }

  flush(): void {
    if (this.timer !== null) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.pending.size === 0) return;

    const state = useChatStore.getState();
    for (const [index, text] of this.pending) {
      state.appendTurnResponseText(this.turnId, index, text, {
        ui_status: "streaming",
      });
    }
    this.pending.clear();
  }
}
