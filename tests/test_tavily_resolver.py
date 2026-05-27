import pytest

from tools.web.tavily_resolver import (
    TAVILY_DEFAULT_CHUNKS_PER_SOURCE,
    TAVILY_DEFAULT_MAX_RESULTS,
    TAVILY_DEFAULT_SEARCH_DEPTH,
    TavilyResolverConfig,
    resolve_tavily_search_options,
)


ENABLED_CONFIG = TavilyResolverConfig(
    enhanced_search_enabled=True,
    chunks_per_source=TAVILY_DEFAULT_CHUNKS_PER_SOURCE,
    domain_rules_enabled=True,
)


def _assert_resolution(
    query: str,
    *,
    expected_category: str,
    expected_topic: str | None = None,
    expected_time_range: str | None = None,
    expected_country_detected: str | None = None,
    expected_country_sent: str | None = None,
    expected_domains: list[str] | None = None,
    expected_domain_rule: str | None = None,
    locale_context: str | None = None,
    config: TavilyResolverConfig = ENABLED_CONFIG,
) -> None:
    resolution = resolve_tavily_search_options(
        query,
        locale_context=locale_context,
        config=config,
        max_results=2,
        search_depth="basic",
    )
    params = resolution.params
    log_fields = resolution.log_fields
    expected_domains = expected_domains or []

    assert params["max_results"] == TAVILY_DEFAULT_MAX_RESULTS
    assert params["search_depth"] == TAVILY_DEFAULT_SEARCH_DEPTH
    assert params["chunks_per_source"] == TAVILY_DEFAULT_CHUNKS_PER_SOURCE
    assert params["include_raw_content"] is False
    assert params["include_answer"] is False
    assert params["auto_parameters"] is False

    if expected_topic:
        assert params["topic"] == expected_topic
    else:
        assert "topic" not in params

    if expected_time_range:
        assert params["time_range"] == expected_time_range
    else:
        assert "time_range" not in params

    if expected_country_sent:
        assert params["country"] == expected_country_sent
    else:
        assert "country" not in params

    if expected_domains:
        assert params["include_domains"] == expected_domains
    else:
        assert "include_domains" not in params

    assert log_fields["enhanced_search_enabled"] is config.enhanced_search_enabled
    assert log_fields["category"] == expected_category
    assert log_fields["topic_sent"] == expected_topic
    assert log_fields["time_range"] == expected_time_range
    assert log_fields["country_detected"] == expected_country_detected
    assert log_fields["country_sent"] == expected_country_sent
    assert log_fields["domain_rule"] == expected_domain_rule
    assert log_fields["include_domain_count"] == len(expected_domains)


@pytest.mark.parametrize(
    (
        "query",
        "expected_category",
        "expected_topic",
        "expected_time_range",
        "expected_country_detected",
        "expected_country_sent",
        "expected_domains",
        "expected_domain_rule",
    ),
    [
        (
            "latest Canada inflation rate",
            "finance",
            "finance",
            "week",
            "canada",
            None,
            ["bankofcanada.ca", "statcan.gc.ca"],
            "canada_economic",
        ),
        (
            "latest Israel Gaza ceasefire update",
            "news",
            "news",
            "week",
            None,
            None,
            [],
            None,
        ),
        (
            "Apple latest earnings SEC filing",
            "finance",
            "finance",
            "week",
            "united states",
            None,
            ["sec.gov"],
            "us_sec",
        ),
        ("what is Pythagorean theorem", "general", None, None, None, None, [], None),
        ("live score Arsenal vs Chelsea", "news", "news", "day", None, None, [], None),
        ("compare US and Canada inflation", "finance", "finance", "week", None, None, [], None),
        ("Fed rate decision latest news", "finance", "finance", "week", None, None, [], None),
        (
            "UK inflation this month",
            "finance",
            "finance",
            "month",
            "united kingdom",
            None,
            ["ons.gov.uk", "bankofengland.co.uk"],
            "uk_economic",
        ),
        ("breaking news Ukraine frontline", "news", "news", "day", None, None, [], None),
        (
            "US jobs report this week",
            "finance",
            "finance",
            "week",
            "united states",
            None,
            ["bls.gov", "bea.gov", "federalreserve.gov"],
            "us_economic",
        ),
        ("best workout routine for fat loss", "health", None, None, None, None, [], None),
        ("symptoms of vitamin D deficiency", "health", None, None, None, None, [], None),
        ("React 19 latest features", "coding", None, "week", None, None, [], None),
        ("Python asyncio bug fix today", "coding", None, "day", None, None, [], None),
        ("FastAPI vs Django which is faster", "coding", None, None, None, None, [], None),
        ("React stock price latest", "finance", "finance", "week", None, None, [], None),
        ("CVE-2024-1234 Python requests vuln", "coding", None, None, None, None, [], None),
        ("historical inflation trends since 1970", "finance", "finance", None, None, None, [], None),
        ("Q3 earnings season summary", "finance", "finance", "month", None, None, [], None),
        ("AI research this year", "general", None, "year", None, None, [], None),
    ],
)
def test_resolver_spec_scenarios(
    query,
    expected_category,
    expected_topic,
    expected_time_range,
    expected_country_detected,
    expected_country_sent,
    expected_domains,
    expected_domain_rule,
):
    _assert_resolution(
        query,
        expected_category=expected_category,
        expected_topic=expected_topic,
        expected_time_range=expected_time_range,
        expected_country_detected=expected_country_detected,
        expected_country_sent=expected_country_sent,
        expected_domains=expected_domains,
        expected_domain_rule=expected_domain_rule,
    )


def test_resolver_uses_locale_only_when_prompt_has_no_country():
    _assert_resolution(
        "inflation rate latest",
        locale_context="Canada",
        expected_category="finance",
        expected_topic="finance",
        expected_time_range="week",
        expected_country_detected="canada",
        expected_domains=["bankofcanada.ca", "statcan.gc.ca"],
        expected_domain_rule="canada_economic",
    )


def test_resolver_prompt_country_wins_over_conflicting_locale():
    _assert_resolution(
        "UK inflation this month",
        locale_context="en-CA",
        expected_category="finance",
        expected_topic="finance",
        expected_time_range="month",
        expected_country_detected="united kingdom",
        expected_domains=["ons.gov.uk", "bankofengland.co.uk"],
        expected_domain_rule="uk_economic",
    )


def test_resolver_omits_country_when_detection_is_inconclusive():
    _assert_resolution(
        "inflation latest",
        expected_category="finance",
        expected_topic="finance",
        expected_time_range="week",
    )


def test_resolver_omits_time_range_for_stable_finance_explanation():
    _assert_resolution(
        "what is inflation",
        expected_category="finance",
        expected_topic="finance",
    )


def test_resolver_omits_country_for_regional_prompt_even_with_locale():
    _assert_resolution(
        "EU inflation latest",
        locale_context="Canada",
        expected_category="finance",
        expected_topic="finance",
        expected_time_range="week",
    )


def test_resolver_sends_country_for_non_topic_health_prompts():
    _assert_resolution(
        "latest COVID outbreak update",
        locale_context="US",
        expected_category="health",
        expected_time_range="week",
        expected_country_detected="united states",
        expected_country_sent="united states",
    )


def test_resolver_kill_switch_omits_enhanced_options():
    disabled = TavilyResolverConfig(
        enhanced_search_enabled=False,
        chunks_per_source=2,
        domain_rules_enabled=True,
    )
    resolution = resolve_tavily_search_options(
        "latest Canada inflation rate",
        locale_context="Canada",
        config=disabled,
    )

    assert resolution.params == {
        "max_results": TAVILY_DEFAULT_MAX_RESULTS,
        "search_depth": TAVILY_DEFAULT_SEARCH_DEPTH,
        "chunks_per_source": 2,
        "include_raw_content": False,
        "include_answer": False,
        "auto_parameters": False,
    }
    assert resolution.log_fields == {
        "enhanced_search_enabled": False,
        "chunks_per_source": 2,
        "category": "general",
        "topic_sent": None,
        "time_range": None,
        "country_detected": None,
        "country_sent": None,
        "domain_rule": None,
        "include_domain_count": 0,
    }


def test_resolver_domain_rules_can_be_disabled():
    config = TavilyResolverConfig(
        enhanced_search_enabled=True,
        chunks_per_source=3,
        domain_rules_enabled=False,
    )
    _assert_resolution(
        "US jobs report this week",
        config=config,
        expected_category="finance",
        expected_topic="finance",
        expected_time_range="week",
        expected_country_detected="united states",
    )


def test_resolver_clamps_invalid_config_chunk_count_to_default():
    config = TavilyResolverConfig(
        enhanced_search_enabled=True,
        chunks_per_source=99,
        domain_rules_enabled=True,
    )
    resolution = resolve_tavily_search_options("what is Pythagorean theorem", config=config)
    assert resolution.params["chunks_per_source"] == TAVILY_DEFAULT_CHUNKS_PER_SOURCE
    assert resolution.log_fields["chunks_per_source"] == TAVILY_DEFAULT_CHUNKS_PER_SOURCE
