export function ProductDetailLoadingState() {
  return (
    <main className="product-main" role="status" aria-live="polite">
      <span className="sr-only">Cargando el producto…</span>
      <div className="product-detail-skeleton" aria-hidden="true">
        <div className="skeleton skeleton--back" />
        <div className="skeleton skeleton--product-kicker" />
        <div className="skeleton skeleton--product-title" />
        <div className="skeleton skeleton--product-description" />
        <div className="skeleton skeleton--product-price" />
        <div className="skeleton-panel">
          <div className="skeleton skeleton--name" />
          <div className="skeleton skeleton--copy" />
        </div>
      </div>
    </main>
  );
}
