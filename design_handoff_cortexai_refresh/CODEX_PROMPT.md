# Codex prompt — paste this

Copy the block below into Codex (ChatGPT) once the `design_handoff_cortexai_refresh/`
folder is in your repo. Adjust the framework line to match your stack.

---

You're applying a visual redesign to our CortexAI app. The reference lives in
`design_handoff_cortexai_refresh/`. **Read `README.md` first**, then
`tokens.css`, `icons/icons.svg.md`, and open `cortex-refresh.html` in a browser
(or read its markup) for exact layout, spacing, and shadows.

Rules:
- This is a **visual layer** change. Do **not** alter routing, data fetching,
  state logic, or API calls. Keep all existing behaviour and component contracts.
- These files are **design references**, not our stack — recreate the look using
  our existing components and styling system (React + Tailwind), not by pasting
  the HTML.
- Implement **both light and dark themes** using the tokens. Wire dark mode to
  our existing theme switch (`[data-theme="dark"]` or our Tailwind `dark:` setup).

Do it in this order, one PR-sized step at a time (stop after each for review):

1. **Tokens + fonts** — add `tokens.css` variables (or merge `tailwind.tokens.js`),
   load Space Grotesk / Manrope / JetBrains Mono. No visual wiring yet.
2. **Brand mark + sidebar** — swap the logo for `brand/brand-mark.svg`, restyle
   the rail: solid-ink "New chat", accent rail on the active nav item, grouped
   history (Today / date), session footer chip.
3. **Icons** — replace existing icons with the set in `icons/Icons.jsx` /
   `icons.svg.md`. Keep our real model-vendor logos; the provider glyphs in the
   reference are placeholders.
4. **Ask answer card** — provider tile + routing badge, mono metric pills
   (latency · tokens · cost), provider-colour top rail, inline source chips,
   hover action toolbar (copy · regenerate · branch · rate).
5. **Composer command bar** — attach button, Smart/Web segmented toggle, Improve
   ghost button, accent send button; Compare variant adds the model-picker row
   (model ⇄ model + Add model) and "With sources".
6. **Compare results** — per-column provider rail, aligned metric strip, run
   summary bar, fastest/cheapest tags.
7. **Mobile** — top bar, bottom tab nav (Ask · Compare · History), segmented
   model switcher for answers, docked composer sheet, streaming skeleton + stop
   (filled square) state, scroll-to-latest FAB.

## Fixes in this revision (apply these — they address bugs in the current build)
- **Metric strip clipping** (timing/cost trimmed, esp. mobile): keep the strip on
  a **single packed line** (`display:flex; gap:6px`, pills `white-space:nowrap`,
  no `space-between`), value-only with abbreviated units (`tok`, `1.7s`,
  `$0.0107`). Mark the winning pill with a green tint. Keep the `· Fastest` /
  `· Cheapest` label **inside the winning pill but desktop-only** — wrap it in a
  `.winner-label` span and `display:none` it under the mobile breakpoint
  (`@media (max-width:640px)`). Desktop has room for the word; mobile shows the
  value alone (green tint still flags the winner). See "Metric strip" in README §4.
  Apply to desktop Compare columns, the Ask answer card, and mobile.
- **Prompt-optimization states** (new — see README §8): the `YOU` bubble must not
  uppercase or truncate the prompt body. Implement the 3 states (improving /
  optimized / already-clear) with the status shown as a pill **below** the bubble,
  sentence-case. This fixes the "IMPROVING YOUR PROMPT… …" rendering.

Match the hex values, radii, and shadow tokens exactly. Ask me before adding any
new copy, sections, or content not present in the reference.
