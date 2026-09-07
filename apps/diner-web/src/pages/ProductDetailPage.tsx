import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import { DinerHeader } from '../components/DinerHeader';
import { ProductConfiguration } from '../components/ProductConfiguration';
import { ProductDetailLoadingState } from '../components/ProductDetailLoadingState';
import { formatPrice, formatQuantity } from '../utils/formatters';

function productErrorCopy(error: unknown) {
  if (error instanceof ApiError && (error.status === 404 || error.state === 'PRODUCT_UNAVAILABLE')) {
    return {
      eyebrow: 'No disponible',
      title: 'Este producto no está disponible',
      message: 'Puede haber cambiado la disponibilidad para tu mesa. Vuelve al menú para explorar otras opciones.',
      retryable: false,
    };
  }
  if (error instanceof ApiError && error.status === 0) {
    return {
      eyebrow: 'Conexión interrumpida',
      title: 'No pudimos cargar el producto',
      message: 'Revisa tu conexión e intenta nuevamente.',
      retryable: true,
    };
  }
  return {
    eyebrow: 'Algo salió mal',
    title: 'No pudimos cargar el producto',
    message: 'El restaurante no pudo mostrar esta información en este momento.',
    retryable: true,
  };
}

export function ProductDetailPage() {
  const { productId = '' } = useParams();
  const numericProductId = Number(productId);
  const validProductId = Number.isInteger(numericProductId) && numericProductId > 0;
  const heading = useRef<HTMLHeadingElement>(null);
  const productQuery = useQuery({
    queryKey: ['diner', 'product', numericProductId],
    queryFn: () => dinerApi.getProduct(numericProductId),
    enabled: validProductId,
  });

  useEffect(() => {
    if (!productQuery.data) return;
    document.title = `${productQuery.data.product.name} · Mesa`;
    heading.current?.focus();
  }, [productQuery.data]);

  if (!validProductId) {
    return (
      <div className="diner-page">
        <DinerHeader />
        <main className="product-state">
          <p className="eyebrow">Producto no encontrado</p>
          <h1>No pudimos abrir este producto</h1>
          <p>Vuelve al menú para elegir una opción disponible.</p>
          <Link className="secondary-button button-link" to="/menu">Volver al menú</Link>
        </main>
      </div>
    );
  }

  if (productQuery.isPending) {
    return <div className="diner-page"><DinerHeader /><ProductDetailLoadingState /></div>;
  }

  if (productQuery.isError) {
    const copy = productErrorCopy(productQuery.error);
    return (
      <div className="diner-page">
        <DinerHeader />
        <main className="product-state" role="alert">
          <span className="product-state-mark" aria-hidden="true">!</span>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p>{copy.message}</p>
          <div className="product-state-actions">
            {copy.retryable && <button className="primary-button button-link" type="button" onClick={() => productQuery.refetch()}>Reintentar</button>}
            <Link className="secondary-button button-link" to="/menu">Volver al menú</Link>
          </div>
        </main>
      </div>
    );
  }

  const { product, fixed_components: fixedComponents, choice_groups: choiceGroups } = productQuery.data;
  const categoryNames = product.category_path.map((category) => category.name);

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="product-main">
        <Link className="back-link" to="/menu"><span aria-hidden="true">←</span> Volver al menú</Link>

        <article className="product-detail">
          <header className="product-detail-hero">
            <div className="product-detail-copy">
              {categoryNames.length > 0 && (
                <nav aria-label="Categorías del producto">
                  <ol className="product-breadcrumbs">
                    {categoryNames.map((name, index) => <li key={`${name}-${index}`}>{name}</li>)}
                  </ol>
                </nav>
              )}
              <div className="product-status-line">
                <span className={`availability-status availability-status--${product.orderable ? 'available' : 'unavailable'}`}>
                  <span aria-hidden="true">{product.orderable ? '✓' : '—'}</span>
                  {product.orderable ? 'Disponible' : 'No disponible'}
                </span>
              </div>
              <h1 ref={heading} tabIndex={-1}>{product.name}</h1>
              {product.description && <p className="product-detail-description">{product.description}</p>}
              <p className="product-detail-price">
                {product.price ? formatPrice(product.price.amount, product.price.currency) : 'Precio no disponible'}
              </p>
            </div>
            <div className="product-monogram" aria-hidden="true">
              <span>{product.name.trim().charAt(0).toLocaleUpperCase('es-MX')}</span>
              <small>De la cocina</small>
            </div>
          </header>

          <div className="product-detail-sections">
            {fixedComponents.length > 0 && (
              <section className="included-panel" aria-labelledby="included-title">
                <p className="panel-kicker">Preparado para ti</p>
                <h2 id="included-title">Incluye</h2>
                <ul>
                  {fixedComponents.map((component) => (
                    <li key={component.product_id}>
                      <span aria-hidden="true">✓</span>
                      <strong>{component.name}</strong>
                      <small>Cantidad {formatQuantity(component.quantity)}</small>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {choiceGroups.length > 0 && product.orderable && (
              <ProductConfiguration key={product.id} productId={product.id} groups={choiceGroups} />
            )}
          </div>

          {!product.orderable && (
            <div className="product-unavailable-notice" role="status">
              <strong>No disponible por el momento</strong>
              <span>Consulta el menú para encontrar otra opción.</span>
            </div>
          )}
        </article>
      </main>
      <footer className="shell-footer"><span>Información proporcionada por el restaurante</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
