const MAX_SUGGESTIONS = 3;
const MAX_REGION_CHARS = 2000;
const MAX_SUGGESTION_CHARS = 180;

const LEAD_IN_SOURCE =
  "(if\\s+you\\s+want|i\\s+can\\s+also|i\\s+can\\s+give\\s+you|i\\s+can\\s+provide|i\\s+can\\s+help\\s+with|would\\s+you\\s+like|want\\s+me\\s+to)";
const LEAD_IN_GLOBAL = new RegExp(LEAD_IN_SOURCE, "gi");
const LEAD_IN_LINE = new RegExp(LEAD_IN_SOURCE, "i");
const LIST_MARKER = /^(\s*(?:[-*]|\d+[.)])\s+)/;
const QUOTED_FOLLOW_UP_QUERY_SOURCE =
  "(?:(?:a\\s+)?(?:focused\\s+)?follow[-\\s]+up\\s+(?:query|question)\\s+could\\s+be|(?:a\\s+)?good\\s+follow[-\\s]+up\\s+(?:query|question)\\s+(?:would|could)\\s+be|(?:a\\s+)?specific\\s+(?:query|question)\\s+would\\s+be\\s+(?:needed|required)(?:,?\\s+such\\s+as)?|you\\s+could\\s+ask)";
const QUOTED_FOLLOW_UP_QUERY_GLOBAL = new RegExp(
  `${QUOTED_FOLLOW_UP_QUERY_SOURCE}\\s*:?\\s*(?:\\*\\*)?["\\u201c](?<query>[^"\\u201d\\n]+)["\\u201d](?:\\*\\*)?`,
  "gi",
);
const SINGLE_OFFER_ACTION =
  "(?:build|compare|convert|create|draft|format|generate|give\\s+you|make|map|outline|prepare|provide|rewrite|show\\s+you|summarize|translate|turn)";
const SINGLE_OFFER_PATTERNS = [
  new RegExp(`\\bi\\s+can(?:\\s+also)?\\s+(?<offer>${SINGLE_OFFER_ACTION}\\b.+)$`, "i"),
  new RegExp(`\\b(?:would\\s+you\\s+like|want)\\s+me\\s+to\\s+(?<offer>${SINGLE_OFFER_ACTION}\\b.+)$`, "i"),
];
const GENERIC_SINGLE_OFFER =
  /\b(anything else|something else|more detail|more details|more context|additional context|more information|help further|help with this|this further|that further)\b/i;

export function extractSuggestedFollowUps(text: string): string[] {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (!normalized) return [];

  const tail = normalized.slice(-MAX_REGION_CHARS);
  const quotedQuery = lastQuotedFollowUpQuery(tail);
  const leadIndex = lastLeadInIndex(tail);
  if (quotedQuery && quotedQuery.index > leadIndex) return [quotedQuery.suggestion];
  if (leadIndex < 0) return quotedQuery ? [quotedQuery.suggestion] : [];

  return uniqueSuggestions(extractOptions(tail.slice(leadIndex)));
}

function lastLeadInIndex(text: string): number {
  LEAD_IN_GLOBAL.lastIndex = 0;
  let lastIndex = -1;
  let match: RegExpExecArray | null;

  while ((match = LEAD_IN_GLOBAL.exec(text)) !== null) {
    lastIndex = match.index;
  }

  return lastIndex;
}

function lastQuotedFollowUpQuery(text: string): { index: number; suggestion: string } | null {
  QUOTED_FOLLOW_UP_QUERY_GLOBAL.lastIndex = 0;
  let lastMatch: { index: number; suggestion: string } | null = null;
  let match: RegExpExecArray | null;

  while ((match = QUOTED_FOLLOW_UP_QUERY_GLOBAL.exec(text)) !== null) {
    const suggestion = cleanSuggestion(match.groups?.query ?? "");
    if (suggestion) {
      lastMatch = { index: match.index, suggestion };
    }
  }

  return lastMatch;
}

function extractOptions(region: string): string[] {
  const lines = region.split("\n").slice(0, 10);
  const hasMarkedList = lines.some((line) => LIST_MARKER.test(line));
  const suggestions: string[] = [];

  for (const line of lines) {
    const raw = line.trim();
    if (!raw) continue;

    if (LEAD_IN_LINE.test(raw)) {
      const inlineOptions = extractInlineOptions(raw);
      if (inlineOptions.length > 0) {
        suggestions.push(...inlineOptions);
      } else if (!hasMarkedList) {
        const singleOffer = extractSingleOffer(raw);
        if (singleOffer) suggestions.push(singleOffer);
      }
      continue;
    }

    if (hasMarkedList && !LIST_MARKER.test(raw)) continue;

    const suggestion = cleanSuggestion(raw);
    if (suggestion) suggestions.push(suggestion);
    if (suggestions.length >= MAX_SUGGESTIONS) break;
  }

  return suggestions.slice(0, MAX_SUGGESTIONS);
}

function extractInlineOptions(line: string): string[] {
  const separator = line.indexOf(":");
  if (separator < 0 || separator === line.length - 1) return [];

  return line
    .slice(separator + 1)
    .split(/;\s+|,\s+(?:or|and)\s+/i)
    .map(cleanSuggestion)
    .filter((suggestion): suggestion is string => !!suggestion);
}

function extractSingleOffer(line: string): string | null {
  const normalized = normalizeOfferText(line);

  for (const pattern of SINGLE_OFFER_PATTERNS) {
    const offer = pattern.exec(normalized)?.groups?.offer;
    if (!offer) continue;

    const suggestion = cleanSuggestion(toUserPrompt(offer));
    if (!suggestion || GENERIC_SINGLE_OFFER.test(suggestion)) return null;
    return suggestion;
  }

  return null;
}

function cleanSuggestion(raw: string): string | null {
  let text = normalizeOfferText(raw)
    .replace(LIST_MARKER, "")
    .replace(/^\[[ xX]\]\s+/, "")
    .trim();

  text = text
    .replace(/^(?:or|and)\s+/i, "")
    .replace(/(?:,?\s+(?:or|and))$/i, "")
    .replace(/[.;:]+$/g, "")
    .trim();

  if (!text) return null;
  if (LEAD_IN_LINE.test(text)) return null;
  if (text.length < 4 || text.length > MAX_SUGGESTION_CHARS) return null;

  return text;
}

function normalizeOfferText(text: string): string {
  return text
    .replace(/\*\*/g, "")
    .replace(/__/g, "")
    .replace(/^[`"']+|[`"']+$/g, "")
    .trim();
}

function toUserPrompt(offer: string): string {
  const prompt = offer
    .replace(/^give\s+you\b/i, "give me")
    .replace(/^show\s+you\b/i, "show me")
    .replace(/\s+for\s+you$/i, "")
    .trim();

  return prompt ? `${prompt.charAt(0).toUpperCase()}${prompt.slice(1)}` : prompt;
}

function uniqueSuggestions(suggestions: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];

  for (const suggestion of suggestions) {
    const key = suggestion.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(suggestion);
  }

  return unique;
}
