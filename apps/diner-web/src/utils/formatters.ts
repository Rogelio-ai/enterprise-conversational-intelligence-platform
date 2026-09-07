export function formatPrice(amount: string, currency: string): string {
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

export function formatQuantity(quantity: string): string {
  const numericQuantity = Number(quantity);
  if (!Number.isFinite(numericQuantity)) return quantity;
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 }).format(numericQuantity);
}
