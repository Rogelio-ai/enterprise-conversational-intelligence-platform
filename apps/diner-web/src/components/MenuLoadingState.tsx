export function MenuLoadingState() {
  return (
    <div className="menu-loading" role="status" aria-live="polite">
      <span className="sr-only">Cargando el menú…</span>
      <div className="skeleton skeleton--title" />
      <div className="skeleton skeleton--tabs" />
      <div className="product-grid" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => (
          <div className="product-card product-card--skeleton" key={item}>
            <div className="skeleton skeleton--eyebrow" />
            <div className="skeleton skeleton--name" />
            <div className="skeleton skeleton--copy" />
            <div className="skeleton skeleton--price" />
          </div>
        ))}
      </div>
    </div>
  );
}
