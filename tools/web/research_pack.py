"""Build citation-formatted research injection text."""

from .contracts import SourceDoc


def build_injected_text(sources: list[SourceDoc]) -> str:
    """
    Build citation-formatted injection text for LLM context with STRONG grounding instructions.

    Args:
        sources: List of SourceDoc objects

    Returns:
        Formatted injection text with hard grounding instructions
    """
    timestamp = sources[0].fetched_at if sources else "N/A"

    lines = [
        "=" * 80,
        "SYSTEM OVERRIDE - MANDATORY INSTRUCTIONS:",
        "=" * 80,
        "CortexAI performed web research and provided sources below.",
        "Do NOT claim lack of internet access / knowledge cutoff.",
        "If web research is provided, do NOT say you lack internet access. Explain limitations only if sources lack the answer.",
        "Use ONLY these sources; cite using format [1][2][3] with consecutive brackets and NO spaces or commas.",
        "IMPORTANT: Cite ALL sources that support each claim. If multiple sources confirm the same fact, cite all of them.",
        f"If not in sources, reply: Not found in the provided sources. | Timestamp: {timestamp}",
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
        "REMINDER: Answer using ONLY the information above. Cite sources as [1][2][3] (consecutive brackets)."
    )
    lines.append("=" * 80)

    return "\n".join(lines)
