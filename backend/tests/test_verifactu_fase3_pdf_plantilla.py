"""Tests de Fase 3 Veri*factu: Plantilla HTML + WeasyPrint, Inspecció PyMuPDF, Chameleon HSL, Emissor Xifrat i Seguretat XSS/SSRF."""

import base64
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pymupdf  # type: ignore[import-untyped]
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import Client, Empresa, Usuari
from app.services.verifactu import (
    _blocked_url_fetcher,
    renderitzar_html_factura_verifactu,
    renderitzar_pdf_factura_verifactu_bytes,
)

VALID_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_token_headers(empresa_id: uuid.UUID, user_id: uuid.UUID, rol: str = "BOSS") -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": str(user_id),
            "rol": rol,
            "empresa_id": str(empresa_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "totp_activat": True,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(empresa_id)}


def test_fase3_chameleon_hsl_logotip_multipagina_i_seguretat_xss_ssrf() -> None:
    """
    Verifica:
    - Injecció real de variables CSS HSL (--accent: hsl(210, 100%, 15%)) i logotip base64.
    - Auto-escaping estricte contra XSS (<script>alert(1)</script>).
    - Bloqueig SSRF i LFI a _blocked_url_fetcher (http://, https://, file://).
    - Paginació multipàgina (>= 2 pàgines amb 45 línies).
    """
    linies_45 = [
        {
            "concepte": f"Partida tècnica d'instal·lació #{i} <script>alert({i})</script>",
            "descripcio_detall": f"Subministrament i muntatge tram {i}",
            "quantitat": 2,
            "preu_venda_unitari": 50.00,
            "descompte_aplicat_pct": 5.0,
            "tipus_iva": 21.0,
            "subtotal": 95.00,
        }
        for i in range(1, 46)
    ]

    html_out = renderitzar_html_factura_verifactu(
        empresa_nom="ElectricPro Catalunya SL",
        empresa_rao_social="ElectricPro Catalunya S.L.U.",
        empresa_eslogan="Enginyeria i Baixa Tensió REBT",
        empresa_nif="B12345678",
        primari_hsl="210 100% 15%",
        logotip_bytes=VALID_PNG_BYTES,
        client_nom="Indústries Nord SA",
        client_nif="A99887766",
        serie="F",
        numero_factura=1,
        exercici=2026,
        num_serie_verifactu="F-2026-0001",
        data_emissio="2026-11-23",
        linies=linies_45,
        base_imposable=4275.00,
        quota_iva=897.75,
        import_total_verifactu=5172.75,
        import_total=5172.75,
        hash_actual="A" * 64,
    )

    assert "--accent: hsl(210, 100%, 15%);" in html_out
    assert "#1b4332" not in html_out
    assert "data:image/png;base64," in html_out
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out

    # Protecció SSRF i LFI al url_fetcher de WeasyPrint
    with pytest.raises(ValueError, match="SSRF_PROTECTION"):
        _blocked_url_fetcher("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ValueError, match="SSRF_PROTECTION"):
        _blocked_url_fetcher("file:///etc/passwd")

    # Renderització PDF multipàgina (45 línies -> >= 2 pàgines)
    pdf_bytes = renderitzar_pdf_factura_verifactu_bytes(
        empresa_nom="ElectricPro Catalunya SL",
        empresa_nif="B12345678",
        primari_hsl="210 100% 15%",
        logotip_bytes=VALID_PNG_BYTES,
        client_nom="Indústries Nord SA",
        client_nif="A99887766",
        serie="F",
        numero_factura=1,
        exercici=2026,
        num_serie_verifactu="F-2026-0001",
        data_emissio="2026-11-23",
        linies=linies_45,
        base_imposable=4275.00,
        quota_iva=897.75,
        import_total_verifactu=5172.75,
        import_total=5172.75,
        hash_actual="A" * 64,
    )
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 2
    full_text = "\n".join(page.get_text() for page in doc)
    assert "Partida tècnica d'instal·lació #1" in full_text
    assert "Partida tècnica d'instal·lació #45" in full_text
    assert "QR tributario" in full_text
    assert "VERI*FACTU" in full_text
    doc.close()


@pytest.mark.asyncio
async def test_fase3_configuracio_emissor_xifrat_i_variants_pdf_e2e(admin_session) -> None:
    """
    Verifica:
    1. PUT /gestio/configuracio/empresa desa IBAN xifrat amb AES-256-GCM (VFENC1:), registre mercantil i dades fiscals.
    2. GET /gestio/configuracio/empresa retorna IBAN desxifrat al BOSS però l'oculta (None) a l'ENGINYER (C-05).
    3. PDF d'Esborrany (PRE) NO mostra 'QR tributario' i mostra l'avís d'esborrany.
    4. PDF de Factura Emesa (F-2026-0001) mostra totes les dades de la plantilla (IBAN, RM, Total factura vs Total líquid a pagar, Suplerts 554, IRPF, Garantia 4308).
    5. PDF de Rectificativa (R-2026-0001) mostra el bloc de factura rectificativa i PDF d'Anul·lada mostra l'avís d'anul·lació.
    """
    emp_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    suf = str(emp_id)[:8].upper()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"HydroPro {suf} SL",
            nif=f"B{suf}",
            subdomini=f"hydro-f3-{suf.lower()}",
            primari_hsl="195 85% 25%",
        )
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(id=boss_id, empresa_id=emp_id, nif=f"1111{suf[:4]}A", nom="Boss", rol="BOSS"),
            Usuari(id=eng_id, empresa_id=emp_id, nif=f"2222{suf[:4]}B", nom="Enginyer", rol="ENGINYER"),
            Client(
                id=cli_id,
                empresa_id=emp_id,
                codi=f"C-{suf[:4]}",
                rao_social="Comunitat Regants Ter",
                nif="G17223344",
                adreca_fiscal="Camí del Canal, 12",
                codi_postal="17100",
                poblacio="La Bisbal d'Empordà",
                provincia="Girona",
                email="factures@regantster.cat",
            ),
        ]
    )
    await admin_session.flush()

    h_boss = _make_token_headers(emp_id, boss_id, "BOSS")
    h_eng = _make_token_headers(emp_id, eng_id, "ENGINYER")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Configurar dades d'emissor amb IBAN i Registre Mercantil
        res_cfg = await ac.put(
            "/api/v1/gestio/configuracio/empresa",
            json={
                "rao_social_fiscal": f"HydroPro {suf} Societat Limitada",
                "eslogan_activitat": "Enginyeria Hidràulica i Bombament Solar",
                "adreca": "Polígon Industrial Sud, Nau 8",
                "codi_postal": "17005",
                "poblacio": "Girona",
                "provincia": "Girona",
                "telefon_facturacio": "+34 972 11 22 33",
                "email_facturacio": "admin@hydropro.cat",
                "titular_compte_bancari": f"HydroPro {suf} SL",
                "iban_cobrament": "ES79 2100 0813 6101 2345 6789",
                "dades_registre_mercantil": "Inscrita al RM de Girona, Tom 3100, Foli 88, Full GI-55443",
                "verifactu_entorn": "PREPRODUCCIO",
            },
            headers=h_boss,
        )
        assert res_cfg.status_code == 200, res_cfg.text

        # Verificar xifratge en repòs a PostgreSQL
        emp_db = (await admin_session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
        assert emp_db.iban_cobrament_xifrat is not None
        assert emp_db.iban_cobrament_xifrat.startswith("VFENC1:")
        assert "ES7921000813610123456789" not in emp_db.iban_cobrament_xifrat

        # BOSS veu l'IBAN desxifrat; ENGINYER rep None (C-05 Zero-Trust)
        res_get_boss = await ac.get("/api/v1/gestio/configuracio/empresa", headers=h_boss)
        assert res_get_boss.status_code == 200
        assert res_get_boss.json()["iban_cobrament"] == "ES7921000813610123456789"

        res_get_eng = await ac.get("/api/v1/gestio/configuracio/empresa", headers=h_eng)
        assert res_get_eng.status_code == 200
        assert res_get_eng.json()["iban_cobrament"] is None
        assert res_get_eng.json()["titular_compte_bancari"] is None

        # 2. Crear Pre-factura en esborrany i verificar PDF d'esborrany
        avui = date(2026, 11, 23).isoformat()
        res_pre = await ac.post(
            "/api/v1/gestio/comptabilitat/prefactures",
            json={
                "client_id": str(cli_id),
                "serie": "PRE",
                "data_emissio": avui,
                "data_operacio": "2026-11-20",
                "data_venciment": "2026-12-23",
                "referencia_client": "EXP-2026-99",
                "retencio_irpf_pct": 15.0,
                "retencio_garantia_pct": 5.0,
                "justificant_suplerts_pdf_path": "/docs/taxa_aca.pdf",
                "notes_factura": "Garantia de 2 anys en peces i mà d'obra.",
                "linies": [
                    {
                        "concepte": "Bomba submergible 15kW",
                        "descripcio_detall": "Inclou variador de freqüència trifàsic",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.00,
                        "descompte_aplicat_pct": 10.0,
                        "tipus_iva_pct": 21.00,
                    },
                    {
                        "concepte": "Taxa connexió ACA (Suplert)",
                        "compte_pgc": "554000",
                        "quantitat": 1,
                        "preu_venda_unitari": 50.00,
                        "tipus_iva_pct": 0.00,
                    },
                ],
            },
            headers=h_boss,
        )
        assert res_pre.status_code == 201, res_pre.text
        pre_id = res_pre.json()["id"]

        pdf_pre_res = await ac.get(f"/api/v1/gestio/comptabilitat/factures/{pre_id}/pdf", headers=h_boss)
        assert pdf_pre_res.status_code == 200
        doc_pre = pymupdf.open(stream=pdf_pre_res.content, filetype="pdf")
        txt_pre = " ".join(" ".join(p.get_text() for p in doc_pre).split())
        doc_pre.close()
        assert "Pre-factura (Esborrany)" in txt_pre
        assert "ESBORRANY / PRE-FACTURA" in txt_pre
        assert "QR tributario" not in txt_pre

        # 3. Emetre definitivament la pre-factura -> F-2026-0001 i inspeccionar el PDF oficial
        res_emit = await ac.post(
            f"/api/v1/gestio/comptabilitat/prefactures/{pre_id}/emetre",
            json={"serie": "F", "data_emissio": avui, "confirmacio_humana_hitl": True},
            headers=h_boss,
        )
        assert res_emit.status_code == 200, res_emit.text

        pdf_em_res = await ac.get(f"/api/v1/gestio/comptabilitat/factures/{pre_id}/pdf", headers=h_boss)
        assert pdf_em_res.status_code == 200
        doc_em = pymupdf.open(stream=pdf_em_res.content, filetype="pdf")
        txt_em = " ".join(" ".join(p.get_text() for p in doc_em).split())
        doc_em.close()

        assert "N.º F-2026-0001" in txt_em
        assert "QR tributario" in txt_em
        assert "VERI*FACTU" in txt_em
        assert "Factura verificable a la seu electrònica de l'AEAT" in txt_em
        assert "ES7921000813610123456789" in txt_em
        assert "Inscrita al RM de Girona" in txt_em
        assert "Inclou variador de freqüència trifàsic" in txt_em
        assert "EXP-2026-99" in txt_em
        # Base = 900.00 (1000 - 10%), IVA 21% = 189.00 -> Total factura = 1089.00 €
        # + Suplerts 50.00 - IRPF 135.00 - Garantia 45.00 -> Total líquid a pagar = 959.00 €
        assert "Total factura" in txt_em
        assert "1089.00 €" in txt_em
        assert "Suplerts exempts (compte 554)" in txt_em
        assert "Total líquid a pagar" in txt_em
        assert "959.00 €" in txt_em

        # 4. Emetre Rectificativa R-2026-0001 i inspeccionar el seu PDF
        res_rect = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{pre_id}/rectificar",
            json={
                "motiu": "Descompte addicional pactat en revisió d'obra",
                "tipus_factura": "R1",
                "tipus_rectificacio": "S",
            },
            headers=h_boss,
        )
        assert res_rect.status_code == 201
        rect_id = res_rect.json()["id"]

        pdf_rect_res = await ac.get(f"/api/v1/gestio/comptabilitat/factures/{rect_id}/pdf", headers=h_boss)
        assert pdf_rect_res.status_code == 200
        doc_rect = pymupdf.open(stream=pdf_rect_res.content, filetype="pdf")
        txt_rect = " ".join(" ".join(p.get_text() for p in doc_rect).split())
        doc_rect.close()
        assert "Factura rectificativa" in txt_rect
        assert "N.º R-2026-0001" in txt_rect
        assert "Rectifica la factura F-2026-0001" in txt_rect
        assert "Per substitució (S)" in txt_rect
        assert "Descompte addicional pactat en revisió d'obra" in txt_rect

        # 5. Anul·lar F-2026-0001 i comprovar que el PDF regenerat mostra l'estat ANUL·LADA
        res_anul = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{pre_id}/anular",
            json={"motiu": "Anul·lació de prova Fase 3", "confirmacio_humana_hitl": True},
            headers=h_boss,
        )
        assert res_anul.status_code == 200

        pdf_anul_res = await ac.get(f"/api/v1/gestio/comptabilitat/factures/{pre_id}/pdf", headers=h_boss)
        assert pdf_anul_res.status_code == 200
        doc_anul = pymupdf.open(stream=pdf_anul_res.content, filetype="pdf")
        txt_anul = " ".join(" ".join(p.get_text() for p in doc_anul).split())
        doc_anul.close()
        assert "FACTURA ANUL·LADA A VERI*FACTU" in txt_anul
