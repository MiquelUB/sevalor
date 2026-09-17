import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Flota E2E', () => {
  test('Alta d\'un nou vehicle via Modal', async ({ page }) => {
    await page.goto('/gestio/flota');
    await expect(page.locator('h1', { hasText: 'Flota de Vehicles' })).toBeVisible();

    await page.click('button:has-text("Nou Vehicle")');
    await expect(page.locator('h3', { hasText: 'Alta de Nou Vehicle' })).toBeVisible();

    const randPart = Date.now().toString().slice(-4);
    const matriculaUnica = `${randPart} ABC`;

    await page.locator('label:has-text("Matrícula") + input').fill(matriculaUnica);
    await page.locator('label:has-text("Marca") + input').fill('Ford');
    await page.locator('label:has-text("Model") + input').fill('Transit Custom');
    
    await page.locator('select').first().selectOption('THERMIC');
    await page.locator('select').nth(1).selectOption('C');

    await page.click('button:has-text("Guardar Vehicle")');

    await expect(page.locator('table')).toContainText(matriculaUnica);
    await expect(page.locator('table')).toContainText('Ford Transit Custom');
  });
});
