import { useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, dinerApi } from '../api/client';
import { DinerHeader } from '../components/DinerHeader';
import { MenuLoadingState } from '../components/MenuLoadingState';
import { ProductCard } from '../components/ProductCard';

function menuErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 0) {
    return 'No pudimos conectar con el restaurante. Revisa tu conexión e intenta de nuevo.';
  }
  return 'No pudimos cargar el menú en este momento. Intenta nuevamente.';
}

export function MenuPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  const menuQuery = useQuery({
    queryKey: ['diner', 'menu'],
    queryFn: dinerApi.getMenu,
  });

  useEffect(() => {
    document.title = 'Menú · Mesa';
    heading.current?.focus();
  }, []);

  const productCount = useMemo(
    () => menuQuery.data?.menus.reduce(
      (menuTotal, menu) => menuTotal + menu.sections.reduce(
        (sectionTotal, section) => sectionTotal + section.products.length,
        0,
      ),
      0,
    ) ?? 0,
    [menuQuery.data],
  );

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="menu-main">
        <header className="menu-hero">
          <p className="eyebrow">Descubre la cocina</p>
          <h1 ref={heading} tabIndex={-1}>Menú</h1>
          <p>Explora lo que el restaurante preparó para tu mesa.</p>
        </header>

        {menuQuery.isPending && <MenuLoadingState />}

        {menuQuery.isError && (
          <section className="menu-notice" role="alert">
            <span className="menu-notice-mark" aria-hidden="true">!</span>
            <div>
              <h2>No pudimos mostrar el menú</h2>
              <p>{menuErrorMessage(menuQuery.error)}</p>
              <button className="secondary-button" type="button" onClick={() => menuQuery.refetch()}>Reintentar</button>
            </div>
          </section>
        )}

        {menuQuery.isSuccess && productCount === 0 && (
          <section className="menu-empty">
            <span aria-hidden="true">◇</span>
            <h2>Aún no hay productos para mostrar</h2>
            <p>El personal del restaurante puede ayudarte con las opciones disponibles.</p>
          </section>
        )}

        {menuQuery.isSuccess && productCount > 0 && menuQuery.data.menus
          .filter((menu) => menu.sections.some((section) => section.products.length > 0))
          .map((menu) => (
          <section className="menu-group" key={menu.id} aria-labelledby={`menu-${menu.id}`}>
            <div className="menu-group-heading">
              <div>
                <p className="menu-kicker">Carta del restaurante</p>
                <h2 id={`menu-${menu.id}`}>{menu.name}</h2>
              </div>
              <nav className="section-nav" aria-label={`Secciones de ${menu.name}`}>
                {menu.sections.filter((section) => section.products.length > 0).map((section) => (
                  <a key={section.id} href={`#section-${menu.id}-${section.id}`}>{section.name}</a>
                ))}
              </nav>
            </div>

            {menu.sections.filter((section) => section.products.length > 0).map((section) => (
              <section className="menu-section" id={`section-${menu.id}-${section.id}`} key={section.id} aria-labelledby={`section-title-${menu.id}-${section.id}`}>
                <header className="menu-section-heading">
                  <h3 id={`section-title-${menu.id}-${section.id}`}>{section.name}</h3>
                  <span>{section.products.length} {section.products.length === 1 ? 'opción' : 'opciones'}</span>
                </header>
                <div className="product-grid">
                  {section.products.map((product) => <ProductCard key={product.id} product={product} />)}
                </div>
              </section>
            ))}
          </section>
          ))}
      </main>
      <footer className="shell-footer"><span>Precios y disponibilidad proporcionados por el restaurante</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
