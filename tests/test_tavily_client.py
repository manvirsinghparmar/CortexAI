from tools.web.tavily_client import TavilyResearchClient


class _FakeRawClient:
    def __init__(self, response):
        self._response = response

    def search(self, **_kwargs):
        return self._response

    def qna_search(self, **_kwargs):
        return self._response


def _make_client(response) -> TavilyResearchClient:
    client = object.__new__(TavilyResearchClient)
    client.client = _FakeRawClient(response)
    return client


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
