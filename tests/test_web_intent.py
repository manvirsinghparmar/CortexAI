from tools.web.intent import sanitize_query, should_reuse_research
from tools.web.research_state import ResearchSource, ResearchState


def _research_state(
    *,
    query: str = "iran israel war latest updates",
    topic: str = "iran israel war",
) -> ResearchState:
    now = "2026-03-02T00:00:00+00:00"
    return ResearchState(
        topic=topic,
        query=query,
        injected_text="WEB RESEARCH SOURCES:\n1) source",
        sources=[
            ResearchSource(
                id=1,
                title="Source",
                url="https://example.com/source",
                fetched_at=now,
                excerpt="excerpt",
            )
        ],
        created_at=now,
        last_used_at=now,
        used=True,
        cache_hit=False,
        error=None,
        session_id="session-detail-followup",
        mode="auto",
        ttl_seconds=900,
    )


def test_sanitize_query_anchors_context_dependent_detail_followup_to_previous_query():
    state = _research_state()
    query = sanitize_query(
        "can be a bit more detailed on it",
        state,
        last_user_message="who is war between iran and israel is going on",
    )
    assert query == "iran israel war latest updates in-depth details"


def test_should_reuse_research_for_context_dependent_detail_followup_in_auto_mode():
    state = _research_state()
    assert should_reuse_research(
        "can you be a bit more detailed on it",
        state,
        current_mode="auto",
    ) is True


def test_sanitize_query_keeps_explicit_topic_when_followup_has_concrete_subject():
    state = _research_state()
    prompt = "go into more detail about iran and israel missile exchanges"
    query = sanitize_query(prompt, state, last_user_message="old context")
    assert query == prompt


def test_sanitize_query_anchors_bollywood_followup_movie_list_to_previous_topic():
    query = sanitize_query(
        (
            "List the top-grossing or most popular films of the 1990s, specifying "
            "the criteria used for ranking."
        ),
        None,
        last_user_message="how has bollywood transitioned over the years in term of movies",
    )

    assert query.startswith("bollywood List the top-grossing")
