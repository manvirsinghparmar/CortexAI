"""Intent detection for determining when to use web research."""


def is_followup_meta(prompt: str) -> bool:
    """
    Detect if prompt is a meta follow-up that should reuse previous research.

    Meta follow-ups are phrases like "can you check", "are you sure", etc.
    that don't contain new information but ask to verify/recheck.

    Args:
        prompt: User prompt to check

    Returns:
        True if this is a meta follow-up
    """
    prompt_lower = prompt.lower().strip()

    # Meta follow-up phrases (exact or partial matches)
    meta_phrases = [
        "check on your own",
        "can you check",
        "can u check",
        "verify",
        "are you sure",
        "check again",
        "double check",
        "confirm",
        "recheck",
        "look it up",
        "search for it",
        "find out",
        "check that",
        "why did you check",
        "why did you search",
        "why did u check",
        "why did u search",
        "dont you have internet",
        "don't you have internet",
        "do you have internet",
        "internet access",
        "how did you check",
        "how did u check",
        "why are you not able",
        "why u r not able",
        "why can't you fetch",
        "why cant you fetch",
    ]

    for phrase in meta_phrases:
        if phrase in prompt_lower:
            return True

    return False


def is_same_topic_followup(prompt: str) -> bool:
    """
    Detect if prompt is a same-topic follow-up that should reuse research.

    Args:
        prompt: User prompt to check

    Returns:
        True if this is a same-topic follow-up
    """
    prompt_lower = prompt.lower().strip()

    # Follow-up starters indicating continuation of current topic
    followup_starters = [
        "why ",
        "how ",
        "but ",
        "what about",
        "then ",
        "so ",
        "also ",
        "and ",
        "i meant",
        "i mean",
    ]

    for starter in followup_starters:
        if prompt_lower.startswith(starter):
            return True

    return False


def is_explicit_web_request(prompt: str) -> bool:
    """
    Detect if user explicitly requests web/internet search.

    Args:
        prompt: User prompt to check

    Returns:
        True if prompt explicitly asks for web search
    """
    prompt_lower = prompt.lower().strip()

    # Explicit web/internet search requests (with negation variants)
    web_keywords = [
        "check internet",
        "search internet",
        "check on internet",
        "check over internet",
        "search on internet",
        "search over internet",
        "check the internet",
        "search the internet",
        "can't you check",
        "can't u check",
        "cant you check",
        "cant u check",
        "can you check",
        "can u check",
        "can you search",
        "can u search",  # Added: explicit search requests
        "could you search",
        "could u search",  # Added
        "browse internet",
        "browse the internet",
        "browse web",
        "look it up",
        "look this up",
        "look that up",
        "search for it",
        "search for this",
        "search online",
        "search using",
        "search with",  # Added: "search using different providers"
        "check online",
        "look online",
        "find online",
        "do a search",
        "do a fresh search",
        "fresh search",
        "do it now",
        "do it",
        "go ahead and",
        "please do",  # Execute previous promise
        "retrieve the",
        "get the",
        "fetch the",  # "retrieve the relevant information"
    ]

    # Time-sensitive keywords that imply need for current data
    time_keywords = [
        "find latest",
        "latest",
        "latest development",
        "latest news",
        "today",
        "current",
        "news",
        "update",
        "updates",
        "real-time",
        "live",
        "as of",
        "right now",
        "recent",
        "recent development",
        "recent news",
        "fresh",
        "new development",
        "last year",
        "this year",
        "last month",
        "this month",  # Relative time
        "last quarter",
        "this quarter",
        "year to date",
        "ytd",
    ]

    # Requests for MORE/ADDITIONAL sources (not just reuse)
    more_sources_keywords = [
        "more sources",
        "more information",
        "more info",
        "additional sources",
        "other sources",
        "different sources",
        "find more",
        "check more",
        "search more",
        "look for more",
        "get more",
    ]

    # Check for more sources request FIRST (takes precedence)
    for keyword in more_sources_keywords:
        if keyword in prompt_lower:
            return True

    # Check web keywords
    for keyword in web_keywords:
        if keyword in prompt_lower:
            return True

    # Check time keywords
    for keyword in time_keywords:
        if keyword in prompt_lower:
            return True

    return False


def wants_more_sources(prompt: str) -> bool:
    """
    Detect if user wants MORE/FRESH sources on THE SAME TOPIC (not a new query).

    This should ONLY match when user explicitly asks to:
    - Re-search the same topic for more sources
    - Get additional/different sources
    - Do a fresh/new search

    This should NOT match when user asks a new question that happens to contain
    freshness keywords like "latest" or "recent" as part of the actual query.

    Args:
        prompt: User prompt to check

    Returns:
        True if user explicitly wants to re-search for more sources
    """
    prompt_lower = prompt.lower().strip()

    # Explicit "more sources" requests (very specific)
    more_indicators = [
        "more sources",
        "more information",
        "more info",
        "additional sources",
        "other sources",
        "different sources",
        "find more sources",
        "get more sources",
        "check more sources",
        "look for more sources",
        "expand sources",
        "broader sources",
        "some more sources",
        "few more sources",
    ]

    # Explicit re-search commands (asking to search AGAIN, not first time)
    search_commands = [
        "do a search",
        "do a fresh search",
        "do another search",
        "search again",
        "check again for",
        "look again for",
        "find updated",
        "get updated",
        "refresh the",
        "update the",
        "new search",
        "fresh search",
        "another search",
    ]

    # Check explicit indicators
    all_indicators = more_indicators + search_commands

    for indicator in all_indicators:
        if indicator in prompt_lower:
            return True

    return False


def rewrite_query(prompt: str) -> str:
    """
    Rewrite finance queries to get better search results.

    For queries about stock indices with "today" + "gain/change",
    rewrite to explicitly search for "percent change today".

    Args:
        prompt: Original user prompt

    Returns:
        Rewritten query (or original if no rewrite needed)
    """
    prompt_lower = prompt.lower()

    # Finance index keywords
    finance_keywords = [
        "s&p",
        "sp 500",
        "s&p 500",
        "spx",
        "nasdaq",
        "dow",
        "djia",
        "dow jones",
        "index",
        "stock",
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
    ]

    # Time indicators
    time_keywords = ["today", "current", "latest", "now", "right now"]

    # Change indicators
    change_keywords = ["gain", "up", "down", "change", "%", "percent", "loss"]

    # Check if all conditions met
    has_finance = any(kw in prompt_lower for kw in finance_keywords)
    has_time = any(kw in prompt_lower for kw in time_keywords)
    has_change = any(kw in prompt_lower for kw in change_keywords)

    if has_finance and has_time and has_change:
        # Extract the main symbol/index
        if "s&p" in prompt_lower or "sp 500" in prompt_lower or "spx" in prompt_lower:
            return "S&P 500 percent change today live quote"
        elif "nasdaq" in prompt_lower:
            return "NASDAQ percent change today live quote"
        elif "dow" in prompt_lower or "djia" in prompt_lower:
            return "Dow Jones percent change today live quote"
        elif "bitcoin" in prompt_lower or "btc" in prompt_lower:
            return "Bitcoin price percent change today"
        elif "ethereum" in prompt_lower or "eth" in prompt_lower:
            return "Ethereum price percent change today"

    return prompt


def should_use_web(prompt: str, research_mode: str) -> tuple[bool, str]:
    """
    Determine if web research should be used based on mode and prompt content.

    Args:
        prompt: User prompt to analyze
        research_mode: One of "off" or "on"

    Returns:
        Tuple of (should_use: bool, reason: str)
    """
    if research_mode == "off":
        return False, "mode_off"

    # Check if this is a meta follow-up (should reuse previous research)
    if is_followup_meta(prompt):
        return True, "followup_reuse_last"

    # Check if this is a same-topic follow-up (should reuse previous research)
    if is_same_topic_followup(prompt) and research_mode != "off":
        return True, "followup_same_topic_reuse_last"

    if research_mode == "on":
        return True, "mode_on"

    # Default: no search
    return False, "mode_off"


def is_meta_followup(prompt: str) -> bool:
    """
    Detect if prompt is a meta follow-up that should NEVER trigger a new web search.

    Meta follow-ups are verification/confirmation requests that should reuse existing research.

    Args:
        prompt: User prompt to check

    Returns:
        True if this is a meta follow-up
    """
    prompt_lower = prompt.lower().strip()

    meta_phrases = [
        "check once more",
        "check again",
        "are you sure",
        "verify",
        "which source",
        "what source",
        "why did you search",
        "why did you check",
        "do you have internet",
        "internet access",
        "did you invent",
        "did you make that up",
        "confirm again",
    ]

    for phrase in meta_phrases:
        if phrase in prompt_lower:
            return True

    return False


def is_short_year_followup(prompt: str) -> str | None:
    """
    Detect if prompt is a short year follow-up like "and in 2025" or "in 2025".

    These should be anchored to the previous topic, not searched literally.

    Args:
        prompt: User prompt to check

    Returns:
        Year string if detected (e.g., "2025"), None otherwise
    """
    import re

    prompt_lower = prompt.lower().strip()

    # Patterns for short year follow-ups
    patterns = [
        r"^and in (\d{4})$",
        r"^in (\d{4})$",
        r"^what about (\d{4})$",
        r"^and (\d{4})$",
        r"^for (\d{4})$",
    ]

    for pattern in patterns:
        match = re.match(pattern, prompt_lower)
        if match:
            return match.group(1)

    return None


def build_anchored_query(state, prompt: str) -> str:
    """
    Build an anchored query for follow-ups to avoid searching literal meta text.

    Args:
        state: ResearchState object
        prompt: User prompt

    Returns:
        Anchored query string (never returns meta text as query)
    """
    # Import here to avoid circular dependency
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        pass

    # Check if this is a short year follow-up
    year = is_short_year_followup(prompt)
    if year and hasattr(state, "query") and state.query:
        return f"{state.query} {year}"

    # Check if this is a meta follow-up
    if is_meta_followup(prompt):
        # Never search using meta text - reuse last search query
        if hasattr(state, "query") and state.query:
            return state.query

    # Default: return prompt as-is
    return prompt


def normalize_topic(text: str) -> str:
    """
    Normalize text to extract canonical topic.

    Args:
        text: Input text (prompt or query)

    Returns:
        Normalized topic string
    """
    # Lowercase and strip
    normalized = text.lower().strip()

    # Remove filler phrases
    filler_phrases = [
        "can you",
        "could you",
        "please",
        "i want to know",
        "tell me about",
        "what is",
        "what are",
        "how is",
        "how are",
        "check",
        "verify",
        "are you sure",
        "confirm",
        "latest on",
    ]

    for phrase in filler_phrases:
        normalized = normalized.replace(phrase, "")

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized


def should_reuse_research(prompt: str, research_state: object | None) -> bool:
    """
    Determine if existing research should be reused.

    Args:
        prompt: User prompt
        research_state: Optional ResearchState object

    Returns:
        True if research should be reused, False if new search needed
    """
    if not research_state:
        return False

    if not hasattr(research_state, "used") or not research_state.used:
        return False

    prompt_lower = prompt.lower().strip()

    # EXCEPTION 1: If user explicitly requests web search, NEVER reuse - always do fresh search
    if is_explicit_web_request(prompt):
        return False

    # EXCEPTION 2: If user wants MORE/FRESH sources, don't reuse - do new search
    if wants_more_sources(prompt):
        return False

    # Meta clarification questions should reuse (don't search literally)
    if is_meta_clarification(prompt):
        return True

    # Meta follow-ups always reuse (but only if NOT explicit web request)
    meta_phrases = [
        "check again",
        "are you sure",
        "verify",
        "check once more",
        "confirm",
        "double check",
        "which source",
        "what source",
        "why did you search",
        "do you have internet",
    ]

    for phrase in meta_phrases:
        if phrase in prompt_lower:
            return True

    # Check topic match using word overlap
    if hasattr(research_state, "topic") and research_state.topic:
        prompt_topic = normalize_topic(prompt)
        state_topic = normalize_topic(research_state.topic)

        # Word overlap check - if prompts share significant words, likely same topic
        prompt_words = set(prompt_topic.split())
        state_words = set(state_topic.split())

        # Remove very common words that don't indicate topic similarity
        common_words = {"is", "are", "was", "were", "the", "a", "an", "of", "to", "for", "in", "on"}
        prompt_words = {w for w in prompt_words if w not in common_words and len(w) > 2}
        state_words = {w for w in state_words if w not in common_words and len(w) > 2}

        # Calculate overlap
        if prompt_words and state_words:
            overlap = len(prompt_words & state_words)
            min_words = min(len(prompt_words), len(state_words))

            # If > 20% overlap, consider same topic (lowered for better recall)
            if overlap > 0 and (overlap / min_words) >= 0.2:
                return True

        # Fallback: simple containment check
        if prompt_topic in state_topic or state_topic in prompt_topic:
            return True

    return False


def should_search(prompt: str, research_mode: str, research_state: object | None = None) -> bool:
    """
    Simple decision logic for whether to perform new search.

    Decision order:
    1. If research_mode == off → NO search
    2. If research_state exists AND should_reuse == True → NO search
    3. If explicit web request ("check internet", "search web") → search
    4. If research_mode == on → search
    5. Else → NO search

    Args:
        prompt: User prompt
        research_mode: Research mode ("off" or "on")
        research_state: Optional existing ResearchState

    Returns:
        True if new search should be performed, False otherwise
    """
    # Rule 1: Mode off - never search
    if research_mode == "off":
        return False

    # Rule 2: Reuse existing research if available
    if should_reuse_research(prompt, research_state):
        return False

    # Rule 3: Check for explicit web request (in any mode except off)
    if is_explicit_web_request(prompt):
        return True

    # Rule 4: Mode on - always search
    if research_mode == "on":
        return True

    # Rule 5: Default - no search
    return False


# Stop-word queries that should NEVER be sent to search
# These are meta-commands without actual search intent
STOP_WORD_QUERIES = [
    "check once more",
    "verify",
    "are you sure",
    "confirm",
    "double check",
    "which source",
    "what source",
    "why did you search",
    "do you have internet",
    "internet access",
    "recheck",
    "did u check",
    "did you check",
    # Meta clarification questions (asking AI to correct itself)
    "was that",
    "is that",
    "was it",
    "is it",  # "was that 2020 or 2025?"
    "or is it",
    "or was it",
]

# Note: Removed "go ahead", "please do", "can't u check", "can't you check"
# because these are now recognized as explicit web requests in certain contexts


def is_meta_clarification(prompt: str) -> bool:
    """
    Detect if prompt is a meta clarification question (asking AI to correct itself).

    Examples:
    - "was last year 2020 or 2025?"
    - "is that right?"
    - "was it X or Y?"

    These should NOT be searched literally.

    Args:
        prompt: User prompt to check

    Returns:
        True if this is a meta clarification question
    """
    prompt_lower = prompt.lower().strip()

    # Pattern: "was/is [something] X or Y?"
    clarification_patterns = [
        "was that",
        "is that",
        "was it",
        "is it",
        "or is it",
        "or was it",
        "or 2025",  # "was it 2020 or 2025?"
        "or 2026",
        " or ",  # Generic OR question pattern
    ]

    # Questions asking about years/dates
    year_clarification = ["what year", "which year", "what is the year", "what's the year"]

    # Check clarification patterns
    for pattern in clarification_patterns:
        if pattern in prompt_lower:
            # If contains "or" AND is short (< 15 words), likely clarification
            words = prompt_lower.split()
            if "or" in words and len(words) < 15:
                return True

    # Check year clarification
    for pattern in year_clarification:
        if pattern in prompt_lower:
            return True

    return False


# Note: Removed phrases like "check again", "check more", "latest on this"
# because they might be part of valid requests like "check for latest"


def sanitize_query(
    prompt: str, research_state: object | None = None, last_user_message: str | None = None
) -> str:
    """
    Sanitize query to prevent garbage search queries.

    If prompt is mostly stop-words or meta-commands, use research_state.query instead.
    EXCEPTION: If user wants "more sources", return previous query for re-search.

    Args:
        prompt: User prompt (potentially garbage)
        research_state: Optional existing ResearchState
        last_user_message: Optional last user message from conversation (for context)

    Returns:
        Sanitized query string (never returns garbage)
    """
    prompt_lower = prompt.lower().strip()

    # SPECIAL CASE: User wants more sources on same topic
    if wants_more_sources(prompt):
        # Return previous query to search again (get more/different sources)
        if research_state and hasattr(research_state, "query") and research_state.query:
            return research_state.query
        # No previous query - can't get "more" of nothing
        return ""

    # SPECIAL CASE: Meta clarification question (don't search literally)
    if is_meta_clarification(prompt):
        # Return empty - these should NOT be searched
        return ""

    # Check if prompt is a stop-word query (exact or partial match)
    for stop_phrase in STOP_WORD_QUERIES:
        if stop_phrase in prompt_lower:
            # Use previous query if available
            if research_state and hasattr(research_state, "query") and research_state.query:
                return research_state.query
            # Otherwise return empty (caller should handle)
            return ""

    # SPECIAL CASE: Explicit web request - check if it's pure meta or has actual content
    if is_explicit_web_request(prompt):
        # Detect pure meta-commands like "check over internet", "search again", etc.
        # These have no actual query content after removing meta-words
        pure_meta_patterns = [
            r"^(?:can|could|would|will|do|please)?\s*(?:you|u|ye)?\s*(?:please|pls)?\s*(?:check|search|look|find|get|fetch|retrieve)\s+(?:again|over|on|using|with|via|the|a|an)?\s*(?:internet|web|online|again)\s*$",
            r"^(?:check|search|look)\s+(?:again|over|on|the)?\s*(?:internet|web|online)?\s*$",
        ]

        import re

        is_pure_meta = any(
            re.match(pattern, prompt_lower, re.IGNORECASE) for pattern in pure_meta_patterns
        )

        if is_pure_meta:
            # Pure meta-command with no actual content - use previous user message
            if last_user_message and len(last_user_message.strip()) > 5:
                return last_user_message.strip()
            if research_state and hasattr(research_state, "query") and research_state.query:
                return research_state.query
            return ""

        # Try to extract the actual query after meta-command phrases
        extraction_patterns = [
            r"(?:can|could|would|will)?\s*(?:you|u|ye)\s*(?:please|pls)?\s*(?:check|search|look|find|get|fetch|retrieve)\s+(?:for|on|about|up)?\s*(.+)",
            r"(?:do|perform)?\s*(?:a|an)?\s*(?:web|internet|online)?\s*(?:search|check|lookup)\s+(?:for|on|about)?\s*(.+)",
        ]

        for pattern in extraction_patterns:
            match = re.search(pattern, prompt_lower, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()

                # Filter out system meta-phrases
                system_meta_phrases = [
                    "using different provider",
                    "different provider",
                    "another provider",
                    "other provider",
                    "different source",
                ]

                is_system_meta = any(phrase in extracted for phrase in system_meta_phrases)
                if is_system_meta:
                    if last_user_message and len(last_user_message.strip()) > 5:
                        return last_user_message.strip()
                    if research_state and hasattr(research_state, "query") and research_state.query:
                        return research_state.query
                    return ""

                # Validate if extracted text has meaningful content
                noise_words = {
                    "again",
                    "over",
                    "on",
                    "the",
                    "internet",
                    "web",
                    "online",
                    "using",
                    "with",
                    "it",
                }
                extracted_words = extracted.split()
                meaningful_words = [w for w in extracted_words if w not in noise_words]

                # If less than 2 meaningful words, it's meta-noise
                if len(meaningful_words) < 2:
                    if last_user_message and len(last_user_message.strip()) > 5:
                        return last_user_message.strip()
                    if research_state and hasattr(research_state, "query") and research_state.query:
                        return research_state.query
                    return ""

                # Has meaningful content after meta-command
                return extracted

        # If extraction failed but it's an explicit request with previous context, reuse
        if last_user_message and len(last_user_message.strip()) > 5:
            return last_user_message.strip()
        if research_state and hasattr(research_state, "query") and research_state.query:
            return research_state.query

    # Check if prompt is mostly stop words or meta-commands
    words = prompt_lower.split()
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "can",
        "may",
        "might",
        "must",
        "shall",
        "you",
        "your",
        "it",
        "u",
        "pls",
        "plz",
        "please",
    }

    # Meta-command words that don't constitute a real query
    meta_words = {
        "check",
        "verify",
        "search",
        "look",
        "find",
        "confirm",
        "recheck",
        "internet",
        "online",
        "web",
        "up",
        "again",
        "once",
        "over",
        "on",
        "the",
        "this",
        "that",
        "it",
        "now",
        "go",
        "ahead",
    }

    # Filter out stop words
    meaningful_words = [w for w in words if w not in stop_words]

    # Check if remaining words are all meta-commands
    non_meta_words = [w for w in meaningful_words if w not in meta_words]

    # If < 2 non-meta words, this is likely a meta-command, not a real query
    if len(non_meta_words) < 2:
        # Use previous query if available
        if research_state and hasattr(research_state, "query") and research_state.query:
            return research_state.query
        # Otherwise return empty (caller should handle)
        return ""

    # Return original prompt
    return prompt
