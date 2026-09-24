# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login.spec.ts >> Auditoria de Test 1: PWA Login E2E >> Test 1: Login reeixit injectant JWT al localStorage
- Location: tests/login.spec.ts:14:7

# Error details

```
TimeoutError: page.waitForFunction: Timeout 10000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e2]:
    - banner [ref=e3]:
      - heading "Sevalor" [level=1] [ref=e4]
      - generic [ref=e5]: Operari
    - main [ref=e7]:
      - generic [ref=e8]:
        - generic [ref=e9]:
          - button "Commutar Tema" [ref=e10] [cursor=pointer]
          - heading "SEVALOR" [level=1] [ref=e21]
          - paragraph [ref=e22]: Terminal de Camp d'Operari
        - generic [ref=e23]:
          - generic [ref=e24]: Failed to fetch
          - generic [ref=e28]:
            - generic [ref=e29]: DNI / NIF de l'Operari
            - 'textbox "Ex: 12345678A" [ref=e31]': 12345678A
          - paragraph [ref=e33]: PIN de 4 dígits
          - generic [ref=e39]:
            - button "1" [ref=e40] [cursor=pointer]
            - button "2" [ref=e41] [cursor=pointer]
            - button "3" [ref=e42] [cursor=pointer]
            - button "4" [active] [ref=e43] [cursor=pointer]
            - button "5" [ref=e44] [cursor=pointer]
            - button "6" [ref=e45] [cursor=pointer]
            - button "7" [ref=e46] [cursor=pointer]
            - button "8" [ref=e47] [cursor=pointer]
            - button "9" [ref=e48] [cursor=pointer]
            - button "C" [ref=e49] [cursor=pointer]
            - button "0" [ref=e50] [cursor=pointer]
            - button [ref=e51] [cursor=pointer]
          - generic [ref=e56]: "NIF:12345678A PIN: LEN:0"
          - button "Entrar al Terminal" [disabled] [ref=e57]
        - button "Configuració del servidor API" [ref=e61] [cursor=pointer]
    - navigation [ref=e66]:
      - generic [ref=e67]:
        - link "Feines" [ref=e68] [cursor=pointer]:
          - /url: /operari/feines/
        - link "Material" [ref=e73] [cursor=pointer]:
          - /url: /operari/material/
        - link "Vehicles" [ref=e79] [cursor=pointer]:
          - /url: /operari/vehicles/
        - link "Ajustos" [ref=e86] [cursor=pointer]:
          - /url: /operari/ajustos/
  - alert [ref=e91]
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe.serial('Auditoria de Test 1: PWA Login E2E', () => {
  4  |   let dialogMessage = '';
  5  | 
  6  |   test.beforeEach(async ({ page }) => {
  7  |     page.on('dialog', async dialog => {
  8  |       dialogMessage = dialog.message();
  9  |       await dialog.accept();
  10 |     });
  11 |     await page.goto('/operari/login');
  12 |   });
  13 | 
  14 |   test('Test 1: Login reeixit injectant JWT al localStorage', async ({ page }) => {
  15 |     const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
  16 |     await nifInput.fill('12345678A'); // Operari creat al seed_db.py
  17 | 
  18 |     // PIN correcte és 1234
  19 |     await page.click('button:has-text("1")');
  20 |     await page.click('button:has-text("2")');
  21 |     await page.click('button:has-text("3")');
  22 |     await page.click('button:has-text("4")');
  23 |     
  24 |     
> 25 |     await page.waitForFunction(() => localStorage.getItem('sevalor_auth_token') !== null || document.cookie.includes('sevalor_auth_token'), null, { timeout: 10000 });
     |                ^ TimeoutError: page.waitForFunction: Timeout 10000ms exceeded.
  26 | 
  27 |     const token = await page.evaluate(() => localStorage.getItem('sevalor_auth_token'));
  28 |     expect(token).toBeTruthy();
  29 |   });
  30 | 
  31 |   test('Test 2: Login invàlid -> Missatge d\'error', async ({ page }) => {
  32 |     const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
  33 |     await nifInput.fill('12345678A');
  34 | 
  35 |     // PIN incorrecte (1111)
  36 |     await page.click('button:has-text("1")');
  37 |     await page.click('button:has-text("1")');
  38 |     await page.click('button:has-text("1")');
  39 |     await page.click('button:has-text("1")');
  40 |     
  41 |     await expect(page.locator('text=invàlides, text=incorrecte, text=Error')).toBeVisible({ timeout: 5000 });
  42 |   });
  43 | 
  44 |   test('Test 3: Bloqueig al 4t intent fallit de PIN', async ({ page }) => {
  45 |     const nifInput = page.locator('input[placeholder="Ex: 12345678A"]');
  46 |     await nifInput.fill('12345678A');
  47 |     
  48 |     for (let i = 0; i < 3; i++) {
  49 |       await page.click('button:has-text("2")');
  50 |       await page.click('button:has-text("2")');
  51 |       await page.click('button:has-text("2")');
  52 |       await page.click('button:has-text("2")');
  53 |         
  54 |     }
  55 |   });
  56 | });
  57 | 
```