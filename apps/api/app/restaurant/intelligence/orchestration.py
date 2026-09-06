from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.restaurant.catalog.resolution import resolve_choice, resolve_product
from app.restaurant.catalog.resolution_contracts import (
    ChoiceResolutionRequest,
    ProductResolutionRequest,
    ResolutionStatus,
)
from app.restaurant.checks import errors as check_errors
from app.restaurant.checks import service as check_service
from app.restaurant.commercial import service as commercial_service
from app.restaurant.diner_experience import service as experience_service
from app.restaurant.diner_experience import states
from app.restaurant.diner_experience.contracts import (
    ExperienceGuidance,
    ExperienceState,
    OperationalRequestInvalidError,
    ProductUnavailableError,
)
from app.restaurant.intelligence.contracts import RestaurantIntentCode
from app.restaurant.orders import acceptance
from app.restaurant.orders import acceptance_errors
from app.restaurant.orders import errors as draft_errors
from app.restaurant.orders import service as draft_service
from app.restaurant.payments import errors as payment_errors
from app.restaurant.payments import service as payment_service


DraftOperation = Literal['ADD', 'CONFIGURE', 'MODIFY', 'REMOVE']
CheckScope = Literal['INDIVIDUAL', 'GLOBAL_TABLE', 'SELECTED']


@dataclass(frozen=True, slots=True)
class DinerOrchestrationContext:
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    service_session_id: int
    diner_session_id: int
    conversation_id: int
    correlation_id: str | None


@dataclass(frozen=True, slots=True)
class ConversationActionCommand:
    intent_code: RestaurantIntentCode
    idempotency_key: str
    operation: DraftOperation | None = None
    reference_text: str | None = None
    product_id: int | None = None
    quantity: Decimal | None = None
    draft_item_id: int | None = None
    choice_group_id: int | None = None
    choice_reference_text: str | None = None
    option_ids: tuple[int, ...] = ()
    expected_draft_version: int | None = None
    expected_commercial_fingerprint: str | None = None
    check_id: int | None = None
    check_scope: CheckScope | None = None
    selected_diner_session_ids: tuple[int, ...] = ()
    payment_method: str | None = None
    continuation_decision: str | None = None
    expected_check_version: int | None = None
    language: str | None = None


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    intent_code: RestaurantIntentCode
    experience: ExperienceGuidance
    authoritative_data: object | None = None
    replayed: bool = False


def _clarification(
    code: str,
    *,
    required_input: tuple[str, ...],
    allowed_actions: tuple[str, ...],
    data: object | None = None,
) -> OrchestrationResult:
    return OrchestrationResult(
        RestaurantIntentCode.UNKNOWN,
        ExperienceGuidance(
            ExperienceState.CLARIFICATION_REQUIRED,
            code,
            required_input=required_input,
            allowed_actions=allowed_actions,
            next_action=allowed_actions[0] if allowed_actions else None,
        ),
        data,
    )


def _result(
    intent: RestaurantIntentCode,
    guidance: ExperienceGuidance,
    data: object | None = None,
    *,
    replayed: bool = False,
) -> OrchestrationResult:
    return OrchestrationResult(intent, guidance, data, replayed)


def _blocked(intent: RestaurantIntentCode, code: str) -> OrchestrationResult:
    return _result(
        intent,
        ExperienceGuidance(
            ExperienceState.ACTION_BLOCKED,
            code,
            allowed_actions=('REQUEST_ASSISTANCE',),
            next_action='REQUEST_ASSISTANCE',
        ),
    )


def _owner(context: DinerOrchestrationContext) -> dict[str, int]:
    return {
        'owner_diner_session_id': context.diner_session_id,
        'owned_conversation_id': context.conversation_id,
    }


def _execution(context: DinerOrchestrationContext) -> ExecutionContext:
    return ExecutionContext(
        ActorType.DINER,
        context.tenant_id,
        context.diner_session_id,
        None,
        context.correlation_id,
    )


async def _resolved_product(
    db: AsyncSession,
    context: DinerOrchestrationContext,
    command: ConversationActionCommand,
) -> tuple[int | None, OrchestrationResult | None]:
    if command.product_id is not None:
        try:
            await experience_service.get_product_detail(
                db,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                location_id=context.location_id,
                product_id=command.product_id,
            )
        except ProductUnavailableError:
            return None, _result(
                command.intent_code,
                states.from_resolution(ResolutionStatus.NOT_ORDERABLE),
            )
        return command.product_id, None
    if not command.reference_text:
        return None, _clarification(
            'PRODUCT_REFERENCE_REQUIRED',
            required_input=('PRODUCT_REFERENCE',),
            allowed_actions=('SHOW_PRODUCT',),
        )
    resolved = await resolve_product(
        db,
        ProductResolutionRequest(
            tenant_id=context.tenant_id,
            organization_id=context.organization_id,
            location_id=context.location_id,
            reference_text=command.reference_text,
            language=command.language,
        ),
    )
    if resolved.status is not ResolutionStatus.RESOLVED:
        return None, _result(
            command.intent_code,
            states.from_resolution(resolved.status),
            {'candidates': resolved.candidates},
        )
    return resolved.candidate.product_id, None


def _draft_guidance(draft) -> ExperienceGuidance:
    if str(draft.readiness) in {'INCOMPLETE', 'INVALID'}:
        return ExperienceGuidance(
            ExperienceState.CONFIGURATION_REQUIRED,
            'CONFIGURATION_REQUIRED',
            required_input=('CHOICE_SELECTIONS',),
            allowed_actions=('CONFIGURE_ITEM', 'REVIEW_DRAFT'),
            next_action='CONFIGURE_ITEM',
        )
    return states.ok('REVIEW_DRAFT', 'CONFIRM_ORDER', next_action='REVIEW_DRAFT')


async def _draft(
    db: AsyncSession, context: DinerOrchestrationContext, *, create: bool
):
    function = draft_service.get_or_create_draft if create else draft_service.get_draft_for_conversation
    return await function(
        db,
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        correlation_id=context.correlation_id,
        **_owner(context),
    )


async def _order_expression(
    db: AsyncSession,
    context: DinerOrchestrationContext,
    command: ConversationActionCommand,
) -> OrchestrationResult:
    operation = command.operation or 'ADD'
    if command.expected_draft_version is None:
        try:
            current = await _draft(db, context, create=True)
        except Exception:
            current = None
        return _clarification(
            'EXPECTED_DRAFT_VERSION_REQUIRED',
            required_input=('EXPECTED_DRAFT_VERSION',),
            allowed_actions=(f'{operation}_ITEM',),
            data=current,
        )
    if operation == 'ADD':
        product_id, unresolved = await _resolved_product(db, context, command)
        if unresolved is not None:
            return unresolved
        if command.quantity is None:
            return _clarification(
                'QUANTITY_REQUIRED',
                required_input=('QUANTITY',),
                allowed_actions=('ADD_ITEM',),
            )
        draft = await _draft(db, context, create=True)
        value = await draft_service.add_item(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft.draft_id,
            product_id=product_id,
            quantity=command.quantity,
            expected_version=command.expected_draft_version,
            correlation_id=context.correlation_id,
            **_owner(context),
        )
        return _result(command.intent_code, _draft_guidance(value), value)
    draft = await _draft(db, context, create=False)
    if command.draft_item_id is None:
        return _clarification(
            'DRAFT_ITEM_REQUIRED',
            required_input=('DRAFT_ITEM_ID',),
            allowed_actions=(f'{operation}_ITEM',),
            data=draft,
        )
    if operation == 'CONFIGURE':
        if command.choice_group_id is None:
            return _clarification(
                'CHOICE_GROUP_REQUIRED',
                required_input=('CHOICE_GROUP_ID',),
                allowed_actions=('CONFIGURE_ITEM',),
                data=draft,
            )
        option_ids = command.option_ids
        if not option_ids and command.choice_reference_text:
            item = next(
                (value for value in draft.items if value.item_id == command.draft_item_id),
                None,
            )
            if item is None:
                return _blocked(command.intent_code, 'DRAFT_ITEM_NOT_FOUND')
            resolved = await resolve_choice(
                db,
                ChoiceResolutionRequest(
                    tenant_id=context.tenant_id,
                    organization_id=context.organization_id,
                    parent_product_id=item.product_id,
                    choice_reference_text=command.choice_reference_text,
                    language=command.language,
                    choice_group_id=command.choice_group_id,
                ),
            )
            if resolved.status is not ResolutionStatus.RESOLVED:
                return _result(
                    command.intent_code,
                    states.from_resolution(resolved.status),
                    {'candidates': resolved.candidates, 'draft': draft},
                )
            option_ids = (resolved.candidate.choice_option_id,)
        if not option_ids:
            return _clarification(
                'CHOICE_SELECTION_REQUIRED',
                required_input=('CHOICE_REFERENCE_OR_OPTION_IDS',),
                allowed_actions=('CONFIGURE_ITEM',),
                data=draft,
            )
        value = await draft_service.replace_group_selections(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft.draft_id,
            item_id=command.draft_item_id,
            group_id=command.choice_group_id,
            option_ids=option_ids,
            expected_version=command.expected_draft_version,
            correlation_id=context.correlation_id,
            **_owner(context),
        )
    elif operation == 'MODIFY':
        if command.quantity is None:
            return _clarification(
                'QUANTITY_REQUIRED',
                required_input=('QUANTITY',),
                allowed_actions=('MODIFY_ITEM',),
                data=draft,
            )
        value = await draft_service.set_item_quantity(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft.draft_id,
            item_id=command.draft_item_id,
            quantity=command.quantity,
            expected_version=command.expected_draft_version,
            correlation_id=context.correlation_id,
            **_owner(context),
        )
    elif operation == 'REMOVE':
        value = await draft_service.remove_item(
            db,
            tenant_id=context.tenant_id,
            draft_id=draft.draft_id,
            item_id=command.draft_item_id,
            expected_version=command.expected_draft_version,
            correlation_id=context.correlation_id,
            **_owner(context),
        )
    else:
        return _blocked(command.intent_code, 'UNSUPPORTED_ORDER_OPERATION')
    return _result(command.intent_code, _draft_guidance(value), value)


async def _create_check(
    db: AsyncSession,
    context: DinerOrchestrationContext,
    command: ConversationActionCommand,
) -> OrchestrationResult:
    if command.check_scope is None:
        return _clarification(
            'PAYMENT_SCOPE_REQUIRED',
            required_input=('CHECK_SCOPE',),
            allowed_actions=('INDIVIDUAL', 'GLOBAL_TABLE', 'SELECTED'),
            data={'supported_scopes': ('INDIVIDUAL', 'GLOBAL_TABLE', 'SELECTED')},
        )
    execution = _execution(context)
    if command.check_scope == 'INDIVIDUAL':
        value, replayed = await check_service.create_individual_check(
            db,
            context=execution,
            diner_session_id=context.diner_session_id,
            idempotency_key=command.idempotency_key,
        )
    elif command.check_scope == 'GLOBAL_TABLE':
        value, replayed = await check_service.create_global_table_check(
            db,
            context=execution,
            service_session_id=context.service_session_id,
            controller_diner_session_id=context.diner_session_id,
            idempotency_key=command.idempotency_key,
        )
    else:
        selected = command.selected_diner_session_ids
        if not selected or context.diner_session_id not in selected:
            return _clarification(
                'SELECTED_DINERS_REQUIRED',
                required_input=('DINER_SESSION_IDS',),
                allowed_actions=('SELECT_DINERS',),
            )
        value, replayed = await check_service.create_check(
            db,
            context=execution,
            diner_ids=selected,
            controller_diner_session_id=context.diner_session_id,
            idempotency_key=command.idempotency_key,
        )
    return _result(
        command.intent_code,
        states.ok('INITIATE_PAYMENT', 'PAYMENT_STATUS', next_action='INITIATE_PAYMENT'),
        value,
        replayed=replayed,
    )


async def _handoff(
    db: AsyncSession,
    context: DinerOrchestrationContext,
    command: ConversationActionCommand,
    request_type: str,
) -> OrchestrationResult:
    value, replayed = await experience_service.create_operational_request(
        db,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        location_id=context.location_id,
        resource_id=context.resource_id,
        service_session_id=context.service_session_id,
        diner_session_id=context.diner_session_id,
        request_type=request_type,
        related_restaurant_check_id=command.check_id,
        idempotency_key=command.idempotency_key,
        correlation_id=context.correlation_id,
    )
    return _result(
        command.intent_code,
        states.staff_assistance_required(),
        value,
        replayed=replayed,
    )


async def orchestrate_action(
    db: AsyncSession,
    *,
    context: DinerOrchestrationContext,
    command: ConversationActionCommand,
) -> OrchestrationResult:
    intent = command.intent_code
    try:
        if intent is RestaurantIntentCode.MENU_QUERY:
            value = await experience_service.get_menu(
                db,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                location_id=context.location_id,
            )
            return _result(intent, states.ok('SHOW_PRODUCT', 'ADD_ITEM'), value)
        if intent in {
            RestaurantIntentCode.PRODUCT_QUERY,
            RestaurantIntentCode.PRICE_QUERY,
            RestaurantIntentCode.PROMOTION_QUERY,
        }:
            product_id, unresolved = await _resolved_product(db, context, command)
            if unresolved is not None:
                return unresolved
            value = await experience_service.get_product_detail(
                db,
                tenant_id=context.tenant_id,
                organization_id=context.organization_id,
                location_id=context.location_id,
                product_id=product_id,
            )
            next_action = 'CONFIGURE_ITEM' if value.product.configuration_required else 'ADD_ITEM'
            return _result(
                intent,
                states.ok('ADD_ITEM', 'SHOW_MENU', next_action=next_action),
                value,
            )
        if intent is RestaurantIntentCode.ORDER_EXPRESSION:
            return await _order_expression(db, context, command)
        if intent is RestaurantIntentCode.DRAFT_REVIEW:
            draft = await _draft(db, context, create=False)
            if str(draft.readiness) != 'READY':
                return _result(intent, _draft_guidance(draft), draft)
            preview = await commercial_service.resolve_checkout_preview(
                db,
                tenant_id=context.tenant_id,
                draft_id=draft.draft_id,
                correlation_id=context.correlation_id,
                **_owner(context),
            )
            return _result(
                intent,
                states.ok('CONFIRM_ORDER', 'MODIFY_ITEM', next_action='CONFIRM_ORDER'),
                preview,
            )
        if intent is RestaurantIntentCode.ORDER_CONFIRMATION:
            if command.expected_draft_version is None or not command.expected_commercial_fingerprint:
                return _clarification(
                    'CONFIRMATION_EVIDENCE_REQUIRED',
                    required_input=('EXPECTED_DRAFT_VERSION', 'COMMERCIAL_FINGERPRINT'),
                    allowed_actions=('REVIEW_DRAFT',),
                )
            value = await acceptance.confirm_current_order(
                db,
                tenant_id=context.tenant_id,
                diner_session_id=context.diner_session_id,
                conversation_id=context.conversation_id,
                expected_draft_version=command.expected_draft_version,
                expected_commercial_fingerprint=command.expected_commercial_fingerprint,
                idempotency_key=command.idempotency_key,
                correlation_id=context.correlation_id,
            )
            return _result(
                intent,
                states.ok('VIEW_ORDER', 'VIEW_ACCOUNT', next_action='VIEW_ORDER'),
                value.order,
                replayed=value.replayed,
            )
        if intent is RestaurantIntentCode.ORDER_STATUS_QUERY:
            value = await acceptance.list_diner_orders(
                db,
                tenant_id=context.tenant_id,
                diner_session_id=context.diner_session_id,
            )
            return _result(intent, states.ok('VIEW_ACCOUNT', 'ADD_ITEM'), value)
        if intent is RestaurantIntentCode.ACCOUNT_QUERY:
            value = await experience_service.get_account_preview(
                db,
                tenant_id=context.tenant_id,
                location_id=context.location_id,
                diner_session_id=context.diner_session_id,
            )
            return _result(intent, states.ok('REQUEST_PAYMENT', 'VIEW_ORDER'), value)
        if intent is RestaurantIntentCode.PAYMENT_REQUEST:
            if command.payment_method == 'CASH':
                if command.check_id is None:
                    return _clarification(
                        'RESTAURANT_CHECK_REQUIRED',
                        required_input=('CHECK_ID',),
                        allowed_actions=('REQUEST_PAYMENT',),
                    )
                return await _handoff(db, context, command, 'CASH_PAYMENT_ASSISTANCE')
            if command.check_id is not None:
                value = await payment_service.get_check_settlement(
                    db,
                    tenant_id=context.tenant_id,
                    check_id=command.check_id,
                    owner_diner_session_id=context.diner_session_id,
                )
                return _result(
                    intent,
                    states.ok('INITIATE_PAYMENT', 'PAYMENT_STATUS'),
                    value,
                )
            return await _create_check(db, context, command)
        if intent is RestaurantIntentCode.PAYMENT_STATUS_QUERY:
            if command.check_id is None:
                return _clarification(
                    'RESTAURANT_CHECK_REQUIRED',
                    required_input=('CHECK_ID',),
                    allowed_actions=('PAYMENT_STATUS',),
                )
            value = await payment_service.get_check_settlement(
                db,
                tenant_id=context.tenant_id,
                check_id=command.check_id,
                owner_diner_session_id=context.diner_session_id,
            )
            guidance = (
                states.from_domain_condition('UNCERTAIN')
                if value.uncertain_exposure > 0
                else states.ok('VIEW_ACCOUNT', 'SERVICE_CONTINUATION')
            )
            return _result(intent, guidance, value)
        if intent is RestaurantIntentCode.INVOICE_REQUEST:
            if command.check_id is None:
                return _clarification(
                    'RESTAURANT_CHECK_REQUIRED',
                    required_input=('CHECK_ID',),
                    allowed_actions=('REQUEST_INVOICE',),
                )
            return await _handoff(db, context, command, 'INVOICE_ASSISTANCE')
        if intent is RestaurantIntentCode.PAID_PRINT_REQUEST:
            if command.check_id is None:
                return _clarification(
                    'RESTAURANT_CHECK_REQUIRED',
                    required_input=('CHECK_ID',),
                    allowed_actions=('REQUEST_PAID_PRINT',),
                )
            return await _handoff(db, context, command, 'PAID_CHECK_PRINT')
        if intent is RestaurantIntentCode.HUMAN_ASSISTANCE_REQUEST:
            return await _handoff(db, context, command, 'HUMAN_ASSISTANCE')
        if intent is RestaurantIntentCode.SERVICE_CONTINUATION:
            if command.check_id is None:
                return _clarification(
                    'RESTAURANT_CHECK_REQUIRED',
                    required_input=('CHECK_ID',),
                    allowed_actions=('SERVICE_CONTINUATION',),
                )
            if command.continuation_decision is None:
                value = await check_service.get_check(
                    db,
                    tenant_id=context.tenant_id,
                    check_id=command.check_id,
                    owner_diner_session_id=context.diner_session_id,
                )
                guidance = (
                    states.from_domain_condition(value.signal)
                    if value.signal
                    else states.ok('VIEW_ACCOUNT')
                )
                return _result(intent, guidance, value)
            if command.expected_check_version is None:
                return _clarification(
                    'EXPECTED_CHECK_VERSION_REQUIRED',
                    required_input=('EXPECTED_CHECK_VERSION',),
                    allowed_actions=('SERVICE_CONTINUATION',),
                )
            value, replayed = await check_service.decide_continuation(
                db,
                context=_execution(context),
                check_id=command.check_id,
                expected_version=command.expected_check_version,
                decision=command.continuation_decision,
                idempotency_key=command.idempotency_key,
            )
            return _result(intent, states.ok('ADD_ITEM', 'END_SESSION'), value, replayed=replayed)
        return _clarification(
            'UNSUPPORTED_INTENT',
            required_input=('SUPPORTED_ACTION',),
            allowed_actions=('SHOW_MENU', 'REQUEST_ASSISTANCE'),
        )
    except ProductUnavailableError:
        return _result(intent, states.from_resolution(ResolutionStatus.NOT_ORDERABLE))
    except draft_errors.InvalidDraftCompositionError:
        return _result(intent, states.from_domain_condition(draft_errors.InvalidDraftCompositionError()))
    except draft_errors.ProductNotOrderableError:
        return _result(intent, states.from_domain_condition(draft_errors.ProductNotOrderableError()))
    except check_errors.OrderingBlockedError as exc:
        return _result(intent, states.from_domain_condition(exc))
    except OperationalRequestInvalidError:
        return _blocked(intent, 'OPERATIONAL_REQUEST_INVALID')
    except (
        draft_errors.DraftNotFoundError,
        draft_errors.DraftItemNotFoundError,
        draft_errors.InvalidDraftQuantityError,
        draft_errors.InvalidDraftSelectionError,
        draft_errors.DraftContextError,
        draft_errors.DraftNotMutableError,
        draft_errors.DraftConcurrencyConflictError,
        acceptance_errors.DraftNotConfirmableError,
        acceptance_errors.ConfirmationStaleError,
        acceptance_errors.OrderAlreadyConfirmedError,
        acceptance_errors.ConfirmationConflictError,
        check_errors.RestaurantCheckError,
        payment_errors.RestaurantPaymentError,
        ValueError,
    ) as exc:
        return _blocked(intent, getattr(exc, 'code', type(exc).__name__.upper()))
