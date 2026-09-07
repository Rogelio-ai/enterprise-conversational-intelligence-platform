export function AccountPreviewLoadingState() {
  return (
    <main className="account-main" aria-busy="true" aria-label="Cargando tu cuenta">
      <span className="sr-only">Cargando tu cuenta…</span>
      <div className="skeleton skeleton--title" />
      <div className="account-layout">
        <div className="account-consumption account-consumption--loading">
          {[0, 1].map((item) => <div className="skeleton skeleton--copy" key={item} />)}
        </div>
        <div className="account-summary-card">
          <div className="skeleton skeleton--name" />
          <div className="skeleton skeleton--tabs" />
        </div>
      </div>
    </main>
  );
}
