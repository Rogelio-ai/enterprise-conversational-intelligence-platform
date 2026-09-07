import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { DraftItemResponse, DraftResponse } from '../api/contracts';
import { DinerHeader } from '../components/DinerHeader';
import { DraftReviewLoadingState } from '../components/DraftReviewLoadingState';
import { ProductConfiguration, type ConfiguredProductSelection } from '../components/ProductConfiguration';
import { formatQuantity } from '../utils/formatters';

const draftQueryKey = ['diner', 'order-draft'] as const;

type DraftEditOperation =
  | { kind: 'quantity'; itemId: number; quantity: string }
  | { kind: 'remove'; itemId: number }
  | { kind: 'configuration'; itemId: number; selection: ConfiguredProductSelection };

interface DraftEditResult {
  draft: DraftResponse;
  operation: DraftEditOperation;
  outcome: 'updated' | 'conflict' | 'reconciled';
  applied: boolean;
}

function selectedOptionIds(item: DraftItemResponse, groupId: number): number[] {
  return item.selections
    .filter((selection) => selection.group_id === groupId)
    .map((selection) => selection.choice_option_id)
    .sort((left, right) => left - right);
}

function canonicalQuantity(value: string): string {
  const [wholePart, fractionalPart = ''] = value.trim().replace(',', '.').split('.');
  const whole = wholePart.replace(/^0+(?=\d)/, '');
  const fractional = fractionalPart.replace(/0+$/, '');
  return fractional ? `${whole}.${fractional}` : whole;
}

function operationIsApplied(operation: DraftEditOperation, draft: DraftResponse): boolean {
  const item = draft.items.find((candidate) => candidate.item_id === operation.itemId);
  if (operation.kind === 'remove') return !item;
  if (!item) return false;
  if (operation.kind === 'quantity') return canonicalQuantity(item.quantity) === canonicalQuantity(operation.quantity);
  return operation.selection.groups.every((group) => {
    const expected = [...group.option_ids].sort((left, right) => left - right);
    const actual = selectedOptionIds(item, group.group_id);
    return expected.length === actual.length && expected.every((optionId, index) => optionId === actual[index]);
  });
}

function draftErrorCopy(error: unknown) {
  if (error instanceof ApiError && error.status === 0) {
    return {
      eyebrow: 'Conexión interrumpida',
      title: 'No pudimos cargar tu pedido',
      message: 'Revisa tu conexión e intenta nuevamente.',
    };
  }
  return {
    eyebrow: 'Algo salió mal',
    title: 'No pudimos cargar tu pedido',
    message: 'El restaurante no pudo mostrar tu pedido en este momento.',
  };
}

function mutationFeedback(result: DraftEditResult | undefined, error: unknown) {
  if (error) {
    if (error instanceof ApiError && error.status === 422) {
      return { tone: 'error', text: 'El restaurante no aceptó el cambio. Revisa el valor o la configuración.' };
    }
    return { tone: 'error', text: 'No pudimos actualizar tu pedido. Conservamos los datos que estabas editando.' };
  }
  if (!result) return null;
  if (result.outcome === 'conflict') {
    return { tone: 'notice', text: 'Tu pedido cambió en otro lugar. Mostramos la versión más reciente para que la revises.' };
  }
  if (result.outcome === 'reconciled' && !result.applied) {
    return { tone: 'notice', text: 'El cambio no quedó aplicado. Mostramos el estado confirmado por el restaurante.' };
  }
  if (result.outcome === 'reconciled') {
    return { tone: 'success', text: 'Confirmamos el cambio al volver a consultar tu pedido.' };
  }
  const text = result.operation.kind === 'remove'
    ? 'Producto eliminado de tu pedido.'
    : result.operation.kind === 'quantity'
      ? 'Cantidad actualizada.'
      : 'Configuración actualizada.';
  return { tone: 'success', text };
}

function QuantityEditor({
  item,
  disabled,
  onSubmit,
}: {
  item: DraftItemResponse;
  disabled: boolean;
  onSubmit: (quantity: string) => void;
}) {
  const [quantity, setQuantity] = useState(item.quantity);
  useEffect(() => setQuantity(item.quantity), [item.quantity]);
  const normalized = quantity.trim().replace(',', '.');
  const valid = /^\d+(?:\.\d{1,4})?$/.test(normalized) && /[1-9]/.test(normalized);
  const unchanged = valid && canonicalQuantity(normalized) === canonicalQuantity(item.quantity);
  const inputId = `draft-quantity-${item.item_id}`;

  return (
    <div className="draft-quantity">
      <label htmlFor={inputId}>Cantidad</label>
      <div>
        <input
          id={inputId}
          type="text"
          inputMode="decimal"
          value={quantity}
          disabled={disabled}
          aria-invalid={quantity.length > 0 && !valid}
          onChange={(event) => setQuantity(event.target.value)}
        />
        <button type="button" disabled={disabled || !valid || unchanged} onClick={() => onSubmit(normalized)}>
          Actualizar
        </button>
      </div>
      {!valid && quantity.length > 0 && <small>Escribe una cantidad mayor que cero, con hasta cuatro decimales.</small>}
    </div>
  );
}

function ConfigurationEditor({
  item,
  disabled,
  onCancel,
  onSubmit,
}: {
  item: DraftItemResponse;
  disabled: boolean;
  onCancel: () => void;
  onSubmit: (selection: ConfiguredProductSelection) => void;
}) {
  const productQuery = useQuery({
    queryKey: ['diner', 'product', item.product_id],
    queryFn: () => dinerApi.getProduct(item.product_id),
  });
  const initialSelection = useMemo<ConfiguredProductSelection>(() => ({
    product_id: item.product_id,
    groups: productQuery.data?.choice_groups.map((group) => ({
      group_id: group.id,
      option_ids: selectedOptionIds(item, group.id).filter((optionId) => (
        group.options.some((option) => option.id === optionId)
      )),
    })) ?? [],
  }), [item, productQuery.data]);
  const [selection, setSelection] = useState<ConfiguredProductSelection | null>(null);
  const [ready, setReady] = useState(false);

  if (productQuery.isPending) {
    return <div className="draft-configuration-loading" role="status">Cargando opciones…</div>;
  }
  if (productQuery.isError) {
    return (
      <div className="draft-inline-error" role="alert">
        <p>No pudimos cargar las opciones actuales.</p>
        <button type="button" onClick={() => productQuery.refetch()}>Reintentar</button>
        <button type="button" onClick={onCancel}>Cancelar</button>
      </div>
    );
  }

  return (
    <div className="draft-configuration-editor">
      <ProductConfiguration
        key={`${item.item_id}-${item.product_id}`}
        productId={item.product_id}
        groups={productQuery.data.choice_groups}
        initialSelection={initialSelection}
        disabled={disabled}
        onSelectionChange={(next, complete) => { setSelection(next); setReady(complete); }}
      />
      <div className="draft-editor-actions">
        <button className="secondary-button" type="button" disabled={disabled} onClick={onCancel}>Cancelar</button>
        <button className="primary-button" type="button" disabled={disabled || !ready || !selection} onClick={() => selection && onSubmit(selection)}>
          {disabled ? 'Guardando…' : 'Guardar configuración'}
        </button>
      </div>
    </div>
  );
}

function DraftLine({
  item,
  disabled,
  editingConfiguration,
  onEditConfiguration,
  onCancelConfiguration,
  onOperation,
}: {
  item: DraftItemResponse;
  disabled: boolean;
  editingConfiguration: boolean;
  onEditConfiguration: () => void;
  onCancelConfiguration: () => void;
  onOperation: (operation: DraftEditOperation) => void;
}) {
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const groups = Array.from(new Map(item.selections.map((selection) => [selection.group_id, selection.group_name])).entries());
  const headingId = `draft-item-${item.item_id}`;
  const readiness = item.readiness === 'READY' ? 'Listo' : item.readiness === 'INCOMPLETE' ? 'Configuración pendiente' : 'Requiere revisión';

  return (
    <article className="draft-line" aria-labelledby={headingId}>
      <header className="draft-line-heading">
        <div>
          <p className="panel-kicker">En tu pedido</p>
          <h2 id={headingId}>{item.product_name}</h2>
        </div>
        <span className={`draft-readiness draft-readiness--${item.readiness.toLowerCase()}`}>{readiness}</span>
      </header>

      {groups.length > 0 && (
        <div className="draft-selections" aria-label={`Configuración de ${item.product_name}`}>
          {groups.map(([groupId, groupName]) => (
            <div key={groupId}>
              <strong>{groupName}</strong>
              <span>{item.selections.filter((selection) => selection.group_id === groupId).map((selection) => selection.selected_product_name).join(', ')}</span>
            </div>
          ))}
        </div>
      )}
      {item.fixed_components.length > 0 && (
        <div className="draft-selections" aria-label={`Componentes incluidos en ${item.product_name}`}>
          {item.fixed_components.map((component) => (
            <div key={component.product_id}>
              <strong>Incluye</strong>
              <span>{component.product_name} · Cantidad {formatQuantity(component.quantity)}</span>
            </div>
          ))}
        </div>
      )}
      {item.missing_choice_groups.length > 0 && (
        <div className="draft-missing-groups" role="status">
          <strong>Configuración pendiente</strong>
          <span>{item.missing_choice_groups.map((group) => group.group_name).join(', ')}</span>
        </div>
      )}

      <div className="draft-line-edit-row">
        <QuantityEditor item={item} disabled={disabled} onSubmit={(quantity) => onOperation({ kind: 'quantity', itemId: item.item_id, quantity })} />
        <div className="draft-line-actions">
          {item.composition_id !== null && !editingConfiguration && (
            <button type="button" disabled={disabled} onClick={onEditConfiguration}>Editar configuración</button>
          )}
          {!confirmingRemove ? (
            <button className="draft-remove" type="button" disabled={disabled} onClick={() => setConfirmingRemove(true)}>Quitar</button>
          ) : (
            <div className="draft-remove-confirm" role="group" aria-label={`Confirmar eliminación de ${item.product_name}`}>
              <span>¿Quitar este producto?</span>
              <button type="button" disabled={disabled} onClick={() => setConfirmingRemove(false)}>Cancelar</button>
              <button className="draft-remove" type="button" disabled={disabled} onClick={() => onOperation({ kind: 'remove', itemId: item.item_id })}>Sí, quitar</button>
            </div>
          )}
        </div>
      </div>

      {editingConfiguration && (
        <ConfigurationEditor
          item={item}
          disabled={disabled}
          onCancel={onCancelConfiguration}
          onSubmit={(selection) => onOperation({ kind: 'configuration', itemId: item.item_id, selection })}
        />
      )}
    </article>
  );
}

export function DraftReviewPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  const headingFocused = useRef(false);
  const queryClient = useQueryClient();
  const [editingConfigurationItemId, setEditingConfigurationItemId] = useState<number | null>(null);
  const [editRevision, setEditRevision] = useState(0);
  const draftQuery = useQuery({
    queryKey: draftQueryKey,
    queryFn: dinerApi.getOrderDraft,
    retry: false,
  });

  useEffect(() => {
    document.title = 'Mi pedido · Mesa';
    if (!headingFocused.current && (draftQuery.data || draftQuery.error)) {
      headingFocused.current = true;
      heading.current?.focus();
    }
  }, [draftQuery.data, draftQuery.error]);

  const editMutation = useMutation({
    mutationFn: async (operation: DraftEditOperation): Promise<DraftEditResult> => {
      const currentDraft = queryClient.getQueryData<DraftResponse>(draftQueryKey);
      if (!currentDraft) throw new Error('Authoritative draft is unavailable');
      let latestDraft = currentDraft;
      try {
        if (operation.kind === 'quantity') {
          latestDraft = await dinerApi.setDraftItemQuantity(operation.itemId, {
            quantity: operation.quantity,
            expected_version: latestDraft.version,
          });
        } else if (operation.kind === 'remove') {
          latestDraft = await dinerApi.removeDraftItem(operation.itemId, latestDraft.version);
        } else {
          for (const group of operation.selection.groups) {
            latestDraft = await dinerApi.replaceDraftGroupSelections(operation.itemId, group.group_id, {
              option_ids: group.option_ids,
              expected_version: latestDraft.version,
            });
            queryClient.setQueryData(draftQueryKey, latestDraft);
          }
        }
        return { draft: latestDraft, operation, outcome: 'updated', applied: true };
      } catch (error) {
        if (error instanceof ApiError && (error.status === 0 || error.status === 409)) {
          const authoritative = await dinerApi.getOrderDraft();
          return {
            draft: authoritative,
            operation,
            outcome: error.status === 409 ? 'conflict' : 'reconciled',
            applied: operationIsApplied(operation, authoritative),
          };
        }
        throw error;
      }
    },
    onSuccess: (result) => {
      queryClient.setQueryData(draftQueryKey, result.draft);
      setEditRevision((current) => current + 1);
      if (result.operation.kind === 'configuration') setEditingConfigurationItemId(null);
    },
  });

  if (draftQuery.isPending) {
    return <div className="diner-page"><DinerHeader /><DraftReviewLoadingState /></div>;
  }

  const noDraft = draftQuery.error instanceof ApiError && draftQuery.error.status === 404;
  if (draftQuery.isError && !noDraft) {
    const copy = draftErrorCopy(draftQuery.error);
    return (
      <div className="diner-page">
        <DinerHeader />
        <main className="product-state" role="alert">
          <span className="product-state-mark" aria-hidden="true">!</span>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1 ref={heading} tabIndex={-1}>{copy.title}</h1>
          <p>{copy.message}</p>
          <div className="product-state-actions">
            <button className="primary-button button-link" type="button" onClick={() => draftQuery.refetch()}>Reintentar</button>
            <Link className="secondary-button button-link" to="/menu">Volver al menú</Link>
          </div>
        </main>
      </div>
    );
  }

  const draft = draftQuery.data;
  const empty = !draft || draft.items.length === 0;
  const feedback = mutationFeedback(editMutation.data, editMutation.error);

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="order-main">
        <header className="order-hero">
          <p className="eyebrow">Revisa antes de continuar</p>
          <h1 ref={heading} tabIndex={-1}>Mi pedido</h1>
          <p>{empty ? 'Tu pedido todavía está vacío.' : 'Aquí puedes revisar y ajustar lo que pediste.'}</p>
        </header>

        {feedback && (
          <div className={`draft-feedback draft-feedback--${feedback.tone}`} role={feedback.tone === 'error' ? 'alert' : 'status'} aria-live="polite">
            <span aria-hidden="true">{feedback.tone === 'success' ? '✓' : feedback.tone === 'error' ? '!' : '↻'}</span>
            <p>{feedback.text}</p>
          </div>
        )}

        {empty ? (
          <section className="draft-empty">
            <span aria-hidden="true">◇</span>
            <h2>Tu pedido está vacío</h2>
            <p>Explora el menú y agrega algo cuando estés listo.</p>
            <Link className="primary-button button-link" to="/menu">Ver el menú</Link>
          </section>
        ) : (
          <>
            <div className="draft-list">
              {draft.items.map((item) => (
                <DraftLine
                  key={`${item.item_id}-${editRevision}`}
                  item={item}
                  disabled={editMutation.isPending}
                  editingConfiguration={editingConfigurationItemId === item.item_id}
                  onEditConfiguration={() => { editMutation.reset(); setEditingConfigurationItemId(item.item_id); }}
                  onCancelConfiguration={() => setEditingConfigurationItemId(null)}
                  onOperation={(operation) => editMutation.mutate(operation)}
                />
              ))}
            </div>
            <aside className={`draft-ready draft-ready--${draft.readiness.toLowerCase()}`}>
              <strong>{draft.readiness === 'READY' ? 'Tu pedido está listo para el siguiente paso' : 'Tu pedido necesita una revisión'}</strong>
              <span>{draft.readiness === 'READY' ? 'Puedes seguir ajustándolo antes de confirmar más adelante.' : 'Revisa las líneas marcadas antes de continuar.'}</span>
            </aside>
          </>
        )}
      </main>
      <footer className="shell-footer"><span>Información del pedido proporcionada por el restaurante</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
