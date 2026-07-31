from tools.web.cache import InMemoryTTLCache
from tools.web.contracts import ProviderSearchResponse, SourceDoc
from tools.web.tavily_service import TavilyResearchService


class _FakeUsageClient:
    def __init__(self, response: ProviderSearchResponse):
        self.response = response
        self.calls = 0

    def get_network_diagnostics_snapshot(self):
        return {}

    def search_with_usage(self, **_kwargs):
        self.calls += 1
        return self.response


def _service(response: ProviderSearchResponse) -> TavilyResearchService:
    service = object.__new__(TavilyResearchService)
    service.client = _FakeUsageClient(response)
    service.cache = InMemoryTTLCache(ttl_seconds=60)
    service.max_sources = 5
    return service


def test_research_context_carries_provider_usage():
    service = _service(
        ProviderSearchResponse(
            sources=[
                SourceDoc(
                    id=1,
                    title="Doc",
                    url="https://example.com/doc",
                    fetched_at="2026-07-31T00:00:00+00:00",
                    excerpt="Evidence",
                )
            ],
            provider_credits_used=3,
            provider_credits_estimated=False,
        )
    )

    context = service.build("latest docs")

    assert context.used is True
    assert context.provider_credits_used == 3
    assert context.provider_credits_estimated is False


def test_cached_research_has_zero_provider_usage_for_the_reused_turn():
    service = _service(
        ProviderSearchResponse(
            sources=[
                SourceDoc(
                    id=1,
                    title="Doc",
                    url="https://example.com/doc",
                    fetched_at="2026-07-31T00:00:00+00:00",
                    excerpt="Evidence",
                )
            ],
            provider_credits_used=2,
        )
    )

    first = service.build("latest docs")
    cached = service.build("latest docs")

    assert first.provider_credits_used == 2
    assert cached.cache_hit is True
    assert cached.provider_credits_used == 0
    assert service.client.calls == 1


def test_empty_provider_response_preserves_billable_usage():
    service = _service(
        ProviderSearchResponse(
            sources=[],
            provider_credits_used=2,
            provider_credits_estimated=True,
        )
    )

    context = service.build("latest docs")

    assert context.used is False
    assert context.error == "no_search_results"
    assert context.provider_credits_used == 2
    assert context.provider_credits_estimated is True
