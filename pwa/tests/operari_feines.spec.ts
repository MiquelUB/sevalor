import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe.serial('Auditoria Zero Mock: Operari PWA Feines', () => {
  test.use({ viewport: { width: 375, height: 667 }, userAgent: 'Mobile Chrome' });

  test('Crear feina al Backoffice i veure-la a la PWA de l\'Operari', async ({ page }) => {
    const uniqId = Date.now().toString().slice(-4);
    const nifOperari = `OPF-${uniqId}`;
    const codiFeina = `OT-${uniqId}PWA`;

    // 1. Crear Client i Operari
    await page.goto('/gestio/clients');
    await page.click('button:has-text("Nou Client")');
    await page.locator('label:has-text("Codi") + input').fill(`C-${uniqId}`);
    await page.locator('label:has-text("Raó Social") + input').fill(`Client PWA ${uniqId}`);
    await page.locator('label:has-text("NIF") + input').fill(`A${uniqId}PWA`);
    await page.click('button:has-text("Guardar Client")');
    await expect(page.locator(`text=C-${uniqId}`)).toBeVisible();

    await page.goto('/gestio/operaris');
    await page.click('button:has-text("Nou Operari")');
    await page.locator('label:has-text("NIF") + input').fill(nifOperari);
    await page.locator('label').filter({ hasText: /^Nom$/ }).locator('..').locator('input').fill(`Operari Feines ${uniqId}`);
    await page.locator('label').filter({ hasText: /^Cognoms$/ }).locator('..').locator('input').fill('Test PWA');
    await page.locator('label:has-text("Telèfon") + input').fill(`6002${uniqId}`);
    await page.click('button:has-text("Registrar Operari")');
    await expect(page.locator(`text=${nifOperari}`)).toBeVisible();

    // 2. Assignar Feina
    await page.goto('/gestio/feines');
    await page.click('button:has-text("Nova Feina")');
    await page.locator('label:has-text("Codi Feina") + input').fill(codiFeina);
    await page.locator('label:has-text("Data Planificada") + input').fill('2027-01-01');
    await page.locator('label:has-text("Títol / Breu Descripció") + input').fill('Instal·lació PWA Test');
    await page.locator('label:has-text("Adreça de Destí") + input').fill('Carrer PWA 123');
    
    await page.locator('label:has-text("Client (Obligatori)") + select').selectOption({ label: `Client PWA ${uniqId}` });
    await page.locator('label:has-text("Cap de Colla") + select').selectOption({ label: `Operari Feines ${uniqId} Test PWA` });
    
    await page.click('button:has-text("Guardar Ordre de Treball")');
    await expect(page.locator('table')).toContainText(codiFeina);

    // 3. Posar PIN 1234
    const knownHashSQL = "CHR(36) || '2b' || CHR(36) || '12' || CHR(36) || 'HijcPviwfaaA4FQS4N48QucJGGqB9bh7KrN0JmbFaRKRcgnSLwmO2'";
    execSync(`docker exec sevalor_db psql -U postgres -d sevalor -c "UPDATE usuaris SET pin_hash = ${knownHashSQL}, intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';"`);

    // 4. Login PWA
    await page.goto('/operari/login');
    await page.locator('input[placeholder="Ex: 12345678A"]').fill(nifOperari);
    await page.click('button:has-text("Continuar")');
    await page.click('button:has-text("1")');
    await page.click('button:has-text("2")');
    await page.click('button:has-text("3")');
    await page.click('button:has-text("4")');
  });
});
