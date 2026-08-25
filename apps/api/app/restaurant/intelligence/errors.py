from __future__ import annotations

from enum import StrEnum


class IntelligenceErrorKind(StrEnum):
    UNDERSTANDING_UNAVAILABLE = 'UNDERSTANDING_UNAVAILABLE'
    INVALID_UNDERSTANDING_RESULT = 'INVALID_UNDERSTANDING_RESULT'
    UNSUPPORTED_INPUT = 'UNSUPPORTED_INPUT'
    KNOWLEDGE_NOT_FOUND = 'KNOWLEDGE_NOT_FOUND'
    KNOWLEDGE_UNAVAILABLE = 'KNOWLEDGE_UNAVAILABLE'


class RestaurantIntelligenceError(Exception):
    kind: IntelligenceErrorKind

    def __init__(self, message: str, *, correlation_id: str | None = None) -> None:
        super().__init__(message)
        self.correlation_id = correlation_id


class UnderstandingUnavailableError(RestaurantIntelligenceError):
    kind = IntelligenceErrorKind.UNDERSTANDING_UNAVAILABLE


class InvalidUnderstandingResultError(RestaurantIntelligenceError):
    kind = IntelligenceErrorKind.INVALID_UNDERSTANDING_RESULT


class UnsupportedUnderstandingInputError(RestaurantIntelligenceError):
    kind = IntelligenceErrorKind.UNSUPPORTED_INPUT


class KnowledgeNotFoundError(RestaurantIntelligenceError):
    kind = IntelligenceErrorKind.KNOWLEDGE_NOT_FOUND


class KnowledgeUnavailableError(RestaurantIntelligenceError):
    kind = IntelligenceErrorKind.KNOWLEDGE_UNAVAILABLE
