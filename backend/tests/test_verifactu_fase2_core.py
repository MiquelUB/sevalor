"""Tests de Fase 2 Veri*factu (Ordre HAC/1177/2024): Huella SHA-256, QR Oficial AEAT, Cadena Global, Rectificatives Multi-IVA i Anul·lacions."""

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.contractes import ContracteManteniment
from app.models.models import (
    Client,
    Empresa,
    OutboxEnviamentAEAT,
    RegistreEsdevenimentsSIF,
    Usuari,
    VerifactuCadenaTenant,
)
from app.services.verifactu import (
    calcular_huella_alta_hac1177,
    calcular_huella_anulacio_hac1177,
    format_num_serie,
    generar_qr_svg_verifactu,
    generar_url_qr_aeat_hac1177,
)


def _make_boss_headers(empresa_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": str(user_id),
            "rol": "BOSS",
            "empresa_id": str(empresa_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "totp_activat": True,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(empresa_id)}


def test_fase2_vectors_oficials_huella_i_qr_hac1177() -> None:
    """
    Verifica els vectors exactes de l'Art. 13, 20 i 21 de l'Ordre HAC/1177/2024:
    - Cadena d'alta amb Huella buida al primer registre i encadenada al segon.
    - Cadena d'anul·lació encadenada.
    - Majúscules hex de 64 caràcters.
    - URL QR de Preproducció i Producció amb nif, numserie, fecha (DD-MM-YYYY) i importe.
    - Generació SVG amb nivell de correcció M.
    """
    ts = "2026-11-23T12:00:00+01:00"
    huella_1, raw_1, ts_out = calcular_huella_alta_hac1177(
        nif_emissor="b12345678",
        num_serie_factura="F-2026-0001",
        fecha_expedicion="2026-11-23",
        tipus_factura="F1",
        cuota_total=Decimal("210.00"),
        importe_total=Decimal("1210.00"),
        hash_anterior=None,
        fecha_hora_huso=ts,
    )
    expected_raw_1 = (
        "IDEmisorFactura=B12345678"
        "&NumSerieFactura=F-2026-0001"
        "&FechaExpedicionFactura=23-11-2026"
        "&TipoFactura=F1"
        "&CuotaTotal=210.00"
        "&ImporteTotal=1210.00"
        "&Huella="
        "&FechaHoraHusoGenRegistro=2026-11-23T12:00:00+01:00"
    )
    assert raw_1 == expected_raw_1
    assert ts_out == ts
    assert huella_1 == hashlib.sha256(expected_raw_1.encode("utf-8")).hexdigest().upper()
    assert len(huella_1) == 64
    assert huella_1.isupper() or huella_1.isdigit()

    # Segon registre encadenat
    ts_2 = "2026-11-23T12:05:00+01:00"
    huella_2, raw_2, _ = calcular_huella_alta_hac1177(
        nif_emissor="B12345678",
        num_serie_factura="F-2026-0002",
        fecha_expedicion=date(2026, 11, 23),
        tipus_factura="F1",
        cuota_total=Decimal("42.00"),
        importe_total=Decimal("242.00"),
        hash_anterior=huella_1,
        fecha_hora_huso=ts_2,
    )
    assert f"&Huella={huella_1}&FechaHoraHusoGenRegistro={ts_2}" in raw_2
    assert len(huella_2) == 64

    # Registre d'anul·lació encadenat a huella_2
    ts_3 = "2026-11-23T12:10:00+01:00"
    huella_anul, raw_anul, _ = calcular_huella_anulacio_hac1177(
        nif_emissor="B12345678",
        num_serie_anulada="F-2026-0001",
        fecha_expedicion_anulada="2026-11-23",
        hash_anterior=huella_2,
        fecha_hora_huso=ts_3,
    )
    expected_raw_anul = (
        "IDEmisorFacturaAnulada=B12345678"
        "&NumSerieFacturaAnulada=F-2026-0001"
        "&FechaExpedicionFacturaAnulada=23-11-2026"
        f"&Huella={huella_2}"
        f"&FechaHoraHusoGenRegistro={ts_3}"
    )
    assert raw_anul == expected_raw_anul
    assert huella_anul == hashlib.sha256(expected_raw_anul.encode("utf-8")).hexdigest().upper()

    # QR URL Preproducció i Producció
    qr_pre = generar_url_qr_aeat_hac1177(
        nif_emissor="B12345678",
        num_serie_factura="F-2026-0001",
        fecha_expedicion="2026-11-23",
        importe_total=Decimal("1210.00"),
        entorn="PREPRODUCCIO",
        modalitat="VERIFACTU",
    )
    assert qr_pre == (
        "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
        "?nif=B12345678&numserie=F-2026-0001&fecha=23-11-2026&importe=1210.00"
    )
    qr_prod = generar_url_qr_aeat_hac1177(
        nif_emissor="B12345678",
        num_serie_factura="F-2026-0001",
        fecha_expedicion="2026-11-23",
        importe_total=Decimal("1210.00"),
        entorn="PRODUCCIO",
        modalitat="VERIFACTU",
    )
    assert qr_prod == (
        "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"
        "?nif=B12345678&numserie=F-2026-0001&fecha=23-11-2026&importe=1210.00"
    )

    svg = generar_qr_svg_verifactu(qr_pre)
    assert svg.startswith("<svg")
    assert "viewBox=" in svg
    assert format_num_serie("F", 2026, 1) == "F-2026-0001"
    assert format_num_serie("R", 2026, 12) == "R-2026-0012"
    assert format_num_serie("SAAS", 2026, 3) == "SAAS-2026-0003"


@pytest.mark.asyncio
async def test_fase2_cadena_global_f_r_multi_iva_anulacio_i_contractes(admin_session) -> None:
    """
    Verifica:
    1. Emissió F-2026-0001 amb multi-IVA (10% + 21%), IRPF (15%) i Garantia 4308 (5%):
       - import_total_verifactu = Base + IVA (sense restar IRPF ni 4308) i és el valor codificat al QR.
       - liquid_exigible = Base + IVA - IRPF - Garantia 4308.
    2. Rectificativa R-2026-0001 (R1, I per diferències) encadenada a F-2026-0001 i preservant els 2 tipus d'IVA (10% i 21%).
    3. Anul·lació (RegistroAnulacion) de F-2026-0001 encadenada a R-2026-0001 + registre SIF EV-04 + Outbox ANULACION.
    4. Emissió posterior des de prefactura de contracte -> encadena amb el hash d'anul·lació de F-2026-0001!
    """
    emp_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    contracte_id = uuid.uuid4()
    suf = str(emp_id)[:8].upper()
    emp_nif = f"B{suf}"

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Verifactu Core {suf} SL",
            nif=emp_nif,
            subdomini=f"vfcore-{suf.lower()}",
            verifactu_entorn="PREPRODUCCIO",
        )
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(
                id=boss_id,
                empresa_id=emp_id,
                nif=f"1234{suf[:4]}A",
                nom="Director",
                rol="BOSS",
            ),
            Client(
                id=cli_id,
                empresa_id=emp_id,
                codi=f"CLI-{suf[:4]}",
                rao_social="Client Multi-IVA S.A.",
                nif="A87654321",
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add(
        ContracteManteniment(
            id=contracte_id,
            empresa_id=emp_id,
            client_id=cli_id,
            numero_contracte=f"CM-{suf[:4]}",
            import_anual=1200.00,
            periodicitat="MENSUAL",
            data_inici=date(2026, 1, 1),
            data_fi=date(2026, 12, 31),
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    headers = _make_boss_headers(emp_id, boss_id)
    avui_str = date(2026, 11, 23).isoformat()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Emetre Factura F-2026-0001 amb 2 línies (1000€ al 21% + 500€ al 10%), IRPF 10% i Garantia 5%
        res_f1 = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(cli_id),
                "serie": "F",
                "tipus_factura": "F1",
                "data_emissio": avui_str,
                "data_venciment": avui_str,
                "retencio_irpf_pct": 10.0,
                "retencio_garantia_pct": 5.0,
                "linies": [
                    {
                        "concepte": "Instal·lació Quadre BT",
                        "descripcio_detall": "Quadre general proteccions",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.00,
                        "tipus_iva_pct": 21.00,
                    },
                    {
                        "concepte": "Manteniment rehabilitació",
                        "quantitat": 1,
                        "preu_venda_unitari": 500.00,
                        "tipus_iva_pct": 10.00,
                    },
                ],
            },
            headers=headers,
        )
        assert res_f1.status_code == 201, res_f1.text
        f1 = res_f1.json()
        f1_id = f1["id"]
        assert f1["num_serie_verifactu"] == "F-2026-0001"
        assert f1["hash_anterior"] is None
        # Base = 1500.00, IVA = 210 + 50 = 260.00 -> import_total_verifactu = 1760.00
        # IRPF 10% = 150.00, Garantia 5% = 75.00 -> liquid_exigible = 1760 - 150 - 75 = 1535.00
        assert Decimal(str(f1["import_total_verifactu"])) == Decimal("1760.00")
        assert Decimal(str(f1["liquid_exigible"])) == Decimal("1535.00")
        assert "numserie=F-2026-0001" in f1["qr_verifactu_payload"]
        assert "importe=1760.00" in f1["qr_verifactu_payload"]

        # 2. Emetre Rectificativa Sèrie R (R1, I per diferències) sobre F-2026-0001
        res_r1 = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f1_id}/rectificar",
            json={
                "motiu": "Abonament per diferències multi-IVA",
                "tipus_factura": "R1",
                "tipus_rectificacio": "I",
            },
            headers=headers,
        )
        assert res_r1.status_code == 201, res_r1.text
        r1 = res_r1.json()
        assert r1["num_serie_verifactu"] == "R-2026-0001"
        assert r1["tipus_factura"] == "R1"
        assert r1["tipus_rectificacio"] == "I"
        assert r1["hash_anterior"] == f1["hash_sha256"]
        assert Decimal(str(r1["import_total_verifactu"])) == Decimal("-1760.00")

        # Verificar que les línies de R-2026-0001 preserven el 10% i el 21%
        res_r1_det = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{r1['id']}",
            headers=headers,
        )
        assert res_r1_det.status_code == 200
        tipus_ives_r1 = sorted(lin["tipus_iva"] for lin in res_r1_det.json()["linies"])
        assert tipus_ives_r1 == [10.0, 21.0]

        # 3. Anul·lar F-2026-0001 (RegistroAnulacion encadenat a R-2026-0001)
        res_anul = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f1_id}/anular",
            json={
                "motiu": "Emissió duplicada detectada en auditoria",
                "confirmacio_humana_hitl": True,
            },
            headers=headers,
        )
        assert res_anul.status_code == 200, res_anul.text
        f1_anul = res_anul.json()
        assert f1_anul["estat_anulacio"] == "ANULADA_VERIFACTU"
        assert len(f1_anul["hash_anulacio_sha256"]) == 64

        # Intentar anul·lar per segona vegada ha de retornar 409 Conflict
        res_anul_dup = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f1_id}/anular",
            json={"motiu": "Segon intent", "confirmacio_humana_hitl": True},
            headers=headers,
        )
        assert res_anul_dup.status_code == 409

        # 4. Prefacturar contracte de manteniment -> ha de néixer com ESBORRANY_PREFACTURA i després emetre's
        res_c_pref = await ac.post(
            f"/api/v1/gestio/contractes/{contracte_id}/prefacturar",
            headers=headers,
        )
        assert res_c_pref.status_code == 200, res_c_pref.text
        pref_c_id = res_c_pref.json()["factura_id"]

        res_pref_det = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{pref_c_id}",
            headers=headers,
        )
        assert res_pref_det.status_code == 200
        assert res_pref_det.json()["estat_document"] == "ESBORRANY_PREFACTURA"
        assert res_pref_det.json()["serie"] == "PRE"

        # Emetre la prefactura del contracte a Veri*factu (ha de ser F-2026-0002 i encadenar amb hash_anulacio_sha256!)
        res_emit_c = await ac.post(
            f"/api/v1/gestio/comptabilitat/prefactures/{pref_c_id}/emetre",
            json={"serie": "F", "data_emissio": avui_str, "confirmacio_humana_hitl": True},
            headers=headers,
        )
        assert res_emit_c.status_code == 200, res_emit_c.text
        f2 = res_emit_c.json()
        assert f2["num_serie_verifactu"] == "F-2026-0002"
        assert f2["hash_anterior"] == f1_anul["hash_anulacio_sha256"]

    # Verificar a PostgreSQL outbox (ALTA + ANULACION) i registre SIF EV-04
    cadena_db = (
        await admin_session.execute(
            select(VerifactuCadenaTenant).where(VerifactuCadenaTenant.empresa_id == emp_id)
        )
    ).scalar_one()
    assert cadena_db.ultim_hash_sha256 == f2["hash_sha256"]
    assert cadena_db.ultim_num_serie == "F-2026-0002"

    outbox_rows = (
        await admin_session.execute(
            select(OutboxEnviamentAEAT).where(OutboxEnviamentAEAT.empresa_id == emp_id)
        )
    ).scalars().all()
    tipus_outbox = [o.tipus_registre for o in outbox_rows]
    assert "ALTA" in tipus_outbox
    assert "ANULACION" in tipus_outbox

    ev_anul = (
        await admin_session.execute(
            select(RegistreEsdevenimentsSIF).where(
                RegistreEsdevenimentsSIF.empresa_id == emp_id,
                RegistreEsdevenimentsSIF.codi_esdeveniment == "EV-04",
            )
        )
    ).scalar_one_or_none()
    assert ev_anul is not None
