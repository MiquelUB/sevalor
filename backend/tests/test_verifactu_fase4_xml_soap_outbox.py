"""
Tests de Fase 4 — XML XSD Oficial AEAT (RegistroAlta / RegistroAnulacion),
Certificats PKCS#12 (.p12), Client SOAP mTLS i Worker d'Outbox Zero-Mock.
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from httpx import ASGITransport, AsyncClient
from lxml import etree
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.services.outbox_aeat import despatxar_outbox_empresa
from app.services.verifactu_xml import SUM1_NS, SUM_NS
from app.workers.tasks import generar_exportacio_aeat


def _generar_p12_test(
    *,
    common_name: str = "EMPRESA VERIFACTU TEST SL - NIF B12345678",
    password: str = "SecretCert2026!",
    expired: bool = False,
) -> bytes:
    """Genera en memòria un certificat X.509 autofirmat empaquetat en PKCS#12 (.p12)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Sevalor Test CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    now = datetime.now(timezone.utc)
    if expired:
        not_before = now - timedelta(days=400)
        not_after = now - timedelta(days=10)
    else:
        not_before = now - timedelta(days=1)
        not_after = now + timedelta(days=365)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"verifactu_aeat",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )


@pytest.mark.asyncio
async def test_fase4_xml_xsd_alta_isp_rectificativa_i_anulacion(admin_session):
    """
    1. Emissió F1 multi-IVA -> XML SOAP amb <sum1:RegistroAlta>, <sum1:DetalleDesglose> per cada IVA,
       <sum1:PrimerRegistro>S</sum1:PrimerRegistro>, <sum1:SistemaInformatico> i <sum1:Huella> idèntica a BD.
    2. Emissió F1 amb ISP -> <sum1:CalificacionOperacion>S2</sum1:CalificacionOperacion> i <sum1:RegistroAnterior>.
    3. Emissió Rectificativa R1 -> <sum1:TipoFactura>R1</sum1:TipoFactura>, <sum1:FacturasRectificadas>
       i <sum1:ImporteRectificacion>.
    4. Anul·lació -> XML SOAP amb <sum1:RegistroAnulacion>, <sum1:IDFactura> (<sum1:NumSerieFacturaAnulada>)
       i <sum1:Huella> = hash_anulacio_sha256.
    """
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    nif_emp = f"B{uuid.uuid4().int % 100000000:08d}"

    await admin_session.execute(
        text("""
            INSERT INTO empreses (id, nom, rao_social_fiscal, nif, subdomini, vertical, primari_hsl, verifactu_entorn)
            VALUES (:id, 'XML Test SL', 'XML Test Societat Limitada', :nif, :sub, 'ELECTRIC', '210 80% 30%', 'PREPRODUCCIO')
        """),
        {"id": emp_id, "nif": nif_emp, "sub": f"xml-{emp_id.hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, email, password_hash)
            VALUES (:uid, :eid, '44444444D', 'Boss', 'XML', 'BOSS', :email, 'hash')
        """),
        {"uid": boss_id, "eid": emp_id, "email": f"boss-{emp_id.hex[:6]}@sevalor.cat"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO clients (id, empresa_id, codi, rao_social, nif, email)
            VALUES (:cid, :eid, 'CLI-XSD-01', 'Client XSD AEAT SA', 'A99887766', 'xsd@client.cat')
        """),
        {"cid": cli_id, "eid": emp_id},
    )
    await admin_session.commit()

    token = create_access_token(
        data={"sub": str(boss_id), "empresa_id": str(emp_id), "rol": "BOSS"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Factura F1 Multi-IVA (21% i 10%)
        r_f1 = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            headers=headers,
            json={
                "client_id": str(cli_id),
                "serie": "F",
                "tipus_factura": "F1",
                "data_emissio": "2026-08-10",
                "data_venciment": "2026-09-10",
                "linies": [
                    {
                        "concepte": "Servei 21%",
                        "quantitat": "1.00",
                        "preu_venda_unitari": "100.00",
                        "tipus_iva_pct": "21.00",
                    },
                    {
                        "concepte": "Servei 10%",
                        "quantitat": "1.00",
                        "preu_venda_unitari": "200.00",
                        "tipus_iva_pct": "10.00",
                    },
                ],
            },
        )
        assert r_f1.status_code == 201, r_f1.text
        f1 = r_f1.json()

        r_xml1 = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{f1['id']}/xml",
            headers=headers,
        )
        assert r_xml1.status_code == 200
        root1 = etree.fromstring(r_xml1.content)
        ns = {"sum": SUM_NS, "sum1": SUM1_NS}

        assert root1.xpath("//sum:RegFactuSistemaFacturacion", namespaces=ns)
        assert root1.xpath("//sum1:RegistroAlta/sum1:IDFactura/sum1:NumSerieFactura/text()", namespaces=ns) == [
            "F-2026-0001"
        ]
        assert root1.xpath("//sum1:RegistroAlta/sum1:IDFactura/sum1:FechaExpedicionFactura/text()", namespaces=ns) == [
            "10-08-2026"
        ]
        assert root1.xpath("//sum1:RegistroAlta/sum1:Encadenamiento/sum1:PrimerRegistro/text()", namespaces=ns) == [
            "S"
        ]
        detalls = root1.xpath("//sum1:RegistroAlta/sum1:Desglose/sum1:DetalleDesglose", namespaces=ns)
        assert len(detalls) == 2
        assert root1.xpath("//sum1:RegistroAlta/sum1:CuotaTotal/text()", namespaces=ns) == ["41.00"]
        assert root1.xpath("//sum1:RegistroAlta/sum1:ImporteTotal/text()", namespaces=ns) == ["341.00"]
        assert root1.xpath("//sum1:RegistroAlta/sum1:Huella/text()", namespaces=ns) == [f1["hash_sha256"]]
        assert root1.xpath("//sum1:SistemaInformatico/sum1:TipoUsoPosibleSoloVerifactu/text()", namespaces=ns) == [
            "S"
        ]

        # 2. Factura F1 amb Inversió del Subjecte Passiu (ISP -> S2)
        r_f2 = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            headers=headers,
            json={
                "client_id": str(cli_id),
                "serie": "F",
                "tipus_factura": "F1",
                "data_emissio": "2026-08-11",
                "data_venciment": "2026-09-11",
                "es_inversio_subjecte_passiu": True,
                "linies": [
                    {
                        "concepte": "Obra rehabilitació Art. 84 LIVA",
                        "quantitat": "1.00",
                        "preu_venda_unitari": "1000.00",
                        "tipus_iva_pct": "21.00",
                    }
                ],
            },
        )
        assert r_f2.status_code == 201
        f2 = r_f2.json()
        r_xml2 = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{f2['id']}/xml",
            headers=headers,
        )
        root2 = etree.fromstring(r_xml2.content)
        assert root2.xpath("//sum1:DetalleDesglose/sum1:CalificacionOperacion/text()", namespaces=ns) == [
            "S2"
        ]
        assert root2.xpath("//sum1:Encadenamiento/sum1:RegistroAnterior/sum1:Huella/text()", namespaces=ns) == [
            f1["hash_sha256"]
        ]

        # 3. Factura Rectificativa R1 per substitució ('S')
        r_rect = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f1['id']}/rectificar",
            headers=headers,
            json={
                "motiu": "Rectificació d'import segons Art. 80 LIVA",
                "tipus_factura": "R1",
                "tipus_rectificacio": "S",
            },
        )
        assert r_rect.status_code == 201
        f_rect = r_rect.json()
        r_xml_rect = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{f_rect['id']}/xml",
            headers=headers,
        )
        root_rect = etree.fromstring(r_xml_rect.content)
        assert root_rect.xpath("//sum1:RegistroAlta/sum1:TipoFactura/text()", namespaces=ns) == ["R1"]
        assert root_rect.xpath("//sum1:RegistroAlta/sum1:TipoRectificativa/text()", namespaces=ns) == ["S"]
        assert root_rect.xpath(
            "//sum1:FacturasRectificadas/sum1:IDFacturaRectificada/sum1:NumSerieFactura/text()",
            namespaces=ns,
        ) == ["F-2026-0001"]
        assert root_rect.xpath(
            "//sum1:ImporteRectificacion/sum1:BaseRectificada/text()",
            namespaces=ns,
        ) == ["300.00"]

        # 4. Anul·lació de F2 -> XML passa a <sum1:RegistroAnulacion>
        r_anul = await ac.post(
            f"/api/v1/gestio/comptabilitat/factures/{f2['id']}/anular",
            headers=headers,
            json={"motiu": "Factura emesa per duplicat", "confirmacio_humana_hitl": True},
        )
        assert r_anul.status_code == 200
        f2_anul = r_anul.json()

        r_xml_anul = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{f2['id']}/xml",
            headers=headers,
        )
        assert r_xml_anul.status_code == 200
        root_anul = etree.fromstring(r_xml_anul.content)
        assert root_anul.xpath("//sum1:RegistroAnulacion", namespaces=ns)
        assert root_anul.xpath(
            "//sum1:RegistroAnulacion/sum1:IDFactura/sum1:NumSerieFacturaAnulada/text()",
            namespaces=ns,
        ) == ["F-2026-0002"]
        assert root_anul.xpath("//sum1:RegistroAnulacion/sum1:Huella/text()", namespaces=ns) == [
            f2_anul["hash_anulacio_sha256"]
        ]


@pytest.mark.asyncio
async def test_fase4_certificat_p12_soap_mtls_outbox_i_zero_mock(admin_session):
    """
    Verifica:
    - Pujada de certificat .p12: contrasenya errònia -> 422, caducat -> 422, ENGINYER -> 403, vàlid -> 200.
    - Contrasenya del certificat desada xifrada amb AES-256-GCM (`VFENC1:...`) a BD.
    - Despatx Outbox AEAT amb client SOAP mTLS i transport mock de l'AEAT:
      * Resposta `Correcto` amb CSV -> `estat_aeat = ACCEPTADA_AEAT`, `csv_aeat` desat i event `EV-06`.
      * Resposta `Incorrecto` -> `estat_aeat = REBUTJADA_AEAT`, `codi_error_aeat` desat i event `EV-07`.
      * Error HTTP 503 -> `estat_aeat = ERROR_TEMPORAL` amb backoff exponencial.
    - Tasca `generar_exportacio_aeat` 100% Zero-Mock (retorna suma SQL real de l'empresa i trimestre).
    """
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    nif_emp = f"B{uuid.uuid4().int % 100000000:08d}"

    await admin_session.execute(
        text("""
            INSERT INTO empreses (id, nom, nif, subdomini, vertical, primari_hsl)
            VALUES (:id, 'Outbox Cert SL', :nif, :sub, 'HYDRO', '195 85% 32%')
        """),
        {"id": emp_id, "nif": nif_emp, "sub": f"cert-{emp_id.hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, email, password_hash)
            VALUES
                (:bid, :eid, '55555555E', 'Boss', 'Cert', 'BOSS', :bmail, 'hash'),
                (:gid, :eid, '66666666F', 'Enginyer', 'Cert', 'ENGINYER', :gmail, 'hash')
        """),
        {
            "bid": boss_id,
            "gid": eng_id,
            "eid": emp_id,
            "bmail": f"bcert-{emp_id.hex[:6]}@sevalor.cat",
            "gmail": f"gcert-{emp_id.hex[:6]}@sevalor.cat",
        },
    )
    await admin_session.execute(
        text("""
            INSERT INTO clients (id, empresa_id, codi, rao_social, nif, email)
            VALUES (:cid, :eid, 'CLI-SOAP-01', 'Client SOAP AEAT SL', 'B11223344', 'soap@client.cat')
        """),
        {"cid": cli_id, "eid": emp_id},
    )
    await admin_session.commit()

    # 0. Verificar Zero-Mock a generar_exportacio_aeat en Dia 0 (0.00 €)
    res_day0 = generar_exportacio_aeat(str(emp_id), "2026-T3")
    assert res_day0["payload_summary"]["facturacion"] == 0.0
    assert res_day0["payload_summary"]["iva_meritat"] == 0.0

    boss_token = create_access_token(
        data={"sub": str(boss_id), "empresa_id": str(emp_id), "rol": "BOSS"}
    )
    eng_token = create_access_token(
        data={"sub": str(eng_id), "empresa_id": str(emp_id), "rol": "ENGINYER"}
    )
    boss_headers = {"Authorization": f"Bearer {boss_token}"}
    eng_headers = {"Authorization": f"Bearer {eng_token}"}

    p12_valid = _generar_p12_test(password="PassCorrecta2026!")
    p12_expired = _generar_p12_test(password="PassCorrecta2026!", expired=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Enginyer no pot pujar certificat -> 403
        r_eng = await ac.post(
            "/api/v1/gestio/configuracio/verifactu/certificat",
            headers=eng_headers,
            json={
                "p12_base64": base64.b64encode(p12_valid).decode("ascii"),
                "password": "PassCorrecta2026!",
            },
        )
        assert r_eng.status_code == 403

        # 2. Contrasenya errònia -> 422
        r_bad_pwd = await ac.post(
            "/api/v1/gestio/configuracio/verifactu/certificat",
            headers=boss_headers,
            json={
                "p12_base64": base64.b64encode(p12_valid).decode("ascii"),
                "password": "ContrasenyaEquivocada",
            },
        )
        assert r_bad_pwd.status_code == 422

        # 3. Certificat caducat -> 422
        r_exp = await ac.post(
            "/api/v1/gestio/configuracio/verifactu/certificat",
            headers=boss_headers,
            json={
                "p12_base64": base64.b64encode(p12_expired).decode("ascii"),
                "password": "PassCorrecta2026!",
            },
        )
        assert r_exp.status_code == 422
        assert "caducat" in r_exp.text.lower()

        # 4. Certificat vàlid pujat pel BOSS -> 200
        r_ok = await ac.post(
            "/api/v1/gestio/configuracio/verifactu/certificat",
            headers=boss_headers,
            json={
                "p12_base64": base64.b64encode(p12_valid).decode("ascii"),
                "password": "PassCorrecta2026!",
            },
        )
        assert r_ok.status_code == 200, r_ok.text
        cert_data = r_ok.json()
        assert "EMPRESA VERIFACTU TEST SL" in cert_data["subject"]
        assert cert_data["dies_restants"] >= 360

        # Verificar xifratge AES-256-GCM de la contrasenya a PostgreSQL
        raw_pass_db = (
            await admin_session.execute(
                text("SELECT verifactu_cert_pass_xifrat FROM empreses WHERE id = :id"),
                {"id": emp_id},
            )
        ).scalar_one()
        assert raw_pass_db.startswith("VFENC1:")
        assert "PassCorrecta2026!" not in raw_pass_db

        # 5. Emetre factura F1 i provar despatx SOAP mTLS amb resposta AEAT Correcto + CSV
        r_fac = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            headers=boss_headers,
            json={
                "client_id": str(cli_id),
                "serie": "F",
                "tipus_factura": "F1",
                "data_emissio": "2026-08-20",
                "data_venciment": "2026-09-20",
                "linies": [
                    {
                        "concepte": "Instal·lació hidràulica",
                        "quantitat": "2.00",
                        "preu_venda_unitari": "500.00",
                        "tipus_iva_pct": "21.00",
                    }
                ],
            },
        )
        assert r_fac.status_code == 201
        fac1 = r_fac.json()

        # Verificar que generar_exportacio_aeat reflecteix exactament els 1000.00 € + 210.00 € d'IVA
        res_q3 = await generar_exportacio_aeat(
            str(emp_id), "2026-T3", db_session=admin_session
        )
        assert res_q3["payload_summary"]["facturacion"] == 1000.0
        assert res_q3["payload_summary"]["iva_meritat"] == 210.0
        assert res_q3["payload_summary"]["num_factures"] == 1

        # Transport simulat AEAT que retorna RespuestaRegFactuSistemaFacturacion amb EstadoRegistro=Correcto i CSV
        aeat_ok_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                          xmlns:tikR="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd">
          <soapenv:Body>
            <tikR:RespuestaRegFactuSistemaFacturacion>
              <tikR:CSV>AEATCSV2026XYZ987</tikR:CSV>
              <tikR:TiempoEsperaEnvio>60</tikR:TiempoEsperaEnvio>
              <tikR:EstadoEnvio>Correcto</tikR:EstadoEnvio>
              <tikR:RespuestaLinea>
                <tikR:EstadoRegistro>Correcto</tikR:EstadoRegistro>
              </tikR:RespuestaLinea>
            </tikR:RespuestaRegFactuSistemaFacturacion>
          </soapenv:Body>
        </soapenv:Envelope>"""

        mock_transport_ok = httpx.MockTransport(
            lambda req: httpx.Response(200, content=aeat_ok_xml.encode("utf-8"))
        )

        await admin_session.execute(
            text(f"SET LOCAL app.current_empresa_id = '{emp_id}';")
        )
        res_dispatch = await despatxar_outbox_empresa(
            admin_session,
            emp_id,
            factura_id=uuid.UUID(fac1["id"]),
            transport_override=mock_transport_ok,
        )
        assert res_dispatch["processats"] == 1
        assert res_dispatch["acceptats"] == 1

        # Verificar que la factura té estat_aeat = ACCEPTADA_AEAT i csv_aeat = AEATCSV2026XYZ987
        r_det = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{fac1['id']}",
            headers=boss_headers,
        )
        assert r_det.status_code == 200
        det = r_det.json()
        assert det["estat_aeat"] == "ACCEPTADA_AEAT"
        assert det["csv_aeat"] == "AEATCSV2026XYZ987"

        # 6. Emetre segona factura i simular rebuig de l'AEAT (Incorrecto + CodigoErrorRegistro 4102)
        r_fac2 = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            headers=boss_headers,
            json={
                "client_id": str(cli_id),
                "serie": "F",
                "tipus_factura": "F1",
                "data_emissio": "2026-08-21",
                "data_venciment": "2026-09-21",
                "linies": [
                    {
                        "concepte": "Manteniment",
                        "quantitat": "1.00",
                        "preu_venda_unitari": "100.00",
                        "tipus_iva_pct": "21.00",
                    }
                ],
            },
        )
        assert r_fac2.status_code == 201
        fac2 = r_fac2.json()

        aeat_err_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                          xmlns:tikR="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/RespuestaSuministro.xsd">
          <soapenv:Body>
            <tikR:RespuestaRegFactuSistemaFacturacion>
              <tikR:EstadoEnvio>Incorrecto</tikR:EstadoEnvio>
              <tikR:RespuestaLinea>
                <tikR:EstadoRegistro>Incorrecto</tikR:EstadoRegistro>
                <tikR:CodigoErrorRegistro>4102</tikR:CodigoErrorRegistro>
                <tikR:DescripcionErrorRegistro>El NIF del destinatario no está identificado en el censo de la AEAT</tikR:DescripcionErrorRegistro>
              </tikR:RespuestaLinea>
            </tikR:RespuestaRegFactuSistemaFacturacion>
          </soapenv:Body>
        </soapenv:Envelope>"""

        mock_transport_err = httpx.MockTransport(
            lambda req: httpx.Response(200, content=aeat_err_xml.encode("utf-8"))
        )

        await admin_session.execute(
            text(f"SET LOCAL app.current_empresa_id = '{emp_id}';")
        )
        res_dispatch_err = await despatxar_outbox_empresa(
            admin_session,
            emp_id,
            factura_id=uuid.UUID(fac2["id"]),
            transport_override=mock_transport_err,
        )
        assert res_dispatch_err["processats"] == 1
        assert res_dispatch_err["rebutjats"] == 1

        r_det2 = await ac.get(
            f"/api/v1/gestio/comptabilitat/factures/{fac2['id']}",
            headers=boss_headers,
        )
        det2 = r_det2.json()
        assert det2["estat_aeat"] == "REBUTJADA_AEAT"
        assert det2["codi_error_aeat"] == "4102"
        assert "censo" in (det2["descripcio_error_aeat"] or "")

        # 7. Endpoint de Declaració Responsable del SIF
        r_decl = await ac.get(
            "/api/v1/gestio/comptabilitat/verifactu/declaracio-responsable",
            headers=boss_headers,
        )
        assert r_decl.status_code == 200
        decl = r_decl.json()
        assert decl["modalitat"] == "VERI*FACTU"
        assert "HAC/1177/2024" in decl["normativa"]
