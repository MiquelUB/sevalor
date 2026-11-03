"""Tests de Fase 2: Validació d'Escriptura i Streaming als Mòduls Operatius cap al Disc del Client."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.models import CarpetaPlanol, Empresa, Usuari


@pytest.mark.asyncio
async def test_alta_client_magatzem_i_proveidor_sync_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que l'alta de client, article i proveïdor genera automàticament les fitxes JSON al disc dur del client."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_client_{empresa_id.hex[:6]}"

    # Donar d'alta l'empresa amb el disc_dur_url apuntant a tmp_path
    emp = Empresa(
        id=empresa_id,
        nom="Instal·lacions del Vallès SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}Z",
        subdomini=f"valles-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    # 1. Alta de Client
    client_payload = {
        "codi": f"CLI-{uuid.uuid4().hex[:6]}",
        "rao_social": "Comunitat Propietaris Provença 123",
        "nif": f"H{uuid.uuid4().int % 10000000:07d}C",
        "direccio": "Carrer de Provença 123, Barcelona",
        "telefon": "934567890",
        "email": "provenca123@comunitats.cat",
    }
    resp_cli = await async_client.post("/gestio/clients", json=client_payload)
    assert resp_cli.status_code == 201, resp_cli.text
    cli_data = resp_cli.json()
    client_id = cli_data["id"]

    fitxa_client = disc_empresa / "01_clients" / "fitxes" / f"{client_id}.json"
    assert fitxa_client.exists(), f"Fitxa de client no trobada a {fitxa_client}"
    assert "Provença 123" in fitxa_client.read_text(encoding="utf-8")

    # 2. Alta d'Article a Magatzem
    art_payload = {
        "referencia_inventari": f"REF-{uuid.uuid4().hex[:6]}",
        "nom": "Bomba Hidràulica Grundfos 1.5kW",
        "familia": "BOMBES",
        "unitat_mesura": "UDS",
        "estoc_optim": 10.0,
        "estoc_minim": 2.0,
        "preu_cost": 285.50,
        "preu_venda": 420.00,
    }
    resp_art = await async_client.post("/gestio/magatzem/articles", json=art_payload)
    assert resp_art.status_code == 201, resp_art.text
    art_data = resp_art.json()
    article_id = art_data["id"]

    fitxa_article = disc_empresa / "03_magatzem" / "articles_i_estoc" / f"{article_id}.json"
    assert fitxa_article.exists(), f"Fitxa d'article no trobada a {fitxa_article}"
    assert "Grundfos" in fitxa_article.read_text(encoding="utf-8")

    # 3. Alta de Proveïdor
    prov_payload = {
        "codi": f"PRV-{uuid.uuid4().hex[:6]}",
        "rao_social": "Subministraments Industrials BCN SA",
        "nif": f"A{uuid.uuid4().int % 10000000:07d}K",
        "telefon": "932223344",
        "email": "pedidos@subministramentsbcn.com",
        "especialitat": "FONTANERIA",
        "iban": "ES9121000418450200051332",
    }
    resp_prov = await async_client.post("/gestio/proveidors", json=prov_payload)
    assert resp_prov.status_code == 201, resp_prov.text
    prov_data = resp_prov.json()
    proveidor_id = prov_data["id"]

    fitxa_prov = disc_empresa / "02_proveidors" / "fitxes" / f"{proveidor_id}.json"
    assert fitxa_prov.exists(), f"Fitxa de proveïdor no trobada a {fitxa_prov}"
    assert "Subministraments Industrials" in fitxa_prov.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_pujar_i_servir_planol_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que la pujada de plànol s'emmagatzema exclusivament al disc del client i es serveix via gateway."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_planols_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Enginyeria Solar SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}Y",
        subdomini=f"solar-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    carpeta = CarpetaPlanol(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        nom="Projecte Gran Via",
        categoria="CLIENTS",
    )
    admin_session.add(carpeta)
    await admin_session.commit()

    contingut_dxf = b"0\nSECTION\n2\nENTITIES\n0\nLINE\n8\nCAPA_SOLAR\n0\nENDSEC\n0\nEOF\n"
    fitxers = {
        "fitxer": ("esquema_fotovoltaic.dxf", contingut_dxf, "application/dxf"),
    }
    data_form = {
        "carpeta_id": str(carpeta.id),
        "titol": "Esquema Fotovoltaic Gran Via",
        "codi_referencia": f"PLN-SOL-{uuid.uuid4().hex[:4]}",
        "tipus_fitxer": "DXF",
    }

    resp_up = await async_client.post("/gestio/planols/upload", data=data_form, files=fitxers)
    assert resp_up.status_code == 201, resp_up.text
    planol_id = resp_up.json()["id"]

    # Comprovar que el fitxer binari s'ha desat al disc del client
    carpeta_planols = disc_empresa / "05_planols" / "arxius_base"
    fitxers_desats = list(carpeta_planols.glob("*esquema_fotovoltaic.dxf"))
    assert len(fitxers_desats) == 1
    assert fitxers_desats[0].read_bytes() == contingut_dxf

    # Comprovar que el fitxer es serveix correctament des de la passarel·la
    resp_down = await async_client.get(f"/gestio/planols/{planol_id}/fitxer")
    assert resp_down.status_code == 200
    assert resp_down.content == contingut_dxf


@pytest.mark.asyncio
async def test_reportar_incidencia_amb_multimedia_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que les incidències de camp desen fotos i àudios exclusivament al disc dur del client."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_incidencies_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Clima Express SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}W",
        subdomini=f"clima-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    # Crear operari
    operari_id = uuid.uuid4()
    op_user = Usuari(
        id=operari_id,
        empresa_id=empresa_id,
        nom="Jordi",
        cognoms="Roca",
        nif="12345678A",
        email=f"jordi_{operari_id.hex[:4]}@clima.cat",
        password_hash="x",
        rol="OPERARI",
        estat="ACTIU",
    )
    admin_session.add(op_user)
    await admin_session.commit()

    # Generar token d'operari
    op_payload = {
        "sub": str(operari_id),
        "rol": "OPERARI",
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    op_token = jwt.encode(op_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    op_headers = {
        "Authorization": f"Bearer {op_token}",
        "X-Empresa-ID": str(empresa_id),
    }

    audio_bytes = b"RIFF....WAVEfmt ....data...audiodemostra"
    foto_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF...fotodemostra"
    files = {
        "audio": ("incidencia_soroll.webm", audio_bytes, "audio/webm"),
        "foto": ("incidencia_fuga.webp", foto_bytes, "image/webp"),
    }
    data_form = {
        "ambit": "TASCA",
        "estat": "VERMELL",
        "text_observacions": "Fuga greu d'aigua a la bomba de pressió",
    }

    resp = await async_client.post(
        "/operari/incidencies",
        data=data_form,
        files=files,
        headers=op_headers,
    )
    assert resp.status_code == 201, resp.text
    inci_id = resp.json()["id"]

    # Verificar que l'àudio s'ha guardat a 07_incidencies/audios_veu
    carpeta_audios = disc_empresa / "07_incidencies" / "audios_veu"
    audios = list(carpeta_audios.glob("*incidencia_soroll.webm"))
    assert len(audios) == 1
    assert audios[0].read_bytes() == audio_bytes

    # Verificar que la foto s'ha guardat a 07_incidencies/fotos_camp
    carpeta_fotos = disc_empresa / "07_incidencies" / "fotos_camp"
    fotos = list(carpeta_fotos.glob("*incidencia_fuga.webp"))
    assert len(fotos) == 1
    assert fotos[0].read_bytes() == foto_bytes

    # Verificar que el registre JSON s'ha guardat a 07_incidencies/registres
    carpeta_registres = disc_empresa / "07_incidencies" / "registres"
    fitxa_inci = carpeta_registres / f"{inci_id}.json"
    assert fitxa_inci.exists()
    assert "Fuga greu d'aigua" in fitxa_inci.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_crear_factura_pdf_i_json_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que les factures Veri*factu PDF i metadades JSON es desen al disc del client."""
    from app.models.models import Client

    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_factures_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Comptabilitat i Serveis SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}F",
        subdomini=f"compta-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    cli = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=f"CLI-{uuid.uuid4().hex[:6]}",
        rao_social="Client Facturacio SL",
        nif="B99887766",
        adreca_fiscal="Carrer Marina 45",
    )
    admin_session.add(cli)
    await admin_session.commit()

    fac_payload = {
        "numero_factura": 42,
        "serie": "2026",
        "client_id": str(cli.id),
        "base_imposable": 1000.00,
        "quota_iva": 210.00,
        "import_retencio": 0.0,
        "import_suplits": 0.0,
        "liquid_exigible": 1210.00,
        "data_emissio": "2026-11-03",
    }
    resp = await async_client.post("/gestio/comptabilitat/factures", json=fac_payload)
    assert resp.status_code == 201, resp.text
    factura_data = resp.json()
    factura_id = factura_data["id"]

    # 1. Comprovar que el PDF és a 04_factures/emeses_verifactu_pdf
    carpeta_factures = disc_empresa / "04_factures" / "emeses_verifactu_pdf"
    pdfs = list(carpeta_factures.glob("FACTURA_2026_00042_*.pdf"))
    assert len(pdfs) == 1
    assert pdfs[0].stat().st_size > 0

    # 2. Comprovar que el JSON de metadades és a 04_factures/emeses_verifactu_pdf/FACTURA_2026_00042.json
    fitxa_fac = carpeta_factures / "FACTURA_2026_00042.json"
    assert fitxa_fac.exists()
    assert "Client Facturacio SL" in fitxa_fac.read_text(encoding="utf-8")

    # 3. Comprovar descàrrega per streaming del PDF des del disc del client
    resp_pdf = await async_client.get(f"/gestio/comptabilitat/factures/{factura_id}/pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert len(resp_pdf.content) == pdfs[0].stat().st_size
