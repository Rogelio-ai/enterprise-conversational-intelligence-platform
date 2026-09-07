import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, dinerApi } from '../api/client';
import type { DraftResponse, RestaurantOrderResponse } from '../api/contracts';
import { formatPrice } from '../utils/formatters';

const draftQueryKey = ['diner', 'order-draft'] as const;
const previewQueryPrefix = ['diner', 'checkout-preview'] as const;

interface ConfirmationIdentity {
  draftId: number;
  draftVersion: number;
  fingerprint: string;
  key: string;
}

type ConfirmationOutcome =
  | { kind: 'accepted'; order: RestaurantOrderResponse }
  | { kind: 'conflict' }
  | { kind: 'unconfirmed' };

class AmbiguousConfirmationError extends Error {
  constructor() {
    super('The order confirmation outcome could not be verified');
    this.name = 'AmbiguousConfirmationError';
  }
}

class UnexpectedOrderStateError extends Error {
  constructor() {
    super('The backend did not return an accepted order');
    this.name = 'UnexpectedOrderStateError';
  }
}

function previewQueryKey(draft: DraftResponse) {
  return [...previewQueryPrefix, draft.draft_id, draft.version] as const;
}

function acceptedOrderForDraft(orders: RestaurantOrderResponse[], draftId: number) {
  return orders.find((order) => order.source_order_draft_id === draftId && order.status === 'ACCEPTED');
}

function confirmationError(error: unknown): string {
  if (error instanceof AmbiguousConfirmationError) {
    return 'No pudimos verificar si el restaurante recibió la confirmación. No la enviaremos de nuevo automáticamente. Revisa tu conexión y vuelve a verificar desde esta pantalla.';
  }
  if (error instanceof UnexpectedOrderStateError) {
    return 'El restaurante respondió con un estado que todavía no confirma la aceptación. Tu pedido no se mostrará como confirmado.';
  }
  if (error instanceof ApiError && error.status === 422) {
    return 'El restaurante no aceptó los datos de confirmación. Revisa el pedido antes de intentarlo nuevamente.';
  }
  if (error instanceof ApiError && error.status === 0) {
    return 'No pudimos conectar con el restaurante. Conservamos la misma identidad de confirmación para evitar duplicados.';
  }
  return 'El restaurante no pudo confirmar tu pedido. Revisa el contenido e intenta nuevamente.';
}

export function OrderConfirmation({
  draft,
  editPending,
  onAccepted,
  onSubmittingChange,
}: {
  draft: DraftResponse;
  editPending: boolean;
  onAccepted: (order: RestaurantOrderResponse) => void;
  onSubmittingChange: (submitting: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const identity = useRef<ConfirmationIdentity | null>(null);
  const submittingGuard = useRef(false);
  const previewQuery = useQuery({
    queryKey: previewQueryKey(draft),
    queryFn: dinerApi.getCheckoutPreview,
    enabled: draft.readiness === 'READY' && draft.items.length > 0,
    retry: false,
  });

  const confirmation = useMutation({
    mutationFn: async (): Promise<ConfirmationOutcome> => {
      const currentDraft = queryClient.getQueryData<DraftResponse>(draftQueryKey);
      const preview = previewQuery.data;
      if (!currentDraft || !preview || currentDraft.draft_id !== preview.draft_id || currentDraft.version !== preview.draft_version) {
        throw new Error('The authoritative draft and commercial preview do not match');
      }

      if (
        !identity.current
        || identity.current.draftId !== preview.draft_id
        || identity.current.draftVersion !== preview.draft_version
        || identity.current.fingerprint !== preview.commercial_fingerprint
      ) {
        identity.current = {
          draftId: preview.draft_id,
          draftVersion: preview.draft_version,
          fingerprint: preview.commercial_fingerprint,
          key: `diner-confirm-${crypto.randomUUID()}`,
        };
      }

      try {
        const order = await dinerApi.confirmOrder({
          expected_draft_version: preview.draft_version,
          expected_commercial_fingerprint: preview.commercial_fingerprint,
        }, identity.current.key);
        if (order.status !== 'ACCEPTED') throw new UnexpectedOrderStateError();
        return { kind: 'accepted', order };
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.state === 'SESSION_CLOSED')) throw error;
        if (!(error instanceof ApiError) || (error.status !== 0 && error.status !== 409)) throw error;

        try {
          const accepted = acceptedOrderForDraft(await dinerApi.listOrders(), preview.draft_id);
          if (accepted) return { kind: 'accepted', order: accepted };
        } catch {
          // Continue with the current-draft read when order reconciliation is unavailable.
        }

        let authoritative: DraftResponse;
        try {
          authoritative = await dinerApi.getOrderDraft();
        } catch {
          if (error.status === 0) throw new AmbiguousConfirmationError();
          throw error;
        }
        queryClient.setQueryData(draftQueryKey, authoritative);
        if (error.status === 409) {
          identity.current = null;
          if (authoritative.draft_id === preview.draft_id && authoritative.version === preview.draft_version) {
            await previewQuery.refetch();
          }
          return { kind: 'conflict' };
        }
        return { kind: 'unconfirmed' };
      }
    },
    onSuccess: (result) => {
      if (result.kind !== 'accepted') return;
      onAccepted(result.order);
    },
  });

  const submit = () => {
    if (submittingGuard.current || confirmation.isPending || editPending || !previewQuery.data) return;
    submittingGuard.current = true;
    onSubmittingChange(true);
    confirmation.mutate(undefined, {
      onSettled: () => {
        submittingGuard.current = false;
        onSubmittingChange(false);
      },
    });
  };

  if (draft.readiness !== 'READY' || draft.items.length === 0) return null;

  if (previewQuery.isPending) {
    return <section className="order-confirmation order-confirmation--loading" aria-busy="true"><span className="spinner" aria-hidden="true" /> Verificando importes con el restaurante…</section>;
  }

  if (previewQuery.isError) {
    return (
      <section className="order-confirmation" aria-labelledby="confirmation-title">
        <p className="eyebrow">Confirmación no disponible</p>
        <h2 id="confirmation-title">Revisa tu pedido nuevamente</h2>
        <div className="draft-feedback draft-feedback--error" role="alert">
          <span aria-hidden="true">!</span>
          <p>No pudimos obtener la validación comercial del restaurante. El pedido no fue confirmado.</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => previewQuery.refetch()}>Volver a verificar</button>
      </section>
    );
  }

  const previewMatches = previewQuery.data.draft_id === draft.draft_id && previewQuery.data.draft_version === draft.version;
  const outcome = confirmation.data;

  return (
    <section className="order-confirmation" aria-labelledby="confirmation-title">
      <div>
        <p className="eyebrow">Confirmación final</p>
        <h2 id="confirmation-title">Confirma tu pedido</h2>
        <p>Al confirmar, el restaurante validará y aceptará este pedido.</p>
      </div>

      <dl className="order-commercial-summary" aria-label="Importes confirmados por el restaurante">
        <div><dt>Subtotal</dt><dd>{formatPrice(previewQuery.data.subtotal, previewQuery.data.currency)}</dd></div>
        {Number(previewQuery.data.total_discount) > 0 && (
          <div><dt>Descuentos</dt><dd>−{formatPrice(previewQuery.data.total_discount, previewQuery.data.currency)}</dd></div>
        )}
        <div className="order-commercial-total"><dt>Total</dt><dd>{formatPrice(previewQuery.data.payable_total, previewQuery.data.currency)}</dd></div>
      </dl>

      {outcome?.kind === 'conflict' && (
        <div className="draft-feedback draft-feedback--notice" role="status">
          <span aria-hidden="true">↻</span>
          <p>El pedido o sus importes cambiaron. Mostramos la versión más reciente; revísala y confirma nuevamente.</p>
        </div>
      )}
      {outcome?.kind === 'unconfirmed' && (
        <div className="draft-feedback draft-feedback--notice" role="status">
          <span aria-hidden="true">i</span>
          <p>No encontramos un pedido aceptado y el borrador sigue disponible. Puedes revisarlo antes de volver a confirmar.</p>
        </div>
      )}
      {confirmation.isError && (
        <div className="draft-feedback draft-feedback--error" role="alert">
          <span aria-hidden="true">!</span>
          <p>{confirmationError(confirmation.error)}</p>
        </div>
      )}

      <button
        className="primary-button order-confirm-button"
        type="button"
        disabled={!previewMatches || editPending || confirmation.isPending}
        aria-describedby="confirmation-commitment"
        onClick={submit}
      >
        {confirmation.isPending ? 'Confirmando con el restaurante…' : 'Confirmar pedido'}
      </button>
      <p className="order-confirmation-note" id="confirmation-commitment">Esta acción envía el pedido al restaurante.</p>
    </section>
  );
}
