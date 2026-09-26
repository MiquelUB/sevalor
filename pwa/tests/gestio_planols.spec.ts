import { test, expect } from '@playwright/test';

test.describe.serial('Auditoria Zero Mock: Plànols E2E', () => {
  test('Renderització base UI de Plànols', async ({ page }) => {
    await page.goto('/gestio/planols');
    await expect(page.locator('h1', { hasText: 'Plànols' })).toBeVisible();
    
    // Crear carpeta
    const novaCarpetaBtn = page.locator('button:has-text("Nova Carpeta")');
    if (await novaCarpetaBtn.isVisible()) {
        await novaCarpetaBtn.click();
        await page.locator('input[placeholder="Nom de la carpeta"]').fill('Projecte A');
        await page.locator('button:has-text("Crear")').click();
        await expect(page.locator('text=Projecte A')).toBeVisible();

        // Navegar a la carpeta
        await page.click('text=Projecte A');
        await expect(page.locator('h1', { hasText: 'Projecte A' })).toBeVisible();
        
        // Upload PDF
        const fileChooserPromise = page.waitForEvent('filechooser');
        await page.locator('button:has-text("Pujar Plànol")').click();
        const fileChooser = await fileChooserPromise;
        // Mock a PDF file upload
        await fileChooser.setFiles({
            name: 'planol.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('%PDF-1.4\n%EOF')
        });
        await expect(page.locator('text=planol.pdf')).toBeVisible();

        // Renderització visor
        await page.click('text=planol.pdf');
        await expect(page.locator('.visor-pdf, canvas, iframe')).toBeVisible();
    }
  });
});
