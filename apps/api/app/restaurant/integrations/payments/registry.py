from __future__ import annotations

from collections.abc import Mapping

from app.restaurant.payments import errors


class PaymentExecutorRegistry:
    """Process-local lookup of runtime implementations by adapter kind."""

    def __init__(self, executors: Mapping[str, object] | None = None) -> None:
        self._executors: dict[str, object] = {}
        for adapter_kind, executor in (executors or {}).items():
            self.register(adapter_kind, executor)

    def register(self, adapter_kind: str, executor: object) -> None:
        key = self._key(adapter_kind)
        if key in self._executors:
            raise errors.DuplicatePaymentExecutorRegistrationError(
                f'Payment executor adapter {key!r} is already registered'
            )
        self._executors[key] = executor

    def resolve(self, adapter_kind: str) -> object:
        key = self._key(adapter_kind)
        executor = self._executors.get(key)
        if executor is None:
            raise errors.PaymentExecutorAdapterNotRegisteredError(
                f'Payment executor adapter {key!r} is not registered'
            )
        return executor

    @staticmethod
    def _key(adapter_kind: str) -> str:
        if not isinstance(adapter_kind, str) or not adapter_kind.strip():
            raise errors.PaymentExecutorAdapterNotRegisteredError(
                'Payment executor adapter kind is required'
            )
        return adapter_kind.strip()
