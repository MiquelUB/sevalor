import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Plànols E2E', () => {
  test('Renderització base UI de Plànols', async ({ page }) => {
    await page.goto('/dashboard/planols');
    await expect(page.locator('h1', { hasText: 'Gestió de Plànols' })).toBeVisible();
    await expect(page.locator('text=Plànols UI Rendered!')).toBeVisible();
  });
});
