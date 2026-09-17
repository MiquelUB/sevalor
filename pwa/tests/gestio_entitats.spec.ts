import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 720 } });

test.describe.serial('Auditoria de Test 2: Operaris i Magatzem E2E', () => {

  test('Mòdul Operaris: Llistat i Alta a /gestio/operaris', async ({ page }) => {
    await page.goto('/gestio/operaris');
    await expect(page.locator('h1', { hasText: "Directori d'Operaris" })).toBeVisible();

    await page.click('button:has-text("Nou Operari")');
    const nomAleatori = 'E2E ' + Date.now();
    await page.fill('input:near(label:has-text("NIF"))', 'E2E' + Math.floor(Date.now()));
    await page.fill('input:near(label:has-text("Nom"))', nomAleatori);
    await page.fill('input:near(label:has-text("Cognoms"))', 'Cognom Test');
    await page.fill('input:near(label:has-text("Telèfon"))', '600000000');
    
    await page.click('button:has-text("Registrar Operari")');

    await expect(page.locator('h3', { hasText: 'Alta Nou Operari' })).toBeHidden({ timeout: 10000 });
    await expect(page.locator('td', { hasText: nomAleatori })).toBeVisible();
  });

  test('Mòdul Magatzem: Alta i Alerta de Stock a /gestio/magatzem', async ({ page }) => {
    await page.goto('/gestio/magatzem');
    await expect(page.locator('h1', { hasText: 'Inventari del Magatzem' })).toBeVisible();
    
    await page.click('button:has-text("Alta Article")');
    const articleNom = 'Cable E2E ' + Date.now();
    await page.fill('input:near(label:has-text("Nom"))', articleNom);
    await page.fill('input:near(label:has-text("Referència (Interna)"))', 'REF-' + Date.now());
    await page.selectOption('select:near(label:has-text("Unitat"))', 'METRES_LINEALS');
    await page.fill('input[type="number"]:near(label:has-text("Stock Inicial"))', '10');
    await page.fill('input[type="number"]:near(label:has-text("Alerta"))', '50');
    await page.click('button:has-text("Registrar al Magatzem")');

    await expect(page.locator('h3', { hasText: 'Registre de Nou Article' })).toBeHidden({ timeout: 10000 });

    const row = page.locator('tr', { hasText: articleNom });
    await expect(row).toBeVisible();
  });
});
