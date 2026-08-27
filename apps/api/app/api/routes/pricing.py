from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer, field_validator, model_validator
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedContext, get_db, require_permission
from app.core.middleware import get_correlation_id
from app.models import Location, Organization, Product, ProductPrice, Promotion, PromotionLocation, PromotionProduct
from app.restaurant.pricing import service as pricing_service

router = APIRouter(tags=['pricing', 'promotions'])
logger = logging.getLogger('ecip.pricing')
Lifecycle = Literal['ACTIVE', 'INACTIVE']
Source = Literal['PLATFORM', 'POS']
PromotionType = Literal['PERCENTAGE_DISCOUNT', 'FIXED_AMOUNT_DISCOUNT']
MAX_MONEY = Decimal('999999999999999.9999')


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError('Binary floating-point values are not valid exact numbers')
    return value


Money = Annotated[Decimal, BeforeValidator(_reject_float), Field(ge=0, allow_inf_nan=False)]
PositiveMoney = Annotated[Decimal, BeforeValidator(_reject_float), Field(gt=0, allow_inf_nan=False)]


def _validate_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value.as_tuple().exponent < -4:
        raise ValueError('At most four fractional digits are allowed')
    if value > MAX_MONEY:
        raise ValueError('Value exceeds DECIMAL(19,4)')
    return value


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().upper()
    if len(value) != 3 or not value.isascii() or not value.isalpha():
        raise ValueError('Currency must be a three-letter ASCII code')
    return value


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Datetime must be timezone-aware')
    return value.astimezone(UTC).replace(tzinfo=None)


class PriceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    amount: Money
    currency: str

    _amount = field_validator('amount')(_validate_decimal)
    _currency = field_validator('currency', mode='before')(_currency)


class PricePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount: Money | None = None
    currency: str | None = None
    status: Lifecycle | None = None

    _amount = field_validator('amount')(_validate_decimal)
    _currency = field_validator('currency', mode='before')(_currency)

    @model_validator(mode='after')
    def patch(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('At least one non-null field is required')
        return self


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    product_id: int
    location_id: int
    amount: Decimal
    currency: str
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class PriceList(BaseModel):
    items: list[PriceResponse]
    limit: int
    offset: int


class CurrentPriceResponse(BaseModel):
    price_id: int
    product_id: int
    location_id: int
    amount: Decimal
    currency: str
    status: str
    source: str
    updated_at: datetime


class PromotionValues(BaseModel):
    promotion_type: PromotionType
    benefit_value: PositiveMoney
    currency: str | None = None

    _benefit = field_validator('benefit_value')(_validate_decimal)
    _currency = field_validator('currency', mode='before')(_currency)

    @model_validator(mode='after')
    def semantics(self):
        if self.promotion_type == 'PERCENTAGE_DISCOUNT':
            if self.benefit_value > 100 or self.currency is not None:
                raise ValueError('Percentage discounts require value <= 100 and no currency')
        elif self.currency is None:
            raise ValueError('Fixed amount discounts require currency')
        return self


class PromotionCreate(PromotionValues):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    starts_at: datetime
    ends_at: datetime
    applies_to_all_locations: bool
    is_combinable: bool = False
    priority: int = Field(default=0, ge=0)

    _starts = field_validator('starts_at')(_utc_naive)
    _ends = field_validator('ends_at')(_utc_naive)

    @model_validator(mode='after')
    def interval(self):
        if self.starts_at >= self.ends_at:
            raise ValueError('starts_at must be before ends_at')
        return self


class PromotionPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    promotion_type: PromotionType | None = None
    benefit_value: PositiveMoney | None = None
    currency: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    applies_to_all_locations: bool | None = None
    is_combinable: bool | None = None
    priority: int | None = Field(default=None, ge=0)
    status: Lifecycle | None = None

    _benefit = field_validator('benefit_value')(_validate_decimal)
    _currency = field_validator('currency', mode='before')(_currency)
    _starts = field_validator('starts_at')(_utc_naive)
    _ends = field_validator('ends_at')(_utc_naive)

    @model_validator(mode='after')
    def patch(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for key in self.model_fields_set - {'description', 'currency'}:
            if getattr(self, key) is None:
                raise ValueError('Promotion fields cannot be null')
        return self


class AssociationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: int = Field(gt=0)


class LocationAssociationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location_id: int = Field(gt=0)


class AssociationPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Lifecycle


class PromotionAssociationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    promotion_id: int
    status: str
    created_at: datetime
    updated_at: datetime


class PromotionProductResponse(PromotionAssociationResponse):
    product_id: int


class PromotionLocationResponse(PromotionAssociationResponse):
    location_id: int


class PromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    organization_id: int
    name: str
    description: str | None
    promotion_type: str
    benefit_value: Decimal
    currency: str | None
    starts_at: datetime
    ends_at: datetime
    applies_to_all_locations: bool
    is_combinable: bool
    priority: int
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    @field_serializer('starts_at', 'ends_at')
    def serialize_utc(self, value: datetime) -> str:
        return value.replace(tzinfo=UTC).isoformat().replace('+00:00', 'Z')


class PromotionDetail(PromotionResponse):
    products: list[PromotionProductResponse]
    locations: list[PromotionLocationResponse]


class PromotionList(BaseModel):
    items: list[PromotionResponse]
    limit: int
    offset: int


class CandidateResponse(BaseModel):
    promotion_id: int
    name: str
    promotion_type: str
    benefit_value: Decimal
    currency: str | None
    starts_at: datetime
    ends_at: datetime
    applies_to_all_locations: bool
    is_combinable: bool
    priority: int

    @field_serializer('starts_at', 'ends_at')
    def serialize_utc(self, value: datetime) -> str:
        return value.replace(tzinfo=UTC).isoformat().replace('+00:00', 'Z')


async def _organization(db, tenant_id, organization_id):
    value = await db.scalar(select(Organization).where(Organization.id == organization_id, Organization.tenant_id == tenant_id))
    if value is None:
        raise HTTPException(404, 'Organization not found')
    return value


async def _product(db, tenant_id, product_id, organization_id=None):
    query = select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    if organization_id is not None:
        query = query.where(Product.organization_id == organization_id)
    value = await db.scalar(query)
    if value is None:
        raise HTTPException(404, 'Product not found')
    return value


async def _location(db, tenant_id, location_id, organization_id=None):
    query = select(Location).where(Location.id == location_id, Location.tenant_id == tenant_id)
    if organization_id is not None:
        query = query.where(Location.organization_id == organization_id)
    value = await db.scalar(query)
    if value is None:
        raise HTTPException(404, 'Location not found')
    return value


async def _price(db, tenant_id, price_id, lock=False):
    query = select(ProductPrice).where(ProductPrice.id == price_id, ProductPrice.tenant_id == tenant_id)
    if lock:
        query = query.with_for_update()
    value = await db.scalar(query)
    if value is None:
        raise HTTPException(404, 'Price not found')
    return value


async def _promotion(db, tenant_id, promotion_id, lock=False):
    query = select(Promotion).where(Promotion.id == promotion_id, Promotion.tenant_id == tenant_id)
    if lock:
        query = query.with_for_update()
    value = await db.scalar(query)
    if value is None:
        raise HTTPException(404, 'Promotion not found')
    return value


def _promo_values(promotion: Promotion, payload: PromotionPatch) -> tuple:
    values = {key: getattr(promotion, key) for key in ('promotion_type', 'benefit_value', 'currency', 'starts_at', 'ends_at', 'applies_to_all_locations', 'status')}
    values.update(payload.model_dump(exclude_unset=True))
    try:
        PromotionValues(promotion_type=values['promotion_type'], benefit_value=values['benefit_value'], currency=values['currency'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if values['starts_at'] >= values['ends_at']:
        raise HTTPException(422, 'starts_at must be before ends_at')
    return values


async def _validate_activation(db, promotion: Promotion, applies_all: bool | None = None):
    active_product = await db.scalar(select(PromotionProduct.id).where(PromotionProduct.promotion_id == promotion.id, PromotionProduct.tenant_id == promotion.tenant_id, PromotionProduct.status == 'ACTIVE').limit(1))
    if active_product is None:
        raise HTTPException(409, 'Promotion requires an active Product target')
    all_locations = promotion.applies_to_all_locations if applies_all is None else applies_all
    if not all_locations:
        active_location = await db.scalar(select(PromotionLocation.id).where(PromotionLocation.promotion_id == promotion.id, PromotionLocation.tenant_id == promotion.tenant_id, PromotionLocation.status == 'ACTIVE').limit(1))
        if active_location is None:
            raise HTTPException(409, 'Selected-Location Promotion requires an active Location target')


@router.get('/prices', response_model=PriceList)
async def list_prices(context: Annotated[AuthenticatedContext, Depends(require_permission('pricing.read'))], db: Annotated[AsyncSession, Depends(get_db)], organization_id: int = Query(gt=0), product_id: int | None = Query(None, gt=0), location_id: int | None = Query(None, gt=0), status_filter: Lifecycle | None = Query(None, alias='status'), source: Source | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    await _organization(db, context.tenant_id, organization_id)
    query = select(ProductPrice).where(ProductPrice.tenant_id == context.tenant_id, ProductPrice.organization_id == organization_id)
    if product_id is not None:
        await _product(db, context.tenant_id, product_id, organization_id)
        query = query.where(ProductPrice.product_id == product_id)
    if location_id is not None:
        await _location(db, context.tenant_id, location_id, organization_id)
        query = query.where(ProductPrice.location_id == location_id)
    if status_filter: query = query.where(ProductPrice.status == status_filter)
    if source: query = query.where(ProductPrice.source == source)
    result = await db.execute(query.order_by(ProductPrice.id).limit(limit).offset(offset))
    return PriceList(items=list(result.scalars()), limit=limit, offset=offset)


@router.post('/prices', response_model=PriceResponse, status_code=201)
async def create_price(payload: PriceCreate, context: Annotated[AuthenticatedContext, Depends(require_permission('pricing.manage'))], db: Annotated[AsyncSession, Depends(get_db)]):
    await _organization(db, context.tenant_id, payload.organization_id)
    await _product(db, context.tenant_id, payload.product_id, payload.organization_id)
    await _location(db, context.tenant_id, payload.location_id, payload.organization_id)
    price = ProductPrice(tenant_id=context.tenant_id, **payload.model_dump(), status='ACTIVE', source='PLATFORM')
    db.add(price)
    try: await db.commit()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, 'Price already exists for Product and Location') from exc
    await db.refresh(price)
    logger.info('Product Price created', extra={'event':'price_created','operation':'create','tenant_id':context.tenant_id,'organization_id':price.organization_id,'location_id':price.location_id,'product_id':price.product_id,'price_id':price.id,'user_id':context.user_id,'correlation_id':get_correlation_id()})
    return price


@router.get('/prices/{price_id}', response_model=PriceResponse)
async def get_price(price_id: Annotated[int, Path(gt=0)], context: Annotated[AuthenticatedContext, Depends(require_permission('pricing.read'))], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _price(db, context.tenant_id, price_id)


@router.patch('/prices/{price_id}', response_model=PriceResponse)
async def patch_price(price_id: Annotated[int, Path(gt=0)], payload: PricePatch, context: Annotated[AuthenticatedContext, Depends(require_permission('pricing.manage'))], db: Annotated[AsyncSession, Depends(get_db)]):
    price = await _price(db, context.tenant_id, price_id, True)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(price, key, value)
    await db.commit(); await db.refresh(price)
    logger.info('Product Price updated', extra={'event':'price_updated','operation':'update','tenant_id':context.tenant_id,'organization_id':price.organization_id,'location_id':price.location_id,'product_id':price.product_id,'price_id':price.id,'user_id':context.user_id,'correlation_id':get_correlation_id()})
    return price


@router.get('/products/{product_id}/price', response_model=CurrentPriceResponse)
async def current_price(product_id: Annotated[int, Path(gt=0)], location_id: int = Query(gt=0), context: Annotated[AuthenticatedContext, Depends(require_permission('pricing.read'))] = None, db: Annotated[AsyncSession, Depends(get_db)] = None):
    try:
        price = await pricing_service.get_canonical_current_price(db, tenant_id=context.tenant_id, product_id=product_id, location_id=location_id)
    except pricing_service.PricingReadContextError as exc:
        raise HTTPException(404, str(exc)) from exc
    if price is None: raise HTTPException(404, 'Current Price not found')
    return CurrentPriceResponse(price_id=price.id, product_id=price.product_id, location_id=price.location_id, amount=price.amount, currency=price.currency, status=price.status, source=price.source, updated_at=price.updated_at)


@router.get('/promotions/applicable', response_model=list[CandidateResponse])
async def applicable_promotions(product_id: int = Query(gt=0), location_id: int = Query(gt=0), effective_at: datetime = Query(), context: Annotated[AuthenticatedContext, Depends(require_permission('promotion.read'))] = None, db: Annotated[AsyncSession, Depends(get_db)] = None):
    try: effective = _utc_naive(effective_at)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    try:
        promotions = await pricing_service.find_canonical_applicable_promotions(db, tenant_id=context.tenant_id, product_id=product_id, location_id=location_id, effective_at=effective)
    except pricing_service.PricingReadContextError as exc:
        raise HTTPException(404, str(exc)) from exc
    return [CandidateResponse(promotion_id=p.id, **{k:getattr(p,k) for k in ('name','promotion_type','benefit_value','currency','starts_at','ends_at','applies_to_all_locations','is_combinable','priority')}) for p in promotions]


@router.get('/promotions', response_model=PromotionList)
async def list_promotions(context: Annotated[AuthenticatedContext, Depends(require_permission('promotion.read'))], db: Annotated[AsyncSession, Depends(get_db)], organization_id: int = Query(gt=0), status_filter: Lifecycle | None = Query(None, alias='status'), promotion_type: PromotionType | None = None, product_id: int | None = Query(None, gt=0), location_id: int | None = Query(None, gt=0), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    await _organization(db, context.tenant_id, organization_id)
    query = select(Promotion).where(Promotion.tenant_id == context.tenant_id, Promotion.organization_id == organization_id)
    if status_filter: query=query.where(Promotion.status == status_filter)
    if promotion_type: query=query.where(Promotion.promotion_type == promotion_type)
    if product_id is not None:
        await _product(db, context.tenant_id, product_id, organization_id); query=query.join(PromotionProduct, and_(PromotionProduct.promotion_id==Promotion.id, PromotionProduct.tenant_id==Promotion.tenant_id)).where(PromotionProduct.product_id==product_id)
    if location_id is not None:
        await _location(db, context.tenant_id, location_id, organization_id); query=query.join(PromotionLocation, and_(PromotionLocation.promotion_id==Promotion.id, PromotionLocation.tenant_id==Promotion.tenant_id)).where(PromotionLocation.location_id==location_id)
    result=await db.execute(query.order_by(Promotion.id).limit(limit).offset(offset)); return PromotionList(items=list(result.scalars()), limit=limit, offset=offset)


@router.post('/promotions', response_model=PromotionResponse, status_code=201)
async def create_promotion(payload: PromotionCreate, context: Annotated[AuthenticatedContext, Depends(require_permission('promotion.manage'))], db: Annotated[AsyncSession, Depends(get_db)]):
    await _organization(db, context.tenant_id, payload.organization_id)
    promotion=Promotion(tenant_id=context.tenant_id, **payload.model_dump(), status='INACTIVE', source='PLATFORM'); db.add(promotion); await db.commit(); await db.refresh(promotion)
    logger.info('Promotion created', extra={'event':'promotion_created','operation':'create','tenant_id':context.tenant_id,'organization_id':promotion.organization_id,'promotion_id':promotion.id,'user_id':context.user_id,'correlation_id':get_correlation_id()}); return promotion


@router.get('/promotions/{promotion_id}', response_model=PromotionDetail)
async def get_promotion(promotion_id: Annotated[int, Path(gt=0)], context: Annotated[AuthenticatedContext, Depends(require_permission('promotion.read'))], db: Annotated[AsyncSession, Depends(get_db)]):
    promotion=await _promotion(db,context.tenant_id,promotion_id)
    products=list((await db.execute(select(PromotionProduct).where(PromotionProduct.promotion_id==promotion.id,PromotionProduct.tenant_id==context.tenant_id).order_by(PromotionProduct.id))).scalars())
    locations=list((await db.execute(select(PromotionLocation).where(PromotionLocation.promotion_id==promotion.id,PromotionLocation.tenant_id==context.tenant_id).order_by(PromotionLocation.id))).scalars())
    detail = PromotionResponse.model_validate(promotion).model_dump()
    return PromotionDetail(**detail, products=products, locations=locations)


@router.patch('/promotions/{promotion_id}', response_model=PromotionResponse)
async def patch_promotion(promotion_id: Annotated[int, Path(gt=0)], payload: PromotionPatch, context: Annotated[AuthenticatedContext, Depends(require_permission('promotion.manage'))], db: Annotated[AsyncSession, Depends(get_db)]):
    promotion=await _promotion(db,context.tenant_id,promotion_id,True); values=_promo_values(promotion,payload)
    if values['status']=='ACTIVE': await _validate_activation(db,promotion,values['applies_to_all_locations'])
    for key,value in payload.model_dump(exclude_unset=True).items(): setattr(promotion,key,value)
    await db.commit(); await db.refresh(promotion)
    logger.info('Promotion updated',extra={'event':'promotion_updated','operation':'update','tenant_id':context.tenant_id,'organization_id':promotion.organization_id,'promotion_id':promotion.id,'user_id':context.user_id,'correlation_id':get_correlation_id()}); return promotion


async def _create_association(db, context, promotion_id, target_id, kind):
    promotion=await _promotion(db,context.tenant_id,promotion_id)
    model,target_model,target_field=(PromotionProduct,Product,'product_id') if kind=='product' else (PromotionLocation,Location,'location_id')
    target=await (_product(db,context.tenant_id,target_id,promotion.organization_id) if kind=='product' else _location(db,context.tenant_id,target_id,promotion.organization_id))
    association=model(tenant_id=context.tenant_id,organization_id=promotion.organization_id,promotion_id=promotion.id,**{target_field:target.id},status='ACTIVE'); db.add(association)
    try: await db.commit()
    except IntegrityError as exc: await db.rollback(); raise HTTPException(409,f'Promotion {kind} association already exists') from exc
    await db.refresh(association)
    logger.info(f'Promotion {kind} updated', extra={'event':f'promotion_{kind}_updated','operation':'create','tenant_id':context.tenant_id,'organization_id':promotion.organization_id,'promotion_id':promotion.id,f'{kind}_id':target.id,'correlation_id':get_correlation_id()})
    return association


@router.post('/promotions/{promotion_id}/products',response_model=PromotionProductResponse,status_code=201)
async def add_promotion_product(promotion_id:int,payload:AssociationCreate,context:Annotated[AuthenticatedContext,Depends(require_permission('promotion.manage'))],db:Annotated[AsyncSession,Depends(get_db)]): return await _create_association(db,context,promotion_id,payload.product_id,'product')


@router.post('/promotions/{promotion_id}/locations',response_model=PromotionLocationResponse,status_code=201)
async def add_promotion_location(promotion_id:int,payload:LocationAssociationCreate,context:Annotated[AuthenticatedContext,Depends(require_permission('promotion.manage'))],db:Annotated[AsyncSession,Depends(get_db)]): return await _create_association(db,context,promotion_id,payload.location_id,'location')


async def _patch_association(db,context,promotion_id,target_id,payload,kind):
    promotion=await _promotion(db,context.tenant_id,promotion_id,True); model,target_field=(PromotionProduct,'product_id') if kind=='product' else (PromotionLocation,'location_id')
    association=await db.scalar(select(model).where(model.promotion_id==promotion.id,model.tenant_id==context.tenant_id,getattr(model,target_field)==target_id).with_for_update())
    if association is None: raise HTTPException(404,f'Promotion {kind} association not found')
    if promotion.status=='ACTIVE' and payload.status=='INACTIVE':
        others=await db.scalar(select(model.id).where(model.promotion_id==promotion.id,model.tenant_id==context.tenant_id,model.status=='ACTIVE',model.id!=association.id).limit(1))
        if others is None and (kind=='product' or not promotion.applies_to_all_locations): raise HTTPException(409,f'Active Promotion requires an active {kind.title()} target')
    association.status=payload.status; await db.commit(); await db.refresh(association)
    logger.info(f'Promotion {kind} updated', extra={'event':f'promotion_{kind}_updated','operation':'update','tenant_id':context.tenant_id,'organization_id':promotion.organization_id,'promotion_id':promotion.id,f'{kind}_id':target_id,'correlation_id':get_correlation_id()})
    return association


@router.patch('/promotions/{promotion_id}/products/{product_id}',response_model=PromotionProductResponse)
async def patch_promotion_product(promotion_id:int,product_id:int,payload:AssociationPatch,context:Annotated[AuthenticatedContext,Depends(require_permission('promotion.manage'))],db:Annotated[AsyncSession,Depends(get_db)]): return await _patch_association(db,context,promotion_id,product_id,payload,'product')


@router.patch('/promotions/{promotion_id}/locations/{location_id}',response_model=PromotionLocationResponse)
async def patch_promotion_location(promotion_id:int,location_id:int,payload:AssociationPatch,context:Annotated[AuthenticatedContext,Depends(require_permission('promotion.manage'))],db:Annotated[AsyncSession,Depends(get_db)]): return await _patch_association(db,context,promotion_id,location_id,payload,'location')
