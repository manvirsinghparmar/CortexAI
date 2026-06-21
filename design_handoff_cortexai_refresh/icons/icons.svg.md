# CortexAI — Raw SVG reference

Framework-agnostic. Every line/action/composer/nav icon shares this wrapper:

```html
<svg width="20" height="20" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" stroke-width="1.75"
     stroke-linecap="round" stroke-linejoin="round">
  <!-- paths below -->
</svg>
```

`stroke="currentColor"` means the icon takes the element's CSS `color`. Just swap the inner paths.

## Navigation
- **ask** · `<path d="M21 11.5a8.4 8.4 0 0 1-12.3 7.5L4 20.5l1.4-4.5A8.4 8.4 0 1 1 21 11.5z"/><path d="M9 10.5h6M9 13.5h4"/>`
- **compare** · `<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><line x1="12" y1="5" x2="12" y2="19"/>`
- **new-chat** · `<path d="M12 20h8"/><path d="M16.5 4.5a2.12 2.12 0 0 1 3 3L8 19l-4 1 1-4z"/>`
- **history** · `<path d="M3.5 9a8.5 8.5 0 1 1 .3 5"/><path d="M3.5 4v5h5"/><path d="M12 8v4l3 2"/>`
- **search** · `<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>`
- **collapse-sidebar** · `<rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="9" y1="4" x2="9" y2="20"/><path d="M15.5 10l-2 2 2 2"/>`
- **user** · `<circle cx="12" cy="8" r="3.4"/><path d="M5 20a7 7 0 0 1 14 0"/>`

## Metrics
- **latency** · `<path d="M13 3 5 13h5l-1 8 8-11h-5z"/>`
- **tokens** · `<path d="M12 3 3 7.5l9 4.5 9-4.5z"/><path d="M3 12.5l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5"/>`
- **cost** · `<circle cx="12" cy="12" r="8.5"/><path d="M14.6 9.4a2.6 2.6 0 0 0-2.6-1.5c-1.5 0-2.6.8-2.6 2 0 2.7 5.4 1.4 5.4 4.1 0 1.3-1.2 2.1-2.8 2.1a2.7 2.7 0 0 1-2.7-1.6M12 6.4v11.2"/>`

## Composer
- **attach** · `<path d="M20 11.5 12 19.5a4.5 4.5 0 0 1-6.4-6.4l8-8a3 3 0 0 1 4.3 4.3l-8 8a1.5 1.5 0 0 1-2.2-2.1l7.3-7.3"/>`
- **smart** · `<path d="M12 3c.4 3.6 1.4 4.6 5 5-3.6.4-4.6 1.4-5 5-.4-3.6-1.4-4.6-5-5 3.6-.4 4.6-1.4 5-5z"/><path d="M18.5 14.5c.2 1.6.6 2 2.2 2.2-1.6.2-2 .6-2.2 2.2-.2-1.6-.6-2-2.2-2.2 1.6-.2 2-.6 2.2-2.2z"/>`
- **web** · `<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18"/>`
- **sources** · `<path d="M9 12a3 3 0 0 0 3 3h2a4 4 0 0 0 0-8h-1M15 12a3 3 0 0 0-3-3h-2a4 4 0 0 0 0 8h1"/>`
- **improve** · `<path d="M5 19 14 10"/><path d="M16 3l1 2.4 2.4 1-2.4 1L16 9.8 15 7.4 12.6 6.4 15 5.4z"/><path d="M6.5 5.5 7 7l1.5.5L7 8l-.5 1.5L6 8l-1.5-.5L6 7z"/>`
- **send** · `<path d="M5 12h13M12 6l6 6-6 6"/>`
- **stop** · filled, no stroke: `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>`

## Answer actions
- **copy** · `<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>`
- **regenerate** · `<path d="M3.5 9a8.5 8.5 0 1 1 .3 5"/><path d="M3.5 4v5h5"/>`
- **branch** · `<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="9" r="2.5"/><path d="M6 8.5v7M8.5 6H14a2 2 0 0 1 2 2v.5"/>`
- **thumb-up** · `<path d="M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1zm0 0 4.5-8a2 2 0 0 1 2 1.6l-.8 4.4H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7"/>`
- **thumb-down** · `<path d="M17 13V4h3a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1zm0 0-4.5 8a2 2 0 0 1-2-1.6l.8-4.4H5a2 2 0 0 1-2-2.3l1.2-6A2 2 0 0 1 6.2 4H17"/>`

## Suggestion cards
- **debug** · `<rect x="8" y="8" width="8" height="9" rx="4"/><path d="M9 8a3 3 0 0 1 6 0M4 11h3M4 15h3M17 11h3M17 15h3M5.5 7l2 1.8M18.5 7l-2 1.8M12 12v5"/>`
- **summarize** · `<rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/>`
- **rewrite** · `<path d="M4 20h4L19 9a2.12 2.12 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/>`
- **analyze** · `<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3M11 8v6M8 11h6"/>`
- **find-solution** · `<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>`
- **review** · `<path d="M21 11.5a8.4 8.4 0 0 1-12.3 7.5L4 20.5l1.4-4.5A8.4 8.4 0 1 1 21 11.5z"/><path d="M8.5 11.5l2 2 4.5-4.5"/>`

## Utility
- **plus** · `<path d="M12 5v14M5 12h14"/>`
- **chevron-down** · `<path d="M6 9l6 6 6-6"/>`
- **swap** · `<path d="M8 4 4 8l4 4M4 8h11M16 20l4-4-4-4M20 16H9"/>`
- **scroll-down** · `<path d="M12 5v14M6 13l6 6 6-6"/>`
- **external-link** (use stroke-width 2.2, size ~12) · `<path d="M7 17 17 7M9 7h8v8"/>`

---

## Brand mark (multi-colour — NOT currentColor)
5-node cortex graph; the middle-left node carries the accent. `viewBox="0 0 32 32"`.
Swap `STROKE` / `NODE` / `ACCENT`:
- On dark tile: STROKE/NODE = `#fff`, ACCENT = `#8B8BF0`
- On light tile: STROKE = `#475569`, NODE = `#334155`, ACCENT = `#5B5BD6`
- Solid accent tile: all `#fff`

```html
<svg viewBox="0 0 32 32" fill="none">
  <line x1="10" y1="8"  x2="10" y2="24" stroke="STROKE" stroke-width="1.7" stroke-opacity=".5"/>
  <line x1="10" y1="8"  x2="22" y2="11" stroke="STROKE" stroke-width="1.7" stroke-opacity=".5"/>
  <line x1="10" y1="16" x2="22" y2="11" stroke="STROKE" stroke-width="1.7" stroke-opacity=".5"/>
  <line x1="10" y1="16" x2="22" y2="21" stroke="STROKE" stroke-width="1.7" stroke-opacity=".5"/>
  <line x1="10" y1="24" x2="22" y2="21" stroke="STROKE" stroke-width="1.7" stroke-opacity=".5"/>
  <circle cx="10" cy="8"  r="2.7" fill="NODE"/>
  <circle cx="10" cy="16" r="2.7" fill="ACCENT"/>
  <circle cx="10" cy="24" r="2.7" fill="NODE"/>
  <circle cx="22" cy="11" r="2.7" fill="NODE"/>
  <circle cx="22" cy="21" r="2.7" fill="NODE"/>
</svg>
```

## Provider glyphs — ORIGINAL PLACEHOLDERS
⚠️ These are neutral, original marks so the mockup isn't tied to any vendor's
trademark. **Replace each with the model vendor's official SVG logo** in your app.
What matters is the *system*: each model slot owns a colour that flows into its
tile background (`*-soft`), card top-rail, and metric tags.

- **Slot A / indigo** (e.g. GPT) tile `#EEF0FB` · `<circle cx="12" cy="12" r="3" fill="#5B5BD6"/><circle cx="12" cy="5" r="1.8" fill="#8B8BF0"/><circle cx="12" cy="19" r="1.8" fill="#8B8BF0"/><circle cx="6" cy="8.5" r="1.8" fill="#8B8BF0"/><circle cx="18" cy="8.5" r="1.8" fill="#8B8BF0"/><circle cx="6" cy="15.5" r="1.8" fill="#8B8BF0"/><circle cx="18" cy="15.5" r="1.8" fill="#8B8BF0"/>`
- **Slot B / coral** (e.g. Claude) tile `#FBEEE6` · stroke `#E07A4D` w2 · `<path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/>`
- **Slot C / blue** (e.g. DeepSeek) tile `#E7F0FC` · stroke `#3D7FF0` w2 · `<path d="M3 14c3-5 6-5 9 0s6 5 9 0"/><path d="M3 9c3-5 6-5 9 0s6 5 9 0"/>`
- **Slot D / violet** (e.g. Gemini) tile `#EFEAFC` · `<path d="M12 3l2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6z" fill="#8454D6"/>`
- **Slot E / graphite** (e.g. Grok) tile `#EEF1F4` · stroke `#475569` w2 · `<path d="M5 19 13 5M11 19l5-9M16 14l3-3"/>`
