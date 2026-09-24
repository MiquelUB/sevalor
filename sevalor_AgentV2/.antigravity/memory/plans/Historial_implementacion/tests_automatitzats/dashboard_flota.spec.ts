import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Flota E2E', () => {
  test('Alta d\'un nou vehicle via Modal', async ({ page }) => {
    await page.goto('/dashboard/flota');
    await expect(page.locator('h1', { hasText: 'Flota de Vehicles' })).toBeVisible();

    await page.click('button:has-text("Nou Vehicle")');
    await expect(page.locator('h3', { hasText: 'Alta de Nou Vehicle' })).toBeVisible();

    // Utilitzar part del timestamp per evitar col·lisions
    const randPart = Date.now().toString().slice(-4);
    const matriculaUnica = `${randPart} ABC`;

    await page.locator('label:has-text("Matrícula") + input').fill(matriculaUnica);
    await page.locator('label:has-text("Marca") + input').fill('Ford');
    await page.locator('label:has-text("Model") + input').fill('Transit Custom');
    
    // Deixem Tipus per defecte o l'assignem
    await page.locator('select').first().selectOption('THERMIC');
    await page.locator('select').nth(1).selectOption('C');

    await page.click('button:has-text("Guardar Vehicle")');

    // Verificar que la matrícula i el vehicle apareixen a la taula
    await expect(page.locator('table')).toContainText(matriculaUnica);
    await expect(page.locator('table')).toContainText('Ford Transit Custom');
    await expect(page.locator('table')).toContainText('THERMIC');
    await expect(page.locator('table')).toContainText('Etiqueta C');
  });
});
