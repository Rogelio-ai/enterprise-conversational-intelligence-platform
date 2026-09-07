import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { AccountPreviewResponse } from '../api/contracts';
import { AccountPreviewLoadingState } from '../components/AccountPreviewLoadingState';
import { DinerHeader } from '../components/DinerHeader';
import { formatPrice, formatQuantity } from '../utils/formatters';

function accountMoney(amount: string, currency: string | null): string {
  return currency ? formatPrice(amount, currency) : `${amount} · moneda no unificada`;
}

function AccountNotices({ preview }: { preview: AccountPreviewResponse }) {
  if (preview.active_check_id === null && !preview.has_active_nonempty_draft) return null;
  return (
    <div className="account-notices" aria-label="Información de tu consumo">
      {preview.active_check_id !== null && (
        <p><strong>Ya existe una cuenta activa.</strong> Esta vista es informativa y no modifica esa cuenta.</p>
      )}
      {preview.has_active_nonempty_draft && (
        <p><strong>Tienes un pedido en borrador.</strong> Se reflejará aquí únicamente después de que el restaurante lo acepte.</p>
      )}
    </div>
  );
}

export function AccountPreviewPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  const headingFocused = useRef(false);
  const accountQuery = useQuery({
    queryKey: ['diner', 'account-preview'],
    queryFn: dinerApi.getAccountPreview,
    retry: false,
  });

  useEffect(() => {
    document.title = 'Mi cuenta · Mesa';
    if (!headingFocused.current && (accountQuery.data || accountQuery.error)) {
      headingFocused.current = true;
      heading.current?.focus();
    }
  }, [accountQuery.data, accountQuery.error]);

  if (accountQuery.isPending) {
    return <div className="diner-page"><DinerHeader /><AccountPreviewLoadingState /></div>;
  }

  if (accountQuery.isError) {
    const network = accountQuery.error instanceof ApiError && accountQuery.error.status === 0;
    return (
      <div className="diner-page">
        <DinerHeader />
        <main className="product-state" role="alert">
          <span className="product-state-mark" aria-hidden="true">!</span>
          <p className="eyebrow">{network ? 'Conexión interrumpida' : 'Cuenta no disponible'}</p>
          <h1 ref={heading} tabIndex={-1}>No pudimos mostrar tu cuenta</h1>
          <p>{network ? 'Revisa tu conexión e intenta nuevamente.' : 'El restaurante no pudo proporcionar esta vista en este momento.'}</p>
          <div className="product-state-actions">
            <button className="primary-button button-link" type="button" onClick={() => accountQuery.refetch()}>Reintentar</button>
            <Link className="secondary-button button-link" to="/menu">Volver al menú</Link>
          </div>
        </main>
      </div>
    );
  }

  const preview = accountQuery.data;
  const empty = preview.lines.length === 0 && preview.eligible_order_ids.length === 0;

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="account-main">
        <header className="account-hero">
          <p className="eyebrow">Vista de consumo</p>
          <h1 ref={heading} tabIndex={-1}>Mi cuenta</h1>
          <p>Consumo de {preview.display_name}, actualizado directamente por el restaurante.</p>
        </header>

        <AccountNotices preview={preview} />

        {empty ? (
          <section className="account-empty">
            <span aria-hidden="true">◇</span>
            <h2>Aún no tienes consumo disponible</h2>
            <p>Tu consumo elegible actual es {accountMoney(preview.eligible_total, preview.currency)}.</p>
            <Link className="primary-button button-link" to="/menu">Volver al menú</Link>
          </section>
        ) : (
          <div className="account-layout">
            <section className="account-consumption" aria-labelledby="account-consumption-title">
              <div className="account-section-heading">
                <p className="panel-kicker">Consumo aceptado</p>
                <h2 id="account-consumption-title">Productos en esta vista</h2>
              </div>
              <ul>
                {preview.lines.map((line) => (
                  <li key={line.order_item_id}>
                    <div className="account-line-heading">
                      <strong>{line.product_name}</strong>
                      <span>{formatQuantity(line.quantity)} × {accountMoney(line.unit_price, preview.currency)}</span>
                    </div>
                    <dl>
                      <div><dt>Descuento</dt><dd>{accountMoney(line.discount_amount, preview.currency)}</dd></div>
                      <div><dt>Importe</dt><dd>{accountMoney(line.commercial_amount, preview.currency)}</dd></div>
                    </dl>
                  </li>
                ))}
              </ul>
            </section>

            <aside className="account-summary-card" aria-labelledby="account-summary-title">
              <p className="panel-kicker">Resumen autoritativo</p>
              <h2 id="account-summary-title">Consumo disponible</h2>
              <strong>{accountMoney(preview.eligible_total, preview.currency)}</strong>
              <p>Esta consulta no crea una cuenta ni reserva tu consumo.</p>
            </aside>
          </div>
        )}
      </main>
      <footer className="shell-footer"><span>Información financiera proporcionada por el restaurante</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
