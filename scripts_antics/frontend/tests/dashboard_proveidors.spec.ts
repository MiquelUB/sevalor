import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Proveïdors E2E', () => {
  test('Alta d\'un nou proveïdor via Modal', async ({ page }) => {
    await page.goto('/dashboard/proveidors');
    await expect(page.locator('h1', { hasText: 'Directori de Proveïdors' })).toBeVisible();

    await page.click('button:has-text("Nou Proveïdor")');
    await expect(page.locator('h3', { hasText: 'Alta de Nou Proveïdor' })).toBeVisible();

    const uniqId = Date.now().toString().slice(-6);
    const nifUnic = `B${uniqId}PRO`;
    const codiUnic = `PRV-${uniqId}`;

    await page.locator('label:has-text("Codi de Proveïdor") + input').fill(codiUnic);
    await page.locator('label:has-text("Raó Social") + input').fill('Materials de Construcció SA');
    await page.locator('label:has-text("NIF / CIF") + input').fill(nifUnic);
    await page.locator('select').selectOption('MAQUINARIA');

    await page.click('button:has-text("Guardar Proveïdor")');

    // Verificar que el proveïdor apareix a la taula
    await expect(page.locator('table')).toContainText(codiUnic);
    await expect(page.locator('table')).toContainText('Materials de Construcció SA');
    await expect(page.locator('table')).toContainText('MAQUINARIA');
  });
});
