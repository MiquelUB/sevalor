import { test, expect } from '@playwright/test';

test.describe('Superadmin - Tenants Management', () => {

  test('Superadmin can login and view tenants list', async ({ page }) => {
    // Navigate to superadmin login
    await page.goto('/superadmin/login');

    // Open config and set API URL to point to backend port 8000
    await page.click('text=Configuració del servidor API');
    await page.fill('input[placeholder="https://api.domini.com/api/v1"]', 'http://127.0.0.1:8000/api/v1');
    await page.click('button:has-text("Desar")');

    // Make sure API url config is hidden or we just type directly
    await page.fill('input[type="email"]', 'admin@sevalor.com');
    await page.fill('input[type="password"]', 'superpassword');
    
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/auth/login')),
      page.click('button[type="submit"]')
    ]);

    // Verify it redirects to telemetria
    await expect(page).toHaveURL(/\/superadmin\/telemetria/);

    // Navigate to Empreses
    await page.click('text=Gestió d\'Empreses');
    await expect(page).toHaveURL(/\/superadmin\/empreses/);

    // Verify we see the E2E Tenant seeded by seed_db
    try { await expect(page.locator('text=Test E2E Empresa')).toBeVisible(); } catch(e) { console.log(await page.content()); throw e; }
    await expect(page.locator('text=e2e.campopro.cat')).toBeVisible();

    // Click on Edit
    const row = page.locator('tr', { hasText: 'Test E2E Empresa' });
    await row.locator('text=Editar').click();

    // Verify detail page
    await expect(page).toHaveURL(/\/superadmin\/empreses\/[a-f0-9-]{36}/);
    await expect(page.locator('h1')).toContainText('Test E2E Empresa');

    // Change status
    await page.selectOption('select', { label: 'SUSPÈS (Impagament)' });
    
    // Save changes
    page.on('dialog', dialog => dialog.accept());
    await page.click('text=Desar Canvis');

    // We can also verify the destructive action but let's just make sure it renders the button
    await expect(page.locator('button:has-text("Forçar Destrucció")')).toBeVisible();
  });

});
