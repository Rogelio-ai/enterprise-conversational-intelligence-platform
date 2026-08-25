from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntelligenceDerivation(Base):
    """Provider-neutral provenance for one derivation from canonical evidence."""

    __tablename__ = 'intelligence_derivations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_intelligence_derivations_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_id', 'tenant_id'],
            ['conversations.id', 'conversations.tenant_id'],
            name='fk_intelligence_derivations_conversation_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_message_id', 'tenant_id', 'conversation_id'],
            [
                'conversation_messages.id',
                'conversation_messages.tenant_id',
                'conversation_messages.conversation_id',
            ],
            name='fk_intelligence_derivations_message_tenant_conversation',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', name='uq_intelligence_derivations_id_tenant'
        ),
        CheckConstraint(
            "CHAR_LENGTH(schema_key) BETWEEN 1 AND 100 AND TRIM(schema_key) <> ''",
            name='ck_intelligence_derivations_schema_key',
        ),
        CheckConstraint(
            "CHAR_LENGTH(schema_version) BETWEEN 1 AND 64 AND TRIM(schema_version) <> ''",
            name='ck_intelligence_derivations_schema_version',
        ),
        CheckConstraint(
            "CHAR_LENGTH(producer_key) BETWEEN 1 AND 128 AND TRIM(producer_key) <> ''",
            name='ck_intelligence_derivations_producer_key',
        ),
        CheckConstraint(
            "CHAR_LENGTH(producer_version) BETWEEN 1 AND 128 "
            "AND TRIM(producer_version) <> ''",
            name='ck_intelligence_derivations_producer_version',
        ),
        CheckConstraint(
            "CHAR_LENGTH(correlation_id) BETWEEN 1 AND 128 AND TRIM(correlation_id) <> ''",
            name='ck_intelligence_derivations_correlation_id',
        ),
        Index(
            'ix_intelligence_derivations_tenant_message_created',
            'tenant_id',
            'source_message_id',
            'created_at',
            'id',
        ),
        Index(
            'ix_intelligence_derivations_tenant_conversation',
            'tenant_id',
            'conversation_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_key: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    producer_key: Mapped[str] = mapped_column(String(128), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class RestaurantMessageIntent(Base):
    """Restaurant-owned intent interpretation attached to Core provenance."""

    __tablename__ = 'restaurant_message_intents'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_restaurant_message_intents_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['derivation_id', 'tenant_id'],
            ['intelligence_derivations.id', 'intelligence_derivations.tenant_id'],
            name='fk_restaurant_message_intents_derivation_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'derivation_id',
            'ordinal',
            name='uq_restaurant_message_intents_derivation_ordinal',
        ),
        CheckConstraint('ordinal >= 1', name='ck_restaurant_message_intents_ordinal'),
        CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='ck_restaurant_message_intents_confidence',
        ),
        CheckConstraint(
            "CHAR_LENGTH(intent_code) BETWEEN 1 AND 64 AND TRIM(intent_code) <> ''",
            name='ck_restaurant_message_intents_code',
        ),
        Index(
            'ix_restaurant_message_intents_tenant_code',
            'tenant_id',
            'intent_code',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    derivation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    intent_code: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
