import pytest
from fastapi import HTTPException

from server import persistence as persistence_service


def test_resolve_api_key_for_request_rejects_empty_api_key():
    with pytest.raises(HTTPException) as exc:
        persistence_service.resolve_api_key_for_request(
            api_key="",
            request_id="req-empty-api-key",
        )

    assert exc.value.status_code == 401
    assert "Invalid or missing credentials" in str(exc.value.detail)


def test_resolve_api_key_for_request_rejects_none_api_key():
    with pytest.raises(HTTPException) as exc:
        persistence_service.resolve_api_key_for_request(  # type: ignore[arg-type]
            api_key=None,
            request_id="req-none-api-key",
        )

    assert exc.value.status_code == 401
    assert "Invalid or missing credentials" in str(exc.value.detail)
