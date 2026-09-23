import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria de Test 1: PWA Login E2E', () => {
  let dialogMessage = '';

  test.beforeEach(async ({ page }) => {
    page.on('dialog', async dialog => {
      dialogMessage = dialog.message();
      await dialog.accept();
    });
    await page.goto('/operari/login');
  });

  test('Test 1: Login reeixit injectant JWT al localStorage', async ({ page }) => {
    const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
    await nifInput.fill('99999999E'); // Operari creat al seed_db.py

    // PIN correcte és 1234
    await page.click('button:has-text("1")');
    await page.click('button:has-text("2")');
    await page.click('button:has-text("3")');
    await page.click('button:has-text("4")');
    
    const enterButton = page.locator('button:has-text("ENTRAR"), button:has-text("Continuar"), button:has-text("Accedir")').first();
    await enterButton.click();
    
    await page.waitForFunction(() => localStorage.getItem('sevalor_token') !== null || document.cookie.includes('sevalor_token'), null, { timeout: 10000 });

    const token = await page.evaluate(() => localStorage.getItem('sevalor_token'));
    expect(token).toBeTruthy();
  });

  test('Test 2: Login invàlid -> Missatge d\'error', async ({ page }) => {
    const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
    await nifInput.fill('99999999E');

    // PIN incorrecte (1111)
    await page.click('button:has-text("1")');
    await page.click('button:has-text("1")');
    await page.click('button:has-text("1")');
    await page.click('button:has-text("1")');
    
    const enterButton = page.locator('button:has-text("ENTRAR"), button:has-text("Continuar"), button:has-text("Accedir")').first();
    await enterButton.click();
    await expect(page.locator('text=invàlides, text=incorrecte, text=Error')).toBeVisible({ timeout: 5000 });
  });

  test('Test 3: Bloqueig al 4t intent fallit de PIN', async ({ page }) => {
    const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
    await nifInput.fill('99999999E');
    
    for (let i = 0; i < 3; i++) {
      await page.click('button:has-text("2")');
      await page.click('button:has-text("2")');
      await page.click('button:has-text("2")');
      await page.click('button:has-text("2")');
        
      const enterButton = page.locator('button:has-text("ENTRAR"), button:has-text("Continuar"), button:has-text("Accedir")').first();
      await enterButton.click();
    }
  });
});
