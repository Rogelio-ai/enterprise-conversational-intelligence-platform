import { useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { DinerHeader } from '../components/DinerHeader';

export function ProductRouteBoundary() {
  const location = useLocation();
  const productName = (location.state as { productName?: string } | null)?.productName;
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${productName || 'Producto'} · Mesa`;
    heading.current?.focus();
  }, [productName]);

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="product-boundary">
        <p className="eyebrow">Producto seleccionado</p>
        <h1 ref={heading} tabIndex={-1}>{productName || 'Tu selección'}</h1>
        <p>Seleccionaste este producto. Vuelve al menú para seguir explorando la carta.</p>
        <Link className="secondary-button button-link" to="/menu">Volver al menú</Link>
      </main>
    </div>
  );
}
