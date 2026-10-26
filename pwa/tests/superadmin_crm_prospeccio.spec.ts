import { test, expect } from '@playwright/test';
import crypto from 'node:crypto';

const JWT_SECRET = 'sevalor-dev-secret-key-32-chars-long-abc';

function createSuperadminToken() {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(
    JSON.stringify({
      sub: '00000000-0000-0000-0000-000000000000',
      rol: 'SUPERADMIN',
      role: 'SUPERADMIN',
      exp: Math.floor(Date.now() / 1000) + 7200,
    })
  ).toString('base64url');
  const data = `${header}.${body}`;
  const sig = crypto.createHmac('sha256', JWT_SECRET).update(data).digest('base64url');
  return `${data}.${sig}`;
}

test.use({ viewport: { width: 1280, height: 800 } });

test.describe('Superadmin CRM - Prospecció & Outreach B2B (E2E)', () => {
  test.beforeEach(async ({ context, page }) => {
    // 1. Injectar autenticació de Superadmin mitjançant cookie i localStorage
    const token = createSuperadminToken();
    await context.addCookies([
      {
        name: 'sevalor_access_token',
        value: token,
        url: 'http://127.0.0.1:3001',
      },
    ]);
    await page.addInitScript((tok) => {
      localStorage.setItem('sevalor_auth_token', JSON.stringify({ token: tok, timestamp: Date.now() }));
    }, token);

    // 2. Interceptar rutes API per a un test E2E determinista i resilient
    await page.route('**/api/v1/superadmin/crm/prospeccio/pipeline', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          etapes: ['PROSPECCIO', 'QUALIFICACIO', 'DEMO_7_DIES', 'PROPOSTA', 'GUANYAT', 'PERDUT'],
          totals_mrr: {
            PROSPECCIO: 350.0,
            QUALIFICACIO: 0.0,
            DEMO_7_DIES: 0.0,
            PROPOSTA: 0.0,
            GUANYAT: 0.0,
            PERDUT: 0.0,
          },
          columnes: {
            PROSPECCIO: [
              {
                id: '11111111-1111-1111-1111-111111111111',
                lead_id: 'aaaa1111-1111-1111-1111-111111111111',
                titol: 'Llicència CampoPro - Regs del Segrià SL',
                etapa: 'PROSPECCIO',
                valor_mensual_estimat: 350.0,
                valor_ia_setup: 0.0,
                probabilitat_percent: 25,
                nom_empresa: 'Regs del Segrià SL',
                vertical: 'CampoPro',
                nom_contacte: 'Jordi Prat',
                email: 'jordi@regssegria.cat',
                telefon: '973123456',
                data_fi_demo: null,
                demo_activa: false,
                created_at: new Date().toISOString(),
              },
            ],
            QUALIFICACIO: [],
            DEMO_7_DIES: [],
            PROPOSTA: [],
            GUANYAT: [],
            PERDUT: [],
          },
        }),
      });
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/leads', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'aaaa1111-1111-1111-1111-111111111111',
            nom_empresa: 'Regs del Segrià SL',
            nom_contacte: 'Jordi Prat',
            email: 'jordi@regssegria.cat',
            telefon: '973123456',
            vertical: 'CampoPro',
            estat_qualificacio: 'NOU',
            operaris_estimats: 5,
            score_qualificacio: 75,
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/tasques-cp', async (route) => {
      if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}');
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'OK',
            tasca_id: '99999999-9999-9999-9999-999999999999',
            codi_postal: body.codi_postal || '25001',
            vertical: body.vertical || 'CampoPro',
            operaris_minims: body.operaris_minims || 5,
            total_trobats: 2,
            total_seleccionats: 1,
            total_descartats: 1,
            total_duplicats: 0,
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: '99999999-9999-9999-9999-999999999999',
              codi_postal: '25001',
              vertical: 'Manteniment de Climatització Industrial',
              operaris_minims: 5,
              estat: 'COMPLETAT',
              total_trobats: 2,
              total_seleccionats: 1,
              total_descartats: 1,
              total_duplicats: 0,
              created_at: new Date().toISOString(),
            },
          ]),
        });
      }
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/tasques-cp/99999999-9999-9999-9999-999999999999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '99999999-9999-9999-9999-999999999999',
          codi_postal: '25001',
          vertical: 'Manteniment de Climatització Industrial',
          estat: 'COMPLETAT',
          candidats: [
            {
              id: 'c1111111-1111-1111-1111-111111111111',
              nom_empresa: 'Climatització Segrià SL',
              cif: 'B25123456',
              web_url: 'https://climasegria.cat',
              domini_normalitzat: 'climasegria.cat',
              adreca_fisica: 'Polígon El Segre, Nau 4, Lleida',
              decisor_nom: 'Antoni Solé',
              decisor_carrec: 'Director Tècnic',
              email_detectat: 'antoni@climasegria.cat',
              fonts_investigades: 'web,linkedin',
              score: 84,
              estat_decisio: 'SELECCIONAT',
              motiu_detallat_ia: 'Empresa amb 8 operaris i servei d\'assistència tècnica',
            },
            {
              id: 'c2222222-2222-2222-2222-222222222222',
              nom_empresa: 'Botiga Aire i Llum SL',
              cif: 'B25654321',
              web_url: 'https://aireillumlledia.cat',
              domini_normalitzat: 'aireillumlledia.cat',
              adreca_fisica: 'Carrer Major, 10, Lleida',
              decisor_nom: 'Carme Roca',
              decisor_carrec: 'Comercial Botiga',
              email_detectat: 'info@aireillumlledia.cat',
              fonts_investigades: 'web',
              score: 35,
              estat_decisio: 'DESCARTAT',
              motiu_detallat_ia: 'Comerç minorista sense quadrilles al terreny',
            },
          ],
        }),
      });
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/candidats/*/corregir-criteri', async (route) => {
      const body = JSON.parse(route.request().postData() || '{}');
      if (!body.motiu_correccio_humana || body.motiu_correccio_humana.length < 10) {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'La justificació humana ha de tenir com a mínim 10 caràcters.' }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'OK',
          nova_decisio: body.nova_decisio || 'DESCARTAT',
          motiu_correccio_humana: body.motiu_correccio_humana,
        }),
      });
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/calendari', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          pendents_aprovacio_avui: 1,
          total_esdeveniments: 3,
          items: [
            {
              id: 'm1111111-1111-1111-1111-111111111111',
              lead_id: 'aaaa1111-1111-1111-1111-111111111111',
              nom_empresa: 'Climatització Segrià SL',
              nom_contacte: 'Antoni Solé',
              vertical: 'Manteniment de Climatització Industrial',
              tipus_item_calendari: 'EMAIL_CAMPANYA',
              pas_sequencia: 1,
              tempo_dies_offset: 0,
              data_programada: new Date().toISOString(),
              direccio: 'OUTBOUND',
              estat_enviament: 'ESBORRANY_PROGRAMAT',
              estat_calendari: 'PENDENT_APROVACIO_AVUI',
              pendent_aprovacio: true,
              es_avui: true,
              remitent: 'tecnic@sevalor.net',
              destinatari: 'antoni@climasegria.cat',
              assumpte: 'Optimització de fulls de treball per a Climatització Segrià',
              cos_text: 'Hola Antoni, us presentem la solució Sevalor PWA i el Bot Oficial de Telegram.',
            },
            {
              id: 'm2222222-2222-2222-2222-222222222222',
              lead_id: 'aaaa1111-1111-1111-1111-111111111111',
              nom_empresa: 'Climatització Segrià SL',
              nom_contacte: 'Antoni Solé',
              vertical: 'Manteniment de Climatització Industrial',
              tipus_item_calendari: 'EMAIL_CAMPANYA',
              pas_sequencia: 2,
              tempo_dies_offset: 4,
              data_programada: new Date(Date.now() + 4 * 86400000).toISOString(),
              direccio: 'OUTBOUND',
              estat_enviament: 'ESBORRANY_PROGRAMAT',
              estat_calendari: 'ESBORRANY_PROGRAMAT',
              pendent_aprovacio: false,
              es_avui: false,
              remitent: 'tecnic@sevalor.net',
              destinatari: 'antoni@climasegria.cat',
              assumpte: 'Com altres instal·ladors han reduït un 40% el temps d\'administració',
              cos_text: 'Hola Antoni, un cas d\'èxit similar en el vostre sector...',
            },
            {
              id: 'm3333333-3333-3333-3333-333333333333',
              lead_id: 'aaaa1111-1111-1111-1111-111111111111',
              nom_empresa: 'Climatització Segrià SL',
              nom_contacte: 'Antoni Solé',
              vertical: 'Manteniment de Climatització Industrial',
              tipus_item_calendari: 'EMAIL_CAMPANYA',
              pas_sequencia: 3,
              tempo_dies_offset: 8,
              data_programada: new Date(Date.now() + 8 * 86400000).toISOString(),
              direccio: 'OUTBOUND',
              estat_enviament: 'ESBORRANY_PROGRAMAT',
              estat_calendari: 'ESBORRANY_PROGRAMAT',
              pendent_aprovacio: false,
              es_avui: false,
              remitent: 'tecnic@sevalor.net',
              destinatari: 'antoni@climasegria.cat',
              assumpte: 'Activació de la Demo Real de 7 dies per a Climatització Segrià',
              cos_text: 'Hola Antoni, us convidem a activar la demo...',
            },
          ],
        }),
      });
    });

    await page.route('**/api/v1/superadmin/crm/prospeccio/oportunitats/*/registrar-exit', async (route) => {
      const body = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'OK',
          etapa: 'GUANYAT',
          es_replicable: body.es_replicable ?? true,
          rao_tancament_exit: body.rao_tancament_exit || 'El Bot de Telegram els resol la signatura d\'albarans.',
          requisits_replicables: body.requisits_replicables || 'Empreses de fred industrial amb >5 operaris.',
        }),
      });
    });

    await page.goto('/superadmin/crm');
  });

  test('E2E: Explorador de CP amb Vertical Lliure, botó Preparar Següent CP i Justificació Obligatòria', async ({ page }) => {
    // 1. Canviar a la pestanya Explorador
    await page.click('button:has-text("Explorador de Leads per CP")');
    await expect(page.locator('text=Prospecció Atòmica per Codi Postal & Vertical Lliure')).toBeVisible();

    // 2. Input de Vertical lliure i Codi Postal
    const verticalInput = page.locator('input[placeholder*="climatització industrial"]');
    await verticalInput.fill('Manteniment de Climatització Industrial');

    const cpInput = page.locator('input[placeholder="ex: 25001"]');
    await cpInput.fill('25001');

    // 3. Provar el botó manual 'Preparar Següent CP' (sense auto-encadenament)
    await page.click('button:has-text("Preparar Següent CP")');
    await expect(cpInput).toHaveValue('25002');
    await expect(page.locator('text=Següent Codi Postal preparat (25002)')).toBeVisible();

    // Retornar a 25001 per carregar la tasca
    await cpInput.fill('25001');

    // 4. Llançar la cerca atòmica
    await page.click('button:has-text("Llançar Cerca Atòmica")');
    await expect(page.locator('text=CP 25001').first()).toBeVisible();
    await expect(page.locator('text=Climatització Segrià SL')).toBeVisible();

    // 5. Corregir criteri amb justificació humana obligatòria
    const row = page.locator('tr', { hasText: 'Climatització Segrià SL' });
    await row.locator('button:has-text("Corregir Criteri")').click();

    await expect(page.locator('text=Corregir Criteri de Prospecció (Doble Bucle)')).toBeVisible();

    // Justificació massa curta (< 10 caràcters) -> botó desactivat
    const motiuInput = page.locator('textarea[placeholder*="Per què canvies el criteri"]');
    await motiuInput.fill('Curt');
    const submitCorreccioBtn = page.locator('button:has-text("Guardar Correcció & Aprendre")');
    await expect(submitCorreccioBtn).toBeDisabled();

    // Justificació vàlida (>= 10 caràcters) -> botó s'activa
    await motiuInput.fill('Empresa dedicada exclusivament a climatització residencial petita, no industrial.');
    await expect(submitCorreccioBtn).toBeEnabled();
    await submitCorreccioBtn.click();
    await expect(page.locator('text=Corregir Criteri de Prospecció (Doble Bucle)')).toBeHidden();
  });

  test('E2E: Calendari Comercial & Campanyes amb tempo Pas 1 [D0], Pas 2 [D+4], Pas 3 [D+8] i botó HITL', async ({ page }) => {
    // 1. Canviar a la pestanya Calendari Comercial
    await page.click('button:has-text("Calendari Comercial & Campanyes")');
    await expect(page.locator('text=Calendari Comercial Integrat & Seqüències d\'Emails')).toBeVisible();

    // 2. Canviar al filtre 'Tots els Esdeveniments' per veure la seqüència sencera
    await page.click('button:has-text("Tots els Esdeveniments")');

    // 3. Verificar que es mostren els 3 passos de correu segons tempo
    await expect(page.getByText('Pas 1 [D0]').first()).toBeVisible();
    await expect(page.getByText('Pas 2 [D+4]').first()).toBeVisible();
    await expect(page.getByText('Pas 3 [D+8]').first()).toBeVisible();

    // 4. Verificar el botó HITL 'Aprovar i Enviar des de tecnic@sevalor.net'
    const enviarBtn = page.locator('button:has-text("Aprovar i Enviar des de tecnic@sevalor.net")').first();
    await expect(enviarBtn).toBeVisible();
  });

  test('E2E: Modal Registrar Tancament d\'Èxit Replicable (GUANYAT)', async ({ page }) => {
    // 1. Estar a la pestanya Pipeline Kanban
    await page.click('button:has-text("Pipeline Kanban")');
    await expect(page.locator('text=Regs del Segrià SL').first()).toBeVisible();

    // 2. Obrir modal de Tancament d'Èxit des del botó de la targeta (Passar a Guanyat Replicable)
    const exitBtn = page.locator('button[title*="Guanyat Replicable"]').first();
    await exitBtn.click({ force: true });

    await expect(page.locator('text=Registrar Tancament d\'Èxit Replicable (GUANYAT)')).toBeVisible();

    // 3. Omplir el formulari de tancament replicable
    const raoInput = page.locator('textarea[placeholder*="Tenien 12 instal·ladors"]');
    await raoInput.fill('El Bot Oficial de Telegram els permet fitxar i signar albarans d\'urgència sense cobertura.');

    const requisitsInput = page.locator('input[placeholder*="quadrilla > 8 operaris"]');
    await requisitsInput.fill('Instal·ladors de fred industrial amb servei 24h.');

    await expect(page.locator('input#replicable-toggle')).toBeChecked();

    const submitExitBtn = page.locator('button:has-text("Confirmar GUANYAT & Guardar Patró")');
    await expect(submitExitBtn).toBeEnabled();
    await submitExitBtn.click();

    await expect(page.locator('text=Registrar Tancament d\'Èxit Replicable (GUANYAT)')).toBeHidden();
    await expect(page.locator('text=Tancament registrat com a GUANYAT')).toBeVisible();
  });

  test('Norma Suprema: Prohibició estricta del mot WhatsApp a tota la interfície', async ({ page }) => {
    const pageContent = (await page.content()).toLowerCase();
    expect(pageContent).not.toContain('whatsapp');
  });
});
