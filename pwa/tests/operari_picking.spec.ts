import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test.describe.serial('Auditoria Zero Mock: Operari PWA Picking i Detall', () => {
  test.use({ viewport: { width: 375, height: 667 }, userAgent: 'Mobile Chrome' });

  test('Validar informació d\'Ordre de Treball i actualitzar consum de material', async ({ page }) => {
    const uniqId = Date.now().toString().slice(-4);
    const nifOperari = `OPP-${uniqId}`;
    const codiFeina = `OT-${uniqId}PICK`;

    // 1. Preparar Dades
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
  });
});
