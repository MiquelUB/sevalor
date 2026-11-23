"""
Generador XML Oficial Veri*factu conforme als esquemes XSD de l'AEAT (Ordre HAC/1177/2024):
- SuministroLR.xsd (RegFactuSistemaFacturacion)
- SuministroInformacion.xsd (RegistroAlta, RegistroAnulacion, SistemaInformatico, Desglose, Encadenamiento)
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Sequence

from lxml import etree

from app.core.config import settings
from app.services.verifactu import (
    format_fecha_aeat,
    format_num_serie,
    generar_timestamp_huso_aeat,
    normalitzar_huella_anterior,
)

SOAPENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SUM_NS = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
SUM1_NS = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"

NSMAP_SOAP = {
    "soapenv": SOAPENV_NS,
    "sum": SUM_NS,
    "sum1": SUM1_NS,
}

NSMAP_REG = {
    "sum": SUM_NS,
    "sum1": SUM1_NS,
}


def _q2(val: Any) -> Decimal:
    return Decimal(str(val or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt(val: Any) -> str:
    return f"{_q2(val):.2f}"


def _sub(parent: etree._Element, ns: str, tag: str, text_val: Optional[str] = None) -> etree._Element:
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text_val is not None:
        el.text = str(text_val)
    return el


def _afegir_sistema_informatic(parent: etree._Element) -> etree._Element:
    sist = _sub(parent, SUM1_NS, "SistemaInformatico")
    _sub(sist, SUM1_NS, "NombreRazon", settings.VERIFACTU_SIF_NOM_PRODUCTOR[:120])
    _sub(sist, SUM1_NS, "NIF", settings.VERIFACTU_SIF_NIF_PRODUCTOR.strip().upper())
    _sub(sist, SUM1_NS, "NombreSistemaInformatico", settings.VERIFACTU_SIF_NOMBRE[:30])
    _sub(sist, SUM1_NS, "IdSistemaInformatico", settings.VERIFACTU_SIF_ID[:2])
    _sub(sist, SUM1_NS, "Version", settings.VERIFACTU_SIF_VERSION[:50])
    _sub(sist, SUM1_NS, "NumeroInstalacion", settings.VERIFACTU_SIF_NUM_INSTALACION[:100])
    _sub(sist, SUM1_NS, "TipoUsoPosibleSoloVerifactu", "S")
    _sub(sist, SUM1_NS, "TipoUsoPosibleMultiOT", "S")
    _sub(sist, SUM1_NS, "IndicadorMultiplesOT", "S")
    return sist


def construir_element_registro_alta(
    *,
    nif_emissor: str,
    nom_emissor: str,
    num_serie_factura: str,
    fecha_expedicion: Any,
    tipus_factura: str = "F1",
    tipus_rectificacio: Optional[str] = None,
    num_serie_rectificada: Optional[str] = None,
    fecha_rectificada: Optional[Any] = None,
    base_rectificada: Optional[float | Decimal] = None,
    cuota_rectificada: Optional[float | Decimal] = None,
    fecha_operacion: Optional[Any] = None,
    descripcio_operacio: str = "Prestació de serveis tècnics",
    client_nom: str = "Client",
    client_nif: str = "00000000X",
    linies: Optional[Sequence[Any]] = None,
    base_imposable: float | Decimal = 0.0,
    quota_iva: float | Decimal = 0.0,
    quota_recarrec_equivalencia: float | Decimal = 0.0,
    import_total_verifactu: Optional[float | Decimal] = None,
    es_isp: bool = False,
    causa_exempcio: Optional[str] = None,
    hash_anterior: Optional[str] = None,
    num_serie_anterior: Optional[str] = None,
    fecha_expedicion_anterior: Optional[Any] = None,
    hash_sha256: str,
    fecha_hora_huso_gen_registro: Optional[str] = None,
) -> etree._Element:
    """Construeix el node XML <sum1:RegistroAlta> conforme a SuministroInformacion.xsd."""
    reg_alta = etree.Element(f"{{{SUM1_NS}}}RegistroAlta", nsmap=NSMAP_REG)
    _sub(reg_alta, SUM1_NS, "IDVersion", "1.0")

    nif_e = (nif_emissor or "").strip().upper()
    num_s = (num_serie_factura or "").strip()
    fecha_exp = format_fecha_aeat(fecha_expedicion)
    tipus_f = (tipus_factura or "F1").strip().upper()

    id_fac = _sub(reg_alta, SUM1_NS, "IDFactura")
    _sub(id_fac, SUM1_NS, "IDEmisorFactura", nif_e)
    _sub(id_fac, SUM1_NS, "NumSerieFactura", num_s)
    _sub(id_fac, SUM1_NS, "FechaExpedicionFactura", fecha_exp)

    _sub(reg_alta, SUM1_NS, "NombreRazonEmisor", (nom_emissor or "Empresa").strip()[:120])
    _sub(reg_alta, SUM1_NS, "TipoFactura", tipus_f)

    if tipus_f.startswith("R"):
        mod_rect = (tipus_rectificacio or "S").strip().upper()
        _sub(reg_alta, SUM1_NS, "TipoRectificativa", mod_rect if mod_rect in ("S", "I") else "S")
        if num_serie_rectificada:
            facs_rect = _sub(reg_alta, SUM1_NS, "FacturasRectificadas")
            id_rect = _sub(facs_rect, SUM1_NS, "IDFacturaRectificada")
            _sub(id_rect, SUM1_NS, "IDEmisorFactura", nif_e)
            _sub(id_rect, SUM1_NS, "NumSerieFactura", num_serie_rectificada.strip())
            _sub(
                id_rect,
                SUM1_NS,
                "FechaExpedicionFactura",
                format_fecha_aeat(fecha_rectificada or fecha_expedicion),
            )
        if mod_rect == "S" and base_rectificada is not None:
            imp_rect = _sub(reg_alta, SUM1_NS, "ImporteRectificacion")
            _sub(imp_rect, SUM1_NS, "BaseRectificada", _fmt(base_rectificada))
            _sub(imp_rect, SUM1_NS, "CuotaRectificada", _fmt(cuota_rectificada or 0))

    if fecha_operacion:
        _sub(reg_alta, SUM1_NS, "FechaOperacion", format_fecha_aeat(fecha_operacion))

    _sub(
        reg_alta,
        SUM1_NS,
        "DescripcionOperacion",
        (descripcio_operacio or f"Factura {num_s}").strip()[:500],
    )

    if tipus_f not in ("F2", "R5"):
        dests = _sub(reg_alta, SUM1_NS, "Destinatarios")
        id_dest = _sub(dests, SUM1_NS, "IDDestinatario")
        _sub(id_dest, SUM1_NS, "NombreRazon", (client_nom or "Client").strip()[:120])
        _sub(id_dest, SUM1_NS, "NIF", (client_nif or "00000000X").strip().upper())

    # Agrupació de bases per tipus d'IVA per al node <sum1:Desglose>
    desglose = _sub(reg_alta, SUM1_NS, "Desglose")
    buckets: Dict[tuple[Decimal, Decimal], Dict[str, Decimal]] = {}

    for raw_lin in linies or []:
        get_v = (lambda k: raw_lin.get(k)) if isinstance(raw_lin, dict) else (lambda k: getattr(raw_lin, k, None))
        compte_pgc = str(get_v("compte_pgc") or "700000")
        if compte_pgc.startswith("554"):
            continue
        iva_pct = Decimal("0.00") if es_isp else _q2(get_v("tipus_iva") or get_v("tipus_iva_pct") or 0)
        rec_pct = Decimal("0.00") if es_isp else _q2(get_v("tipus_recarrec_equivalencia") or 0)
        sub_val = get_v("subtotal")
        if sub_val is not None:
            sub_dec = _q2(sub_val)
        else:
            qt = Decimal(str(get_v("quantitat") or 1))
            preu = _q2(get_v("preu_venda_unitari") or 0)
            dto = _q2(get_v("descompte_aplicat_pct") or 0)
            sub_dec = _q2(qt * preu * (Decimal("1.00") - dto / Decimal("100.00")))
        rec_q = _q2(get_v("quota_recarrec_linia") or (sub_dec * rec_pct / Decimal("100.00")))
        b = buckets.setdefault(
            (iva_pct, rec_pct),
            {"base": Decimal("0.00"), "recarrec": Decimal("0.00")},
        )
        b["base"] += sub_dec
        b["recarrec"] += rec_q

    if not buckets:
        base_d = _q2(base_imposable)
        iva_d = _q2(quota_iva)
        rec_d = _q2(quota_recarrec_equivalencia)
        iva_p = _q2((iva_d / base_d) * Decimal("100")) if (base_d != 0 and not es_isp) else Decimal("0.00")
        rec_p = _q2((rec_d / base_d) * Decimal("100")) if (base_d != 0 and rec_d != 0) else Decimal("0.00")
        buckets[(iva_p, rec_p)] = {"base": base_d, "recarrec": rec_d}

    for (iva_pct, rec_pct), vals in sorted(buckets.items(), key=lambda x: x[0]):
        det = _sub(desglose, SUM1_NS, "DetalleDesglose")
        _sub(det, SUM1_NS, "Impuesto", "01")
        _sub(det, SUM1_NS, "ClaveRegimen", "01")
        base_b = _q2(vals["base"])
        if es_isp:
            _sub(det, SUM1_NS, "CalificacionOperacion", "S2")
            _sub(det, SUM1_NS, "TipoImpositivo", "0.00")
            _sub(det, SUM1_NS, "BaseImponibleOimporteNoSujeto", _fmt(base_b))
            _sub(det, SUM1_NS, "CuotaRepercutida", "0.00")
        elif causa_exempcio and causa_exempcio.upper().startswith("E"):
            _sub(det, SUM1_NS, "OperacionExenta", causa_exempcio.upper()[:2])
            _sub(det, SUM1_NS, "BaseImponibleOimporteNoSujeto", _fmt(base_b))
        else:
            quota_b = _q2(base_b * (iva_pct / Decimal("100.00")))
            _sub(det, SUM1_NS, "CalificacionOperacion", "S1")
            _sub(det, SUM1_NS, "TipoImpositivo", _fmt(iva_pct))
            _sub(det, SUM1_NS, "BaseImponibleOimporteNoSujeto", _fmt(base_b))
            _sub(det, SUM1_NS, "CuotaRepercutida", _fmt(quota_b))
            if rec_pct > Decimal("0.00") or vals["recarrec"] > Decimal("0.00"):
                _sub(det, SUM1_NS, "TipoRecargoEquivalencia", _fmt(rec_pct))
                _sub(det, SUM1_NS, "CuotaRecargoEquivalencia", _fmt(vals["recarrec"]))

    cuota_total_dec = _q2(_q2(quota_iva) + _q2(quota_recarrec_equivalencia))
    imp_total_dec = (
        _q2(import_total_verifactu)
        if import_total_verifactu is not None
        else _q2(_q2(base_imposable) + cuota_total_dec)
    )
    _sub(reg_alta, SUM1_NS, "CuotaTotal", _fmt(cuota_total_dec))
    _sub(reg_alta, SUM1_NS, "ImporteTotal", _fmt(imp_total_dec))

    enc = _sub(reg_alta, SUM1_NS, "Encadenamiento")
    huella_ant = normalitzar_huella_anterior(hash_anterior)
    if not huella_ant:
        _sub(enc, SUM1_NS, "PrimerRegistro", "S")
    else:
        reg_ant = _sub(enc, SUM1_NS, "RegistroAnterior")
        _sub(reg_ant, SUM1_NS, "IDEmisorFactura", nif_e)
        _sub(reg_ant, SUM1_NS, "NumSerieFactura", (num_serie_anterior or "ANTERIOR").strip())
        _sub(
            reg_ant,
            SUM1_NS,
            "FechaExpedicionFactura",
            format_fecha_aeat(fecha_expedicion_anterior or fecha_expedicion),
        )
        _sub(reg_ant, SUM1_NS, "Huella", huella_ant)

    _afegir_sistema_informatic(reg_alta)

    ts_huso = (fecha_hora_huso_gen_registro or "").strip() or generar_timestamp_huso_aeat()
    _sub(reg_alta, SUM1_NS, "FechaHoraHusoGenRegistro", ts_huso)
    _sub(reg_alta, SUM1_NS, "TipoHuella", "01")
    _sub(reg_alta, SUM1_NS, "Huella", (hash_sha256 or "").strip().upper())
    return reg_alta


def construir_element_registro_anulacion(
    *,
    nif_emissor: str,
    nom_emissor: str,
    num_serie_anulada: str,
    fecha_expedicion_anulada: Any,
    hash_anterior: Optional[str],
    num_serie_anterior: Optional[str] = None,
    fecha_expedicion_anterior: Optional[Any] = None,
    hash_anulacio_sha256: str,
    fecha_hora_huso_gen_registro: Optional[str] = None,
) -> etree._Element:
    """Construeix el node XML <sum1:RegistroAnulacion> conforme a SuministroInformacion.xsd."""
    reg_anul = etree.Element(f"{{{SUM1_NS}}}RegistroAnulacion", nsmap=NSMAP_REG)
    _sub(reg_anul, SUM1_NS, "IDVersion", "1.0")

    nif_e = (nif_emissor or "").strip().upper()
    num_s = (num_serie_anulada or "").strip()
    fecha_exp = format_fecha_aeat(fecha_expedicion_anulada)

    id_fac = _sub(reg_anul, SUM1_NS, "IDFactura")
    _sub(id_fac, SUM1_NS, "IDEmisorFacturaAnulada", nif_e)
    _sub(id_fac, SUM1_NS, "NumSerieFacturaAnulada", num_s)
    _sub(id_fac, SUM1_NS, "FechaExpedicionFacturaAnulada", fecha_exp)

    enc = _sub(reg_anul, SUM1_NS, "Encadenamiento")
    huella_ant = normalitzar_huella_anterior(hash_anterior)
    if not huella_ant:
        _sub(enc, SUM1_NS, "PrimerRegistro", "S")
    else:
        reg_ant = _sub(enc, SUM1_NS, "RegistroAnterior")
        _sub(reg_ant, SUM1_NS, "IDEmisorFactura", nif_e)
        _sub(reg_ant, SUM1_NS, "NumSerieFactura", (num_serie_anterior or num_s).strip())
        _sub(
            reg_ant,
            SUM1_NS,
            "FechaExpedicionFactura",
            format_fecha_aeat(fecha_expedicion_anterior or fecha_expedicion_anulada),
        )
        _sub(reg_ant, SUM1_NS, "Huella", huella_ant)

    _afegir_sistema_informatic(reg_anul)

    ts_huso = (fecha_hora_huso_gen_registro or "").strip() or generar_timestamp_huso_aeat()
    _sub(reg_anul, SUM1_NS, "FechaHoraHusoGenRegistro", ts_huso)
    _sub(reg_anul, SUM1_NS, "TipoHuella", "01")
    _sub(reg_anul, SUM1_NS, "Huella", (hash_anulacio_sha256 or "").strip().upper())
    return reg_anul


def embolcallar_soap_suministro_aeat(
    *,
    nom_emissor: str,
    nif_emissor: str,
    registres_elements: Sequence[etree._Element],
) -> str:
    """
    Embolcalla un o més nodes <sum1:RegistroAlta> o <sum1:RegistroAnulacion> dins el sobre SOAP oficial
    <soapenv:Envelope> -> <sum:RegFactuSistemaFacturacion> de l'AEAT (fins a 1.000 registres per enviament).
    """
    envelope = etree.Element(f"{{{SOAPENV_NS}}}Envelope", nsmap=NSMAP_SOAP)
    _sub(envelope, SOAPENV_NS, "Header")
    body = _sub(envelope, SOAPENV_NS, "Body")

    reg_sis = _sub(body, SUM_NS, "RegFactuSistemaFacturacion")
    cab = _sub(reg_sis, SUM_NS, "Cabecera")
    oblig = _sub(cab, SUM1_NS, "ObligadoEmision")
    _sub(oblig, SUM1_NS, "NombreRazon", (nom_emissor or "Empresa").strip()[:120])
    _sub(oblig, SUM1_NS, "NIF", (nif_emissor or "").strip().upper())

    for el in registres_elements:
        reg_fac = _sub(reg_sis, SUM_NS, "RegistroFactura")
        reg_fac.append(el)

    xml_bytes: bytes = etree.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )
    return str(xml_bytes.decode("utf-8"))


def generar_xml_factura_complet_aeat(
    *,
    factura: Any,
    empresa: Optional[Any],
    client: Optional[Any],
    linies: Sequence[Any],
    factura_rectificada: Optional[Any] = None,
    tipus_registre: str = "ALTA",
    sobre_soap: bool = True,
) -> str:
    """Genera l'XML oficial AEAT (RegistroAlta o RegistroAnulacion) per a una FacturaCapcalera."""
    nif_e = (empresa.nif if empresa else "B00000000").strip().upper()
    nom_e = ((empresa.rao_social_fiscal or empresa.nom) if empresa else "Sevalor Suite").strip()
    exercici = int(getattr(factura, "exercici", None) or 2026)
    num_serie = getattr(factura, "num_serie_verifactu", None) or format_num_serie(
        factura.serie, exercici, int(factura.numero_factura)
    )

    if tipus_registre.upper() == "ANULACION":
        el = construir_element_registro_anulacion(
            nif_emissor=nif_e,
            nom_emissor=nom_e,
            num_serie_anulada=num_serie,
            fecha_expedicion_anulada=factura.data_emissio,
            hash_anterior=factura.hash_sha256,
            num_serie_anterior=num_serie,
            fecha_expedicion_anterior=factura.data_emissio,
            hash_anulacio_sha256=str(getattr(factura, "hash_anulacio_sha256", None) or factura.hash_sha256),
            fecha_hora_huso_gen_registro=getattr(factura, "fecha_hora_huso_gen_registro", None),
        )
    else:
        num_serie_rect = None
        fecha_rect = None
        base_rect = None
        cuota_rect = None
        if factura_rectificada is not None:
            ex_r = int(getattr(factura_rectificada, "exercici", None) or exercici)
            num_serie_rect = getattr(factura_rectificada, "num_serie_verifactu", None) or format_num_serie(
                factura_rectificada.serie, ex_r, int(factura_rectificada.numero_factura)
            )
            fecha_rect = factura_rectificada.data_emissio
            base_rect = factura_rectificada.base_imposable
            cuota_rect = factura_rectificada.quota_iva

        desc_op = (
            str(linies[0].concepte)[:500]
            if linies and getattr(linies[0], "concepte", None)
            else f"Factura {num_serie}"
        )

        el = construir_element_registro_alta(
            nif_emissor=nif_e,
            nom_emissor=nom_e,
            num_serie_factura=num_serie,
            fecha_expedicion=factura.data_emissio,
            tipus_factura=str(getattr(factura, "tipus_factura", None) or "F1"),
            tipus_rectificacio=getattr(factura, "tipus_rectificacio", None),
            num_serie_rectificada=num_serie_rect,
            fecha_rectificada=fecha_rect,
            base_rectificada=base_rect,
            cuota_rectificada=cuota_rect,
            fecha_operacion=getattr(factura, "data_operacio", None),
            descripcio_operacio=desc_op,
            client_nom=client.rao_social if client else "Client",
            client_nif=client.nif if client else "00000000X",
            linies=linies,
            base_imposable=float(factura.base_imposable or 0),
            quota_iva=float(factura.quota_iva or 0),
            quota_recarrec_equivalencia=float(getattr(factura, "quota_recarrec_equivalencia", 0) or 0),
            import_total_verifactu=float(
                getattr(factura, "import_total_verifactu", 0)
                or ((factura.base_imposable or 0) + (factura.quota_iva or 0) + (getattr(factura, "quota_recarrec_equivalencia", 0) or 0))
            ),
            es_isp=bool(getattr(factura, "es_inversio_subjecte_passiu", False)),
            causa_exempcio=getattr(factura, "causa_exempcio", None),
            hash_anterior=factura.hash_anterior,
            hash_sha256=factura.hash_sha256,
            fecha_hora_huso_gen_registro=getattr(factura, "fecha_hora_huso_gen_registro", None),
        )

    if sobre_soap:
        return embolcallar_soap_suministro_aeat(
            nom_emissor=nom_e,
            nif_emissor=nif_e,
            registres_elements=[el],
        )
    raw_out: bytes = etree.tostring(el, encoding="utf-8", xml_declaration=True, pretty_print=True)
    return str(raw_out.decode("utf-8"))
