import { expect, test } from '@playwright/test';

test('WS-DEMO-01 login and populated cross-module walkthrough', async ({ page }) => {
  const fatalResponses: string[] = [];
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 500) {
      fatalResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto('login');
  await page.getByLabel('Correo electrónico').fill('manager@restaurant.demo');
  await page.getByLabel('Contraseña').fill('DemoManager123!');
  await page.getByRole('button', { name: 'Ingresar a operación' }).click();
  await expect(page.getByText('Centro Demo', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('DEMO · datos ficticios')).toBeVisible();

  for (const [link, heading] of [
    ['Host', 'Mesas en servicio'], ['Mesero', 'Solicitudes'], ['Cocina', 'Preparación'],
    ['Caja', 'Caja'], ['Gerencia', 'Gerencia'], ['Inventario', 'Inventario'],
  ] as const) {
    await page.getByRole('link', { name: link, exact: true }).click();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  }

  await expect(page.getByText('Abastos La Estrella (Ficticio)')).toBeVisible();
  await page.getByRole('link', { name: 'Existencias', exact: true }).click();
  await expect(page.getByText('Cerdo ficticio').first()).toBeVisible();
  for (const view of [
    'Recepción', 'Pérdidas', 'Conteos físicos', 'Conciliación',
    'Órdenes de compra', 'Preparaciones', 'Reabastecimiento', 'Lotes',
    'Transferencias', 'Valuación',
  ]) {
    await page.getByRole('link', { name: view, exact: true }).click();
    await expect(page.locator('main')).not.toContainText('No pudimos cargar la inteligencia');
  }
  await page.getByRole('link', { name: 'Lotes', exact: true }).click();
  await expect(page.getByText('DEMO-PREP-LOT-01')).toBeVisible();
  await page.getByRole('link', { name: 'Valuación', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Capas FIFO actuales' })).toBeVisible();
  await expect(page.getByText('FINALIZED · STANDARD_COST')).toBeVisible();

  expect(pageErrors).toEqual([]);
  expect(fatalResponses).toEqual([]);
});
