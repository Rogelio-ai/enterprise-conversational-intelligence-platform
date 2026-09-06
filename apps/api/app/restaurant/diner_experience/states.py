from __future__ import annotations

from app.restaurant.catalog.resolution_contracts import ResolutionStatus
from app.restaurant.checks import errors as check_errors
from app.restaurant.diner_experience.contracts import ExperienceGuidance, ExperienceState
from app.restaurant.orders import errors as order_errors


def ok(*allowed_actions: str, next_action: str | None = None) -> ExperienceGuidance:
    return ExperienceGuidance(
        ExperienceState.OK, 'OK', allowed_actions=tuple(allowed_actions), next_action=next_action
    )


def staff_assistance_required() -> ExperienceGuidance:
    return ExperienceGuidance(
        ExperienceState.STAFF_ASSISTANCE_REQUIRED,
        'STAFF_ASSISTANCE_REQUIRED',
        allowed_actions=('VIEW_OPERATIONAL_REQUEST',),
        next_action='WAIT_FOR_STAFF',
    )


def from_resolution(status: ResolutionStatus) -> ExperienceGuidance:
    if status is ResolutionStatus.AMBIGUOUS:
        return ExperienceGuidance(
            ExperienceState.CLARIFICATION_REQUIRED,
            'AMBIGUOUS_REFERENCE',
            required_input=('SELECTION',),
            allowed_actions=('SELECT_CANDIDATE',),
            next_action='SELECT_CANDIDATE',
        )
    if status in {ResolutionStatus.NOT_FOUND, ResolutionStatus.NOT_ORDERABLE}:
        return ExperienceGuidance(
            ExperienceState.PRODUCT_UNAVAILABLE,
            'PRODUCT_UNAVAILABLE',
            allowed_actions=('BROWSE_MENU',),
            next_action='BROWSE_MENU',
        )
    return ok()


def from_domain_condition(value: object) -> ExperienceGuidance:
    if isinstance(value, order_errors.ProductNotOrderableError):
        return from_resolution(ResolutionStatus.NOT_ORDERABLE)
    if isinstance(value, order_errors.InvalidDraftCompositionError):
        return ExperienceGuidance(
            ExperienceState.CONFIGURATION_REQUIRED,
            'CONFIGURATION_REQUIRED',
            required_input=('CHOICE_SELECTIONS',),
            allowed_actions=('CONFIGURE_PRODUCT',),
            next_action='CONFIGURE_PRODUCT',
        )
    if isinstance(value, check_errors.OrderingBlockedError):
        return ExperienceGuidance(
            ExperienceState.ACTION_BLOCKED,
            value.code,
            allowed_actions=('VIEW_CHECK', 'VIEW_PAYMENT_STATUS'),
            next_action='VIEW_CHECK',
        )
    if value == 'SERVICE_CONTINUATION_DECISION_REQUIRED':
        return ExperienceGuidance(
            ExperienceState.CONTINUATION_REQUIRED,
            'SERVICE_CONTINUATION_DECISION_REQUIRED',
            required_input=('YES_OR_NO',),
            allowed_actions=('SERVICE_CONTINUATION',),
            next_action='SERVICE_CONTINUATION',
        )
    if value == 'UNCERTAIN':
        return ExperienceGuidance(
            ExperienceState.PAYMENT_UNCERTAIN,
            'PAYMENT_UNCERTAIN',
            allowed_actions=('VIEW_PAYMENT_STATUS', 'REQUEST_HUMAN_ASSISTANCE'),
            next_action='WAIT_FOR_PAYMENT_RESOLUTION',
        )
    if value == 'SESSION_CLOSED':
        return ExperienceGuidance(
            ExperienceState.SESSION_CLOSED, 'SESSION_CLOSED', next_action='LEAVE_SESSION'
        )
    return ok()
