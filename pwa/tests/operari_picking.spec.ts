import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe.serial('Auditoria Zero Mock: Operari PWA Picking i Detall', () => {
  test.use({ viewport: { width: 375, height: 667 }, userAgent: 'Mobile Chrome' });

  test('Validar informació d\'Ordre de Treball i actualitzar consum de material', async ({ page }) => {
    const uniqId = Date.now().toString().slice(-4);
    const nifOperari = `OPP-${uniqId}`;
    const codiFeina = `OT-${uniqId}PICK`;

    // 1. BACKOFFICE: Preparar Dades (Article, Client, Operari, Feina)
    await page.goto('/gestio/magatzem');
    await page.click('button:has-text("Alta Article")');
    await page.locator('label:has-text("Referència (Interna)") + input').fill(`ART-${uniqId}`);
    await page.locator('label:has-text("Nom de l\'article") + input').fill(`Tub PVC ${uniqId}`);
    await page.click('button:has-text("Registrar al Magatzem")');

    await page.goto('/gestio/clients');
    await page.click('button:has-text("Nou Client")');
    await page.locator('label:has-text("Codi") + input').fill(`CP-${uniqId}`);
    await page.locator('label:has-text("Raó Social") + input').fill(`Client Picking ${uniqId}`);
    await page.locator('label:has-text("NIF") + input').fill(`B${uniqId}PICK`);
    await page.click('button:has-text("Guardar Client")');

    await page.goto('/gestio/operaris');
    await page.click('button:has-text("Nou Operari")');
    await page.locator('label:has-text("NIF") + input').fill(nifOperari);
    await page.locator('label').filter({ hasText: /^Nom$/ }).locator('..').locator('input').fill(`Operari Picking ${uniqId}`);
    await page.locator('label').filter({ hasText: /^Cognoms$/ }).locator('..').locator('input').fill('Test');
    await page.locator('label:has-text("Telèfon") + input').fill(`6003${uniqId}`);
    await page.click('button:has-text("Registrar Operari")');

    await page.goto('/gestio/feines');
    await page.click('button:has-text("Nova Feina")');
    await page.locator('label:has-text("Codi Feina") + input').fill(codiFeina);
    await page.locator('label:has-text("Data Planificada") + input').fill('2027-01-01');
    await page.locator('label:has-text("Títol / Breu Descripció") + input').fill('Reparació amb Tub');
    await page.locator('label:has-text("Adreça de Destí") + input').fill('Carrer Picking 456');
    await page.locator('label:has-text("Client (Obligatori)") + select').selectOption({ label: `Client Picking ${uniqId}` });
    await page.locator('label:has-text("Cap de Colla") + select').selectOption({ label: `Operari Picking ${uniqId} Test` });
    await page.click('button:has-text("Guardar Ordre de Treball")');
    await expect(page.locator('table')).toContainText(codiFeina);

    // SQL HACK: As we haven't built Backoffice Picking UI yet, we insert the FullaPicking and LiniaPicking directly in DB.
    // Also we need to unblock the PIN for the operari.
    execSync(`
      docker exec sevalor_db psql -U postgres -d sevalor -c "
        DO \\$\\$
        DECLARE
          v_feina_id UUID;
          v_empresa_id UUID;
          v_article_id UUID;
          v_picking_id UUID;
        BEGIN
          SELECT id, empresa_id INTO v_feina_id, v_empresa_id FROM ordres_treball WHERE codi = '${codiFeina}';
          SELECT id INTO v_article_id FROM articles WHERE referencia_inventari = 'ART-${uniqId}';
          
          INSERT INTO fulles_picking (empresa_id, ordre_treball_id, estat_picking) 
          VALUES (v_empresa_id, v_feina_id, 'PENDENT') RETURNING id INTO v_picking_id;
          
          INSERT INTO linies_picking (empresa_id, picking_id, article_id, quantitat_prevista, quantitat_carregada_pick_in)
          VALUES (v_empresa_id, v_picking_id, v_article_id, 10.0, 0.0);

          UPDATE usuaris SET pin_hash = CHR(36) || '2b' || CHR(36) || '12' || CHR(36) || 'HijcPviwfaaA4FQS4N48QucJGGqB9bh7KrN0JmbFaRKRcgnSLwmO2', intents_pin_fallits = 0, pin_bloquejat = false WHERE nif = '${nifOperari}';
        END \\$\\$;
      "
    `);

    // 2. PWA: Login amb l'Operari i accedir a la Feina
    await page.goto('/operari/login');
    await page.locator('input[placeholder="Ex: 12345678A"]').fill(nifOperari);
    await page.click('button:has-text("Continuar")');
    for (let i = 1; i <= 4; i++) await page.click(`button:has-text("${i}")`);
    await page.waitForURL('**/operari', { timeout: 10000 });

    await page.click('nav >> text=Feines');
    await page.waitForURL('**/operari/feines');
    
    // Clic a la tarjeta de la feina per anar al detall
    await page.click(`text=${codiFeina}`);
    await page.waitForURL(`**/operari/feines/**`);

    // 3. PWA: Validar "Tot en una plana"
    await expect(page.locator(`h1:has-text("Reparació amb Tub")`)).toBeVisible();
    await expect(page.locator(`text=Client Picking ${uniqId}`)).toBeVisible();
    await expect(page.locator('text=Carrer Picking 456')).toBeVisible();
    await expect(page.locator('text=Plànols adjunts')).toBeVisible();

    // Validar Picking
    await expect(page.locator(`text=Tub PVC ${uniqId}`)).toBeVisible();
    await expect(page.locator('text=Previst: 10')).toBeVisible();

    // Incrementar quantitat utilitzada de 0 a 2
    await page.click('button:has-text("+")'); // +1
    await page.click('button:has-text("+")'); // +2
    await expect(page.locator('span.w-6.text-center')).toHaveText('2');

    // 4. PWA: Validar "Alerta de Material Faltant"
    await page.click('button:has-text("Alerta de Material Faltant")');
    await expect(page.locator('text=Material no assignat')).toBeVisible();
    await page.locator('textarea').fill('Em falta una vàlvula per poder acabar.');
    
    // Alerta JS
    page.on('dialog', dialog => dialog.accept());
    await page.click('button:has-text("Enviar Alerta")');
  });
});
