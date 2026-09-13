import type {
  ApiErrorBody,
  BillingDocument,
  BillingFiscalContext,
  CashCount,
  CashMovement,
  CashSession,
  CheckSettlement,
  FiscalIssuance,
  FiscalProfileBase,
  LocationListResponse,
  LoginRequest,
  LoginResponse,
  ManagerOperationalOverview,
  Organization,
  OpenServiceSessionResponse,
  PaidCheckDispatch,
  PreparationConnector,
  RecipientFiscalProfile,
  RegeneratedAccessCodeResponse,
  ResourceListResponse,
  RestaurantCheckDetail,
  RestaurantCheckListResponse,
  RestaurantPayment,
  IssuerFiscalProfile,
  ClosedServiceSessionResponse,
  CurrentServiceSession,
  StaffIdentity,
  StaffOperationalRequest,
  StaffOperationalRequestListResponse,
  OperationalRequestStatus,
  OperationalRequestType,
  PreparationAreaListResponse,
  PreparationDispatch,
  PreparationState,
  PreparationTransitionResult,
  PreparationWork,
  Tenant,
  GoodsReceipt,
  InventoryIntelligence,
  InventoryLoss,
  InventoryOffering,
  InventoryReconciliation,
  InventorySupplier,
  PhysicalCount,
  PurchaseOrder,
} from './contracts';
import { readCredential } from '../session/storage';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
const API_BASE_URL = configuredBaseUrl || '/api';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly kind: 'network' | 'authentication' | 'authorization' | 'backend',
    public readonly correlationId?: string,
    message = code,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  if (authenticated) {
    const credential = readCredential();
    if (!credential) {
      unauthorizedListeners.forEach((listener) => listener());
      throw new ApiError(401, 'missing_authentication', 'authentication');
    }
    headers.set('Authorization', `Bearer ${credential.accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'network_unavailable', 'network', undefined, 'No fue posible conectar con el servicio.');
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try { body = await response.json() as ApiErrorBody; } catch { /* safe status fallback */ }
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message;
    const code = body.error?.code || (typeof body.detail === 'object' ? body.detail.code : undefined) || `http_${response.status}`;
    const kind = response.status === 401 ? 'authentication' : response.status === 403 ? 'authorization' : 'backend';
    if (authenticated && response.status === 401) unauthorizedListeners.forEach((listener) => listener());
    throw new ApiError(response.status, code, kind, body.correlation_id, body.error?.message || detail || 'La operación no pudo completarse.');
  }

  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export const staffApi = {
  login(payload: LoginRequest): Promise<LoginResponse> {
    return request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }, false);
  },
  me(): Promise<StaffIdentity> {
    return request('/auth/me');
  },
  managerOperationalOverview(locationId: number): Promise<ManagerOperationalOverview> {
    return request(`/staff/manager/operational-overview?location_id=${locationId}`);
  },
  currentTenant(): Promise<Tenant> {
    return request('/tenants/current');
  },
  locations(): Promise<LocationListResponse> {
    return request('/locations?limit=100&offset=0');
  },
  organization(organizationId: number): Promise<Organization> {
    return request(`/organizations/${organizationId}`);
  },
  inventoryIntelligence(locationId: number, warehouseId?: number): Promise<InventoryIntelligence> {
    const query = new URLSearchParams({ location_id: String(locationId), limit: '100', offset: '0' });
    if (warehouseId) query.set('warehouse_id', String(warehouseId));
    return request(`/inventory/intelligence?${query.toString()}`);
  },
  inventorySuppliers(locationId: number): Promise<{ items: InventorySupplier[] }> {
    return request(`/inventory/suppliers?location_id=${locationId}`);
  },
  inventoryOfferings(locationId: number, supplierId: number): Promise<{ items: InventoryOffering[] }> {
    return request(`/inventory/suppliers/${supplierId}/offerings?location_id=${locationId}`);
  },
  createGoodsReceipt(payload: object): Promise<GoodsReceipt> {
    return request('/inventory/goods-receipts', { method: 'POST', body: JSON.stringify(payload) });
  },
  acceptGoodsReceipt(receiptId: number, expectedVersion: number, key: string): Promise<GoodsReceipt> {
    return request(`/inventory/goods-receipts/${receiptId}:accept`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ expected_version: expectedVersion }) });
  },
  purchaseOrders(locationId: number): Promise<{items: PurchaseOrder[]}> { return request(`/inventory/purchase-orders?location_id=${locationId}`); },
  createPurchaseOrder(payload: object): Promise<PurchaseOrder> { return request('/inventory/purchase-orders', { method: 'POST', body: JSON.stringify(payload) }); },
  amendPurchaseOrder(id: number, payload: object): Promise<PurchaseOrder> { return request(`/inventory/purchase-orders/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }); },
  actOnPurchaseOrder(id: number, action: 'submit'|'approve'|'cancel'|'close', expectedVersion: number, key: string): Promise<PurchaseOrder> { return request(`/inventory/purchase-orders/${id}:${action}`, { method: 'POST', headers: {'Idempotency-Key': key}, body: JSON.stringify({expected_version: expectedVersion}) }); },
  inventoryItems(locationId: number): Promise<{items: import('./contracts').InventoryItemOption[]}> { return request(`/inventory-items?location_id=${locationId}&limit=100&offset=0`); },
  replenishmentPolicies(locationId:number): Promise<{items:import('./contracts').ReplenishmentPolicy[]}> { return request(`/inventory/replenishment-policies?location_id=${locationId}`); },
  putReplenishmentPolicy(warehouseId:number,itemId:number,payload:object): Promise<import('./contracts').ReplenishmentPolicy> { return request(`/inventory/replenishment-policies/${warehouseId}/${itemId}`,{method:'PUT',body:JSON.stringify(payload)}); },
  inventoryLots(locationId:number): Promise<{items:import('./contracts').InventoryLot[]}> { return request(`/inventory/lots?location_id=${locationId}`); },
  valuationSnapshots(locationId:number): Promise<{items:import('./contracts').InventoryValuationSnapshot[]}> { return request(`/inventory/valuation-snapshots?location_id=${locationId}`); },
  createValuationSnapshot(payload:object,key:string): Promise<import('./contracts').InventoryValuationSnapshot> { return request('/inventory/valuation-snapshots',{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(payload)}); },
  preparationRecipes(locationId: number): Promise<{items: import('./contracts').PreparationRecipeVersion[]}> { return request(`/inventory/preparation-recipes?location_id=${locationId}`); },
  publishPreparationRecipe(payload: object): Promise<import('./contracts').PreparationRecipeVersion> { return request('/inventory/preparation-recipes', { method:'POST', body:JSON.stringify(payload) }); },
  preparationBatches(locationId: number): Promise<{items: import('./contracts').PreparationBatch[]}> { return request(`/inventory/preparation-batches?location_id=${locationId}`); },
  createPreparationBatch(payload: object): Promise<import('./contracts').PreparationBatch> { return request('/inventory/preparation-batches', { method:'POST', body:JSON.stringify(payload) }); },
  actOnPreparationBatch(id:number, action:'start'|'complete'|'cancel', expectedVersion:number, key?:string): Promise<import('./contracts').PreparationBatch> { return request(`/inventory/preparation-batches/${id}:${action}`, { method:'POST', headers:key?{'Idempotency-Key':key}:undefined, body:JSON.stringify({expected_version:expectedVersion}) }); },
  inventoryLosses(locationId: number): Promise<{ items: InventoryLoss[] }> {
    return request(`/inventory/losses?location_id=${locationId}`);
  },
  createInventoryLoss(payload: object): Promise<InventoryLoss> {
    return request('/inventory/losses', { method: 'POST', body: JSON.stringify(payload) });
  },
  actOnInventoryLoss(lossId: number, action: 'post' | 'approve', expectedVersion: number, key: string): Promise<InventoryLoss> {
    return request(`/inventory/losses/${lossId}:${action}`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ expected_version: expectedVersion }) });
  },
  physicalCounts(locationId: number): Promise<{ items: PhysicalCount[] }> {
    return request(`/inventory/physical-counts?location_id=${locationId}`);
  },
  createPhysicalCount(payload: object): Promise<PhysicalCount> {
    return request('/inventory/physical-counts', { method: 'POST', body: JSON.stringify(payload) });
  },
  putPhysicalCountLine(countId: number, itemId: number, payload: object): Promise<PhysicalCount> {
    return request(`/inventory/physical-counts/${countId}/lines/${itemId}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  transitionPhysicalCount(countId: number, action: 'submit' | 'approve' | 'post', expectedVersion: number, key?: string): Promise<PhysicalCount> {
    return request(`/inventory/physical-counts/${countId}:${action}`, { method: 'POST', headers: key ? { 'Idempotency-Key': key } : undefined, body: JSON.stringify({ expected_version: expectedVersion }) });
  },
  createInventoryReconciliation(lineId: number, periodStart: string): Promise<InventoryReconciliation> {
    return request('/inventory/reconciliations', { method: 'POST', body: JSON.stringify({ physical_count_line_id: lineId, period_start: periodStart }) });
  },
  closeInventoryReconciliation(id: number, expectedVersion: number): Promise<InventoryReconciliation> {
    return request(`/inventory/reconciliations/${id}:close`, { method: 'POST', body: JSON.stringify({ expected_version: expectedVersion }) });
  },
  tables(locationId: number): Promise<ResourceListResponse> {
    const query = new URLSearchParams({
      location_id: String(locationId),
      resource_type: 'TABLE',
      status: 'ACTIVE',
      limit: '100',
      offset: '0',
    });
    return request(`/resources?${query.toString()}`);
  },
  cashRegisters(locationId: number): Promise<ResourceListResponse> {
    const query = new URLSearchParams({
      location_id: String(locationId), resource_type: 'CASH_REGISTER',
      status: 'ACTIVE', limit: '100', offset: '0',
    });
    return request(`/resources?${query.toString()}`);
  },
  async activeCashSession(locationId: number, resourceId: number): Promise<CashSession | null> {
    const query = new URLSearchParams({ location_id: String(locationId), resource_id: String(resourceId) });
    try { return await request(`/cash-sessions/active?${query.toString()}`); }
    catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  openCashSession(locationId: number, resourceId: number, currency: string, key: string): Promise<CashSession> {
    return request(`/resources/${resourceId}/cash-sessions?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ currency }),
    });
  },
  cashSession(locationId: number, sessionId: number): Promise<CashSession> {
    return request(`/cash-sessions/${sessionId}?location_id=${locationId}`);
  },
  cashMovements(locationId: number, sessionId: number): Promise<CashMovement[]> {
    return request(`/cash-sessions/${sessionId}/movements?location_id=${locationId}`);
  },
  createCashMovement(locationId: number, sessionId: number, payload: {
    movement_type: string; amount: string; currency: string; reason?: string; reference?: string;
  }, key: string): Promise<CashMovement> {
    return request(`/cash-sessions/${sessionId}/movements?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(payload),
    });
  },
  createCashCount(locationId: number, sessionId: number, amount: string, currency: string, key: string): Promise<CashCount> {
    return request(`/cash-sessions/${sessionId}/counts?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key },
      body: JSON.stringify({ counted_amount: amount, currency }),
    });
  },
  closeCashSession(locationId: number, sessionId: number, countId: number, reason: string | undefined, key: string): Promise<CashSession> {
    return request(`/cash-sessions/${sessionId}/close?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key },
      body: JSON.stringify({ cash_count_id: countId, variance_reason: reason || null }),
    });
  },
  restaurantChecks(locationId: number): Promise<RestaurantCheckListResponse> {
    return request(`/restaurant-checks?location_id=${locationId}&limit=100&offset=0`);
  },
  restaurantCheck(locationId: number, checkId: number): Promise<RestaurantCheckDetail> {
    return request(`/restaurant-checks/${checkId}?location_id=${locationId}`);
  },
  settlement(locationId: number, checkId: number): Promise<CheckSettlement> {
    return request(`/restaurant-checks/${checkId}/settlement?location_id=${locationId}`);
  },
  createCashPayment(locationId: number, checkId: number, payload: {
    expected_check_version: number; expected_check_fingerprint: string; amount: string;
    currency: string; cash_session_id: number; cash_tendered_amount: string;
  }, key: string): Promise<RestaurantPayment> {
    return request(`/restaurant-checks/${checkId}/payments?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({
        ...payload, method_category: 'CASH', payer_type: 'OTHER', payer_reference: 'cashier',
      }),
    });
  },
  recoverPayment(locationId: number, paymentId: number): Promise<RestaurantPayment> {
    return request(`/restaurant-payments/${paymentId}/recover?location_id=${locationId}`, { method: 'POST' });
  },
  fiscalContext(locationId: number, checkId: number): Promise<BillingFiscalContext> {
    return request(`/restaurant-checks/${checkId}/fiscal-context?location_id=${locationId}`);
  },
  saveIssuerFiscalProfile(locationId: number, checkId: number, payload: FiscalProfileBase): Promise<IssuerFiscalProfile> {
    return request(`/restaurant-checks/${checkId}/issuer-fiscal-profile?location_id=${locationId}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
  },
  saveRecipientFiscalProfile(locationId: number, checkId: number, payload: FiscalProfileBase & { invoice_usage: string }): Promise<RecipientFiscalProfile> {
    return request(`/restaurant-checks/${checkId}/recipient-fiscal-profile?location_id=${locationId}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
  },
  billingDocuments(locationId: number, checkId: number): Promise<BillingDocument[]> {
    return request(`/restaurant-checks/${checkId}/billing-documents?location_id=${locationId}`);
  },
  createBillingDocument(locationId: number, checkId: number, organizationId: number, issuerId: number, recipientId: number, key: string): Promise<BillingDocument> {
    return request(`/restaurant-checks/${checkId}/billing-documents`, {
      method: 'POST', headers: { 'Idempotency-Key': key },
      body: JSON.stringify({
        organization_id: organizationId, location_id: locationId,
        issuer_fiscal_profile_id: issuerId, recipient_fiscal_profile_id: recipientId,
      }),
    });
  },
  fiscalIssuances(locationId: number, organizationId: number, documentId: number): Promise<FiscalIssuance[]> {
    return request(`/billing-documents/${documentId}/issuances?organization_id=${organizationId}&location_id=${locationId}`);
  },
  initiateFiscalIssuance(locationId: number, organizationId: number, documentId: number, providerKey: string, key: string): Promise<FiscalIssuance> {
    return request(`/billing-documents/${documentId}/issuances?organization_id=${organizationId}&location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ provider_key: providerKey }),
    });
  },
  recoverFiscalIssuance(locationId: number, organizationId: number, issuanceId: number): Promise<FiscalIssuance> {
    return request(`/billing-issuances/${issuanceId}/recover?organization_id=${organizationId}&location_id=${locationId}`, { method: 'POST' });
  },
  retryFiscalIssuance(locationId: number, organizationId: number, issuanceId: number): Promise<FiscalIssuance> {
    return request(`/billing-issuances/${issuanceId}/retry?organization_id=${organizationId}&location_id=${locationId}`, { method: 'POST' });
  },
  preparationConnectors(locationId: number): Promise<PreparationConnector[]> {
    return request(`/preparation-delivery-connectors?location_id=${locationId}`);
  },
  paidCheckDispatches(locationId: number, checkId: number): Promise<PaidCheckDispatch[]> {
    return request(`/restaurant-checks/${checkId}/paid-print-dispatches?location_id=${locationId}`);
  },
  createPaidCheckDispatch(locationId: number, checkId: number, cashierResourceId: number, connectorId: number, localTargetKey: string, key: string): Promise<PaidCheckDispatch> {
    return request(`/restaurant-checks/${checkId}/paid-print?location_id=${locationId}`, {
      method: 'POST', headers: { 'Idempotency-Key': key },
      body: JSON.stringify({ cashier_resource_id: cashierResourceId, connector_id: connectorId, local_target_key: localTargetKey }),
    });
  },
  async currentServiceSession(resourceId: number): Promise<CurrentServiceSession | null> {
    try {
      return await request(`/resources/${resourceId}/service-sessions/current`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  openServiceSession(resourceId: number, partySize: number): Promise<OpenServiceSessionResponse> {
    return request(`/resources/${resourceId}/service-sessions`, {
      method: 'POST',
      body: JSON.stringify({ party_size: partySize }),
    });
  },
  regenerateAccessCode(sessionId: number): Promise<RegeneratedAccessCodeResponse> {
    return request(`/restaurant-service-sessions/${sessionId}/access-code/regenerate`, { method: 'POST' });
  },
  closeServiceSession(sessionId: number): Promise<ClosedServiceSessionResponse> {
    return request(`/restaurant-service-sessions/${sessionId}/close`, { method: 'POST' });
  },
  operationalRequests(
    locationId: number,
    filters: { status?: OperationalRequestStatus; requestType?: OperationalRequestType },
  ): Promise<StaffOperationalRequestListResponse> {
    const query = new URLSearchParams({
      location_id: String(locationId),
      limit: '100',
      offset: '0',
    });
    if (filters.status) query.set('status', filters.status);
    if (filters.requestType) query.set('request_type', filters.requestType);
    return request(`/staff/operational-requests?${query.toString()}`);
  },
  acknowledgeOperationalRequest(
    requestId: number,
    locationId: number,
  ): Promise<StaffOperationalRequest> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/staff/operational-requests/${requestId}/acknowledge?${query.toString()}`, {
      method: 'POST',
    });
  },
  completeOperationalRequest(
    requestId: number,
    locationId: number,
  ): Promise<StaffOperationalRequest> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/staff/operational-requests/${requestId}/complete?${query.toString()}`, {
      method: 'POST',
    });
  },
  preparationAreas(locationId: number): Promise<PreparationAreaListResponse> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/preparation-areas?${query.toString()}`);
  },
  preparationWorks(
    locationId: number,
    filters: { state?: PreparationState; areaId?: number },
  ): Promise<PreparationWork[]> {
    const query = new URLSearchParams({ location_id: String(locationId), limit: '200' });
    if (filters.state) query.set('execution_state', filters.state);
    if (filters.areaId) query.set('preparation_area_id', String(filters.areaId));
    return request(`/preparation-works?${query.toString()}`);
  },
  transitionPreparationItem(
    itemId: number,
    expectedState: PreparationState,
    expectedVersion: number,
    toState: PreparationState,
    idempotencyKey: string,
  ): Promise<PreparationTransitionResult> {
    return request(`/preparation-work-items/${itemId}/transitions`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({
        expected_state: expectedState,
        expected_version: expectedVersion,
        to_state: toState,
      }),
    });
  },
  preparationDispatches(locationId: number): Promise<PreparationDispatch[]> {
    const query = new URLSearchParams({ location_id: String(locationId), limit: '200' });
    return request(`/preparation-dispatches?${query.toString()}`);
  },
  reprintPreparationDispatch(dispatchId: number): Promise<PreparationDispatch> {
    return request(`/preparation-dispatches/${dispatchId}/reprints`, { method: 'POST' });
  },
};
