import pytest

from tools.web.tavily_client import TavilyResearchClient


class _FakeRawClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self._response

    def qna_search(self, **_kwargs):
        return self._response


def _make_client(response) -> TavilyResearchClient:
    client = object.__new__(TavilyResearchClient)
    client.client = _FakeRawClient(response)
    return client


@pytest.fixture(autouse=True)
def _stable_tavily_resolver_env(monkeypatch):
    monkeypatch.setenv("TAVILY_ENHANCED_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TAVILY_CHUNKS_PER_SOURCE", "3")
    monkeypatch.setenv("TAVILY_ENHANCED_SEARCH_DOMAIN_RULES", "true")


def test_search_uses_server_utc_fallback_when_provider_timestamp_missing(monkeypatch):
    fallback_timestamp = "2026-03-13T10:00:00+00:00"
    monkeypatch.setattr(
        TavilyResearchClient,
        "_utc_now_iso",
        staticmethod(lambda: fallback_timestamp),
    )

    client = _make_client(
        {
            "query_time": 0.42,  # duration, not a timestamp
            "results": [
                {"title": "Doc", "url": "https://example.com/doc", "content": "snippet", "score": 0.8}
            ],
        }
    )

    sources = client.search("latest docs")
    assert len(sources) == 1
    assert sources[0].fetched_at == fallback_timestamp


def test_search_prefers_result_level_published_timestamp_over_fallback(monkeypatch):
    monkeypatch.setattr(
        TavilyResearchClient,
        "_utc_now_iso",
        staticmethod(lambda: "2026-03-13T10:00:00+00:00"),
    )

    client = _make_client(
        {
            "query_time": 0.24,
            "results": [
                {
                    "title": "Doc",
                    "url": "https://example.com/doc",
                    "content": "snippet",
                    "published_date": "2026-03-12T15:30:00Z",
                }
            ],
        }
    )

    sources = client.search("latest docs")
    assert len(sources) == 1
    assert sources[0].fetched_at == "2026-03-12T15:30:00+00:00"


def test_error_classifier_detects_dns_resolution_failures():
    exc = RuntimeError("Temporary failure in name resolution while calling Tavily")
    kind = TavilyResearchClient._classify_error_kind(exc)
    assert kind == "dns_resolution_failed"


def test_error_classifier_detects_auth_forbidden():
    exc = RuntimeError("403 Forbidden from Tavily API")
    kind = TavilyResearchClient._classify_error_kind(exc)
    assert kind == "auth_forbidden"


def test_search_passes_enhanced_resolver_options_to_tavily():
    client = _make_client({"results": []})

    client.search("latest Canada inflation rate", max_results=1, search_depth="basic")

    call = client.client.calls[0]
    assert call["query"] == "latest Canada inflation rate"
    assert call["max_results"] == 5
    assert call["search_depth"] == "advanced"
    assert call["chunks_per_source"] == 3
    assert call["include_raw_content"] is False
    assert call["include_answer"] is False
    assert call["auto_parameters"] is False
    assert call["topic"] == "finance"
    assert call["time_range"] == "week"
    assert call["include_domains"] == ["bankofcanada.ca", "statcan.gc.ca"]
    assert "country" not in call


def test_search_kill_switch_passes_only_fixed_tavily_options(monkeypatch):
    monkeypatch.setenv("TAVILY_ENHANCED_SEARCH_ENABLED", "false")
    client = _make_client({"results": []})

    client.search("latest Canada inflation rate")

    call = client.client.calls[0]
    assert call == {
        "query": "latest Canada inflation rate",
        "max_results": 5,
        "search_depth": "advanced",
        "chunks_per_source": 3,
        "include_raw_content": False,
        "include_answer": False,
        "auto_parameters": False,
    }


def test_search_invalid_chunk_env_uses_default(monkeypatch):
    monkeypatch.setenv("TAVILY_CHUNKS_PER_SOURCE", "9")
    client = _make_client({"results": []})

    client.search("what is Pythagorean theorem")

    call = client.client.calls[0]
    assert call["chunks_per_source"] == 3


def test_search_with_usage_returns_provider_reported_credits():
    client = _make_client(
        {
            "usage": {"credits": 3},
            "results": [
                {
                    "title": "Doc",
                    "url": "https://example.com/doc",
                    "content": "snippet",
                }
            ],
        }
    )

    result = client.search_with_usage("latest docs")

    assert len(result.sources) == 1
    assert result.provider_credits_used == 3
    assert result.provider_credits_estimated is False


def test_search_with_usage_marks_default_when_provider_omits_usage():
    client = _make_client({"results": []})

    result = client.search_with_usage("latest docs")

    assert result.sources == []
    assert result.provider_credits_used == 2
    assert result.provider_credits_estimated is True


def test_search_with_usage_preserves_explicit_zero_provider_credits():
    client = _make_client({"usage": {"credits": 0}, "results": []})

    result = client.search_with_usage("latest docs")

    assert result.provider_credits_used == 0
    assert result.provider_credits_estimated is False


def test_search_with_usage_returns_empty_contract_when_provider_fails(monkeypatch):
    client = _make_client({"results": []})

    def _fail_search(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(client.client, "search", _fail_search)

    result = client.search_with_usage("latest docs")

    assert result.sources == []
    assert result.provider_credits_used == 0
    assert result.provider_credits_estimated is False
