"""Canonical Restaurant catalog services."""

from app.restaurant.catalog.service import resolve_external_product

__all__ = ['resolve_external_product']
from app.restaurant.catalog.resolution import normalize_alias, normalize_reference, resolve_choice, resolve_product
from app.restaurant.catalog.resolution_contracts import (
    ChoiceResolutionCandidate,
    ChoiceResolutionRequest,
    ChoiceResolutionResult,
    MatchSource,
    ProductResolutionCandidate,
    ProductResolutionRequest,
    ProductResolutionResult,
    ResolutionStatus,
)

__all__ = [
    'ChoiceResolutionCandidate',
    'ChoiceResolutionRequest',
    'ChoiceResolutionResult',
    'MatchSource',
    'ProductResolutionCandidate',
    'ProductResolutionRequest',
    'ProductResolutionResult',
    'ResolutionStatus',
    'normalize_alias',
    'normalize_reference',
    'resolve_choice',
    'resolve_product',
]
