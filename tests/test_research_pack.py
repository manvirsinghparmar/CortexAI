from tools.web.contracts import SourceDoc
from tools.web.research_pack import build_injected_text


def _source(*, fetched_at: str = "2026-03-13T00:00:00+00:00") -> SourceDoc:
    return SourceDoc(
        id=1,
        title="Example Source",
        url="https://example.com/source",
        fetched_at=fetched_at,
        excerpt="Example excerpt.",
    )


def test_research_pack_removes_canned_not_found_fallback_line():
    text = build_injected_text([_source()])

    assert "Not found in the provided sources." not in text
    assert "Timestamp: N/A" not in text
    assert "best sourced summary first" in text
    assert "suggest one focused follow-up query" in text


def test_research_pack_never_emits_na_timestamp_line():
    text = build_injected_text([_source(fetched_at="N/A")])

    assert "Research retrieved at (UTC): " in text
    assert "Research retrieved at (UTC): N/A" not in text


def test_research_pack_does_not_force_source_only_answers():
    text = build_injected_text([_source()])

    assert "SYSTEM OVERRIDE - MANDATORY INSTRUCTIONS" not in text
    assert "Answer using only the information above" not in text
    assert "primary evidence for current or source-dependent factual claims" in text
    assert "You may use model knowledge for stable background context" in text
