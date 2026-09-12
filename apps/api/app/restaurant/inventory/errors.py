class InventoryError(RuntimeError):
    code = 'INVENTORY_ERROR'

    def __init__(self, message: str | None = None):
        super().__init__(message or self.code)


class InventoryScopeNotFoundError(InventoryError):
    code = 'INVENTORY_SCOPE_NOT_FOUND'


class InventoryItemNotFoundError(InventoryError):
    code = 'INVENTORY_ITEM_NOT_FOUND'


class WarehouseNotFoundError(InventoryError):
    code = 'WAREHOUSE_NOT_FOUND'


class WarehouseVersionConflictError(InventoryError):
    code = 'WAREHOUSE_VERSION_CONFLICT'


class NegativeStockBlockedError(InventoryError):
    code = 'NEGATIVE_STOCK_BLOCKED'


class DuplicateInventoryItemCodeError(InventoryError):
    code = 'DUPLICATE_INVENTORY_ITEM_CODE'


class InvalidInventoryItemError(InventoryError):
    code = 'INVALID_INVENTORY_ITEM'


class InventoryItemVersionConflictError(InventoryError):
    code = 'INVENTORY_ITEM_VERSION_CONFLICT'


class ItemUomConversionNotFoundError(InventoryError):
    code = 'ITEM_UOM_CONVERSION_NOT_FOUND'


class InvalidItemUomConversionError(InventoryError):
    code = 'INVALID_ITEM_UOM_CONVERSION'


class DuplicateItemUomConversionError(InventoryError):
    code = 'DUPLICATE_ITEM_UOM_CONVERSION'


class InventoryCostNotDerivableError(InventoryError):
    code = 'INVENTORY_COST_NOT_DERIVABLE'


class InvalidInventoryCostRevisionError(InventoryError):
    code = 'INVALID_INVENTORY_COST_REVISION'


class InventoryCostRevisionConflictError(InventoryError):
    code = 'INVENTORY_COST_REVISION_CONFLICT'


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
