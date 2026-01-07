"""
MultiUnifiedResponse - Aggregation container for parallel model comparisons.

Immutable dataclass that wraps multiple UnifiedResponse objects from
concurrent API calls to different providers/models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from typing import Tuple
import uuid

from models.unified_response import UnifiedResponse


@dataclass(frozen=True)
class MultiUnifiedResponse:
    """
    Immutable container for multiple UnifiedResponse objects.
    
    Used by MultiModelOrchestrator to return results from parallel
    API calls to multiple providers/models.
    
    Attributes:
        request_group_id: Unique UUID for this comparison group
        created_at: UTC timestamp when the comparison was initiated
        responses: Tuple of UnifiedResponse objects (order matches input clients)
    """
    request_group_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    responses: Tuple[UnifiedResponse, ...] = field(default_factory=tuple)

    @property
    def total_cost(self) -> float:
        """Sum of estimated_cost for all successful responses."""
        return sum(
            r.estimated_cost for r in self.responses
            if r.is_success and r.estimated_cost is not None
        )

    @property
    def total_tokens(self) -> int:
        """Sum of total_tokens for all successful responses."""
        return sum(
            r.token_usage.total_tokens for r in self.responses
            if r.is_success and r.token_usage is not None
        )

    @property
    def success_count(self) -> int:
        """Number of successful responses."""
        return sum(1 for r in self.responses if r.is_success)

    @property
    def error_count(self) -> int:
        """Number of error responses."""
        return sum(1 for r in self.responses if r.is_error)

    def __len__(self) -> int:
        """Number of responses in this group."""
        return len(self.responses)
