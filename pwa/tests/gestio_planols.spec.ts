import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Plànols E2E', () => {
  test('Renderització base UI de Plànols', async ({ page }) => {
    await page.goto('/gestio/planols');
    await expect(page.locator('h1', { hasText: 'Plànols' })).toBeVisible();
  });
});
