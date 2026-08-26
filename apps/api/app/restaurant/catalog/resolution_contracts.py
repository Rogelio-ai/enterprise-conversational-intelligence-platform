from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResolutionStatus(StrEnum):
    RESOLVED = 'RESOLVED'
    AMBIGUOUS = 'AMBIGUOUS'
    NOT_FOUND = 'NOT_FOUND'
    NOT_ORDERABLE = 'NOT_ORDERABLE'
    INVALID_CONTEXT = 'INVALID_CONTEXT'


class MatchSource(StrEnum):
    CANONICAL_NAME = 'CANONICAL_NAME'
    ALIAS = 'ALIAS'


@dataclass(frozen=True, slots=True)
class ProductResolutionRequest:
    tenant_id: int
    organization_id: int
    location_id: int | None
    reference_text: str
    language: str | None = None


@dataclass(frozen=True, slots=True)
class ProductResolutionCandidate:
    product_id: int
    display_name: str
    matched_by: MatchSource


@dataclass(frozen=True, slots=True)
class ProductResolutionResult:
    status: ResolutionStatus
    candidate: ProductResolutionCandidate | None = None
    candidates: tuple[ProductResolutionCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class ChoiceResolutionRequest:
    tenant_id: int
    organization_id: int
    parent_product_id: int
    choice_reference_text: str
    language: str | None = None
    choice_group_id: int | None = None


@dataclass(frozen=True, slots=True)
class ChoiceResolutionCandidate:
    choice_group_id: int
    choice_option_id: int
    option_product_id: int
    display_name: str
    matched_by: MatchSource


@dataclass(frozen=True, slots=True)
class ChoiceResolutionResult:
    status: ResolutionStatus
    candidate: ChoiceResolutionCandidate | None = None
    candidates: tuple[ChoiceResolutionCandidate, ...] = ()
