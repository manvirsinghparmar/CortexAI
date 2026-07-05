# Handoff: CortexAI — Visual Refresh

## Overview
A visual identity refresh for **CortexAI**, an LLM gateway with two modes —
**Ask** (single answer with smart routing) and **Compare** (one prompt, several
models side by side) — plus a **History** view, available on desktop and mobile.
The structure and behaviour are unchanged; this refresh adds a brand mark, a
tighter slate type/colour system with one restrained indigo accent, richer model
cards, a full custom icon set, and a complete dark theme.

## About the design files
The files in this bundle are **design references created in HTML/SVG** — they show
the intended look and behaviour. They are **not** production code to paste in.
Recreate these designs in the app's existing environment (React + Tailwind, or
whatever the repo uses), following its established component and styling patterns.
`cortex-refresh.html` is a single self-contained reference board — open it in a
browser to inspect any frame; read its markup for exact values.

## Fidelity
**High-fidelity.** Final colours, typography, spacing, radii, shadows, and
interaction affordances are specified. Recreate pixel-faithfully using the
codebase's libraries. Exact tokens are in `tokens.css` / `tailwind.tokens.js`;
all icons in `icons/`.

---

## Design system

### Typography
| Role | Family | Weights | Notes |
|---|---|---|---|
| Display / headings | **Space Grotesk** | 600, 700 | letter-spacing `-0.02em` to `-0.025em` |
| UI / body | **Manrope** | 400–800 | default app font |
| Mono | **JetBrains Mono** | 400–600 | model IDs, metrics, token/cost values, eyebrow labels |

Scale: page H1 40px / `-0.025em`; empty-state H2 30px; card title 17px (desktop)
/ 14px (mobile); body 14.5px / line-height 1.6; secondary 12.5px; metric/mono
12px; eyebrow labels mono 10–12px, `letter-spacing 0.16–0.2em`, uppercase.

### Colour — neutral slate + one accent
Full token list with hex in **`tokens.css`** (light = `:root`, dark =
`[data-theme="dark"]`). Principles:
- Near-monochrome slate/ink for surfaces and text.
- **Indigo accent `#5B5BD6` (light) / `#8B8BF0` (dark)** used *sparingly*: brand
  mark node, active nav/tab rail, send button, focus ring, primary links/source
  chips. Primary action buttons stay **ink `#0B1220`** (e.g. "New chat", "Smart",
  "With sources").
- Success green for "N succeeded" and cheapest/fastest tags.
- Dark theme is a **full token swap**, not inverted greys (canvas `#0B0D11`,
  surface `#11151B`, hairline `#1F262F`).

### Per-provider colour system
Each model slot owns a colour used in 3 places: the glyph tile background, the
card's 3px top rail, and its metric tags. Defaults: A indigo `#5B5BD6`,
B coral `#E07A4D`, C blue `#3D7FF0`, D violet `#8454D6`, E graphite `#475569`.
This keeps Compare columns scannable. (Assign per real model in your app.)

### Brand mark
A five-node "cortex" graph; the middle-left node carries the accent. Files:
`brand/brand-mark.svg` (dark tile) and `<BrandMark>` in `icons/Icons.jsx`
(themeable). Lockup: 34–46px rounded-square tile + "CortexAI" (Space Grotesk 700)
over "LLM GATEWAY" (mono, uppercase, `0.12em`).

### Icons
One family: 24×24 grid, **1.75 stroke**, round caps/joins, `fill:none`,
`stroke="currentColor"`. Provided three ways: `icons/Icons.jsx` (React),
`icons/icons.svg.md` (raw paths for any framework), and rendered in the reference
board. Set: ask, compare, new-chat, history, search, collapse, user, latency,
tokens, cost, attach, smart, web, sources, improve, send, stop, copy, regenerate,
branch, thumb-up/down, debug, summarize, rewrite, analyze, find-solution, review,
plus, chevron-down, swap, scroll-down, external-link, **theme** (appearance
toggle; `sun`/`moon` alternates included).
**Provider glyphs are original placeholders — swap in each vendor's official logo.**

### Radii & shadows
Radii: control 8–10px, button 11–13px, card 14–16px, phone frame 34px.
Shadows (tokens): `--cx-shadow-card` for frames, `--cx-shadow-pop` for the
composer, `--cx-shadow-accent` for the send button.

---

## Screens / views

### 1. Sidebar (desktop, 264px, persistent)
- **Background** `--cx-sidebar`, right border `--cx-hairline`.
- **Logo lockup** (top) + collapse-sidebar icon button (right).
- **New chat**: full-width, **solid ink** `#0B1220`, white text, 42px tall,
  radius 11px, new-chat icon left, mono `⌘K` chip right.
- **Nav** (Ask, Compare): 40px rows, radius 10px. Active = white surface +
  `--cx-shadow-sm` + a 3px accent rail (`--cx-accent`) inset at the left,
  text ink-900 bold. Inactive = ink-500, weight 500.
- **History**: section label (mono) + "Clear"; search input (search icon);
  list **grouped by date** ("Today", "Jun 17"). Each item: title (1 line,
  ellipsis), then a mode tag chip (`COMPARE` accent-soft / `ASK` slate) + time.
  Active item = `#EEF1F4` surface, title ink-900.
- **Footer chip**: pulsing green dot + truncated mono session id + "Session active".

### 2. Ask — answer view (desktop)
Top tab bar (Ask active = 2px ink underline; Compare inactive) + right header
icon buttons (plus, user). Scroll body:
- **User bubble** (right aligned): ink `#0B1220`, radius `16px 16px 6px 16px`,
  mono "YOU" eyebrow in accent `#7C86F5`, body `#E9ECF2`, soft drop shadow.
- **Answer card**: 1px hairline, radius 16px, a **3px provider-colour top rail**
  (gradient for the smart slot). Header: provider glyph tile (42px) + name
  (Space Grotesk 17) + mono model id, and a routing badge top-right
  (`SMART · MODEL`, accent-soft pill). **Metric pills row**: 3 pills (latency,
  tokens, cost) — surface-2 bg, 1px hairline, mono values, leading line-icon.
  Body: 14.5px/1.6, bold key phrases ink-900, section H4 in Space Grotesk; inline
  **source chips** = accent-soft pill with label + external-link icon.
  **Action toolbar** (top border): Copy / Regenerate / Branch ghost buttons
  (icon + label), spacer, then thumb-up / thumb-down icon buttons.
- **Composer** — see §6.

### 3. Compare — empty state (desktop)
Centered: mono eyebrow "COMPARE MODE" (accent), H2 "Ask once. Compare answers
across models." (Space Grotesk 700), one-line description, then **3 suggestion
cards in a row** (compare / find-solution / review icons in accent). Composer +
model-picker docked at bottom.

### 4. Compare — results (desktop)
- User bubble, then a **run summary row**: "N succeeded" (green-soft),
  "0 errors", "NN,NNN tok", "$X" (mono chips).
- **3 columns** (`grid 1fr 1fr 1fr`, gap 14px). Each column = surface card with a
  3px provider rail, header (glyph tile 30px + name + mono id + routing badge),
  a **metric strip** (see "Metric strip" below), then the answer with numbered or
  bulleted lists and source chips.
- Docked composer with the **model-picker row**: model pill ⇄ (swap icon) model
  pill + dashed "Add model"; "With sources" (ink) + send.

### Metric strip (latency / tokens / cost) — winner label is desktop-only
Each card shows three mono pills: latency, tokens, cost. Rules:
- **Single line, packed tight** (`display:flex; gap:6px`, pills
  `white-space:nowrap`). Don't space the pills apart (no `justify-content:
  space-between`) — left-pack them; the leftover room is what lets the winner
  word fit on desktop. Value only + abbreviated units (`tok`, `1.7s`, `$0.0107`).
- The **winning pill gets a green tint** (success-soft bg + success-text) in every
  viewport — this alone marks "best" and needs no words.
- The **`· Fastest` / `· Cheapest` label lives inside the winning pill, but is
  shown on desktop only.** On mobile (≤ the app's phone breakpoint) hide the
  label so the pill shows the value alone:
  ```html
  <span class="metric winner">$0.0023<span class="winner-label"> · Cheapest</span></span>
  ```
  ```css
  @media (max-width: 640px) { .winner-label { display: none; } }
  ```
  Desktop columns are wide enough to show the word; mobile cards stay compact with
  value-only pills (green tint still flags the winner). This is the fix: the word
  never causes overflow because it's removed exactly where space is tight.

### 5. History (mobile shown; desktop reuses the sidebar list)
Search field, then grouped cards: mode chip + timestamp, title (up to 2 lines),
and a mono meta line "`N turns · model(s)`". Active card = accent-soft surface.

### 6. Composer (command bar) — light & dark
Rounded container (radius 16–18px), 1px hairline, `--cx-shadow-pop`, placeholder
text. Bottom row: **attach** icon button · **Smart/Web** segmented toggle (track
`--cx-surface-3`, active segment ink `#0B1220` white text, icon + label) ·
**Improve** ghost button · spacer · **send** = 40–44px accent square,
`--cx-shadow-accent`. Compare swaps placeholder to "Ask once and compare model
responses" and shows "With sources" + the model-picker row.

### 7. Mobile (≤ ~430px) — 5 states
Phone frame: sticky **top bar** (logo + new-chat + user), content, **bottom tab
nav** (Ask · Compare · History; active = accent text + accent-soft–filled icon).
- **Compare · empty** — eyebrow, heading, 3 stacked suggestion cards, docked
  sheet: model-picker row + Add Model + composer.
- **Compare · results** — user bubble, summary chips (wrap), a **segmented model
  switcher** (DeepSeek / Claude / GPT) showing one answer card at a time.
- **Ask · answer** — bubble, summary chips, model switcher, single answer card,
  composer with Smart/Web/Improve.
- **History** — search + grouped list (see §5).
- **Compare · streaming** — segmented switcher, answer card with elapsed timer +
  "Queued" chip, "Checking sources…" line, **3 skeleton bars**; a **scroll-to-
  latest FAB** (ink circle, scroll-down icon) above the composer; the send button
  becomes a **Stop** button (ink square, white rounded inner square).

### 8. Prompt optimization states (the "Improve" flow)
The app optimizes the user's prompt before sending. This has **three states** the
first cut missed — and they must not break the `YOU` bubble. Core rules:
**never uppercase or truncate the prompt body** (only the small `YOU` eyebrow is
uppercased), and show optimization status **outside** the bubble.
1. **Improving (pending)** — show the user's prompt in the bubble (sentence/normal
   case), and a right-aligned **status pill below the bubble**: sparkle icon +
   "Improving your prompt" + animated dots. Accent-soft bg. Not inside the bubble.
2. **Optimized (rewritten)** — the bubble shows the *sent* (improved) prompt; below
   it a quiet chip: sparkle + "Prompt optimized" + a "View original" toggle that
   reveals what the user typed.
3. **Already clear (kept)** — if no change is made, replace the status with a green
   confirmation chip: check icon + "Already clear — sent as-is".
⚠️ Bug seen in the build: the bubble rendered the prompt UPPERCASED and truncated
("IMPROVING YOUR PROMPT… …"). Cause = applying the eyebrow's `text-transform:
uppercase` / a fixed-width truncation to the body, and putting the status text
inside the bubble. Keep body text normal-case, full (wrap, no clamp), and move
status to the pill below.

---

## Interactions & behaviour
- **Hover**: cards/buttons lift slightly (`translateY(-1–2px)`) with a shadow/
  border transition (~180ms, ease-out). Reference uses class `.lift`.
- **Active nav / tab**: accent rail (sidebar) or 2px underline (top tabs).
- **Segmented toggles** (Smart/Web, model switcher): selected segment = filled
  surface/ink with `--cx-shadow-sm`; others transparent.
- **Send → Stop**: while a response streams, the accent send button is replaced
  by an ink Stop button; show elapsed timer, "Queued" chip, and skeleton bars in
  the pending card; show the scroll-to-latest FAB when not at bottom.
- **Source chips**: clickable, open the cited URL (external-link icon).
- **Answer toolbar**: Copy (clipboard), Regenerate (re-run same model),
  Branch (fork conversation), thumb up/down (feedback).
- **Focus**: 2px accent ring on inputs/buttons for keyboard nav.

## States to cover
Empty (Ask / Compare), loading/streaming (skeleton + stop), success (summary
chips), error ("N errors" in summary; per-card error styling — red-soft), and
light/dark for all.

## Responsive behaviour
- **Desktop** (≥ ~1024px): 264px sidebar + main; Compare = up to 3+ columns.
- **Mobile** (≤ ~430px): sidebar collapses to bottom tab nav; Compare/Ask answers
  collapse to a **segmented switcher** (one model at a time) instead of columns;
  composer + model-picker become a docked bottom sheet.

## State management (visual only — keep existing logic)
No new app state required beyond what exists. UI state the design implies:
active tab/route, active model in the mobile switcher, composer mode flags
(smart/web/sources/improve), streaming flag (send↔stop), theme (light/dark),
sidebar collapsed. Wire these to existing stores; **do not** change data fetching.

## Design tokens
See `tokens.css` (CSS variables) and `tailwind.tokens.js` (Tailwind extend).
Both include the full slate scale, accent, success, per-provider colours, radii,
shadows, and font families, for light and dark.

## Assets
- `brand/brand-mark.svg` — CortexAI mark (dark tile). Themeable version:
  `<BrandMark>` in `icons/Icons.jsx`.
- `icons/Icons.jsx` + `icons/icons.svg.md` — full icon set (`currentColor`).
- Provider glyphs are **original placeholders** — replace with official vendor
  logos in the app. Their *colour assignment* is the part to keep.

## Files in this bundle
- `README.md` — this spec.
- `CODEX_PROMPT.md` — paste-ready instructions + recommended build order.
- `cortex-refresh.html` — self-contained visual reference board (all screens,
  light + dark, components, icon library, mobile). Open in a browser.
- `tokens.css`, `tailwind.tokens.js` — design tokens.
- `icons/Icons.jsx`, `icons/icons.svg.md` — icons.
- `brand/brand-mark.svg` — brand mark.
- `screenshots/` — PNGs of the key frames (visual targets).
