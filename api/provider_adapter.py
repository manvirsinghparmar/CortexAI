from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from api.base_client import BaseAIClient


class ProviderAdapter(Protocol):
    """Provider adapter interface used by the client registry."""

    provider_id: str
    api_key_env: str
    default_model_env: str
    default_model: str

    def create_client(self, *, api_key: str, model_name: str) -> BaseAIClient:
        """Create a provider client instance."""


@dataclass(frozen=True)
class RegistryProviderAdapter:
    """Concrete adapter implementation backed by a simple factory callable."""

    provider_id: str
    api_key_env: str
    default_model_env: str
    default_model: str
    client_factory: Callable[[str, str], BaseAIClient]

    def create_client(self, *, api_key: str, model_name: str) -> BaseAIClient:
        return self.client_factory(api_key, model_name)
