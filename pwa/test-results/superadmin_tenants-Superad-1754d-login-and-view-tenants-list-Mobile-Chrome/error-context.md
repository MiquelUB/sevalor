# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: superadmin_tenants.spec.ts >> Superadmin - Tenants Management >> Superadmin can login and view tenants list
- Location: tests/superadmin_tenants.spec.ts:5:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('text=Configuració del servidor API')

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e2]:
    - generic [ref=e4]:
      - generic [ref=e6]:
        - link [ref=e8] [cursor=pointer]:
          - /url: /
          - img "Home" [ref=e9]
        - generic [ref=e11]:
          - group [ref=e12]:
            - generic [ref=e13]: Email*
            - textbox "Email" [active] [ref=e15]
          - group [ref=e16]:
            - generic [ref=e17]: Password*
            - generic [ref=e18]:
              - textbox "Password" [ref=e19]
              - button "Toggle Visiblity" [ref=e21] [cursor=pointer]
          - group [ref=e25]:
            - generic [ref=e26] [cursor=pointer]:
              - checkbox "Remember Me" [ref=e27]
              - generic [ref=e29]: Remember Me
          - button "Login" [ref=e31] [cursor=pointer]
        - link "Forgot your password?" [ref=e33] [cursor=pointer]:
          - /url: https://easypanel.io/docs#reseting-the-password
      - heading [level=1] [ref=e35]:
        - link "Hosting Control Panel" [ref=e36] [cursor=pointer]:
          - /url: https://easypanel.io/
    - region "Notifications alt+T"
  - generic:
    - region "Notifications-top"
    - region "Notifications-top-left"
    - region "Notifications-top-right"
    - region "Notifications-bottom-left"
    - region "Notifications-bottom"
    - region "Notifications-bottom-right"
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('Superadmin - Tenants Management', () => {
  4  | 
  5  |   test('Superadmin can login and view tenants list', async ({ page }) => {
  6  |     // Navigate to superadmin login
  7  |     await page.goto('/superadmin/login');
  8  | 
  9  |     // Open config and set API URL to point to backend port 8000
> 10 |     await page.click('text=Configuració del servidor API');
     |                ^ Error: page.click: Test timeout of 30000ms exceeded.
  11 |     await page.fill('input[placeholder="https://api.domini.com/api/v1"]', 'http://127.0.0.1:8000/api/v1');
  12 |     await page.click('button:has-text("Desar")');
  13 | 
  14 |     // Make sure API url config is hidden or we just type directly
  15 |     await page.fill('input[type="email"]', 'admin@sevalor.com');
  16 |     await page.fill('input[type="password"]', 'superpassword');
  17 |     
  18 |     await Promise.all([
  19 |       page.waitForResponse(resp => resp.url().includes('/auth/login')),
  20 |       page.click('button[type="submit"]')
  21 |     ]);
  22 | 
  23 |     // Verify it redirects to telemetria
  24 |     await expect(page).toHaveURL(/\/superadmin\/telemetria/);
  25 | 
  26 |     // Navigate to Empreses
  27 |     await page.click('text=Gestió d\'Empreses');
  28 |     await expect(page).toHaveURL(/\/superadmin\/empreses/);
  29 | 
  30 |     // Verify we see the E2E Tenant seeded by seed_db
  31 |     await expect(page.locator('text=Test E2E Empresa')).toBeVisible();
  32 |     await expect(page.locator('text=e2e.campopro.cat')).toBeVisible();
  33 | 
  34 |     // Click on Edit
  35 |     const row = page.locator('tr', { hasText: 'Test E2E Empresa' });
  36 |     await row.locator('text=Editar').click();
  37 | 
  38 |     // Verify detail page
  39 |     await expect(page).toHaveURL(/\/superadmin\/empreses\/[a-f0-9-]{36}/);
  40 |     await expect(page.locator('h1')).toContainText('Test E2E Empresa');
  41 | 
  42 |     // Change status
  43 |     await page.selectOption('select', { label: 'SUSPÈS (Impagament)' });
  44 |     
  45 |     // Save changes
  46 |     page.on('dialog', dialog => dialog.accept());
  47 |     await page.click('text=Desar Canvis');
  48 | 
  49 |     // We can also verify the destructive action but let's just make sure it renders the button
  50 |     await expect(page.locator('button:has-text("Forçar Destrucció")')).toBeVisible();
  51 |   });
  52 | 
  53 | });
  54 | 
```