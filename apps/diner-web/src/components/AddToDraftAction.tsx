import { useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { DraftResponse } from '../api/contracts';
import type { ConfiguredProductSelection } from './ProductConfiguration';

interface DraftAddProgress {
  draft: DraftResponse;
  itemId: number | null;
  nextGroupIndex: number;
  refreshBeforeRetry: boolean;
}

class UnconfirmedDraftAddError extends Error {
  constructor() {
    super('The add-item response was not received');
    this.name = 'UnconfirmedDraftAddError';
  }
}

class DraftConfigurationRejectedError extends Error {
  constructor() {
    super('The configured item is not ready in the authoritative draft');
    this.name = 'DraftConfigurationRejectedError';
  }
}

function errorCopy(error: unknown): { title: string; message: string; retryable: boolean } {
  if (error instanceof UnconfirmedDraftAddError) {
    return {
      title: 'No pudimos confirmar la acción',
      message: 'Para evitar agregar el producto dos veces, no vuelvas a enviarlo desde esta pantalla. Regresa al menú y continúa desde ahí.',
      retryable: false,
    };
  }
  if (error instanceof DraftConfigurationRejectedError || (error instanceof ApiError && error.status === 422)) {
    return {
      title: 'Revisa tu configuración',
      message: 'El restaurante no pudo aceptar estas elecciones. Puedes ajustarlas e intentar nuevamente.',
      retryable: true,
    };
  }
  if (error instanceof ApiError && error.status === 409) {
    return {
      title: 'No se pudo agregar en este momento',
      message: 'El estado de tu pedido o del producto cambió. Revisa tus elecciones e intenta nuevamente.',
      retryable: true,
    };
  }
  if (error instanceof ApiError && error.status === 0) {
    return {
      title: 'Conexión interrumpida',
      message: 'Tus elecciones siguen aquí. Revisa tu conexión e intenta nuevamente.',
      retryable: true,
    };
  }
  return {
    title: 'No pudimos agregar el producto',
    message: 'Tus elecciones siguen aquí. Intenta nuevamente en un momento.',
    retryable: true,
  };
}

export function AddToDraftAction({
  selection,
  ready,
  onSubmittingChange,
}: {
  selection: ConfiguredProductSelection;
  ready: boolean;
  onSubmittingChange: (submitting: boolean) => void;
}) {
  const progress = useRef<DraftAddProgress | null>(null);
  const submittingGuard = useRef(false);
  const previousSelection = useRef(selection);

  const mutation = useMutation({
    mutationFn: async () => {
      let current = progress.current;
      if (!current) {
        current = {
          draft: await dinerApi.createOrderDraft(),
          itemId: null,
          nextGroupIndex: 0,
          refreshBeforeRetry: false,
        };
        progress.current = current;
      } else if (current.refreshBeforeRetry) {
        const refreshed = await dinerApi.getOrderDraft();
        const previousItemId = current.itemId;
        const itemStillExists = previousItemId === null || refreshed.items.some((item) => item.item_id === previousItemId);
        current = {
          draft: refreshed,
          itemId: itemStillExists ? current.itemId : null,
          nextGroupIndex: itemStillExists ? current.nextGroupIndex : 0,
          refreshBeforeRetry: false,
        };
        progress.current = current;
      }

      if (current.itemId === null) {
        const existingItemIds = new Set(current.draft.items.map((item) => item.item_id));
        let added: DraftResponse;
        try {
          added = await dinerApi.addDraftItem({
            product_id: selection.product_id,
            quantity: '1',
            expected_version: current.draft.version,
          });
        } catch (error) {
          if (error instanceof ApiError && error.status === 0) throw new UnconfirmedDraftAddError();
          if (error instanceof ApiError && error.status === 409) current.refreshBeforeRetry = true;
          throw error;
        }
        const addedItems = added.items.filter((item) => !existingItemIds.has(item.item_id));
        if (addedItems.length !== 1 || addedItems[0].product_id !== selection.product_id) {
          throw new UnconfirmedDraftAddError();
        }
        current = {
          draft: added,
          itemId: addedItems[0].item_id,
          nextGroupIndex: 0,
          refreshBeforeRetry: false,
        };
        progress.current = current;
      }

      const itemId = current.itemId;
      if (itemId === null) throw new UnconfirmedDraftAddError();

      for (let index = current.nextGroupIndex; index < selection.groups.length; index += 1) {
        const group = selection.groups[index];
        try {
          const updated = await dinerApi.replaceDraftGroupSelections(itemId, group.group_id, {
            option_ids: group.option_ids,
            expected_version: current.draft.version,
          });
          current = { ...current, draft: updated, nextGroupIndex: index + 1 };
          progress.current = current;
        } catch (error) {
          if (error instanceof ApiError && (error.status === 0 || error.status === 409)) {
            current.refreshBeforeRetry = true;
          }
          throw error;
        }
      }

      const addedItem = current.draft.items.find((item) => item.item_id === itemId);
      if (!addedItem || addedItem.readiness !== 'READY') {
        current.nextGroupIndex = 0;
        current.refreshBeforeRetry = true;
        throw new DraftConfigurationRejectedError();
      }
      progress.current = null;
      return current.draft;
    },
  });

  useEffect(() => {
    if (previousSelection.current === selection) return;
    previousSelection.current = selection;
    if (progress.current?.itemId != null) {
      progress.current.nextGroupIndex = 0;
      progress.current.refreshBeforeRetry = true;
    }
    mutation.reset();
  }, [selection]);

  const submit = () => {
    if (!ready || submittingGuard.current) return;
    submittingGuard.current = true;
    onSubmittingChange(true);
    mutation.mutate(undefined, {
      onSettled: () => {
        submittingGuard.current = false;
        onSubmittingChange(false);
      },
    });
  };

  if (mutation.isSuccess) {
    return (
      <div className="add-to-draft-result add-to-draft-result--success" role="status" aria-live="polite">
        <span aria-hidden="true">✓</span>
        <div>
          <strong>Agregado a tu pedido</strong>
          <p>El restaurante confirmó el producto en tu pedido.</p>
          <button className="text-button" type="button" onClick={() => mutation.reset()}>Agregar otro igual</button>
        </div>
      </div>
    );
  }

  const copy = mutation.isError ? errorCopy(mutation.error) : null;
  const addOutcomeUnconfirmed = mutation.error instanceof UnconfirmedDraftAddError;

  return (
    <section className="add-to-draft" aria-labelledby="add-to-draft-title">
      <div>
        <p className="panel-kicker">Tu elección</p>
        <h2 id="add-to-draft-title">¿Listo para pedir?</h2>
        <p>{ready ? 'Agrega este producto a tu pedido.' : 'Completa las elecciones obligatorias para continuar.'}</p>
      </div>
      <button className="primary-button" type="button" disabled={!ready || mutation.isPending || addOutcomeUnconfirmed} onClick={submit}>
        {mutation.isPending ? 'Agregando…' : addOutcomeUnconfirmed ? 'Acción sin confirmar' : 'Agregar al pedido'}
      </button>
      {copy && (
        <div className="add-to-draft-result add-to-draft-result--error" role="alert">
          <span aria-hidden="true">!</span>
          <div>
            <strong>{copy.title}</strong>
            <p>{copy.message}</p>
            <div className="add-to-draft-recovery">
              {copy.retryable && <button className="text-button" type="button" onClick={submit}>Intentar nuevamente</button>}
              {!copy.retryable && <Link to="/menu">Volver al menú</Link>}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
