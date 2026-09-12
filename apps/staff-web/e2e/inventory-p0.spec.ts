import { expect, test, type Page } from '@playwright/test';

const PASSWORD = 'WS34 Browser Test 123!';
const OPERATOR = 'ws34-b7-e2e-operator@example.test';
const APPROVER = 'ws34-b7-e2e-approver@example.test';

async function login(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Correo electrónico').fill(email);
  const password = page.getByLabel('Contraseña');
  await password.fill(PASSWORD);
  await password.press('Enter');
  await expect(page.getByText('WS-34 B7 Isolated Location', { exact: true })).toBeVisible();
}

async function switchActor(page: Page, email: string) {
  await page.getByRole('button', { name: 'Salir' }).click();
  await login(page, email);
}

async function openInventory(page: Page, view?: string) {
  await page.getByRole('link', { name: 'Inventario', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inventario' })).toBeVisible();
  if (view) await page.getByRole('link', { name: view }).click();
}

async function addReceiptLine(page: Page, offeringIndex: number, received: string, cost: string) {
  await page.getByLabel('Artículo / presentación').selectOption({ index: offeringIndex });
  await page.getByLabel('Recibido', { exact: true }).fill(received);
  await page.getByLabel('Aceptado', { exact: true }).fill(received);
  await page.getByLabel('Costo unitario', { exact: true }).fill(cost);
  await page.getByRole('button', { name: 'Agregar línea' }).click();
}

async function addCountLine(page: Page, itemName: string, amount: string) {
  const optionValue = await page.getByRole('option', { name: new RegExp(itemName) }).getAttribute('value');
  if (!optionValue) throw new Error(`Count option for ${itemName} has no value`);
  await page.getByLabel('Artículo').selectOption(optionValue);
  await page.getByLabel('Cantidad contada').fill(amount);
  await page.getByRole('button', { name: 'Guardar observación' }).click();
  await expect(page.getByText(new RegExp(`CONTADO ${amount}`)).first()).toBeVisible();
}

test('WS-34-B7 deterministic Staff Web P0 journey reaches real inventory authorities', async ({ page }) => {
  await login(page, OPERATOR);
  await openInventory(page, 'Existencias');
  await expect(page.getByRole('heading', { name: 'Stock actual por almacén' })).toBeVisible();
  await expect(page.getByText('Tomate E2E')).toBeVisible();
  await expect(page.getByText('10 UNIT').first()).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Costos' })).toBeVisible();
  await expect(page.getByText(/Estándar.*10/).first()).toBeVisible();
  const hiddenLocationStatus = await page.evaluate(async () => {
    const credential = JSON.parse(sessionStorage.getItem('staff-auth-session-v1')!);
    return (await fetch('/api/inventory/intelligence?location_id=2147483647', {
      headers: { Authorization: `Bearer ${credential.accessToken}` },
    })).status;
  });
  expect(hiddenLocationStatus).toBe(404);

  await page.getByRole('link', { name: 'Recepción' }).click();
  await page.getByLabel('Proveedor').selectOption({ label: 'Proveedor E2E' });
  await addReceiptLine(page, 1, '2', '20');
  await addReceiptLine(page, 2, '3', '6');
  await expect(page.getByRole('button', { name: 'Quitar línea 2' })).toBeVisible();
  await page.getByLabel('Costo línea 2').fill('5');
  await page.getByRole('button', { name: 'Crear un DRAFT con todas las líneas' }).click();
  await expect(page.getByText('DRAFT · SIN CAMBIO DE STOCK')).toBeVisible();
  await expect(page.getByText('No publicados')).toBeVisible();
  await page.getByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }).click();
  await expect(page.getByText('ACCEPTED · STOCK PUBLICADO')).toBeVisible();

  await page.getByRole('link', { name: 'Existencias' }).click();
  await expect(page.getByText('12 UNIT')).toBeVisible();
  await expect(page.getByText('13 UNIT')).toBeVisible();
  await expect(page.getByText(/Última compra.*20/)).toBeVisible();

  await page.getByRole('link', { name: 'Pérdidas' }).click();
  await page.getByLabel('Artículo').selectOption({ label: 'Tomate E2E' });
  await page.getByLabel('Cantidad').fill('1');
  await page.getByLabel('Fecha/hora de ocurrencia (opcional)').fill('2026-09-10T08:30');
  await page.getByLabel(/Razón/).fill('Pérdida E2E observada');
  await page.getByRole('button', { name: 'Crear DRAFT' }).click();
  await expect(page.getByText(/Ocurrencia autoritativa/)).toBeVisible();
  await page.getByRole('button', { name: 'Enviar / publicar' }).click();
  await expect(page.getByText(/APROBACIÓN OBLIGATORIA/)).toBeVisible();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Pérdidas');
  await page.getByRole('button', { name: /WASTE · PENDING_APPROVAL/ }).click();
  await page.getByRole('button', { name: 'Aprobar y publicar' }).click();
  await expect(page.getByText(/Historial publicado inmutable/)).toBeVisible();
  await page.getByRole('link', { name: 'Existencias' }).click();
  await expect(page.getByText('11 UNIT')).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Conteos físicos');
  await page.getByRole('button', { name: 'Abrir conteo' }).click();
  await addCountLine(page, 'Sal E2E', '12');
  await page.getByRole('button', { name: 'Enviar' }).click();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Conteos físicos');
  await page.getByRole('button', { name: /PARTIAL · SUBMITTED/ }).click();
  await page.getByRole('button', { name: 'Aprobar' }).click();
  await page.getByRole('button', { name: 'Publicar ajustes' }).click();
  await expect(page.getByText(/PARTIAL · POSTED/).first()).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Conteos físicos');
  await page.getByLabel('Alcance').selectOption('FULL');
  await page.getByRole('button', { name: 'Abrir conteo' }).click();
  await addCountLine(page, 'Tomate E2E', '11');
  await page.getByRole('button', { name: 'Enviar' }).click();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Conteos físicos');
  await page.getByRole('button', { name: /FULL · SUBMITTED/ }).click();
  await page.getByRole('button', { name: 'Aprobar' }).click();
  await page.getByRole('button', { name: 'Publicar ajustes' }).click();
  await expect(page.getByRole('alert')).toContainText('FULL count is incomplete');
  await expect(page.getByText('NO CONTADO')).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Conteos físicos');
  await page.getByLabel('Alcance').selectOption('FULL');
  await page.getByRole('button', { name: 'Abrir conteo' }).click();
  await addCountLine(page, 'Tomate E2E', '11');
  await addCountLine(page, 'Sal E2E', '12');
  await page.getByRole('button', { name: 'Enviar' }).click();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Conteos físicos');
  await page.getByRole('button', { name: /FULL · SUBMITTED/ }).click();
  await page.getByRole('button', { name: 'Aprobar' }).click();
  await page.getByRole('button', { name: 'Publicar ajustes' }).click();
  await expect(page.getByText(/FULL · POSTED/).first()).toBeVisible();

  await page.getByRole('link', { name: 'Conciliación' }).click();
  await page.getByLabel('Línea de conteo publicado').selectOption({ index: 1 });
  await page.getByLabel('Inicio del periodo').fill('2026-09-01T00:00');
  await page.getByRole('button', { name: 'Crear conciliación OPEN' }).click();
  await expect(page.getByText(/Conciliación #\d+ · OPEN/)).toBeVisible();
  await expect(page.getByText('Entradas')).toBeVisible();
  await expect(page.getByText('Consumo teórico')).toBeVisible();
  await expect(page.getByText('Pérdidas registradas')).toBeVisible();
  await expect(page.getByText('Conteo físico')).toBeVisible();
  await expect(page.getByText('Varianza sin explicar')).toBeVisible();
  await page.getByRole('button', { name: 'Cerrar y calcular' }).click();
  await expect(page.getByText(/Conciliación #\d+ · CLOSED/)).toBeVisible();

  await page.getByRole('link', { name: 'Resumen' }).click();
  await expect(page.getByRole('heading', { name: 'Entradas aceptadas recientes' })).toBeVisible();
  await page.getByRole('link', { name: 'Existencias' }).click();
  await expect(page.getByText('11 UNIT')).toBeVisible();
  await expect(page.getByText('12 UNIT')).toBeVisible();
  await expect(page.getByText(/Última compra.*20/)).toBeVisible();
});
