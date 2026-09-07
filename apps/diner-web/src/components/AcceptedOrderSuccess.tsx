import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import type { RestaurantOrderResponse } from '../api/contracts';
import { formatPrice, formatQuantity } from '../utils/formatters';
import { DinerHeader } from './DinerHeader';

function acceptedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export function AcceptedOrderSuccess({ order }: { order: RestaurantOrderResponse }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = 'Pedido confirmado · Mesa';
    heading.current?.focus();
  }, []);

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="accepted-order" aria-labelledby="accepted-order-title">
        <span className="accepted-order-mark" aria-hidden="true">✓</span>
        <p className="eyebrow">Pedido aceptado</p>
        <h1 ref={heading} id="accepted-order-title" tabIndex={-1}>Tu pedido fue confirmado</h1>
        <p>El restaurante recibió y aceptó tu pedido el {acceptedAt(order.accepted_at)}.</p>

        <section className="accepted-order-summary" aria-labelledby="accepted-summary-title">
          <h2 id="accepted-summary-title">Resumen aceptado</h2>
          <ul>
            {order.items.map((item) => (
              <li key={item.id}>
                <span>{formatQuantity(item.quantity)} × {item.product_name}</span>
                <strong>{formatPrice(item.commercial_amount, order.currency)}</strong>
              </li>
            ))}
          </ul>
          <div><span>Total aceptado</span><strong>{formatPrice(order.payable_total, order.currency)}</strong></div>
        </section>

        <Link className="primary-button button-link" to="/menu">Volver al menú</Link>
      </main>
      <footer className="shell-footer"><span>Pedido confirmado por el restaurante</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
