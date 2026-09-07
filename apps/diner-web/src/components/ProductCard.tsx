import { Link } from 'react-router-dom';
import type { ProductSummaryResponse } from '../api/contracts';

function formatPrice(amount: string, currency: string): string {
  const numericAmount = Number(amount);
  if (!Number.isFinite(numericAmount)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericAmount);
  } catch {
    return `${amount} ${currency}`;
  }
}

export function ProductCard({ product }: { product: ProductSummaryResponse }) {
  const category = product.category_path.map((item) => item.name).join(' · ');

  return (
    <article className={`product-card${product.orderable ? '' : ' product-card--unavailable'}`}>
      <div className="product-card-topline">
        {category ? <p className="product-category">{category}</p> : <span />}
        {!product.orderable && <span className="availability-badge">No disponible</span>}
      </div>
      <h4>{product.name}</h4>
      {product.description && <p className="product-description">{product.description}</p>}
      <div className="product-card-footer">
        <div>
          <strong className="product-price">
            {product.price ? formatPrice(product.price.amount, product.price.currency) : 'Precio no disponible'}
          </strong>
          {product.configuration_required ? (
            <span className="configuration-note">Requiere elegir opciones</span>
          ) : product.configuration_available ? (
            <span className="configuration-note">Personalizable</span>
          ) : null}
        </div>
        {product.orderable ? (
          <Link
            className="product-action"
            to={`/products/${product.id}`}
            state={{ productName: product.name }}
            aria-label={`Ver ${product.name}`}
          >
            Ver <span aria-hidden="true">→</span>
          </Link>
        ) : (
          <span className="product-action product-action--disabled" aria-label={`${product.name} no está disponible`}>—</span>
        )}
      </div>
    </article>
  );
}
