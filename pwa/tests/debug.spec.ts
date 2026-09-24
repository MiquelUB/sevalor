import { test, expect } from '@playwright/test';
test('Debug Login', async ({ page }) => {
  await page.goto('/operari/login');
  const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
  await nifInput.fill('12345678A');
  await page.click('button:has-text("1")');
  await page.click('button:has-text("2")');
  await page.click('button:has-text("3")');
  await page.click('button:has-text("4")');
  const debugText = await page.locator('#debug').textContent();
  console.log("DEBUG DIV:", debugText);
});
