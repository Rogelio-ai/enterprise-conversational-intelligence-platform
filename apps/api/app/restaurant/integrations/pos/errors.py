from __future__ import annotations

from enum import StrEnum


class PosErrorKind(StrEnum):
    INVALID_DATA = 'INVALID_DATA'
    MAPPING = 'MAPPING'
    NOT_FOUND = 'NOT_FOUND'
    UNSUPPORTED_CAPABILITY = 'UNSUPPORTED_CAPABILITY'
    TEMPORARY_FAILURE = 'TEMPORARY_FAILURE'
    REJECTED = 'REJECTED'
    UNCERTAIN_RESULT = 'UNCERTAIN_RESULT'


class PosIntegrationError(Exception):
    """Safe, vendor-neutral failure returned by a POS adapter."""

    kind: PosErrorKind

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        connector_key: str,
        correlation_id: str,
        external_entity_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.connector_key = connector_key
        self.correlation_id = correlation_id
        self.external_entity_type = external_entity_type


class PosInvalidDataError(PosIntegrationError):
    kind = PosErrorKind.INVALID_DATA


class PosMappingError(PosIntegrationError):
    kind = PosErrorKind.MAPPING


class PosNotFoundError(PosIntegrationError):
    kind = PosErrorKind.NOT_FOUND


class PosUnsupportedCapabilityError(PosIntegrationError):
    kind = PosErrorKind.UNSUPPORTED_CAPABILITY


class PosTemporaryFailureError(PosIntegrationError):
    kind = PosErrorKind.TEMPORARY_FAILURE


class PosRejectedError(PosIntegrationError):
    kind = PosErrorKind.REJECTED


class PosUncertainResultError(PosIntegrationError):
    kind = PosErrorKind.UNCERTAIN_RESULT
