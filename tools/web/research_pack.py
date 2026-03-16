"""Build citation-formatted research injection text."""

from datetime import datetime, timezone

from .contracts import SourceDoc


def _resolve_pack_timestamp(sources: list[SourceDoc]) -> str:
    """
    Resolve a stable retrieval timestamp for prompt injection metadata.

    Falls back to server UTC time if source timestamps are missing.
    """
    for source in sources:
        fetched_at = str(getattr(source, "fetched_at", "") or "").strip()
        if fetched_at and fetched_at.upper() != "N/A":
            return fetched_at
    return datetime.now(timezone.utc).isoformat()


def build_injected_text(sources: list[SourceDoc]) -> str:
    """
    Build citation-formatted injection text for LLM context.

    Args:
        sources: List of SourceDoc objects

    Returns:
        Formatted injection text with grounding instructions
    """
    timestamp = _resolve_pack_timestamp(sources)

    lines = [
        "=" * 80,
        "SYSTEM OVERRIDE - MANDATORY INSTRUCTIONS:",
        "=" * 80,
        "CortexAI performed web research and provided sources below.",
        "Do NOT claim lack of internet access or knowledge cutoff.",
        "Use ONLY these sources for factual claims from this turn.",
        "Cite using format [1][2][3] with consecutive brackets and no commas.",
        "If multiple sources support the same fact, cite all supporting sources.",
        "If the sources are partial, provide the best sourced summary first.",
        "If an exact detail is missing, clearly state what is missing and suggest one focused follow-up query.",
        f"Research retrieved at (UTC): {timestamp}",
        "",
        "=" * 80,
        "WEB RESEARCH SOURCES:",
        "=" * 80,
        "",
    ]

    for source in sources:
        lines.append(f"[{source.id}] {source.title}")
        lines.append(f"URL: {source.url}")
        lines.append("")
        lines.append(source.excerpt)
        lines.append("")
        lines.append("-" * 80)
        lines.append("")

    lines.append("=" * 80)
    lines.append(
        "REMINDER: Answer using only the information above and cite sources as [1][2][3]."
    )
    lines.append("=" * 80)

    return "\n".join(lines)
