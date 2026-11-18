import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 720 } });

test.describe.serial('Auditoria Zero Mock: Gestio Clients E2E', () => {
  test('Alta d\'un nou client via Modal a /gestio/clients', async ({ page }) => {
    await page.goto('/gestio/clients');
    await expect(page.locator('h1', { hasText: 'Directori de Clients' })).toBeVisible();

    await page.click('button:has-text("Nou Client")');
    const clientNom = 'Client E2E ' + Date.now();
    await page.fill('input[type="text"]:near(label:has-text("Raó Social"))', clientNom);
    await page.fill('input[type="text"]:near(label:has-text("NIF"))', 'C' + Date.now().toString().slice(-8));
    await page.click('button:has-text("Desar Client")');

    await expect(page.locator('h3', { hasText: 'Alta de Client Fiscal' })).toBeHidden({ timeout: 10000 });
    await expect(page.locator('text=' + clientNom)).toBeVisible();
  });
});
