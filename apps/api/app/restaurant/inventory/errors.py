class InventoryError(RuntimeError):
    code = 'INVENTORY_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class InventoryScopeNotFoundError(InventoryError):
    code = 'INVENTORY_SCOPE_NOT_FOUND'


class InventoryItemNotFoundError(InventoryError):
    code = 'INVENTORY_ITEM_NOT_FOUND'


class DuplicateInventoryItemCodeError(InventoryError):
    code = 'DUPLICATE_INVENTORY_ITEM_CODE'


class InvalidInventoryItemError(InventoryError):
    code = 'INVALID_INVENTORY_ITEM'


class InventoryItemVersionConflictError(InventoryError):
    code = 'INVENTORY_ITEM_VERSION_CONFLICT'


class ConsumptionDefinitionNotFoundError(InventoryError):
    code = 'CONSUMPTION_DEFINITION_NOT_FOUND'


class ConsumptionDefinitionVersionConflictError(InventoryError):
    code = 'CONSUMPTION_DEFINITION_VERSION_CONFLICT'


class InvalidConsumptionDefinitionError(InventoryError):
    code = 'INVALID_CONSUMPTION_DEFINITION'


class InvalidStockMovementError(InventoryError):
    code = 'INVALID_STOCK_MOVEMENT'


class StockMovementNotFoundError(InventoryError):
    code = 'STOCK_MOVEMENT_NOT_FOUND'


class StockMovementIdempotencyConflictError(InventoryError):
    code = 'STOCK_MOVEMENT_IDEMPOTENCY_CONFLICT'


class DuplicateOpeningBalanceError(InventoryError):
    code = 'DUPLICATE_OPENING_BALANCE'


class StockMovementAlreadyReversedError(InventoryError):
    code = 'STOCK_MOVEMENT_ALREADY_REVERSED'


class OrderConsumptionNotFoundError(InventoryError):
    code = 'ORDER_CONSUMPTION_NOT_FOUND'


class OrderConsumptionConflictError(InventoryError):
    code = 'ORDER_CONSUMPTION_CONFLICT'
