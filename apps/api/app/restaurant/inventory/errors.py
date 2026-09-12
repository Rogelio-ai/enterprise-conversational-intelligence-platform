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


class SupplierNotFoundError(InventoryError):
    code = 'SUPPLIER_NOT_FOUND'


class SupplierConflictError(InventoryError):
    code = 'SUPPLIER_CONFLICT'


class InvalidSupplierError(InventoryError):
    code = 'INVALID_SUPPLIER'


class SupplierOfferingNotFoundError(InventoryError):
    code = 'SUPPLIER_OFFERING_NOT_FOUND'


class SupplierOfferingConflictError(InventoryError):
    code = 'SUPPLIER_OFFERING_CONFLICT'


class InvalidSupplierOfferingError(InventoryError):
    code = 'INVALID_SUPPLIER_OFFERING'


class GoodsReceiptNotFoundError(InventoryError):
    code = 'GOODS_RECEIPT_NOT_FOUND'


class GoodsReceiptConflictError(InventoryError):
    code = 'GOODS_RECEIPT_CONFLICT'


class InvalidGoodsReceiptError(InventoryError):
    code = 'INVALID_GOODS_RECEIPT'


class InventoryLossNotFoundError(InventoryError):
    code = 'INVENTORY_LOSS_NOT_FOUND'


class InventoryLossConflictError(InventoryError):
    code = 'INVENTORY_LOSS_CONFLICT'


class InvalidInventoryLossError(InventoryError):
    code = 'INVALID_INVENTORY_LOSS'


class InventoryLossApprovalRequiredError(InventoryError):
    code = 'INVENTORY_LOSS_APPROVAL_REQUIRED'


class InventoryLossPolicyNotFoundError(InventoryError):
    code = 'INVENTORY_LOSS_POLICY_NOT_FOUND'


class InventoryLossPolicyConflictError(InventoryError):
    code = 'INVENTORY_LOSS_POLICY_CONFLICT'


class PhysicalCountNotFoundError(InventoryError):
    code = 'PHYSICAL_COUNT_NOT_FOUND'


class PhysicalCountConflictError(InventoryError):
    code = 'PHYSICAL_COUNT_CONFLICT'


class InvalidPhysicalCountError(InventoryError):
    code = 'INVALID_PHYSICAL_COUNT'


class InventoryReconciliationNotFoundError(InventoryError):
    code = 'INVENTORY_RECONCILIATION_NOT_FOUND'


class InventoryReconciliationConflictError(InventoryError):
    code = 'INVENTORY_RECONCILIATION_CONFLICT'
