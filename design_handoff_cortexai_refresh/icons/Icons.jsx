/* ============================================================
   CortexAI Icon Set — React (framework-agnostic SVG inside)
   - 24x24 grid, 1.75 stroke, round caps/joins, fill:none
   - stroke="currentColor" => colour via CSS `color` / text-* class
   - Usage:  <Ask className="w-5 h-5 text-cx-ink-500" />
   - For plain HTML/Vue/Svelte, copy the <path> contents from
     icons.svg.md instead.
   ============================================================ */
import React from 'react';

const S = ({ size = 20, children, ...rest }) => (
  <svg
    width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.75"
    strokeLinecap="round" strokeLinejoin="round" {...rest}
  >{children}</svg>
);

/* ---- Navigation ---- */
export const Ask = (p) => <S {...p}><path d="M21 11.5a8.4 8.4 0 0 1-12.3 7.5L4 20.5l1.4-4.5A8.4 8.4 0 1 1 21 11.5z"/><path d="M9 10.5h6M9 13.5h4"/></S>;
export const Compare = (p) => <S {...p}><rect x="3.5" y="5" width="17" height="14" rx="2.5"/><line x1="12" y1="5" x2="12" y2="19"/></S>;
export const NewChat = (p) => <S {...p}><path d="M12 20h8"/><path d="M16.5 4.5a2.12 2.12 0 0 1 3 3L8 19l-4 1 1-4z"/></S>;
export const History = (p) => <S {...p}><path d="M3.5 9a8.5 8.5 0 1 1 .3 5"/><path d="M3.5 4v5h5"/><path d="M12 8v4l3 2"/></S>;
export const Search = (p) => <S {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></S>;
export const CollapseSidebar = (p) => <S {...p}><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="9" y1="4" x2="9" y2="20"/><path d="M15.5 10l-2 2 2 2"/></S>;
export const User = (p) => <S {...p}><circle cx="12" cy="8" r="3.4"/><path d="M5 20a7 7 0 0 1 14 0"/></S>;

/* ---- Metrics ---- */
export const Latency = (p) => <S {...p}><path d="M13 3 5 13h5l-1 8 8-11h-5z"/></S>;
export const Tokens = (p) => <S {...p}><path d="M12 3 3 7.5l9 4.5 9-4.5z"/><path d="M3 12.5l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5"/></S>;
export const Cost = (p) => <S {...p}><circle cx="12" cy="12" r="8.5"/><path d="M14.6 9.4a2.6 2.6 0 0 0-2.6-1.5c-1.5 0-2.6.8-2.6 2 0 2.7 5.4 1.4 5.4 4.1 0 1.3-1.2 2.1-2.8 2.1a2.7 2.7 0 0 1-2.7-1.6M12 6.4v11.2"/></S>;

/* ---- Composer ---- */
export const Attach = (p) => <S {...p}><path d="M20 11.5 12 19.5a4.5 4.5 0 0 1-6.4-6.4l8-8a3 3 0 0 1 4.3 4.3l-8 8a1.5 1.5 0 0 1-2.2-2.1l7.3-7.3"/></S>;
export const Smart = (p) => <S {...p}><path d="M12 3c.4 3.6 1.4 4.6 5 5-3.6.4-4.6 1.4-5 5-.4-3.6-1.4-4.6-5-5 3.6-.4 4.6-1.4 5-5z"/><path d="M18.5 14.5c.2 1.6.6 2 2.2 2.2-1.6.2-2 .6-2.2 2.2-.2-1.6-.6-2-2.2-2.2 1.6-.2 2-.6 2.2-2.2z"/></S>;
export const Web = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18"/></S>;
export const Sources = (p) => <S {...p}><path d="M9 12a3 3 0 0 0 3 3h2a4 4 0 0 0 0-8h-1M15 12a3 3 0 0 0-3-3h-2a4 4 0 0 0 0 8h1"/></S>;
export const Improve = (p) => <S {...p}><path d="M5 19 14 10"/><path d="M16 3l1 2.4 2.4 1-2.4 1L16 9.8 15 7.4 12.6 6.4 15 5.4z"/><path d="M6.5 5.5 7 7l1.5.5L7 8l-.5 1.5L6 8l-1.5-.5L6 7z"/></S>;
export const Send = (p) => <S {...p}><path d="M5 12h13M12 6l6 6-6 6"/></S>;
export const Stop = ({ size = 20, ...p }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" {...p}><rect x="7" y="7" width="10" height="10" rx="2"/></svg>;

/* ---- Answer actions ---- */
export const Copy = (p) => <S {...p}><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/></S>;
export const Regenerate = (p) => <S {...p}><path d="M3.5 9a8.5 8.5 0 1 1 .3 5"/><path d="M3.5 4v5h5"/></S>;
export const Branch = (p) => <S {...p}><circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="9" r="2.5"/><path d="M6 8.5v7M8.5 6H14a2 2 0 0 1 2 2v.5"/></S>;
export const ThumbUp = (p) => <S {...p}><path d="M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1zm0 0 4.5-8a2 2 0 0 1 2 1.6l-.8 4.4H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7"/></S>;
export const ThumbDown = (p) => <S {...p}><path d="M17 13V4h3a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1zm0 0-4.5 8a2 2 0 0 1-2-1.6l.8-4.4H5a2 2 0 0 1-2-2.3l1.2-6A2 2 0 0 1 6.2 4H17"/></S>;

/* ---- Suggestion cards ---- */
export const Debug = (p) => <S {...p}><rect x="8" y="8" width="8" height="9" rx="4"/><path d="M9 8a3 3 0 0 1 6 0M4 11h3M4 15h3M17 11h3M17 15h3M5.5 7l2 1.8M18.5 7l-2 1.8M12 12v5"/></S>;
export const Summarize = (p) => <S {...p}><rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/></S>;
export const Rewrite = (p) => <S {...p}><path d="M4 20h4L19 9a2.12 2.12 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/></S>;
export const Analyze = (p) => <S {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3M11 8v6M8 11h6"/></S>;
export const FindSolution = (p) => <S {...p}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></S>;
export const Review = (p) => <S {...p}><path d="M21 11.5a8.4 8.4 0 0 1-12.3 7.5L4 20.5l1.4-4.5A8.4 8.4 0 1 1 21 11.5z"/><path d="M8.5 11.5l2 2 4.5-4.5"/></S>;

/* ---- Utility ---- */
export const Plus = (p) => <S {...p}><path d="M12 5v14M5 12h14"/></S>;
export const ChevronDown = (p) => <S {...p}><path d="M6 9l6 6 6-6"/></S>;
export const Swap = (p) => <S {...p}><path d="M8 4 4 8l4 4M4 8h11M16 20l4-4-4-4M20 16H9"/></S>;
export const ScrollDown = (p) => <S {...p}><path d="M12 5v14M6 13l6 6 6-6"/></S>;
export const ExternalLink = ({ size = 12, ...p }) => <S size={size} strokeWidth="2.2" {...p}><path d="M7 17 17 7M9 7h8v8"/></S>;

/* ---- Brand mark (multi-colour; NOT currentColor) ---- */
/* nodeAccent highlights the middle-left node. Pass light/dark stroke + node colours. */
export const BrandMark = ({ size = 24, stroke = '#fff', node = '#fff', nodeAccent = '#8B8BF0' }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
    <line x1="10" y1="8" x2="10" y2="24" stroke={stroke} strokeWidth="1.7" strokeOpacity=".5"/>
    <line x1="10" y1="8" x2="22" y2="11" stroke={stroke} strokeWidth="1.7" strokeOpacity=".5"/>
    <line x1="10" y1="16" x2="22" y2="11" stroke={stroke} strokeWidth="1.7" strokeOpacity=".5"/>
    <line x1="10" y1="16" x2="22" y2="21" stroke={stroke} strokeWidth="1.7" strokeOpacity=".5"/>
    <line x1="10" y1="24" x2="22" y2="21" stroke={stroke} strokeWidth="1.7" strokeOpacity=".5"/>
    <circle cx="10" cy="8" r="2.7" fill={node}/>
    <circle cx="10" cy="16" r="2.7" fill={nodeAccent}/>
    <circle cx="10" cy="24" r="2.7" fill={node}/>
    <circle cx="22" cy="11" r="2.7" fill={node}/>
    <circle cx="22" cy="21" r="2.7" fill={node}/>
  </svg>
);
