"""Decision logic for when to skip/reuse/search research."""

from .research_state import Decision, ResearchMode, ResearchState


def decide_research(
    prompt: str,
    mode: ResearchMode,
    *,
    state: ResearchState | None,
    is_meta_followup: bool,
    is_same_topic_followup: bool,
    needs_web: bool,
    topic_key: str,
    is_explicit_web_request: bool,
) -> tuple[Decision, str]:
    """
    Determine whether to skip, reuse, or perform new research.

    Args:
        prompt: User prompt
        mode: Research mode ("off", "auto", "on")
        state: Current ResearchState (may be None)
        is_meta_followup: True if meta follow-up ("do you have internet", etc.)
        is_same_topic_followup: True if same-topic follow-up ("but", "what about", etc.)
        needs_web: True if should_use_web returned True (for auto mode)
        topic_key: Computed topic key for current prompt
        is_explicit_web_request: True if user explicitly requests web search

    Returns:
        Tuple of (Decision, reason_string)

    Decision rules:
    - mode=="off": always skip
    - Check reuse conditions first (state exists, same topic, not expired, AND follow-up)
    - Explicit web requests always trigger search
    - mode=="on": always search (unless reused above)
    - mode=="auto": search if needs_web (unless reused above)
    """
    # Rule 1: If mode is off, never research
    if mode == "off":
        return ("skip", "mode_off")

    # Rule 2: Check reuse conditions (ONLY if follow-up AND valid state exists)
    if state and state.used and state.topic_key == topic_key and not state.is_expired():
        if is_meta_followup or is_same_topic_followup:
            followup_type = "meta" if is_meta_followup else "same_topic"
            return ("reuse", f"reuse_last_context_{followup_type}")

    # Rule 3: Explicit web requests always trigger search
    if is_explicit_web_request:
        return ("search", "explicit_web_request")

    # Rule 4: Mode is "on" - always search
    if mode == "on":
        return ("search", "mode_on")

    # Rule 5: Mode is "auto" - search only if needs_web
    if mode == "auto":
        if not needs_web:
            return ("skip", "auto_no_need")
        else:
            return ("search", "auto_need_web")

    # Fallback (should never reach here)
    return ("skip", "unknown_mode")
