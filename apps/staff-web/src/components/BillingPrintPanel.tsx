import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type {
  CheckSettlement,
  FiscalProfileBase,
  RestaurantCheckSummary,
  StaffOperationalRequest,
} from '../api/contracts';
import { useAuth } from '../session/AuthContext';

type Props = {
  locationId: number;
  check: RestaurantCheckSummary;
  settlement: CheckSettlement | undefined;
  registerId: number | null;
};

type FiscalForm = FiscalProfileBase & { invoice_usage?: string };
type Feedback = { kind: 'success' | 'warning' | 'error'; message: string };

const emptyProfile: FiscalForm = {
  legal_name: '', tax_identifier: '', tax_regime: '', fiscal_postal_code: '', invoice_usage: '',
};

const errorText = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.kind === 'network') return 'Resultado no confirmado. Reconcilia con el servidor antes de repetir.';
    return error.message;
  }
  return 'No fue posible completar la operación.';
};

const stateLabel: Record<string, string> = {
  PENDING: 'Pendiente', IN_PROGRESS: 'En proceso', SUCCEEDED: 'Emitida', FAILED: 'Fallida',
  REJECTED: 'Rechazada', UNCERTAIN: 'Incierta', DESTINATION_SUBMISSION_ACCEPTED: 'Entrega aceptada por destino',
  RETRYABLE_FAILURE: 'Fallo reintentable', ACTION_REQUIRED: 'Requiere atención',
};

export function BillingPrintPanel({ locationId, check, settlement, registerId }: Props) {
  const { hasPermission } = useAuth();
  const [issuer, setIssuer] = useState<FiscalForm>(emptyProfile);
  const [recipient, setRecipient] = useState<FiscalForm>(emptyProfile);
  const [providerKey, setProviderKey] = useState('FINKOK');
  const [connectorId, setConnectorId] = useState<number | null>(null);
  const [targetKey, setTargetKey] = useState('cashier_printer');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [fiscalAmbiguous, setFiscalAmbiguous] = useState(false);
  const [printAmbiguous, setPrintAmbiguous] = useState(false);
  const documentKey = useRef<string | null>(null);
  const issuanceKey = useRef<string | null>(null);
  const printKey = useRef<string | null>(null);

  const fiscalContext = useQuery({
    queryKey: ['staff', 'billing', 'context', locationId, check.id],
    queryFn: () => staffApi.fiscalContext(locationId, check.id), retry: false,
  });
  const documents = useQuery({
    queryKey: ['staff', 'billing', 'documents', locationId, check.id],
    queryFn: () => staffApi.billingDocuments(locationId, check.id), retry: false,
  });
  const document = documents.data?.at(-1) ?? null;
  const issuances = useQuery({
    queryKey: ['staff', 'billing', 'issuances', locationId, document?.id],
    queryFn: () => staffApi.fiscalIssuances(locationId, check.organization_id, document!.id),
    enabled: Boolean(document), retry: false,
  });
  const issuance = issuances.data?.at(-1) ?? null;
  const connectors = useQuery({
    queryKey: ['staff', 'billing', 'connectors', locationId],
    queryFn: () => staffApi.preparationConnectors(locationId),
    enabled: hasPermission('preparation.read'), retry: false,
  });
  const dispatches = useQuery({
    queryKey: ['staff', 'billing', 'dispatches', locationId, check.id],
    queryFn: () => staffApi.paidCheckDispatches(locationId, check.id), retry: false,
  });
  const invoiceRequests = useQuery({
    queryKey: ['staff', 'billing', 'requests', locationId, 'INVOICE_ASSISTANCE'],
    queryFn: () => staffApi.operationalRequests(locationId, { requestType: 'INVOICE_ASSISTANCE' }),
    enabled: hasPermission('operational_request.read'), retry: false,
  });
  const printRequests = useQuery({
    queryKey: ['staff', 'billing', 'requests', locationId, 'PAID_CHECK_PRINT'],
    queryFn: () => staffApi.operationalRequests(locationId, { requestType: 'PAID_CHECK_PRINT' }),
    enabled: hasPermission('operational_request.read'), retry: false,
  });

  const actionable = (item: StaffOperationalRequest) => item.status === 'PENDING' || item.status === 'ACKNOWLEDGED';
  const relevantInvoiceRequests = (invoiceRequests.data?.items ?? []).filter((item) => item.request_type === 'INVOICE_ASSISTANCE' && item.related_restaurant_check_id === check.id && actionable(item));
  const relevantPrintRequests = (printRequests.data?.items ?? []).filter((item) => item.request_type === 'PAID_CHECK_PRINT' && item.related_restaurant_check_id === check.id && actionable(item));
  const settled = settlement?.check_status === 'SETTLED';

  useEffect(() => {
    const profile = fiscalContext.data?.issuer_profiles[0];
    setIssuer(profile ? {
      legal_name: profile.legal_name, tax_identifier: profile.tax_identifier,
      tax_regime: profile.tax_regime, fiscal_postal_code: profile.fiscal_postal_code,
    } : emptyProfile);
    const customer = fiscalContext.data?.recipient_profile;
    setRecipient(customer ? {
      legal_name: customer.legal_name, tax_identifier: customer.tax_identifier,
      tax_regime: customer.tax_regime, fiscal_postal_code: customer.fiscal_postal_code,
      invoice_usage: customer.invoice_usage,
    } : emptyProfile);
  }, [fiscalContext.data]);

  useEffect(() => {
    const values = (connectors.data ?? []).filter((item) => item.status === 'ACTIVE');
    if (!values.some((item) => item.id === connectorId)) setConnectorId(values[0]?.id ?? null);
  }, [connectorId, connectors.data]);

  const refreshFiscal = async () => {
    const results = await Promise.all([fiscalContext.refetch(), documents.refetch()]);
    const issuanceResult = document ? await issuances.refetch() : null;
    const confirmed = results.every((result) => result.isSuccess) && (!issuanceResult || issuanceResult.isSuccess);
    if (confirmed) setFiscalAmbiguous(false);
  };
  const refreshPrint = async () => {
    const result = await dispatches.refetch();
    if (result.isSuccess) setPrintAmbiguous(false);
  };

  const saveIssuer = useMutation({
    mutationFn: () => staffApi.saveIssuerFiscalProfile(locationId, check.id, issuer),
    onSuccess: async () => { setFeedback({ kind: 'success', message: 'Datos fiscales del emisor guardados por el backend.' }); await fiscalContext.refetch(); },
    onError: (error) => setFeedback({ kind: 'error', message: errorText(error) }),
  });
  const saveRecipient = useMutation({
    mutationFn: () => staffApi.saveRecipientFiscalProfile(locationId, check.id, {
      legal_name: recipient.legal_name, tax_identifier: recipient.tax_identifier,
      tax_regime: recipient.tax_regime, fiscal_postal_code: recipient.fiscal_postal_code,
      invoice_usage: recipient.invoice_usage ?? '',
    }),
    onSuccess: async () => { setFeedback({ kind: 'success', message: 'Datos fiscales del cliente validados y guardados.' }); await fiscalContext.refetch(); },
    onError: (error) => setFeedback({ kind: 'error', message: errorText(error) }),
  });
  const createDocument = useMutation({
    mutationFn: () => {
      documentKey.current ??= `billing-document-${crypto.randomUUID()}`;
      return staffApi.createBillingDocument(
        locationId, check.id, check.organization_id,
        fiscalContext.data!.issuer_profiles[0].id,
        fiscalContext.data!.recipient_profile!.id,
        documentKey.current,
      );
    },
    onSuccess: async () => { documentKey.current = null; setFeedback({ kind: 'success', message: 'Documento fiscal preparado con evidencia congelada.' }); await documents.refetch(); },
    onError: async (error) => { if (error instanceof ApiError && error.kind === 'network') setFiscalAmbiguous(true); setFeedback({ kind: error instanceof ApiError && error.kind === 'network' ? 'warning' : 'error', message: errorText(error) }); await refreshFiscal(); },
  });
  const issue = useMutation({
    mutationFn: () => {
      issuanceKey.current ??= `fiscal-issuance-${crypto.randomUUID()}`;
      return staffApi.initiateFiscalIssuance(locationId, check.organization_id, document!.id, providerKey, issuanceKey.current);
    },
    onSuccess: async (value) => { issuanceKey.current = null; setFeedback({ kind: value.state === 'SUCCEEDED' ? 'success' : 'warning', message: `Emisión confirmada por el backend: ${stateLabel[value.state] ?? value.state}.` }); await issuances.refetch(); },
    onError: async (error) => { if (error instanceof ApiError && error.kind === 'network') setFiscalAmbiguous(true); setFeedback({ kind: error instanceof ApiError && error.kind === 'network' ? 'warning' : 'error', message: errorText(error) }); await refreshFiscal(); },
  });
  const fiscalRecovery = useMutation({
    mutationFn: (mode: 'recover' | 'retry') => mode === 'recover'
      ? staffApi.recoverFiscalIssuance(locationId, check.organization_id, issuance!.id)
      : staffApi.retryFiscalIssuance(locationId, check.organization_id, issuance!.id),
    onSuccess: async (value) => { setFeedback({ kind: value.state === 'SUCCEEDED' ? 'success' : 'warning', message: `Estado fiscal confirmado: ${stateLabel[value.state] ?? value.state}.` }); await issuances.refetch(); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await issuances.refetch(); },
  });
  const print = useMutation({
    mutationFn: () => {
      printKey.current ??= `paid-print-${crypto.randomUUID()}`;
      return staffApi.createPaidCheckDispatch(locationId, check.id, registerId!, connectorId!, targetKey, printKey.current);
    },
    onSuccess: async () => { printKey.current = null; setFeedback({ kind: 'success', message: 'Despacho creado. La entrega aún depende del conector local.' }); await dispatches.refetch(); },
    onError: async (error) => { if (error instanceof ApiError && error.kind === 'network') setPrintAmbiguous(true); setFeedback({ kind: error instanceof ApiError && error.kind === 'network' ? 'warning' : 'error', message: errorText(error) }); await refreshPrint(); },
  });
  const completeRequest = useMutation({
    mutationFn: async (item: StaffOperationalRequest) => {
      if (item.status === 'PENDING') await staffApi.acknowledgeOperationalRequest(item.id, locationId);
      return staffApi.completeOperationalRequest(item.id, locationId);
    },
    onSuccess: async () => { setFeedback({ kind: 'success', message: 'Solicitud operativa completada explícitamente.' }); await Promise.all([invoiceRequests.refetch(), printRequests.refetch()]); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await Promise.all([invoiceRequests.refetch(), printRequests.refetch()]); },
  });

  const issuerReady = fiscalContext.data?.issuer_profiles.length;
  const recipientReady = Boolean(fiscalContext.data?.recipient_profile);
  const canManage = hasPermission('restaurant_check.manage');
  const canManageRequests = hasPermission('operational_request.manage');
  const latestDispatch = dispatches.data?.at(-1) ?? null;

  return <section className="cashier-panel billing-print-panel" aria-labelledby="billing-print-heading">
    <div className="cashier-panel-heading"><div><p className="eyebrow">06 · Facturación e impresión</p><h2 id="billing-print-heading">Factura y cuenta pagada</h2></div><button className="secondary-button" type="button" onClick={() => void Promise.all([refreshFiscal(), refreshPrint()])}>Reconciliar estados</button></div>
    {feedback ? <div className={`cashier-feedback cashier-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}>{feedback.message}</div> : null}
    <div className={settled ? 'eligibility-banner eligibility-banner--ready' : 'eligibility-banner'}><strong>Check #{check.id}: {settlement?.check_status ?? 'consultando'}</strong><span>{settled ? 'Liquidación autoritativa confirmada.' : 'Facturación e impresión permanecen bloqueadas hasta SETTLED.'}</span></div>
    <div className="handoff-grid"><div><span>Solicitudes de factura</span><strong>{relevantInvoiceRequests.length}</strong></div><div><span>Solicitudes de impresión</span><strong>{relevantPrintRequests.length}</strong></div></div>

    <div className="billing-print-grid">
      <div className="billing-column"><h3>Datos fiscales</h3>
        {fiscalContext.isError ? <p role="alert">{errorText(fiscalContext.error)}</p> : null}
        {fiscalContext.data ? <p className="privacy-note">Cliente: {fiscalContext.data.customer_display_name ?? `#${fiscalContext.data.customer_id}`}{fiscalContext.data.customer_email ? ` · ${fiscalContext.data.customer_email}` : ''}. Los datos permanecen en esta sesión y se envían sólo al backend.</p> : null}
        <FiscalFields legend="Emisor" value={issuer} onChange={setIssuer} />
        <button className="secondary-button" type="button" disabled={!canManage || saveIssuer.isPending} onClick={() => saveIssuer.mutate()}>Guardar emisor</button>
        <FiscalFields legend="Cliente fiscal" value={recipient} onChange={setRecipient} recipient />
        <button className="secondary-button" type="button" disabled={!canManage || saveRecipient.isPending} onClick={() => saveRecipient.mutate()}>Guardar cliente fiscal</button>
        <div className="commit-block"><h3>Documento y CFDI</h3>
          {!document ? <button className="primary-button" type="button" disabled={!settled || !issuerReady || !recipientReady || !canManage || createDocument.isPending || fiscalAmbiguous} onClick={() => createDocument.mutate()}>Preparar factura</button> : <p>Documento #{document.id} · {document.status} · Total backend {document.total} {document.currency}</p>}
          {document && !issuance ? <><label><span>Proveedor fiscal configurado</span><input aria-label="Proveedor fiscal configurado" value={providerKey} onChange={(event) => setProviderKey(event.target.value)} /></label><button className="primary-button" type="button" disabled={!providerKey || issue.isPending || fiscalAmbiguous || !canManage} onClick={() => issue.mutate()}>Emitir factura</button></> : null}
          {issuance ? <div className={`operation-state operation-state--${issuance.state.toLowerCase()}`}><strong>{stateLabel[issuance.state] ?? issuance.state}</strong><span>Emisión #{issuance.id} · {issuance.provider_key} · {issuance.external_status ?? 'sin estado externo'}</span>{issuance.state === 'UNCERTAIN' ? <button className="secondary-button" type="button" disabled={fiscalRecovery.isPending} onClick={() => fiscalRecovery.mutate('recover')}>Recuperar emisión</button> : null}{issuance.state === 'FAILED' ? <button className="secondary-button" type="button" disabled={fiscalRecovery.isPending} onClick={() => fiscalRecovery.mutate('retry')}>Reintentar emisión</button> : null}</div> : null}
          {fiscalAmbiguous ? <p className="safety-lock" role="alert">Emisión bloqueada hasta reconciliar el resultado autoritativo.</p> : null}
          {issuance?.state === 'SUCCEEDED' && canManageRequests && relevantInvoiceRequests.map((item) => <button className="secondary-button" type="button" key={item.id} onClick={() => completeRequest.mutate(item)}>Completar solicitud de factura #{item.id}</button>)}
        </div>
      </div>

      <div className="billing-column"><h3>Cuenta pagada</h3><p>El navegador no imprime. El backend crea un PaidCheckDispatch para el conector local.</p>
        <label><span>Conector local</span><select aria-label="Conector local" value={connectorId ?? ''} onChange={(event) => setConnectorId(Number(event.target.value))}><option value="">Selecciona</option>{(connectors.data ?? []).filter((item) => item.status === 'ACTIVE').map((item) => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</select></label>
        <label><span>Destino local</span><input aria-label="Destino local" value={targetKey} onChange={(event) => setTargetKey(event.target.value)} /></label>
        <button className="primary-button" type="button" disabled={!settled || !registerId || !connectorId || !targetKey || !canManage || print.isPending || printAmbiguous} onClick={() => print.mutate()}>{latestDispatch ? 'Crear reimpresión autorizada' : 'Imprimir cuenta pagada'}</button>
        {printAmbiguous ? <p className="safety-lock" role="alert">Despacho bloqueado hasta reconciliar; no se enviará otro trabajo a ciegas.</p> : null}
        <div className="dispatch-list">{(dispatches.data ?? []).map((item) => <article key={item.id} className={`operation-state operation-state--${item.state.toLowerCase()}`}><strong>{stateLabel[item.state] ?? item.state}</strong><span>Despacho #{item.id} · {item.connector_name} · {item.attempt_count} intento(s)</span>{item.last_error_message ? <small>{item.last_error_kind}: {item.last_error_message}</small> : null}</article>)}</div>
        {latestDispatch?.state === 'DESTINATION_SUBMISSION_ACCEPTED' && canManageRequests && relevantPrintRequests.map((item) => <button className="secondary-button" type="button" key={item.id} onClick={() => completeRequest.mutate(item)}>Completar solicitud de impresión #{item.id}</button>)}
      </div>
    </div>
  </section>;
}

function FiscalFields({ legend, value, onChange, recipient = false }: {
  legend: string; value: FiscalForm; onChange: (value: FiscalForm) => void; recipient?: boolean;
}) {
  const field = (name: keyof FiscalForm, label: string) => <label><span>{label}</span><input aria-label={`${legend}: ${label}`} value={value[name] ?? ''} onChange={(event) => onChange({ ...value, [name]: event.target.value })} /></label>;
  return <fieldset className="fiscal-fields"><legend>{legend}</legend>{field('legal_name', 'Razón social')}{field('tax_identifier', 'RFC / identificador fiscal')}{field('tax_regime', 'Régimen fiscal')}{field('fiscal_postal_code', 'Código postal fiscal')}{recipient ? field('invoice_usage', 'Uso de factura') : null}</fieldset>;
}
