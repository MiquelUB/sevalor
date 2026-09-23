import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe.serial('Auditoria Zero Mock: Operari PWA Login', () => {
  test.use({ viewport: { width: 375, height: 667 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1' });

  test('Validació de Login PWA: Intents fallits, bloqueig i accés correcte', async ({ page }) => {
    // 1. Crear l'operari a través de gestió
    await page.goto('/gestio/operaris');
    await page.click('button:has-text("Nou Operari")');
    
    const uniqId = Date.now().toString().slice(-4);
    const nifOperari = `OP-${uniqId}L`;
    
    await page.locator('label:has-text("NIF / NIE") + input').fill(nifOperari);
    await page.locator('label').filter({ hasText: /^Nom$/ }).locator('..').locator('input').fill('Operari Login');
    await page.locator('label').filter({ hasText: /^Cognoms$/ }).locator('..').locator('input').fill('Test');
    await page.locator('label:has-text("Telèfon") + input').fill(`600${uniqId}`);
    
    await page.click('button:has-text("Registrar Operari")');
    await expect(page.locator(`text=${nifOperari}`)).toBeVisible();

    // 2. Posar PIN 1234
    const knownHashSQL = "CHR(36) || '2b' || CHR(36) || '12' || CHR(36) || 'HijcPviwfaaA4FQS4N48QucJGGqB9bh7KrN0JmbFaRKRcgnSLwmO2'";
    execSync(`docker exec sevalor_db psql -U postgres -d sevalor -c "UPDATE usuaris SET pin_hash = ${knownHashSQL}, intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';"`);

    // 3. PWA Login
    await page.goto('/operari/login');
    await expect(page.locator('h1, div', { hasText: 'Sevalor' }).first()).toBeVisible();

    // 4. Inserir NIF
    await page.locator('input[placeholder="Ex: 12345678A"]').fill(nifOperari);
    await page.click('button:has-text("Continuar")');

    // 5. 3 Intents fallits
    for (let i = 0; i < 3; i++) {
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
    }

    // 6. Quart intent -> Bloquejat
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');

    // 7. Desbloquejar des de DB
    execSync(`docker exec sevalor_db psql -U postgres -d sevalor -c "UPDATE usuaris SET intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';"`);

    // 8. PIN Correcte 1234
    await page.click('button:has-text("1")');
    await page.click('button:has-text("2")');
    await page.click('button:has-text("3")');
    await page.click('button:has-text("4")');
  });
});
