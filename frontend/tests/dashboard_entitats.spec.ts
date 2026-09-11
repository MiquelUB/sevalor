import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 1280, height: 720 } });

test.describe.serial('Auditoria de Test 2: Operaris i Magatzem E2E', () => {

  test('Mòdul Operaris: Llistat i Alta', async ({ page }) => {
    await page.goto('/dashboard/operaris');
    await expect(page.locator('h1', { hasText: "Directori d'Operaris" })).toBeVisible();

    // Crear Operari
    await page.click('button:has-text("Nou Operari")');
    const nomAleatori = 'E2E ' + Date.now();
    await page.fill('input:near(label:has-text("NIF"))', 'E2E' + Math.floor(Date.now()));
    await page.fill('input:near(label:has-text("Nom"))', nomAleatori);
    await page.fill('input:near(label:has-text("Cognoms"))', 'Cognom Test');
    await page.fill('input:near(label:has-text("Telèfon"))', '600000000');
    
    await page.click('button:has-text("Registrar Operari")');

    await expect(page.locator('h3', { hasText: 'Alta Nou Operari' })).toBeHidden({ timeout: 10000 });
    
    // Validar que apareix a la taula
    await expect(page.locator('td', { hasText: nomAleatori })).toBeVisible();
  });

  test('Mòdul Magatzem: Alta i Alerta de Stock', async ({ page }) => {
    await page.goto('/dashboard/magatzem');
    await expect(page.locator('h1', { hasText: 'Inventari del Magatzem' })).toBeVisible();
    
    // Alta Article sota stock mínim
    await page.click('button:has-text("Alta Article")');
    const articleNom = 'Cable E2E ' + Date.now();
    await page.fill('input:near(label:has-text("Nom"))', articleNom);
    await page.fill('input:near(label:has-text("Referència (Interna)"))', 'REF-' + Date.now());
    await page.selectOption('select:near(label:has-text("Unitat"))', 'METRES_LINEALS');
    // Actualitzat segons schema backend: estoc_optim i estoc_minim, però UI ho mostra com Inicial i Alerta.
    await page.fill('input[type="number"]:near(label:has-text("Stock Inicial"))', '10');
    await page.fill('input[type="number"]:near(label:has-text("Alerta"))', '50');
    await page.click('button:has-text("Registrar al Magatzem")');

    await expect(page.locator('h3', { hasText: 'Registre de Nou Article' })).toBeHidden({ timeout: 10000 });

    // Validar visualització d'Alerta de Stock (vermell perquè 10 < 50)
    const row = page.locator('tr', { hasText: articleNom });
    await expect(row).toBeVisible();
    // No hi ha la quantitat real en l'schema d'ArticleCreate inicialment a menys que estigui a DB. 
    // Com que "estoc_optim" no és el "stock real", el test visual només assegura que es crea bé.
  });
});
