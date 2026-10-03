const fs = require('fs');
let code = fs.readFileSync('pwa/tests/superadmin_tenants.spec.ts', 'utf8');
code = code.replace(
  "await expect(page.locator('text=Test E2E Empresa')).toBeVisible();",
  "try { await expect(page.locator('text=Test E2E Empresa')).toBeVisible(); } catch(e) { console.log(await page.content()); throw e; }"
);
fs.writeFileSync('pwa/tests/superadmin_tenants.spec.ts', code);
