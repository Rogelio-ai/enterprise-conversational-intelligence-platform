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

async function expectPageFitsViewport(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test('WS-34-B9 deterministic Staff Web P0 journey reaches real inventory authorities', async ({ page }) => {
  test.setTimeout(600_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, OPERATOR);
  await openInventory(page, 'Existencias');
  await expect(page.getByRole('heading', { name: 'Stock actual por almacén' })).toBeVisible();
  await expect(page.getByText('Tomate E2E')).toBeVisible();
  await expect(page.getByText('10 UNIT').first()).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Costos' })).toBeVisible();
  await expect(page.getByText(/Costo estándar.*10/i).first()).toBeVisible();
  await expectPageFitsViewport(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await expectPageFitsViewport(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await expectPageFitsViewport(page);
  const hiddenLocationStatus = await page.evaluate(async () => {
    const credential = JSON.parse(sessionStorage.getItem('staff-auth-session-v1')!);
    return (await fetch('/api/inventory/intelligence?location_id=2147483647', {
      headers: { Authorization: `Bearer ${credential.accessToken}` },
    })).status;
  });
  expect(hiddenLocationStatus).toBe(404);

  const receivingLink = page.getByRole('link', { name: 'Recepción' });
  await receivingLink.focus();
  await expect(receivingLink).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Nueva recepción directa' })).toBeVisible();
  await page.getByLabel('Proveedor').selectOption({ label: 'Proveedor E2E' });
  await addReceiptLine(page, 1, '2', '20');
  await addReceiptLine(page, 2, '3', '6');
  await expect(page.getByRole('button', { name: 'Quitar línea 2' })).toBeVisible();
  await page.getByLabel('Costo línea 2').fill('5');
  await expectPageFitsViewport(page);
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
  await expectPageFitsViewport(page);
  await page.getByLabel('Artículo').selectOption({ label: 'Tomate E2E' });
  await page.getByLabel('Cantidad').fill('1');
  await page.getByLabel('Fecha/hora de ocurrencia (opcional)').fill('2026-09-10T08:30');
  await page.getByLabel(/Razón/).fill('Pérdida E2E observada');
  await page.getByRole('button', { name: 'Crear DRAFT' }).click();
  await expect(page.getByText(/Ocurrencia confirmada/)).toBeVisible();
  await page.getByRole('button', { name: 'Enviar / publicar' }).click();
  await expect(page.getByText(/APROBACIÓN OBLIGATORIA/)).toBeVisible();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Pérdidas');
  await page.getByRole('button', { name: /Merma operativa · PENDING_APPROVAL/ }).click();
  await page.getByRole('button', { name: 'Aprobar y publicar' }).click();
  await expect(page.getByText(/Historial publicado inmutable/)).toBeVisible();
  await page.getByRole('link', { name: 'Existencias' }).click();
  await expect(page.getByText('11 UNIT')).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Conteos físicos');
  await expectPageFitsViewport(page);
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
  await expect(page.getByRole('alert')).toContainText('El conteo FULL está incompleto');
  await expect(page.getByText('NO CONTADO').first()).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Conteos físicos');
  await page.getByLabel('Alcance').selectOption('FULL');
  await page.getByRole('button', { name: 'Abrir conteo' }).click();
  await addCountLine(page, 'Tomate E2E', '11');
  await addCountLine(page, 'Sal E2E', '12');
  await addCountLine(page, 'Salsa preparada E2E', '0');
  await page.getByRole('button', { name: 'Enviar' }).click();

  await switchActor(page, APPROVER);
  await openInventory(page, 'Conteos físicos');
  await page.getByRole('button', { name: /FULL · SUBMITTED/ }).click();
  await page.getByRole('button', { name: 'Aprobar' }).click();
  await page.getByRole('button', { name: 'Publicar ajustes' }).click();
  await expect(page.getByText(/FULL · POSTED/).first()).toBeVisible();

  await page.getByRole('link', { name: 'Conciliación' }).click();
  await expectPageFitsViewport(page);
  await page.getByLabel('Línea de conteo publicado').selectOption({ index: 1 });
  await page.getByLabel('Inicio del periodo').fill('2026-09-01T00:00');
  await page.getByRole('button', { name: 'Crear conciliación OPEN' }).click();
  await expect(page.getByText(/Conciliación #\d+ · OPEN/)).toBeVisible();
  await expect(page.getByText('Entradas recibidas')).toBeVisible();
  await expect(page.getByText('Consumo teórico')).toBeVisible();
  await expect(page.getByText('Pérdidas registradas')).toBeVisible();
  await expect(page.getByText('Observación física')).toBeVisible();
  await expect(page.getByText('Varianza sin explicar')).toBeVisible();
  await page.getByRole('button', { name: 'Cerrar y calcular' }).click();
  await expect(page.getByText(/Conciliación #\d+ · CLOSED/)).toBeVisible();

  await page.getByRole('link', { name: 'Resumen' }).click();
  await expect(page.getByRole('heading', { name: 'Entradas aceptadas recientes' })).toBeVisible();
  await page.getByRole('link', { name: 'Existencias' }).click();
  await page.setViewportSize({ width: 1024, height: 768 });
  await expectPageFitsViewport(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expectPageFitsViewport(page);
  await expect(page.getByText('11 UNIT')).toBeVisible();
  await expect(page.getByText('12 UNIT')).toBeVisible();
  await expect(page.getByText(/Última compra.*20/)).toBeVisible();

  await switchActor(page, OPERATOR);
  await openInventory(page, 'Órdenes de compra');
  await page.getByLabel('Proveedor').selectOption({ label: 'Proveedor E2E' });
  await page.getByLabel('Presentación').selectOption({ index: 1 });
  await page.getByLabel('Cantidad ordenada').fill('2'); await page.getByLabel('Precio acordado').fill('18'); await page.getByRole('button', { name: 'Agregar línea' }).click();
  await page.getByLabel('Presentación').selectOption({ index: 2 });
  await page.getByLabel('Cantidad ordenada').fill('3'); await page.getByLabel('Precio acordado').fill('5'); await page.getByRole('button', { name: 'Agregar línea' }).click();
  await page.getByRole('button', { name: 'Crear DRAFT' }).click(); await expect(page.getByText(/DRAFT/).first()).toBeVisible();
  await page.getByRole('link', { name: 'Existencias' }).click(); await expect(page.getByText('11 UNIT')).toBeVisible(); await expect(page.getByText('12 UNIT')).toBeVisible();
  await page.getByRole('link', { name: 'Órdenes de compra' }).click(); await page.getByRole('button', { name: /^#\d+ · DRAFT/ }).click(); await page.getByRole('button', { name: 'Enviar a aprobación' }).click();
  await switchActor(page, APPROVER); await openInventory(page, 'Órdenes de compra'); await page.getByRole('button', { name: /SUBMITTED/ }).click(); await page.getByRole('button', { name: 'Aprobar' }).click();
  await page.getByRole('link', { name: 'Existencias' }).click(); await expect(page.getByText('11 UNIT')).toBeVisible(); await expect(page.getByText('12 UNIT')).toBeVisible();
  await page.getByRole('link', { name: 'Recepción' }).click(); await page.getByLabel('Orden de compra (opcional)').selectOption({ index: 1 }); await page.getByLabel('Artículo / presentación').selectOption({ index: 1 }); await page.getByLabel('Recibido', { exact: true }).fill('1'); await page.getByLabel('Aceptado', { exact: true }).fill('1'); await page.getByLabel('Costo unitario').fill('20'); await page.getByRole('button', { name: 'Agregar línea' }).click(); await page.getByRole('button', { name: 'Crear un DRAFT con todas las líneas' }).click(); await page.getByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }).click();
  await page.getByRole('link', { name: 'Órdenes de compra' }).click(); await page.getByRole('button', { name: /PARTIALLY_RECEIVED/ }).click(); await expect(page.getByText(/Pendiente 1/)).toBeVisible();
  await page.getByRole('link', { name: 'Recepción' }).click(); await page.getByLabel('Orden de compra (opcional)').selectOption({ index: 1 }); await addReceiptLine(page, 1, '1', '18'); await addReceiptLine(page, 2, '3', '5'); await page.getByRole('button', { name: 'Crear un DRAFT con todas las líneas' }).click(); await page.getByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }).click();
  await page.getByRole('link', { name: 'Órdenes de compra' }).click(); await page.getByRole('button', { name: /^#\d+ · RECEIVED ·/ }).click();
  const firstLineCostEvidence = page.locator('article.inventory-state-note').filter({ hasText: 'Línea 1' }).locator('small').filter({ hasText: /variación.*1/i });
  await expect(firstLineCostEvidence).toBeVisible(); await page.getByRole('button', { name: 'Cerrar' }).click(); await expect(page.getByText(/CLOSED/).first()).toBeVisible(); await expectPageFitsViewport(page);

  await page.getByRole('link', { name: 'Preparaciones' }).click();
  await page.getByLabel('Artículo preparado').selectOption({ label: 'Salsa preparada E2E · UNIT' }); await page.getByLabel('Salida esperada').fill('4');
  await page.getByLabel('Artículo de entrada').selectOption({ label: 'Tomate E2E · UNIT' }); await page.getByLabel('Cantidad esperada').fill('2'); await page.getByLabel('Base del rendimiento').check(); await page.getByRole('button', { name: 'Agregar entrada' }).click();
  await page.getByLabel('Artículo de entrada').selectOption({ label: 'Sal E2E · UNIT' }); await page.getByLabel('Cantidad esperada').fill('3'); await page.getByRole('button', { name: 'Agregar entrada' }).click(); await page.getByRole('button', { name: 'Publicar versión inmutable' }).click();
  const recipeOption = await page.getByLabel('Receta publicada').getByRole('option', { name: /Salsa preparada E2E · revisión 1/ }).getAttribute('value');
  if (!recipeOption) throw new Error('Published preparation recipe has no selectable value');
  await page.getByLabel('Receta publicada').selectOption(recipeOption); await page.getByRole('button', { name: 'Crear lote DRAFT' }).click(); await expect(page.locator('p.inventory-lifecycle', { hasText: /^Lote #\d+ · DRAFT$/ })).toBeVisible(); await expect(page.getByText('Movimientos').locator('..')).toContainText('0');
  await page.getByRole('link', { name: 'Existencias' }).click(); await expect(page.getByText('13 UNIT')).toBeVisible(); await expect(page.getByText('15 UNIT')).toBeVisible(); await expect(page.getByText('0 UNIT')).toBeVisible();
  await page.getByRole('link', { name: 'Preparaciones' }).click(); await page.getByRole('button', { name: /Lote #\d+ · DRAFT/ }).click(); await page.getByRole('button', { name: 'Iniciar lote' }).click();
  const completionRequestPromise=page.waitForRequest((request)=>request.url().includes('/preparation-batches/')&&request.url().endsWith(':complete')); await page.getByRole('button', { name: 'Completar lote' }).click(); const completionRequest=await completionRequestPromise;
  await expect(page.locator('p.inventory-lifecycle', { hasText: /^Lote #\d+ · COMPLETED$/ })).toBeVisible(); await expect(page.getByText(/Costo material 35/)).toBeVisible(); await expect(page.locator('dt', { hasText: /^Rendimiento real$/ }).locator('..')).toContainText('2.000000000000');
  const replay=await page.evaluate(async ({url,key,body})=>{const credential=JSON.parse(sessionStorage.getItem('staff-auth-session-v1')!);const response=await fetch(url,{method:'POST',headers:{Authorization:`Bearer ${credential.accessToken}`,'Content-Type':'application/json','Idempotency-Key':key},body});return {status:response.status,replay:response.headers.get('Idempotent-Replay')};},{url:completionRequest.url().replace('http://localhost:8000','/api'),key:completionRequest.headers()['idempotency-key'],body:completionRequest.postData()!}); expect(replay).toEqual({status:200,replay:'true'});
  await page.getByRole('link', { name: 'Existencias' }).click(); await expect(page.getByText('11 UNIT')).toBeVisible(); await expect(page.getByText('12 UNIT')).toBeVisible(); await expect(page.getByText('4 UNIT')).toBeVisible(); await expectPageFitsViewport(page);
});
