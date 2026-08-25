from __future__ import annotations

from dataclasses import dataclass, field

from app.restaurant.intelligence.contracts import (
    RestaurantUnderstandingRequest,
    RestaurantUnderstandingResult,
)
from app.restaurant.intelligence.errors import RestaurantIntelligenceError


@dataclass
class DeterministicRestaurantUnderstandingFake:
    """Deterministic test double; never a production understanding provider."""

    result: RestaurantUnderstandingResult | None = None
    failure: RestaurantIntelligenceError | None = None
    requests: list[RestaurantUnderstandingRequest] = field(default_factory=list, init=False)

    async def understand(
        self, request: RestaurantUnderstandingRequest
    ) -> RestaurantUnderstandingResult:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        if self.result is None:
            raise RuntimeError('Deterministic fake requires a result or configured failure')
        return self.result
