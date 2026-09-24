import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 720 } });

test.describe.serial('Auditoria de Test 2: Clients E2E', () => {
  test('Alta d\'un nou client via Modal', async ({ page }) => {
    await page.goto('/dashboard/clients');
    await expect(page.locator('h1', { hasText: 'Directori de Clients' })).toBeVisible();

    await page.click('button:has-text("Nou Client")');
    const clientNom = 'Client E2E ' + Date.now();
    await page.fill('input[type="text"]:near(label:has-text("Codi"))', 'CLI-' + Math.floor(Date.now()));
    await page.fill('input[type="text"]:near(label:has-text("Raó Social"))', clientNom);
    await page.fill('input[type="text"]:near(label:has-text("NIF"))', 'C' + Date.now());
    await page.click('button:has-text("Guardar Client")');

    await expect(page.locator('h3', { hasText: 'Alta de Nou Client' })).toBeHidden({ timeout: 10000 });
    
    await expect(page.locator('td', { hasText: clientNom })).toBeVisible();
  });
});
