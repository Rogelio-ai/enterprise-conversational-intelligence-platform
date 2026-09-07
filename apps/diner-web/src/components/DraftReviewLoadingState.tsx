export function DraftReviewLoadingState() {
  return (
    <main className="order-main" aria-busy="true" aria-label="Cargando tu pedido">
      <div className="skeleton skeleton--title" />
      <span className="sr-only">Cargando tu pedido…</span>
      <div className="draft-list">
        {[0, 1].map((item) => (
          <div className="draft-line draft-line--skeleton" key={item}>
            <div className="skeleton skeleton--name" />
            <div className="skeleton skeleton--copy" />
            <div className="skeleton skeleton--tabs" />
          </div>
        ))}
      </div>
    </main>
  );
}
