import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Feines E2E', () => {
  test('Creació complerta d\'una Ordre de Treball', async ({ page }) => {
    // 1. Crear un Client previ (per garantir que n'hi ha almenys un)
    await page.goto('/dashboard/clients');
    const uniqId = Date.now().toString().slice(-5);
    await page.click('button:has-text("Nou Client")');
    await page.locator('label:has-text("Codi") + input').fill(`C-${uniqId}`);
    await page.locator('label:has-text("Raó Social") + input').fill(`Client Feina ${uniqId}`);
    await page.locator('label:has-text("NIF / CIF") + input').fill(`A${uniqId}123`);
    await page.click('button:has-text("Guardar Client")');
    // Esperar a que el modal es tanqui i s'actualitzi
    await expect(page.locator(`text=C-${uniqId}`)).toBeVisible();

    // 2. Crear un Operari previ
    await page.goto('/dashboard/operaris');
    await page.click('button:has-text("Nou Operari")');
    await page.locator('label:has-text("NIF") + input').fill(`X${uniqId}Z`);
    await page.locator('label').filter({ hasText: /^Nom$/ }).locator('..').locator('input').fill('Operari');
    await page.locator('label').filter({ hasText: /^Cognoms$/ }).locator('..').locator('input').fill('Feina');
    await page.locator('label:has-text("Telèfon") + input').fill('600123456');
    await page.click('button:has-text("Registrar Operari")');
    await expect(page.locator(`text=X${uniqId}Z`)).toBeVisible();

    // 3. Crear la Feina (Ordre de Treball)
    await page.goto('/dashboard/feines');
    await expect(page.locator('h1', { hasText: 'Ordres de Treball (Feines)' })).toBeVisible();

    await page.click('button:has-text("Nova Feina")');
    await expect(page.locator('h3', { hasText: 'Alta de Nova Ordre de Treball' })).toBeVisible();

    const codiFeina = `OT-${uniqId}`;
    await page.locator('label:has-text("Codi Feina") + input').fill(codiFeina);
    await page.locator('label:has-text("Data Planificada") + input').fill('2027-01-01');
    await page.locator('label:has-text("Títol / Breu Descripció") + input').fill('Instal·lació de prova');
    await page.locator('label:has-text("Adreça de Destí") + input').fill('Carrer Fals 123');

    // Seleccionar de les llistes
    // Busquem els options que contenen el text que hem creat
    const clientSelect = page.locator('label:has-text("Client (Obligatori)") + select');
    await clientSelect.selectOption({ label: `Client Feina ${uniqId}` });

    const operariSelect = page.locator('label:has-text("Cap de Colla") + select');
    await operariSelect.selectOption({ label: 'Operari Feina' });

    // Guardem
    await page.click('button:has-text("Guardar Ordre de Treball")');

    // Validem la renderització a la taula
    await expect(page.locator('table')).toContainText(codiFeina);
    await expect(page.locator('table')).toContainText('Instal·lació de prova');
    await expect(page.locator('table')).toContainText('Carrer Fals 123');
    await expect(page.locator('table')).toContainText('PENDENT');
  });
});
