import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe.serial('Auditoria Zero Mock: Operari PWA Login', () => {
  // Configurar emulació mòbil per a la prova
  test.use({ viewport: { width: 375, height: 667 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1' });

  test('Validació de Login PWA: Intents fallits, bloqueig i accés correcte', async ({ page }) => {
    // 1. Crear l'operari a través de l'oficina (E2E pur)
    await page.goto('/dashboard/operaris');
    await page.click('button:has-text("Nou Operari")');
    
    const uniqId = Date.now().toString().slice(-4);
    const nifOperari = `OP-${uniqId}L`;
    
    await page.locator('label:has-text("NIF / NIE") + input').fill(nifOperari);
    await page.locator('label').filter({ hasText: /^Nom$/ }).locator('..').locator('input').fill('Operari Login');
    await page.locator('label').filter({ hasText: /^Cognoms$/ }).locator('..').locator('input').fill('Test');
    await page.locator('label:has-text("Telèfon") + input').fill(`600${uniqId}`);
    
    await page.click('button:has-text("Registrar Operari")');
    await expect(page.locator(`text=${nifOperari}`)).toBeVisible();

    // 2. Com que l'API ha generat un PIN aleatori i l'ha enviat per SMS, "hackejarem" la base de dades
    // des de fora per posar el PIN a '1234' i poder seguir amb el test 100% E2E de la PWA.
    const knownHashSQL = "CHR(36) || '2b' || CHR(36) || '12' || CHR(36) || 'HijcPviwfaaA4FQS4N48QucJGGqB9bh7KrN0JmbFaRKRcgnSLwmO2'"; // hash per '1234'
    execSync(`docker exec sevalor_db psql -U postgres -d sevalor -c "UPDATE usuaris SET pin_hash = ${knownHashSQL}, intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';"`);

    // 3. Anar a la PWA Login
    await page.goto('/operari/login');
    await expect(page.locator('h1', { hasText: 'Sevalor' })).toBeVisible();

    // 4. Inserir NIF
    await page.locator('input[placeholder="Ex: 12345678A"]').fill(nifOperari);
    await page.click('button:has-text("Continuar")');

    // Comprovar que el NIF es mostra a la segona pantalla
    await expect(page.locator(`text=${nifOperari}`)).toBeVisible();

    // 5. Intents Fallits (Error)
    // El teclat numèric s'acciona fent click als botons
    for (let i = 0; i < 3; i++) {
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
      await page.click('button:has-text("0")');
      
      await expect(page.locator('text=Credencials invàlides')).toBeVisible();
    }

    // Al quart intent falla i bloqueja!
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');
    await page.click('button:has-text("0")');
    await expect(page.locator('text=El compte ha estat bloquejat')).toBeVisible();

    // 6. Desbloquejar des de DB per poder finalitzar el test d'accés (simularia acció d'oficina)
    execSync(`docker exec sevalor_db psql -U postgres -d sevalor -c "UPDATE usuaris SET intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';"`);

    // 7. Accés Correcte (1234)
    await page.click('button:has-text("1")');
    await page.click('button:has-text("2")');
    await page.click('button:has-text("3")');
    await page.click('button:has-text("4")');

    // Esperem la navegació a la root
    await page.waitForURL('**/operari', { timeout: 10000 });

    await expect(page.locator('text=Iniciant Jornada')).toBeVisible();
    const h2Text = await page.locator('h2').textContent().catch(() => null);
    console.log('H2 TEXT IS:', h2Text);
    await expect(page.locator('h2', { hasText: 'Hola, Operari Login' })).toBeVisible();
    
    // Verifiquem que veiem el menú inferior (Home, Feines, Material, Perfil)
    await expect(page.locator('nav >> text=Feines')).toBeVisible();
  });
});
