import hashlib
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contractes import ContracteManteniment, RevisionsContracte
from app.models.models import (
    ApuntBancariNorma43,
    Article,
    Client,
    ContracteMantenimentMRR,
    DespesaComptable,
    DespesaFixaRecurrent,
    Empresa,
    EstocMagatzem,
    FacturaCapcalera,
    FacturaLinia,
    FacturaProveidor,
    FullaPicking,
    LiniaPicking,
    MantenimentVehicle,
    OrdreTreball,
    OrdreTreballTramTemps,
    OutboxEnviamentAEAT,
    RegistreEsdevenimentsSIF,
    RegistreJornadaLaboral,
    RetencioGarantia,
    SerieFiscalVerifactu,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.schemas.comptabilitat import (
    AlertaErosioMargeDTO,
    Art80ItemDTO,
    ClientRiscSanititzatDTO,
    ContracteMRRAuditoriaDTO,
    DashboardEconomicResponseDTO,
    DespesaFixaCreateDTO,
    DespesaFixaResponseDTO,
    DespesaFixaUpdateDTO,
    FacturaCobramentRequestDTO,
    FacturaEmissioCreateDTO,
    FacturaLiniaCreateDTO,
    Norma43MovimentDTO,
    OperariCostEfectiuDTO,
    PrefacturaEmetreDTO,
    PrefacturaUpdateDTO,
    RetencioGarantiaDTO,
    TiquetAuditoriaRequestDTO,
    TiquetDespesaResponseDTO,
    WIPControlResponseDTO,
    WIPItemDTO,
)
from app.services.barema_service import (
    obtenir_barema_empresa,
    obtenir_cost_hora_operaris_map,
    resoldre_preu_hora_control_panel,
)
from app.services.magatzem_comptabilitat_service import calcular_cost_i_marge_analitic_ot
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.verifactu import (
    VerifactuCoreService,
    format_num_serie,
    renderitzar_pdf_factura_verifactu,
)
from app.services.verifactu_xml import generar_xml_factura_complet_aeat

logger = logging.getLogger("sevalor.economic_suite")

ESTATS_OT_PENDENTS_PREFACTURACIO: Tuple[str, ...] = (
    "COMPLERT",
    "COMPLETADA",
    "FINALITZADA",
    "TANCADA",
    "EXECUTADA_PENDENT_VALIDACIO",
    "ALBARA_SIGNAT",
    "VALIDADA_PER_FACTURAR",
)


def q2(val: Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EconomicSuiteService:
    """Implementació 100% real (Zero-Mock) i asíncrona de la Spec 007 v5.0."""

    @staticmethod
    async def registrar_esdeveniment_sif(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: Optional[uuid.UUID],
        codi: str,
        descripcio: str,
        dades_event: Optional[Dict[str, Any]] = None,
    ) -> RegistreEsdevenimentsSIF:
        raw = f"{empresa_id}|{usuari_id}|{codi}|{descripcio}|{datetime.now(timezone.utc).isoformat()}"
        sello = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        ev = RegistreEsdevenimentsSIF(
            empresa_id=empresa_id,
            codi_esdeveniment=codi,
            usuari_id=usuari_id,
            descripcio=descripcio,
            hash_sello=sello,
            dades_event=dades_event or {},
        )
        db.add(ev)
        await db.flush()
        return ev

    # --- HELPERS INTERNS DE FACTURACIÓ I PREFACTURACIÓ ---
    @staticmethod
    async def _lock_or_create_serie(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        codi_serie: str,
        exercici: int,
    ) -> SerieFiscalVerifactu:
        stmt_serie = (
            select(SerieFiscalVerifactu)
            .where(
                SerieFiscalVerifactu.empresa_id == empresa_id,
                SerieFiscalVerifactu.codi_serie == codi_serie,
                SerieFiscalVerifactu.exercici == exercici,
            )
            .with_for_update()
        )
        serie_row = (await db.execute(stmt_serie)).scalar_one_or_none()
        if not serie_row:
            serie_row = SerieFiscalVerifactu(
                empresa_id=empresa_id,
                codi_serie=codi_serie,
                exercici=exercici,
                ultim_numero=0,
                ultim_hash_sha256="0" * 64,
            )
            db.add(serie_row)
            await db.flush()
        return serie_row

    @staticmethod
    async def _construir_linies_i_totals(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        linies_dto: Sequence[FacturaLiniaCreateDTO],
        es_inversio_subjecte_passiu: bool,
        retencio_irpf_pct: Decimal,
        retencio_garantia_pct: Decimal,
    ) -> Tuple[List[FacturaLinia], Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        bases_per_iva: Dict[Decimal, Decimal] = {}
        total_recarrec_eq = Decimal("0.00")
        total_suplerts_554 = Decimal("0.00")
        linies_models: List[FacturaLinia] = []

        for l_dto in linies_dto:
            cost_historic = Decimal("0.0000")
            if l_dto.article_id:
                art = await db.get(Article, l_dto.article_id)
                if art and art.empresa_id == empresa_id:
                    cost_historic = Decimal(str(art.preu_cost_mitja or art.preu_cost or 0))

            factor_dto = Decimal("1.00") - (l_dto.descompte_aplicat_pct / Decimal("100.00"))
            import_base = q2(l_dto.quantitat * l_dto.preu_venda_unitari * factor_dto)
            rec_pct = (
                Decimal("0.00")
                if (es_inversio_subjecte_passiu or l_dto.compte_pgc.startswith("554"))
                else getattr(l_dto, "tipus_recarrec_equivalencia_pct", Decimal("0.00"))
            )
            quota_rec_linia = q2(import_base * (rec_pct / Decimal("100.00")))

            if l_dto.compte_pgc.startswith("554"):
                total_suplerts_554 += import_base
                iva_linia = Decimal("0.00")
            else:
                iva_linia = (
                    Decimal("0.00")
                    if es_inversio_subjecte_passiu
                    else l_dto.tipus_iva_pct
                )
                bases_per_iva[iva_linia] = bases_per_iva.get(iva_linia, Decimal("0.00")) + import_base
                total_recarrec_eq += quota_rec_linia

            linies_models.append(
                FacturaLinia(
                    empresa_id=empresa_id,
                    obra_id=l_dto.obra_id,
                    centre_de_cost_id=l_dto.centre_de_cost_id,
                    article_id=l_dto.article_id,
                    concepte=l_dto.concepte[:200],
                    descripcio_detall=getattr(l_dto, "descripcio_detall", None),
                    compte_pgc=l_dto.compte_pgc,
                    quantitat=float(l_dto.quantitat),
                    quantitat_merma=float(l_dto.quantitat_merma),
                    preu_venda_unitari=float(l_dto.preu_venda_unitari),
                    descompte_aplicat_pct=float(l_dto.descompte_aplicat_pct),
                    cost_unitari_historic=float(cost_historic),
                    tipus_iva=float(iva_linia),
                    tipus_recarrec_equivalencia=float(rec_pct),
                    quota_recarrec_linia=float(quota_rec_linia),
                    subtotal=float(import_base),
                )
            )

        base_imposable_total = q2(sum(bases_per_iva.values(), Decimal("0.00")))
        quota_iva_total = Decimal("0.00")
        if not es_inversio_subjecte_passiu:
            for tipus, base_agregada in bases_per_iva.items():
                quota_iva_total += q2(base_agregada * (tipus / Decimal("100.00")))

        quota_recarrec_total = q2(total_recarrec_eq)
        import_total_verifactu = q2(base_imposable_total + quota_iva_total + quota_recarrec_total)

        import_ret_irpf = q2(base_imposable_total * (retencio_irpf_pct / Decimal("100.00")))
        import_ret_garantia = q2(
            base_imposable_total * (retencio_garantia_pct / Decimal("100.00"))
        )

        # Fórmula RF-05.3 + RF-33
        liquid_exigible = q2(
            import_total_verifactu
            + total_suplerts_554
            - import_ret_irpf
            - import_ret_garantia
        )
        return (
            linies_models,
            base_imposable_total,
            quota_iva_total,
            quota_recarrec_total,
            import_total_verifactu,
            total_suplerts_554,
            import_ret_irpf,
            import_ret_garantia,
            liquid_exigible,
        )

    @staticmethod
    async def _generar_pdf_i_pujar(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        factura: FacturaCapcalera,
        linies: Sequence[FacturaLinia],
    ) -> Optional[str]:
        emp = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
        cli = (
            await db.execute(
                select(Client).where(
                    Client.id == factura.client_id,
                    Client.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()

        num_serie_rect = None
        data_rect = None
        if factura.factura_rectificada_id:
            orig_f = (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.id == factura.factura_rectificada_id,
                        FacturaCapcalera.empresa_id == empresa_id,
                    )
                )
            ).scalar_one_or_none()
            if orig_f:
                num_serie_rect = orig_f.num_serie_verifactu or format_num_serie(
                    orig_f.serie, int(orig_f.exercici or 2026), int(orig_f.numero_factura)
                )
                data_rect = (
                    orig_f.data_emissio.strftime("%Y-%m-%d")
                    if isinstance(orig_f.data_emissio, datetime)
                    else str(orig_f.data_emissio)
                )

        data_em_str = (
            factura.data_emissio.strftime("%Y-%m-%d")
            if isinstance(factura.data_emissio, datetime)
            else str(factura.data_emissio)
        )
        data_ven_str = factura.data_venciment.isoformat() if factura.data_venciment else None
        temp_dir = "/tmp/sevalor_factures_temp"
        os.makedirs(temp_dir, exist_ok=True)
        prefix_pdf = "FACTURA_ANULADA" if getattr(factura, "estat_anulacio", "ACTIVA") == "ANULADA_VERIFACTU" else "FACTURA"
        nom_pdf = f"{prefix_pdf}_{factura.serie}_{int(factura.numero_factura):05d}_{data_em_str}.pdf"
        ruta_tmp = os.path.join(temp_dir, f"{uuid.uuid4()}_{nom_pdf}")

        try:
            renderitzar_pdf_factura_verifactu(
                empresa_nom=emp.nom if emp else "Sevalor Suite",
                empresa_rao_social=(emp.rao_social_fiscal or emp.nom) if emp else "Sevalor Suite",
                empresa_eslogan=emp.eslogan_activitat if emp else None,
                empresa_nif=emp.nif if emp else "B00000000",
                empresa_adreca=emp.adreca if emp else None,
                empresa_cp=emp.codi_postal if emp else None,
                empresa_poblacio=emp.poblacio if emp else None,
                empresa_provincia=emp.provincia if emp else None,
                empresa_telefon=emp.telefon_facturacio if emp else None,
                empresa_email=emp.email_facturacio if emp else None,
                empresa_registre_mercantil=emp.dades_registre_mercantil if emp else None,
                empresa_titular_compte=emp.titular_compte_bancari if emp else None,
                empresa_iban=emp.iban_cobrament_xifrat if emp else None,
                primari_hsl=emp.primari_hsl if emp else "150 40 20",
                client_nom=cli.rao_social if cli else "Client",
                client_nif=cli.nif if cli else "00000000X",
                client_adreca=cli.adreca_fiscal if cli else None,
                client_cp=cli.codi_postal if cli else None,
                client_poblacio=cli.poblacio if cli else None,
                client_provincia=cli.provincia if cli else None,
                client_email=cli.email if cli else None,
                serie=str(factura.serie),
                numero_factura=int(factura.numero_factura),
                exercici=int(factura.exercici or 2026),
                num_serie_verifactu=factura.num_serie_verifactu,
                tipus_factura=str(factura.tipus_factura or "F1"),
                tipus_rectificacio=factura.tipus_rectificacio,
                num_serie_rectificada=num_serie_rect,
                data_factura_rectificada=data_rect,
                motiu_rectificacio=factura.motiu_rectificacio,
                data_emissio=data_em_str,
                data_operacio=factura.data_operacio.isoformat() if factura.data_operacio else None,
                data_venciment=data_ven_str,
                metode_pagament=str(factura.metode_pagament or "TRANSFERENCIA"),
                referencia_comanda=factura.referencia_client,
                estat_document=str(factura.estat_document),
                estat_anulacio=str(factura.estat_anulacio or "ACTIVA"),
                linies=list(linies),
                base_imposable=float(factura.base_imposable or 0),
                quota_iva=float(factura.quota_iva or 0),
                quota_recarrec_equivalencia=float(factura.quota_recarrec_equivalencia or 0),
                import_total_verifactu=float(
                    factura.import_total_verifactu
                    or ((factura.base_imposable or 0) + (factura.quota_iva or 0) + (factura.quota_recarrec_equivalencia or 0))
                ),
                import_suplits=float(factura.import_suplits or 0),
                import_retencio=float(factura.import_retencio or 0),
                import_retencio_garantia=float(factura.import_retencio_garantia_4308 or 0),
                import_total=float(factura.liquid_exigible or 0),
                es_isp=bool(factura.es_inversio_subjecte_passiu),
                mencio_legal=factura.mencio_legal,
                notes_factura=factura.notes_factura,
                hash_actual=str(factura.hash_sha256 or ""),
                hash_anterior=factura.hash_anterior,
                qr_content=factura.qr_verifactu_payload,
                csv_aeat=factura.csv_aeat,
                ruta_desti=ruta_tmp,
            )
            with open(ruta_tmp, "rb") as f_bin:
                pdf_bytes = f_bin.read()
            ruta_sobirana = await SovereignStorageGateway.pujar_fitxer_binari(
                db=db,
                empresa_id=str(empresa_id),
                categoria="factures_pdf",
                nom_fitxer=nom_pdf,
                content=pdf_bytes,
                content_type="application/pdf",
            )
            return ruta_sobirana
        except Exception as exc:
            logger.warning("No s'ha pogut generar/desar el PDF de la factura %s: %s", factura.id, exc)
            return None
        finally:
            try:
                if os.path.exists(ruta_tmp):
                    os.remove(ruta_tmp)
            except OSError:
                pass

    @staticmethod
    async def _generar_xml_i_pujar(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        factura: FacturaCapcalera,
        linies: Sequence[FacturaLinia],
        tipus_registre: str = "ALTA",
    ) -> str:
        emp = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
        cli = (
            await db.execute(
                select(Client).where(
                    Client.id == factura.client_id,
                    Client.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        orig_f = None
        if factura.factura_rectificada_id:
            orig_f = (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.id == factura.factura_rectificada_id,
                        FacturaCapcalera.empresa_id == empresa_id,
                    )
                )
            ).scalar_one_or_none()

        num_s = factura.num_serie_verifactu or format_num_serie(
            factura.serie, int(factura.exercici or 2026), int(factura.numero_factura)
        )
        prefix_xml = "ANULACION" if tipus_registre.upper() == "ANULACION" else "ALTA"
        nom_xml = f"VERIFACTU_{prefix_xml}_{num_s.replace('/', '-')}.xml"
        try:
            xml_str = generar_xml_factura_complet_aeat(
                factura=factura,
                empresa=emp,
                client=cli,
                linies=linies,
                factura_rectificada=orig_f,
                tipus_registre=tipus_registre,
                sobre_soap=True,
            )
            return await SovereignStorageGateway.pujar_fitxer_binari(
                db=db,
                empresa_id=str(empresa_id),
                categoria="factures_xml",
                nom_fitxer=nom_xml,
                content=xml_str.encode("utf-8"),
                content_type="application/xml",
            )
        except Exception as exc:
            logger.warning("No s'ha pogut desar l'XML Veri*factu de %s: %s", factura.id, exc)
            return f"/docs/{empresa_id}/factures/outbox/{nom_xml}"

    @staticmethod
    async def obtenir_materials_consumits_ots(
        db: AsyncSession,
        empresa_id: uuid.UUID,
        ot_ids: Sequence[uuid.UUID],
    ) -> Dict[uuid.UUID, List[Dict[str, Any]]]:
        if not ot_ids:
            return {}
        stmt = (
            select(FullaPicking.ordre_treball_id, LiniaPicking, Article)
            .join(LiniaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.empresa_id == empresa_id,
                FullaPicking.ordre_treball_id.in_(list(ot_ids)),
                LiniaPicking.empresa_id == empresa_id,
            )
        )
        rows = (await db.execute(stmt)).all()
        resultat: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        for ot_id, lp, art in rows:
            pick_in = Decimal(str(lp.quantitat_carregada_pick_in or 0))
            pick_out = Decimal(str(lp.quantitat_retornada_pick_out or 0))
            consum = max(Decimal("0.000"), pick_in - pick_out)
            if consum <= 0:
                continue
            preu_venda = Decimal(str(art.preu_venda or 0))
            resultat.setdefault(ot_id, []).append(
                {
                    "article_id": art.id,
                    "nom": art.nom,
                    "quantitat": consum,
                    "preu_venda": preu_venda,
                    "subtotal": q2(consum * preu_venda),
                }
            )
        return resultat

    # --- CREACIÓ I EDICIÓ DE PRE-FACTURES EDITABLES (HITL) ---
    @classmethod
    async def crear_prefactura_esborrany(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        payload: FacturaEmissioCreateDTO,
    ) -> FacturaCapcalera:
        if not payload.linies:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La pre-factura ha de contenir almenys una línia.",
            )

        exercici = payload.data_emissio.year
        serie_row = await cls._lock_or_create_serie(db, empresa_id, "PRE", exercici)
        serie_row.ultim_numero += 1
        num_pref = serie_row.ultim_numero
        num_serie_pref = format_num_serie("PRE", exercici, num_pref)

        (
            linies_models,
            base_imposable_total,
            quota_iva_total,
            quota_recarrec_total,
            import_total_verifactu,
            total_suplerts_554,
            import_ret_irpf,
            import_ret_garantia,
            liquid_exigible,
        ) = await cls._construir_linies_i_totals(
            db=db,
            empresa_id=empresa_id,
            linies_dto=payload.linies,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            retencio_irpf_pct=payload.retencio_irpf_pct,
            retencio_garantia_pct=payload.retencio_garantia_pct,
        )

        prefactura = FacturaCapcalera(
            empresa_id=empresa_id,
            exercici=exercici,
            numero_factura=num_pref,
            serie="PRE",
            num_serie_verifactu=num_serie_pref,
            tipus_factura=(payload.tipus_factura or "F1").strip().upper(),
            tipus_rectificacio=payload.tipus_rectificacio,
            client_id=payload.client_id,
            estat_document="ESBORRANY_PREFACTURA",
            estat_cobrament="PENDENT",
            estat_enviament="ESBORRANY",
            data_emissio=datetime.combine(payload.data_emissio, datetime.min.time(), tzinfo=timezone.utc),
            data_operacio=payload.data_operacio,
            data_venciment=payload.data_venciment,
            metode_pagament=payload.metode_pagament,
            referencia_client=payload.referencia_client,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            causa_exempcio=payload.causa_exempcio or ("ISP" if payload.es_inversio_subjecte_passiu else None),
            mencio_legal=payload.mencio_legal,
            notes_factura=payload.notes_factura,
            base_imposable=float(base_imposable_total),
            quota_iva=float(quota_iva_total),
            quota_recarrec_equivalencia=float(quota_recarrec_total),
            import_total_verifactu=float(import_total_verifactu),
            import_suplits=float(total_suplerts_554),
            justificant_suplerts_pdf_path=payload.justificant_suplerts_pdf_path,
            import_retencio=float(import_ret_irpf),
            import_retencio_garantia_4308=float(import_ret_garantia),
            liquid_exigible=float(liquid_exigible),
            hash_anterior=None,
            hash_sha256="ESBORRANY_PREFACTURA",
            qr_verifactu_payload=None,
        )
        db.add(prefactura)
        await db.flush()

        for lm in linies_models:
            lm.factura_id = prefactura.id
            db.add(lm)
            if lm.obra_id:
                ot = await db.get(OrdreTreball, lm.obra_id)
                if ot and ot.empresa_id == empresa_id:
                    ot.factura_id = prefactura.id
                    ot.estat = "PREFACTURADA"

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-01",
            f"Creació Esborrany Pre-factura {num_serie_pref} (HITL)",
        )
        await db.commit()
        return prefactura

    @classmethod
    async def actualitzar_prefactura_esborrany(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
        payload: PrefacturaUpdateDTO,
    ) -> FacturaCapcalera:
        pref = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id,
                    FacturaCapcalera.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not pref:
            raise HTTPException(status_code=404, detail="Pre-factura no trobada.")
        if pref.estat_document != "ESBORRANY_PREFACTURA":
            raise HTTPException(
                status_code=400,
                detail="Només es poden editar pre-factures en estat esborrany; les factures emeses a Veri*factu són immutables.",
            )

        (
            linies_models,
            base_imposable_total,
            quota_iva_total,
            quota_recarrec_total,
            import_total_verifactu,
            total_suplerts_554,
            import_ret_irpf,
            import_ret_garantia,
            liquid_exigible,
        ) = await cls._construir_linies_i_totals(
            db=db,
            empresa_id=empresa_id,
            linies_dto=payload.linies,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            retencio_irpf_pct=payload.retencio_irpf_pct,
            retencio_garantia_pct=payload.retencio_garantia_pct,
        )

        existing_obra_ids = list(
            (
                await db.execute(
                    select(FacturaLinia.obra_id).where(
                        FacturaLinia.factura_id == pref.id,
                        FacturaLinia.empresa_id == empresa_id,
                        FacturaLinia.obra_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        default_obra_id = existing_obra_ids[0] if existing_obra_ids else None

        await db.execute(
            delete(FacturaLinia).where(
                FacturaLinia.factura_id == pref.id,
                FacturaLinia.empresa_id == empresa_id,
            )
        )

        for lm in linies_models:
            lm.factura_id = pref.id
            if lm.obra_id is None and default_obra_id is not None:
                lm.obra_id = default_obra_id
            db.add(lm)

        if payload.data_emissio is not None:
            pref.data_emissio = datetime.combine(
                payload.data_emissio, datetime.min.time(), tzinfo=timezone.utc
            )
            pref.exercici = payload.data_emissio.year
        if payload.data_operacio is not None:
            pref.data_operacio = payload.data_operacio
        if payload.data_venciment is not None:
            pref.data_venciment = payload.data_venciment
        if payload.tipus_factura:
            pref.tipus_factura = payload.tipus_factura.strip().upper()
        if payload.referencia_client is not None:
            pref.referencia_client = payload.referencia_client
        if payload.causa_exempcio is not None:
            pref.causa_exempcio = payload.causa_exempcio
        if payload.mencio_legal is not None:
            pref.mencio_legal = payload.mencio_legal
        if payload.notes_factura is not None:
            pref.notes_factura = payload.notes_factura
        pref.metode_pagament = payload.metode_pagament
        pref.es_inversio_subjecte_passiu = payload.es_inversio_subjecte_passiu
        pref.justificant_suplerts_pdf_path = payload.justificant_suplerts_pdf_path
        pref.base_imposable = float(base_imposable_total)
        pref.quota_iva = float(quota_iva_total)
        pref.quota_recarrec_equivalencia = float(quota_recarrec_total)
        pref.import_total_verifactu = float(import_total_verifactu)
        pref.import_suplits = float(total_suplerts_554)
        pref.import_retencio = float(import_ret_irpf)
        pref.import_retencio_garantia_4308 = float(import_ret_garantia)
        pref.liquid_exigible = float(liquid_exigible)
        pref.updated_at = datetime.now(timezone.utc)

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-01",
            f"Edició Esborrany Pre-factura {pref.num_serie_verifactu or f'{pref.serie}-{pref.numero_factura:04d}'}",
        )
        await db.commit()
        return pref

    @classmethod
    async def descartar_prefactura_esborrany(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
    ) -> None:
        pref = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id,
                    FacturaCapcalera.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not pref:
            raise HTTPException(status_code=404, detail="Pre-factura no trobada.")
        if pref.estat_document != "ESBORRANY_PREFACTURA":
            raise HTTPException(
                status_code=400,
                detail="No es pot descartar una factura ja emesa a Veri*factu.",
            )

        ots_vinculades = (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.empresa_id == empresa_id,
                    OrdreTreball.factura_id == pref.id,
                )
            )
        ).scalars().all()
        for ot in ots_vinculades:
            ot.factura_id = None
            ot.estat = "COMPLERT"

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-01",
            f"Descartar Esborrany Pre-factura {pref.serie}-{pref.numero_factura:04d} (OT retornada a WIP)",
        )
        await db.delete(pref)
        await db.commit()

    @classmethod
    async def emetre_prefactura_a_verifactu(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
        payload: PrefacturaEmetreDTO,
    ) -> FacturaCapcalera:
        if not payload.confirmacio_humana_hitl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cal confirmació humana explícita (HITL) abans d'emetre la factura definitiva.",
            )
        serie_desti = payload.serie.strip().upper()
        if not serie_desti or serie_desti == "PRE":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La sèrie fiscal definitiva no pot ser 'PRE' (ex: 'F').",
            )

        pref = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id,
                    FacturaCapcalera.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not pref:
            raise HTTPException(status_code=404, detail="Pre-factura no trobada.")
        if pref.estat_document != "ESBORRANY_PREFACTURA":
            raise HTTPException(
                status_code=400,
                detail="Aquesta factura ja ha estat emesa definitivament.",
            )

        if Decimal(str(pref.import_suplits or 0)) > Decimal("0.00") and not pref.justificant_suplerts_pdf_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Els suplerts (compte 554) exigeixen adjuntar el PDF del justificant oficial.",
            )

        linies = list(
            (
                await db.execute(
                    select(FacturaLinia).where(
                        FacturaLinia.factura_id == pref.id,
                        FacturaLinia.empresa_id == empresa_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not linies:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No es pot emetre una factura sense línies.",
            )

        emp = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
        emp_nif = emp.nif if emp else "B00000000"
        entorn_vf = emp.verifactu_entorn if emp else None

        data_em_date = (
            payload.data_emissio
            or (pref.data_emissio.date() if isinstance(pref.data_emissio, datetime) else date.today())
        )
        data_ven_date = payload.data_venciment or pref.data_venciment or data_em_date
        if payload.data_operacio is not None:
            pref.data_operacio = payload.data_operacio
        exercici = data_em_date.year
        tipus_fac = (payload.tipus_factura or pref.tipus_factura or "F1").strip().upper()

        base_imp = q2(Decimal(str(pref.base_imposable or 0)))
        quota_iva = q2(Decimal(str(pref.quota_iva or 0)))
        quota_rec = q2(Decimal(str(pref.quota_recarrec_equivalencia or 0)))
        cuota_total_aeat = q2(quota_iva + quota_rec)
        importe_total_aeat = q2(base_imp + cuota_total_aeat)

        reg = await VerifactuCoreService.adquirir_seguent_registre_alta(
            db=db,
            empresa_id=empresa_id,
            empresa_nif=emp_nif,
            serie=serie_desti,
            exercici=exercici,
            data_emissio=data_em_date,
            tipus_factura=tipus_fac,
            cuota_total=cuota_total_aeat,
            importe_total_verifactu=importe_total_aeat,
            entorn=entorn_vf,
        )

        codi_complet = reg["num_serie_verifactu"]
        hash_propi = reg["hash_sha256"]

        pref.exercici = exercici
        pref.serie = serie_desti
        pref.numero_factura = reg["numero_factura"]
        pref.num_serie_verifactu = codi_complet
        pref.tipus_factura = tipus_fac
        pref.import_total_verifactu = float(importe_total_aeat)
        pref.data_emissio = datetime.combine(data_em_date, datetime.min.time(), tzinfo=timezone.utc)
        pref.data_venciment = data_ven_date
        pref.estat_document = "EMESA"
        pref.estat_enviament = "PENDENT"
        pref.hash_anterior = reg["hash_anterior"]
        pref.hash_sha256 = hash_propi
        pref.fecha_hora_huso_gen_registro = reg["fecha_hora_huso_gen_registro"]
        pref.qr_verifactu_payload = reg["qr_verifactu_payload"]
        pref.updated_at = datetime.now(timezone.utc)

        import_ret_gar = Decimal(str(pref.import_retencio_garantia_4308 or 0))
        if import_ret_gar > Decimal("0.00"):
            pct_gar = float(q2((import_ret_gar / base_imp) * Decimal("100"))) if base_imp > 0 else 0.0
            db.add(
                RetencioGarantia(
                    empresa_id=empresa_id,
                    tipus="CLIENT_4308",
                    factura_client_id=pref.id,
                    client_id=pref.client_id,
                    import_retingut=float(import_ret_gar),
                    percentatge_aplicat=pct_gar,
                    data_retencio=data_em_date,
                    data_venciment_garantia=data_em_date + timedelta(days=365),
                    estat="RETINGUDA",
                )
            )

        ots_vinc = (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.empresa_id == empresa_id,
                    OrdreTreball.factura_id == pref.id,
                )
            )
        ).scalars().all()
        for ot in ots_vinc:
            ot.estat = "FACTURADA"

        for lin in linies:
            if lin.obra_id:
                ot_lin = await db.get(OrdreTreball, lin.obra_id)
                if ot_lin and ot_lin.empresa_id == empresa_id:
                    ot_lin.factura_id = pref.id
                    ot_lin.estat = "FACTURADA"

        ruta_pdf = await cls._generar_pdf_i_pujar(db, empresa_id, pref, linies)
        if ruta_pdf:
            pref.pdf_path = ruta_pdf

        ruta_xml = await cls._generar_xml_i_pujar(db, empresa_id, pref, linies, tipus_registre="ALTA")

        db.add(
            OutboxEnviamentAEAT(
                empresa_id=empresa_id,
                factura_id=pref.id,
                tipus_registre="ALTA",
                payload_xml_path=ruta_xml,
                hash_sha256=hash_propi,
            )
        )
        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-02",
            f"Validació HITL i Emissió Factura Veri*factu {codi_complet} Hash:{hash_propi[:12]}",
        )
        await db.commit()
        return pref

    # --- EMISSIÓ DE FACTURES VERI*FACTU + RETENCIONS 4308 (RF-05 a RF-15, RF-33) ---
    @classmethod
    async def emetre_factura_verifactu(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        payload: FacturaEmissioCreateDTO,
    ) -> FacturaCapcalera:
        serie_clean = payload.serie.strip().upper()
        if serie_clean.startswith("R") and not payload.factura_rectificada_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les factures rectificatives (Sèrie R) exigeixen informar factura_rectificada_id.",
            )

        (
            linies_models,
            base_imposable_total,
            quota_iva_total,
            quota_recarrec_total,
            import_total_verifactu,
            total_suplerts_554,
            import_ret_irpf,
            import_ret_garantia,
            liquid_exigible,
        ) = await cls._construir_linies_i_totals(
            db=db,
            empresa_id=empresa_id,
            linies_dto=payload.linies,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            retencio_irpf_pct=payload.retencio_irpf_pct,
            retencio_garantia_pct=payload.retencio_garantia_pct,
        )

        if total_suplerts_554 > Decimal("0.00") and not payload.justificant_suplerts_pdf_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Els suplerts (compte 554) exigeixen adjuntar el PDF del justificant oficial.",
            )

        emp = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
        emp_nif = emp.nif if emp else "B00000000"
        entorn_vf = emp.verifactu_entorn if emp else None

        exercici = payload.data_emissio.year
        tipus_fac = (
            payload.tipus_factura.strip().upper()
            if payload.tipus_factura
            else ("R1" if serie_clean.startswith("R") else "F1")
        )
        if serie_clean.startswith("R") and not tipus_fac.startswith("R"):
            tipus_fac = "R1"
        tipus_rect = (
            (payload.tipus_rectificacio or "S").strip().upper()
            if (serie_clean.startswith("R") or tipus_fac.startswith("R"))
            else None
        )

        cuota_total_aeat = q2(quota_iva_total + quota_recarrec_total)
        reg = await VerifactuCoreService.adquirir_seguent_registre_alta(
            db=db,
            empresa_id=empresa_id,
            empresa_nif=emp_nif,
            serie=serie_clean,
            exercici=exercici,
            data_emissio=payload.data_emissio,
            tipus_factura=tipus_fac,
            cuota_total=cuota_total_aeat,
            importe_total_verifactu=import_total_verifactu,
            entorn=entorn_vf,
        )

        codi_complet = reg["num_serie_verifactu"]
        hash_propi = reg["hash_sha256"]

        factura = FacturaCapcalera(
            empresa_id=empresa_id,
            exercici=exercici,
            numero_factura=reg["numero_factura"],
            serie=serie_clean,
            num_serie_verifactu=codi_complet,
            tipus_factura=tipus_fac,
            tipus_rectificacio=tipus_rect,
            client_id=payload.client_id,
            estat_document="EMESA",
            estat_cobrament="PENDENT",
            estat_enviament="PENDENT",
            data_emissio=datetime.combine(payload.data_emissio, datetime.min.time(), tzinfo=timezone.utc),
            data_operacio=payload.data_operacio,
            data_venciment=payload.data_venciment,
            metode_pagament=payload.metode_pagament,
            referencia_client=payload.referencia_client,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            causa_exempcio=payload.causa_exempcio or ("ISP" if payload.es_inversio_subjecte_passiu else None),
            mencio_legal=payload.mencio_legal,
            notes_factura=payload.notes_factura,
            base_imposable=float(base_imposable_total),
            quota_iva=float(quota_iva_total),
            quota_recarrec_equivalencia=float(quota_recarrec_total),
            import_total_verifactu=float(import_total_verifactu),
            import_suplits=float(total_suplerts_554),
            justificant_suplerts_pdf_path=payload.justificant_suplerts_pdf_path,
            import_retencio=float(import_ret_irpf),
            import_retencio_garantia_4308=float(import_ret_garantia),
            liquid_exigible=float(liquid_exigible),
            factura_rectificada_id=payload.factura_rectificada_id,
            motiu_rectificacio=payload.motiu_rectificacio,
            hash_anterior=reg["hash_anterior"],
            hash_sha256=hash_propi,
            fecha_hora_huso_gen_registro=reg["fecha_hora_huso_gen_registro"],
            qr_verifactu_payload=reg["qr_verifactu_payload"],
        )
        db.add(factura)
        await db.flush()

        for lm in linies_models:
            lm.factura_id = factura.id
            db.add(lm)

        if import_ret_garantia > Decimal("0.00"):
            ret_garantia = RetencioGarantia(
                empresa_id=empresa_id,
                tipus="CLIENT_4308",
                factura_client_id=factura.id,
                client_id=payload.client_id,
                import_retingut=float(import_ret_garantia),
                percentatge_aplicat=float(payload.retencio_garantia_pct),
                data_retencio=payload.data_emissio,
                data_venciment_garantia=payload.data_emissio + timedelta(days=365),
                estat="RETINGUDA",
            )
            db.add(ret_garantia)

        for linia in linies_models:
            if linia.obra_id:
                ot = await db.get(OrdreTreball, linia.obra_id)
                if ot and ot.empresa_id == empresa_id:
                    ot.factura_id = factura.id
                    ot.estat = "FACTURADA"

        ruta_pdf = await cls._generar_pdf_i_pujar(db, empresa_id, factura, linies_models)
        if ruta_pdf:
            factura.pdf_path = ruta_pdf

        ruta_xml = await cls._generar_xml_i_pujar(
            db, empresa_id, factura, linies_models, tipus_registre="ALTA"
        )

        outbox = OutboxEnviamentAEAT(
            empresa_id=empresa_id,
            factura_id=factura.id,
            tipus_registre="ALTA",
            payload_xml_path=ruta_xml,
            hash_sha256=hash_propi,
        )
        db.add(outbox)

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-02",
            f"Emissió Factura Veri*factu {codi_complet} Hash:{hash_propi[:12]}",
        )
        await db.commit()
        return factura

    @classmethod
    async def anular_factura_verifactu(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
        motiu: str,
        confirmacio_humana_hitl: bool = True,
    ) -> FacturaCapcalera:
        """
        Emet un Registre d'Anul·lació (RegistroAnulacion) encadenat a la mateixa cadena SHA-256 de l'empresa
        segons l'Art. 13.2 de l'Ordre HAC/1177/2024.
        """
        if not confirmacio_humana_hitl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cal confirmació humana explícita (HITL) per anul·lar una factura Veri*factu.",
            )
        factura = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id,
                    FacturaCapcalera.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no trobada.")
        if factura.estat_document != "EMESA" or factura.serie.upper() == "PRE":
            raise HTTPException(
                status_code=400,
                detail="Només es poden anul·lar factures emeses definitivament (les pre-factures s'esborren).",
            )
        if factura.estat_anulacio == "ANULADA_VERIFACTU":
            raise HTTPException(
                status_code=409,
                detail="Aquesta factura ja disposa d'un registre d'anul·lació Veri*factu.",
            )

        emp = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
        emp_nif = emp.nif if emp else "B00000000"
        num_serie_anulada = factura.num_serie_verifactu or format_num_serie(
            factura.serie, int(factura.exercici or 2026), int(factura.numero_factura)
        )

        reg_anul = await VerifactuCoreService.registrar_anulacio_cadena(
            db=db,
            empresa_id=empresa_id,
            empresa_nif=emp_nif,
            num_serie_anulada=num_serie_anulada,
            data_emissio_anulada=factura.data_emissio,
        )

        factura.estat_anulacio = "ANULADA_VERIFACTU"
        factura.data_anulacio = datetime.now(timezone.utc)
        factura.motiu_anulacio = motiu.strip()
        factura.hash_anulacio_sha256 = reg_anul["hash_anulacio_sha256"]
        factura.estat_cobrament = "ANULADA"
        factura.updated_at = datetime.now(timezone.utc)

        linies = list(
            (
                await db.execute(
                    select(FacturaLinia).where(
                        FacturaLinia.factura_id == factura.id,
                        FacturaLinia.empresa_id == empresa_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        ruta_pdf = await cls._generar_pdf_i_pujar(db, empresa_id, factura, linies)
        if ruta_pdf:
            factura.pdf_path = ruta_pdf

        ruta_xml_anul = await cls._generar_xml_i_pujar(
            db, empresa_id, factura, linies, tipus_registre="ANULACION"
        )

        db.add(
            OutboxEnviamentAEAT(
                empresa_id=empresa_id,
                factura_id=factura.id,
                tipus_registre="ANULACION",
                payload_xml_path=ruta_xml_anul,
                hash_sha256=reg_anul["hash_anulacio_sha256"],
            )
        )
        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-04",
            f"Registre d'Anul·lació Veri*factu {num_serie_anulada} Motiu:{motiu.strip()} Hash:{reg_anul['hash_anulacio_sha256'][:12]}",
            dades_event={
                "factura_id": str(factura.id),
                "num_serie_anulada": num_serie_anulada,
                "hash_anulacio_sha256": reg_anul["hash_anulacio_sha256"],
                "hash_anterior": reg_anul["hash_anterior"],
                "fecha_hora_huso_gen_registro": reg_anul["fecha_hora_huso_gen_registro"],
            },
        )
        await db.commit()
        return factura

    # --- MILLORA 1: CONTROL DEL WIP (OBRA EN CURS NO FACTURADA) (RF-31, RF-32) ---
    @classmethod
    async def obtenir_control_wip(
        cls, db: AsyncSession, empresa_id: uuid.UUID, avui: Optional[date] = None
    ) -> WIPControlResponseDTO:
        avui = avui or date.today()
        rows = (
            await db.execute(
                select(OrdreTreball, Client.rao_social)
                .outerjoin(Client, OrdreTreball.client_id == Client.id)
                .where(
                    OrdreTreball.empresa_id == empresa_id,
                    OrdreTreball.factura_id.is_(None),
                    OrdreTreball.estat.in_(ESTATS_OT_PENDENTS_PREFACTURACIO),
                )
                .order_by(OrdreTreball.created_at.desc())
            )
        ).all()

        ots = [ot for ot, _ in rows]
        items: List[WIPItemDTO] = []
        total_pvp = Decimal("0.00")
        total_cost = Decimal("0.00")
        envellides = 0

        barema_empresa = await obtenir_barema_empresa(db, empresa_id)
        cap_ids = [ot.cap_de_colla_id for ot in ots if ot.cap_de_colla_id is not None]
        costs_map = await obtenir_cost_hora_operaris_map(db, empresa_id, cap_ids)
        picking_mat_map = await cls.obtenir_materials_consumits_ots(
            db, empresa_id, [ot.id for ot in ots]
        )

        for ot, client_nom in rows:
            data_ref = ot.data_finalitzacio_camp or ot.data_planificacio or avui
            dies_wip = max(0, (avui - data_ref).days)
            es_envellit = dies_wip > 7

            hores = Decimal(str(ot.hores_imputades_facturables or 0))
            preu_hora_real = await resoldre_preu_hora_control_panel(
                db,
                empresa_id,
                ot,
                barema_cache=barema_empresa,
                barema_fetched=True,
            )
            pvp_h = Decimal(str(preu_hora_real))
            pvp_mat = Decimal(str(ot.pvp_materials_aplicat or 0))
            if pvp_mat <= 0 and ot.id in picking_mat_map:
                pvp_mat = q2(sum((m["subtotal"] for m in picking_mat_map[ot.id]), Decimal("0.00")))
            cost_mat = Decimal(str(ot.cost_materials_pmp or 0))

            valor_pvp = q2((hores * pvp_h) + pvp_mat)
            if ot.cost_ma_obra_real and float(ot.cost_ma_obra_real) > 0:
                cost_mo = Decimal(str(ot.cost_ma_obra_real))
            elif ot.cap_de_colla_id and ot.cap_de_colla_id in costs_map:
                cost_mo = hores * costs_map[ot.cap_de_colla_id]
            else:
                cost_mo = Decimal("0.00")
            cost_avancat = q2(cost_mo + cost_mat)

            total_pvp += valor_pvp
            total_cost += cost_avancat
            if es_envellit:
                envellides += 1

            items.append(
                WIPItemDTO(
                    ordre_treball_id=ot.id,
                    codi_ot=ot.codi,
                    titol_ot=ot.titol,
                    client_id=ot.client_id,
                    client_nom=client_nom,
                    estat_ot=ot.estat,
                    hores_imputades=q2(hores),
                    preu_hora_aplicat=q2(pvp_h),
                    pvp_materials=q2(pvp_mat),
                    dies_en_wip=dies_wip,
                    valor_wip_pvp=valor_pvp,
                    cost_wip_avancat=cost_avancat,
                    es_wip_envellit_alerta=es_envellit,
                )
            )

        return WIPControlResponseDTO(
            total_wip_valorat_pvp=total_pvp,
            total_cost_wip_avancat=total_cost,
            nombre_ots_en_wip=len(items),
            nombre_ots_envellides_critiques=envellides,
            items=items,
        )

    # --- MILLORA 2: RETENCIONS DE GARANTIA 5% (RF-33, RF-34) ---
    @classmethod
    async def llistar_retencions_garantia(
        cls, db: AsyncSession, empresa_id: uuid.UUID, avui: Optional[date] = None
    ) -> List[RetencioGarantiaDTO]:
        avui = avui or date.today()
        rets = (
            (await db.execute(select(RetencioGarantia).where(RetencioGarantia.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
        resultat: List[RetencioGarantiaDTO] = []
        dirty = False
        for r in rets:
            dies_restants = (r.data_venciment_garantia - avui).days
            alerta = r.estat in ("RETINGUDA", "PENDENT_RECLAMACIO") and dies_restants <= 15
            if alerta and r.estat == "RETINGUDA":
                r.estat = "PENDENT_RECLAMACIO"
                dirty = True
            resultat.append(
                RetencioGarantiaDTO(
                    id=r.id,
                    tipus=r.tipus,
                    factura_client_id=r.factura_client_id,
                    import_retingut=q2(Decimal(str(r.import_retingut))),
                    data_retencio=r.data_retencio,
                    data_venciment_garantia=r.data_venciment_garantia,
                    dies_fins_venciment=dies_restants,
                    estat=r.estat,
                    alerta_venciment_proper=alerta,
                )
            )
        if dirty:
            await db.commit()
        return resultat

    @classmethod
    async def reclamar_retencio_garantia(
        cls, db: AsyncSession, empresa_id: uuid.UUID, usuari_id: uuid.UUID, retencio_id: uuid.UUID
    ) -> RetencioGarantia:
        ret = (
            await db.execute(
                select(RetencioGarantia).where(
                    RetencioGarantia.id == retencio_id,
                    RetencioGarantia.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not ret:
            raise HTTPException(status_code=404, detail="Retenció de garantia no trobada.")
        ret.estat = "RECLAMADA"
        await cls.registrar_esdeveniment_sif(
            db, empresa_id, usuari_id, "EV-04", f"Reclamació alliberament retenció garantia {ret.id}"
        )
        await db.commit()
        await db.refresh(ret)
        return ret

    # --- REGISTRE MANUAL DE COBRAMENTS DE FACTURES EMESES ---
    @classmethod
    async def registrar_cobrament_factura(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
        payload: FacturaCobramentRequestDTO,
    ) -> FacturaCapcalera:
        factura = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id,
                    FacturaCapcalera.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not factura:
            raise HTTPException(status_code=404, detail="Factura no trobada.")

        if factura.estat_document != "EMESA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No es pot registrar un cobrament sobre una pre-factura en esborrany.",
            )
        if str(factura.estat_anulacio or "ACTIVA") == "ANULADA_VERIFACTU":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No es pot registrar un cobrament sobre una factura anul·lada a Veri*factu.",
            )

        liquid = q2(Decimal(str(factura.liquid_exigible or 0)))
        estat_nou = payload.estat_cobrament.upper()
        import_final: Decimal
        data_cob: Optional[date]

        if estat_nou == "COBRADA":
            import_final = q2(payload.import_cobrat) if payload.import_cobrat is not None else liquid
            if liquid > Decimal("0.00"):
                if import_final > liquid:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="L'import cobrat no pot superar el líquid exigible de la factura.",
                    )
                if import_final <= Decimal("0.00"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Per marcar una factura com a COBRADA cal indicar un import positiu.",
                    )
                if import_final < liquid:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Per a cobraments inferiors al líquid exigible utilitza l'estat PARCIAL.",
                    )
            data_cob = payload.data_cobrament_real or date.today()
        elif estat_nou == "PARCIAL":
            if payload.import_cobrat is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Cal especificar import_cobrat per a un cobrament PARCIAL.",
                )
            import_final = q2(payload.import_cobrat)
            if import_final <= Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="L'import d'un cobrament parcial ha de ser superior a 0.",
                )
            if liquid > Decimal("0.00") and import_final > liquid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="L'import cobrat no pot superar el líquid exigible de la factura.",
                )
            if liquid > Decimal("0.00") and import_final == liquid:
                estat_nou = "COBRADA"
            data_cob = payload.data_cobrament_real or date.today()
        else:
            # PENDENT o IMPAGADA
            import_final = q2(payload.import_cobrat) if payload.import_cobrat is not None else Decimal("0.00")
            if liquid > Decimal("0.00") and import_final >= liquid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Si s'ha cobrat la totalitat del líquid exigible, utilitza l'estat COBRADA.",
                )
            data_cob = payload.data_cobrament_real if import_final > Decimal("0.00") else None

        factura.estat_cobrament = estat_nou
        factura.import_cobrat = float(import_final)
        factura.data_cobrament_real = data_cob

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-06",
            f"Registre manual cobrament factura {factura.num_serie_verifactu or factura.numero_factura}: "
            f"{estat_nou} ({import_final} EUR)",
            dades_event={
                "factura_id": str(factura.id),
                "estat_cobrament": estat_nou,
                "import_cobrat": str(import_final),
                "data_cobrament_real": data_cob.isoformat() if data_cob else None,
                "notes": payload.notes,
            },
        )
        await db.flush()
        await cls.evaluar_risc_client(db, empresa_id, factura.client_id, auto_commit=False)
        await db.commit()
        return factura

    # --- MILLORA 3: SEMÀFOR DE RISC DE CRÈDIT I BLOQUEIG OPERATIU A CAMP (RF-35, RF-36) ---
    @classmethod
    async def evaluar_risc_client(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id: uuid.UUID,
        avui: Optional[date] = None,
        auto_commit: bool = True,
    ) -> Client:
        avui = avui or date.today()
        client = (
            await db.execute(
                select(Client).where(Client.id == client_id, Client.empresa_id == empresa_id)
            )
        ).scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client no trobat")

        if client.estat_risc_operatiu == "OVERRIDE_BOSS":
            return client

        factures_pendents = (
            (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.empresa_id == empresa_id,
                        FacturaCapcalera.client_id == client_id,
                        FacturaCapcalera.estat_document == "EMESA",
                        func.coalesce(FacturaCapcalera.estat_anulacio, "ACTIVA") != "ANULADA_VERIFACTU",
                        FacturaCapcalera.estat_cobrament.in_(["PENDENT", "PARCIAL", "IMPAGADA"]),
                    )
                )
            )
            .scalars()
            .all()
        )

        deute_viu_ordinari = Decimal("0.00")
        te_impagat_critic_90d = False

        for f in factures_pendents:
            pendent_factura = max(
                Decimal("0.00"),
                Decimal(str(f.liquid_exigible or 0)) - Decimal(str(f.import_cobrat or 0)),
            )
            deute_viu_ordinari += pendent_factura
            data_venc = f.data_venciment or f.data_emissio.date()
            dies_retard = (avui - data_venc).days
            if pendent_factura > Decimal("0.00") and dies_retard > 90:
                te_impagat_critic_90d = True

        limit = Decimal(str(client.limit_risc_credit or 15000))
        if te_impagat_critic_90d or deute_viu_ordinari > limit:
            client.estat_risc_operatiu = "BLOQUEJAT_RISC"
        else:
            client.estat_risc_operatiu = "APTE"

        if auto_commit:
            await db.commit()
        else:
            await db.flush()
        return client

    @classmethod
    async def override_risc_pel_boss(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        boss_id: uuid.UUID,
        client_id: uuid.UUID,
        motiu: str,
    ) -> Client:
        client = (
            await db.execute(
                select(Client).where(Client.id == client_id, Client.empresa_id == empresa_id)
            )
        ).scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client no trobat")

        client.estat_risc_operatiu = "OVERRIDE_BOSS"
        client.motiu_override_risc = motiu
        client.override_boss_usuari_id = boss_id
        client.data_override_risc = datetime.now(timezone.utc)

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            boss_id,
            "EV-06",
            f"Desbloqueig cautelar de risc client {client.nif}: {motiu}",
        )
        await db.commit()
        await db.refresh(client)
        return client

    @classmethod
    async def validar_operacio_camp_client(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id: uuid.UUID,
        enforce_lock: bool = True,
        evaluate_risk: bool = False,
    ) -> ClientRiscSanititzatDTO:
        client: Optional[Client]
        if evaluate_risk:
            client = await cls.evaluar_risc_client(db, empresa_id, client_id)
        else:
            client = (
                await db.execute(
                    select(Client).where(Client.id == client_id, Client.empresa_id == empresa_id)
                )
            ).scalar_one_or_none()
            if not client:
                raise HTTPException(status_code=404, detail="Client no trobat")
        pot_operar = client.estat_risc_operatiu in ("APTE", "OVERRIDE_BOSS")
        if enforce_lock and not pot_operar:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="BLOQUEJAT PER RISC ADMINISTRATIU: No es poden obrir noves OTs ni fer Picking sense autorització del BOSS.",
            )
        return ClientRiscSanititzatDTO(
            client_id=client.id,
            estat_risc_operatiu=client.estat_risc_operatiu,
            pot_obrir_ot_i_picking=pot_operar,
            missatge_operatiu=(
                "Client operatiu autoritzat." if pot_operar else "BLOQUEJAT PER RISC ADMINISTRATIU"
            ),
        )

    # --- MILLORA 4: MOTOR DE RECUPERACIÓ D'IVA D'INCOBRABLES (ART. 80 LIVA) ---
    @classmethod
    async def processar_finestres_art80_liva(
        cls, db: AsyncSession, empresa_id: uuid.UUID, avui: Optional[date] = None
    ) -> List[Art80ItemDTO]:
        avui = avui or date.today()
        factures = (
            (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.empresa_id == empresa_id,
                        FacturaCapcalera.estat_document == "EMESA",
                        func.coalesce(FacturaCapcalera.estat_anulacio, "ACTIVA") != "ANULADA_VERIFACTU",
                        FacturaCapcalera.estat_cobrament.in_(["PENDENT", "PARCIAL", "IMPAGADA"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        items: List[Art80ItemDTO] = []
        dirty = False
        for f in factures:
            if f.serie.upper().startswith("R"):
                continue
            pendent = Decimal(str(f.liquid_exigible or 0)) - Decimal(str(f.import_cobrat or 0))
            if pendent <= Decimal("0.00"):
                continue
            data_em = f.data_emissio.date() if isinstance(f.data_emissio, datetime) else f.data_emissio
            dies_des_emissio = (avui - data_em).days
            if 180 <= dies_des_emissio <= 270:
                if f.estat_art80 == "NO_APLICA":
                    f.estat_art80 = "FINESTRA_ART80_OBERTA"
                    dirty = True
                items.append(
                    Art80ItemDTO(
                        factura_id=f.id,
                        numero_factura=f.numero_factura,
                        serie=f.serie,
                        client_id=f.client_id,
                        data_emissio=data_em,
                        data_limit_art80=data_em + timedelta(days=270),
                        base_imposable=q2(Decimal(str(f.base_imposable))),
                        quota_iva=q2(Decimal(str(f.quota_iva))),
                        dies_impagada=dies_des_emissio,
                        estat_art80=f.estat_art80,
                    )
                )
            elif dies_des_emissio > 270 and f.estat_art80 != "RECLAMADA_AEAT":
                if f.estat_art80 != "FINESTRA_ART80_EXPIRADA":
                    f.estat_art80 = "FINESTRA_ART80_EXPIRADA"
                    dirty = True
                items.append(
                    Art80ItemDTO(
                        factura_id=f.id,
                        numero_factura=f.numero_factura,
                        serie=f.serie,
                        client_id=f.client_id,
                        data_emissio=data_em,
                        data_limit_art80=data_em + timedelta(days=270),
                        base_imposable=q2(Decimal(str(f.base_imposable))),
                        quota_iva=q2(Decimal(str(f.quota_iva))),
                        dies_impagada=dies_des_emissio,
                        estat_art80=f.estat_art80,
                    )
                )
        if dirty:
            await db.commit()
        return items

    @classmethod
    async def generar_rectificativa_art80(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        factura_id: uuid.UUID,
        justificant_notarial_path: str,
        avui: Optional[date] = None,
    ) -> FacturaCapcalera:
        avui = avui or date.today()
        await cls.processar_finestres_art80_liva(db, empresa_id, avui)
        orig = (
            await db.execute(
                select(FacturaCapcalera).where(
                    FacturaCapcalera.id == factura_id, FacturaCapcalera.empresa_id == empresa_id
                )
            )
        ).scalar_one_or_none()
        if not orig:
            raise HTTPException(status_code=404, detail="Factura original no trobada.")

        if orig.estat_art80 == "FINESTRA_ART80_EXPIRADA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FINESTRA_ART80_EXPIRADA: S'ha superat el termini legal de 270 dies (6m + 3m) de l'Art. 80 LIVA.",
            )
        if orig.estat_art80 != "FINESTRA_ART80_OBERTA":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La factura encara no ha complert els 180 dies d'impagament exigits per l'Art. 80.Quatre LIVA.",
            )
        if not justificant_notarial_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cal adjuntar el requeriment notarial o reclamació judicial per recuperar l'IVA d'incobrables.",
            )

        orig.justificant_reclamacio_art80_path = justificant_notarial_path
        orig.estat_art80 = "RECLAMADA_AEAT"

        from app.schemas.comptabilitat import FacturaLiniaCreateDTO

        dto_rect = FacturaEmissioCreateDTO(
            client_id=orig.client_id,
            serie="R",
            data_emissio=avui,
            data_venciment=avui,
            factura_rectificada_id=orig.id,
            motiu_rectificacio="Rectificació de modificació de base imposable per crèdit incobrable (Art. 80.Quatre LIVA)",
            linies=[
                FacturaLiniaCreateDTO(
                    concepte=f"Recuperació IVA incobrable s/Factura {orig.serie}-{orig.numero_factura}",
                    compte_pgc="430900",
                    quantitat=Decimal("1.00"),
                    preu_venda_unitari=Decimal(str(orig.base_imposable)),
                    tipus_iva_pct=Decimal("21.00"),
                )
            ],
        )
        return await cls.emetre_factura_verifactu(db, empresa_id, usuari_id, dto_rect)

    # --- CRUD DESPESES FIXES RECURRENTS (ESTRUCTURA / BREAK-EVEN / BURN RATE) ---
    @staticmethod
    def _normalitzar_mensual_despesa_fixa(import_val: Decimal, periodicitat: str) -> Decimal:
        per = (periodicitat or "MENSUAL").strip().upper()
        if per == "TRIMESTRAL":
            return q2(import_val / Decimal("3"))
        if per == "ANUAL":
            return q2(import_val / Decimal("12"))
        return q2(import_val)

    @classmethod
    def _serialitzar_despesa_fixa(cls, df: DespesaFixaRecurrent) -> DespesaFixaResponseDTO:
        imp_base = q2(Decimal(str(df.import_base or 0)))
        iva_val = q2(Decimal(str(df.quota_iva or 0)))
        return DespesaFixaResponseDTO(
            id=df.id,
            concepte=df.concepte,
            categoria=df.categoria,
            import_base=imp_base,
            quota_iva=iva_val,
            periodicitat=df.periodicitat or "MENSUAL",
            import_mensual_normalitzat=cls._normalitzar_mensual_despesa_fixa(imp_base, df.periodicitat),
            iva_mensual_normalitzat=cls._normalitzar_mensual_despesa_fixa(iva_val, df.periodicitat),
            dia_carrec=int(df.dia_carrec or 5),
            actiu=bool(df.actiu),
            created_at=df.created_at or datetime.now(timezone.utc),
        )

    @classmethod
    async def llistar_despeses_fixes(
        cls, db: AsyncSession, empresa_id: uuid.UUID, nomes_actives: bool = False
    ) -> List[DespesaFixaResponseDTO]:
        stmt = select(DespesaFixaRecurrent).where(DespesaFixaRecurrent.empresa_id == empresa_id)
        if nomes_actives:
            stmt = stmt.where(DespesaFixaRecurrent.actiu.is_(True))
        stmt = stmt.order_by(DespesaFixaRecurrent.actiu.desc(), DespesaFixaRecurrent.created_at.desc())
        rows = (await db.execute(stmt)).scalars().all()
        return [cls._serialitzar_despesa_fixa(r) for r in rows]

    @classmethod
    async def crear_despesa_fixa(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        payload: DespesaFixaCreateDTO,
    ) -> DespesaFixaResponseDTO:
        ara = datetime.now(timezone.utc)
        nova = DespesaFixaRecurrent(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            concepte=payload.concepte.strip(),
            categoria=payload.categoria.strip().upper(),
            import_base=float(q2(payload.import_base)),
            quota_iva=float(q2(payload.quota_iva)),
            periodicitat=payload.periodicitat.strip().upper(),
            dia_carrec=int(payload.dia_carrec),
            actiu=bool(payload.actiu),
            created_at=ara,
        )
        db.add(nova)
        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-06",
            f"Alta despesa fixa recurrent: {nova.concepte} ({nova.import_base} EUR / {nova.periodicitat})",
        )
        await db.flush()
        dto = cls._serialitzar_despesa_fixa(nova)
        await db.commit()
        return dto

    @classmethod
    async def actualitzar_despesa_fixa(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        despesa_id: uuid.UUID,
        payload: DespesaFixaUpdateDTO,
    ) -> DespesaFixaResponseDTO:
        df = (
            await db.execute(
                select(DespesaFixaRecurrent).where(
                    DespesaFixaRecurrent.id == despesa_id,
                    DespesaFixaRecurrent.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not df:
            raise HTTPException(status_code=404, detail="Despesa fixa no trobada.")

        if payload.concepte is not None:
            df.concepte = payload.concepte.strip()
        if payload.categoria is not None:
            df.categoria = payload.categoria.strip().upper()
        if payload.import_base is not None:
            df.import_base = float(q2(payload.import_base))
        if payload.quota_iva is not None:
            df.quota_iva = float(q2(payload.quota_iva))
        if payload.periodicitat is not None:
            df.periodicitat = payload.periodicitat.strip().upper()
        if payload.dia_carrec is not None:
            df.dia_carrec = int(payload.dia_carrec)
        if payload.actiu is not None:
            df.actiu = bool(payload.actiu)

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-06",
            f"Actualització despesa fixa recurrent {df.id}: {df.concepte}",
        )
        await db.flush()
        dto = cls._serialitzar_despesa_fixa(df)
        await db.commit()
        return dto

    @classmethod
    async def eliminar_despesa_fixa(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        despesa_id: uuid.UUID,
        hard_delete: bool = False,
    ) -> Dict[str, Any]:
        df = (
            await db.execute(
                select(DespesaFixaRecurrent).where(
                    DespesaFixaRecurrent.id == despesa_id,
                    DespesaFixaRecurrent.empresa_id == empresa_id,
                )
            )
        ).scalar_one_or_none()
        if not df:
            raise HTTPException(status_code=404, detail="Despesa fixa no trobada.")

        concepte = df.concepte
        if hard_delete:
            await db.delete(df)
            estat_final = "ELIMINADA"
        else:
            df.actiu = False
            estat_final = "DESACTIVADA"

        await cls.registrar_esdeveniment_sif(
            db,
            empresa_id,
            usuari_id,
            "EV-06",
            f"Baixa despesa fixa recurrent ({estat_final}): {concepte}",
        )
        await db.commit()
        return {"id": str(despesa_id), "status": estat_final}

    # --- MILLORA 5: COST HORA EFECTIU DINÀMIC D'OPERARIS (RF-18, RF-39, RF-40, EDGE-03) ---
    @classmethod
    async def calcular_cost_efectiu_operaris(
        cls, db: AsyncSession, empresa_id: uuid.UUID, rol_peticio: str
    ) -> List[OperariCostEfectiuDTO]:
        operaris = (
            (
                await db.execute(
                    select(Usuari).where(
                        Usuari.empresa_id == empresa_id,
                        Usuari.estat == "ACTIU",
                    )
                )
            )
            .scalars()
            .all()
        )
        trams_tots = (
            (
                await db.execute(
                    select(OrdreTreballTramTemps).where(
                        OrdreTreballTramTemps.empresa_id == empresa_id,
                        OrdreTreballTramTemps.operari_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        ots_cap = (
            (
                await db.execute(
                    select(OrdreTreball).where(
                        OrdreTreball.empresa_id == empresa_id,
                        OrdreTreball.cap_de_colla_id.is_not(None),
                        OrdreTreball.hores_imputades_facturables > 0,
                    )
                )
            )
            .scalars()
            .all()
        )

        trams_by_op: Dict[uuid.UUID, List[OrdreTreballTramTemps]] = {}
        for t in trams_tots:
            if t.operari_id:
                trams_by_op.setdefault(t.operari_id, []).append(t)

        ots_by_cap: Dict[uuid.UUID, List[OrdreTreball]] = {}
        for ot in ots_cap:
            if ot.cap_de_colla_id:
                ots_by_cap.setdefault(ot.cap_de_colla_id, []).append(ot)

        resultat: List[OperariCostEfectiuDTO] = []

        for op in operaris:
            jornades = (
                (
                    await db.execute(
                        select(RegistreJornadaLaboral).where(
                            RegistreJornadaLaboral.empresa_id == empresa_id,
                            RegistreJornadaLaboral.usuari_id == op.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            hores_fitxades = sum(
                (Decimal(str(j.hores_ordinaries or 0)) + Decimal(str(j.hores_extraordinaries or 0)) for j in jornades),
                Decimal("0.00"),
            )

            # 1) Hores reals d'OT procedents de trams de temps (OrdreTreballTramTemps)
            hores_trams = Decimal("0.00")
            ot_ids_amb_trams: set[uuid.UUID] = set()
            for t in trams_by_op.get(op.id, []):
                ot_ids_amb_trams.add(t.ordre_treball_id)
                segons = int(t.durada_segons or 0)
                if segons <= 0 and t.hora_inici and t.hora_fi:
                    segons = max(0, int((t.hora_fi - t.hora_inici).total_seconds()))
                if segons > 0:
                    hores_trams += Decimal(segons) / Decimal("3600")

            # 2) Hores imputades a OTs com a cap de colla sense duplicar les que ja tenen trams
            hores_ots_cap = Decimal("0.00")
            for ot in ots_by_cap.get(op.id, []):
                if ot.id not in ot_ids_amb_trams:
                    hores_ots_cap += Decimal(str(ot.hores_imputades_facturables or 0))

            hores_ot = hores_trams + hores_ots_cap
            # 3) Fallback retrocompatible a RegistreJornadaLaboral.hores_imputades_ot
            if hores_ot == Decimal("0.00"):
                hores_ot = sum(
                    (Decimal(str(j.hores_imputades_ot or 0)) for j in jornades), Decimal("0.00")
                )

            tiquets_op = (
                await db.execute(
                    select(func.coalesce(func.sum(TiquetDespesa.import_total), 0.0)).where(
                        TiquetDespesa.empresa_id == empresa_id,
                        TiquetDespesa.usuari_id == op.id,
                        TiquetDespesa.estat_aprovacio == "APROVAT",
                    )
                )
            ).scalar_one()

            salari_brut = Decimal(str(op.salari_mensual_brut or 0))
            cost_ss = Decimal(str(op.cost_ss_mensual or 0))
            cost_hora_ref = q2(
                Decimal(
                    str(
                        op.cost_hora_eur
                        if op.cost_hora_eur is not None
                        else (op.cost_hora_referencia or 22.5)
                    )
                )
            )
            if (salari_brut + cost_ss) > Decimal("0.00"):
                cost_total_mes = salari_brut + cost_ss + Decimal(str(tiquets_op or 0))
            else:
                base_hores = hores_fitxades if hores_fitxades > Decimal("0.00") else hores_ot
                cost_derivat = q2(base_hores * cost_hora_ref) if (base_hores > Decimal("0.00") and cost_hora_ref > Decimal("0.00")) else Decimal("0.00")
                cost_total_mes = cost_derivat + Decimal(str(tiquets_op or 0))

            if rol_peticio == "SECRETARIA" and op.es_alta_direccio:
                salari_visible = "***"
            else:
                salari_visible = f"{q2(salari_brut + cost_ss)} EUR"

            if hores_ot > Decimal("0.00"):
                cost_efectiu = q2(cost_total_mes / hores_ot)
                eficiencia = (
                    q2((hores_ot / hores_fitxades) * Decimal("100.00"))
                    if hores_fitxades > Decimal("0.00")
                    else Decimal("100.00")
                )
                alerta_improd = eficiencia < Decimal("70.00")
            else:
                cost_efectiu = None
                eficiencia = Decimal("0.00")
                alerta_improd = True

            resultat.append(
                OperariCostEfectiuDTO(
                    usuari_id=op.id,
                    nom_complet=f"{op.nom} {op.cognoms}".strip(),
                    cost_hora_referencia=cost_hora_ref,
                    salari_brut_i_ss_visible=salari_visible,
                    hores_fitxades_mes=q2(hores_fitxades),
                    hores_imputades_ot_mes=q2(hores_ot),
                    ratio_eficiencia_pct=eficiencia,
                    cost_hora_efectiu_mensual=cost_efectiu,
                    alerta_improductivitat=alerta_improd,
                )
            )
        return resultat

    # --- MILLORA 6: AUDITORIA DE SINISTRALITAT DE CONTRACTES MRR (RF-41) ---
    @classmethod
    async def auditar_contractes_mrr(
        cls, db: AsyncSession, empresa_id: uuid.UUID
    ) -> List[ContracteMRRAuditoriaDTO]:
        contractes_reals = (
            (
                await db.execute(
                    select(ContracteManteniment).where(
                        ContracteManteniment.empresa_id == empresa_id,
                        ContracteManteniment.estat == "ACTIU",
                    )
                )
            )
            .scalars()
            .all()
        )
        contractes_legacy = (
            (
                await db.execute(
                    select(ContracteMantenimentMRR).where(
                        ContracteMantenimentMRR.empresa_id == empresa_id,
                        ContracteMantenimentMRR.actiu.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        resultat: List[ContracteMRRAuditoriaDTO] = []

        ops_emp = (
            (
                await db.execute(
                    select(Usuari).where(
                        Usuari.empresa_id == empresa_id,
                        Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA", "CAPATAZ"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        costs_by_uid = {
            u.id: Decimal(str(u.cost_hora_eur if u.cost_hora_eur is not None else (u.cost_hora_referencia or 0)))
            for u in ops_emp
        }
        avg_cost_h = (
            sum(costs_by_uid.values(), Decimal("0.00")) / Decimal(len(costs_by_uid))
            if costs_by_uid
            else Decimal("0.00")
        )

        def _calcular_cost_ots(ots: Sequence[OrdreTreball]) -> Decimal:
            cost_total = Decimal("0.00")
            for ot in ots:
                if ot.cost_ma_obra_real and float(ot.cost_ma_obra_real) > 0:
                    cost_ma_obra = Decimal(str(ot.cost_ma_obra_real))
                else:
                    cost_h = (
                        costs_by_uid.get(ot.cap_de_colla_id, avg_cost_h)
                        if ot.cap_de_colla_id
                        else avg_cost_h
                    )
                    cost_ma_obra = Decimal(str(ot.hores_imputades_facturables or 0)) * cost_h
                cost_km = Decimal(int(ot.km_imputats or 0)) * Decimal("0.32")
                cost_total += q2(cost_ma_obra + Decimal(str(ot.cost_materials_pmp or 0)) + cost_km)
            return cost_total

        def _construir_dto(
            contracte_id: uuid.UUID,
            codi_contracte: str,
            client_id: uuid.UUID,
            quota: Decimal,
            cost_ots: Decimal,
        ) -> ContracteMRRAuditoriaDTO:
            marge = q2(quota - cost_ots)
            sinistralitat = (
                q2((cost_ots / quota) * Decimal("100.00"))
                if quota > Decimal("0.00")
                else Decimal("0.00")
            )
            if sinistralitat < Decimal("65.00"):
                semafor = "RENDIBLE"
            elif sinistralitat <= Decimal("90.00"):
                semafor = "ALERTA_EROSIO"
            else:
                semafor = "DEFICITARI_CRITIC"
            return ContracteMRRAuditoriaDTO(
                contracte_id=contracte_id,
                codi_contracte=codi_contracte,
                client_id=client_id,
                quota_mensual_mrr=q2(quota),
                cost_real_ots_periode=cost_ots,
                marge_net_contracte=marge,
                sinistralitat_pct=sinistralitat,
                semafor=semafor,
            )

        codis_vistos: set[str] = set()

        # 1. Font principal real: contractes_manteniment (/gestio/contractes) + revisions_contracte
        for cm in contractes_reals:
            codis_vistos.add(cm.numero_contracte)
            rev_ot_ids = [
                oid
                for oid in (
                    await db.execute(
                        select(RevisionsContracte.ordre_treball_id).where(
                            RevisionsContracte.empresa_id == empresa_id,
                            RevisionsContracte.contracte_id == cm.id,
                            RevisionsContracte.ordre_treball_id.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
                if oid is not None
            ]
            ots_reals: Sequence[OrdreTreball] = []
            if rev_ot_ids:
                ots_reals = (
                    (
                        await db.execute(
                            select(OrdreTreball).where(
                                OrdreTreball.empresa_id == empresa_id,
                                (OrdreTreball.id.in_(rev_ot_ids))
                                | (OrdreTreball.contracte_mrr_id == cm.id),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            else:
                ots_reals = (
                    (
                        await db.execute(
                            select(OrdreTreball).where(
                                OrdreTreball.empresa_id == empresa_id,
                                OrdreTreball.contracte_mrr_id == cm.id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

            quota_mensual = q2(Decimal(str(cm.import_anual or 0)) / Decimal("12"))
            cost_ots = _calcular_cost_ots(ots_reals)
            resultat.append(
                _construir_dto(
                    contracte_id=cm.id,
                    codi_contracte=cm.numero_contracte,
                    client_id=cm.client_id,
                    quota=quota_mensual,
                    cost_ots=cost_ots,
                )
            )

        # 2. Retrocompatibilitat: contractes_manteniment_mrr (evitant duplicats per codi)
        for c in contractes_legacy:
            if c.codi_contracte in codis_vistos:
                continue
            codis_vistos.add(c.codi_contracte)
            ots_leg = (
                (
                    await db.execute(
                        select(OrdreTreball).where(
                            OrdreTreball.empresa_id == empresa_id,
                            OrdreTreball.contracte_mrr_id == c.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            quota = Decimal(str(c.quota_mensual_mrr or 0))
            cost_ots = _calcular_cost_ots(ots_leg)
            resultat.append(
                _construir_dto(
                    contracte_id=c.id,
                    codi_contracte=c.codi_contracte,
                    client_id=c.client_id,
                    quota=quota,
                    cost_ots=cost_ots,
                )
            )

        return resultat

    # --- TIQUETS DE DESPESA (RF-20 / RF-21) ---
    @classmethod
    async def llistar_tiquets_despesa(
        cls, db: AsyncSession, empresa_id: uuid.UUID
    ) -> List[TiquetDespesaResponseDTO]:
        rows = (
            (
                await db.execute(
                    select(TiquetDespesa)
                    .where(TiquetDespesa.empresa_id == empresa_id)
                    .order_by(TiquetDespesa.data_tiquet.desc())
                )
            )
            .scalars()
            .all()
        )
        return [
            TiquetDespesaResponseDTO(
                id=t.id,
                categoria=t.categoria,
                usuari_id=t.usuari_id,
                vehicle_id=t.vehicle_id,
                ordre_treball_id=t.ordre_treball_id,
                data_tiquet=t.data_tiquet,
                nif_emissor=t.nif_emissor,
                nif_comprador=t.nif_comprador,
                rao_social=t.rao_social,
                base_imposable=q2(Decimal(str(t.base_imposable or 0))),
                iva_pct=q2(Decimal(str(t.iva_pct or 0))),
                quota_iva=q2(Decimal(str(t.quota_iva or 0))),
                import_total=q2(Decimal(str(t.import_total or 0))),
                subcompte_pgc=t.subcompte_pgc or "629000",
                estat_aprovacio=t.estat_aprovacio,
                estat_fiscal=t.estat_fiscal,
                requereix_aprovacio_boss=t.requereix_aprovacio_boss,
                custodia_paper_confirmada=t.custodia_paper_confirmada,
                nom_fitxer_visible=t.nom_fitxer_visible,
            )
            for t in rows
        ]

    @classmethod
    async def auditar_tiquet_despesa(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        rol_peticio: str,
        tiquet_id: uuid.UUID,
        payload: TiquetAuditoriaRequestDTO,
    ) -> TiquetDespesa:
        tiquet = (
            await db.execute(
                select(TiquetDespesa).where(
                    TiquetDespesa.id == tiquet_id, TiquetDespesa.empresa_id == empresa_id
                )
            )
        ).scalar_one_or_none()
        if not tiquet:
            raise HTTPException(status_code=404, detail="Tiquet de despesa no trobat.")

        if (
            tiquet.requereix_aprovacio_boss
            or tiquet.estat_aprovacio == "BLOQUEJAT_EXCEDENCIA_100EUR"
        ) and rol_peticio != "BOSS":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Els tiquets >100 EUR requereixen aprovació exclusiva del BOSS.",
            )

        if payload.accio not in ("APROVAT", "REBUTJAT"):
            raise HTTPException(status_code=400, detail="Acció invàlida (APROVAT o REBUTJAT).")

        if payload.nif_emissor is not None:
            tiquet.nif_emissor = payload.nif_emissor.strip().upper() or None
        if payload.nif_comprador is not None:
            tiquet.nif_comprador = payload.nif_comprador.strip().upper() or None
        if payload.import_total is not None and payload.import_total > 0:
            tiquet.import_total = float(q2(payload.import_total))

        if payload.desglose_carburant_eur is not None or payload.desglose_adblue_eur is not None:
            carb = q2(payload.desglose_carburant_eur or Decimal("0.00"))
            adbl = q2(payload.desglose_adblue_eur or Decimal("0.00"))
            total_desglose = q2(carb + adbl)
            if total_desglose > 0:
                tiquet.import_total = float(total_desglose)

        # RF-20 / EDGE-08: Si manca NIF, quota_iva = 0 i PENDENT_BESCANVI
        if not tiquet.nif_emissor and not tiquet.nif_comprador:
            tiquet.quota_iva = 0.00
            tiquet.iva_pct = 0.00
            tiquet.base_imposable = float(tiquet.import_total or 0.0)
            tiquet.estat_fiscal = "PENDENT_BESCANVI"
        elif tiquet.nif_comprador and tiquet.import_total:
            total_dec = q2(Decimal(str(tiquet.import_total)))
            base_dec = q2(total_dec / Decimal("1.21"))
            tiquet.base_imposable = float(base_dec)
            tiquet.quota_iva = float(q2(total_dec - base_dec))
            tiquet.iva_pct = 21.00
            tiquet.estat_fiscal = "DEDUIBLE"

        tiquet.estat_aprovacio = payload.accio
        if payload.custodia_paper_confirmada is not None:
            tiquet.custodia_paper_confirmada = payload.custodia_paper_confirmada
        if payload.ordre_treball_id is not None:
            tiquet.ordre_treball_id = payload.ordre_treball_id

        # Desblocatge de targeta de carburant del vehicle quan el BOSS aprova l'excedència
        if payload.accio == "APROVAT" and payload.desblocatge_targeta_vehicle and tiquet.vehicle_id:
            veh = (
                await db.execute(
                    select(Vehicle).where(
                        Vehicle.id == tiquet.vehicle_id,
                        Vehicle.empresa_id == empresa_id,
                    )
                )
            ).scalar_one_or_none()
            if veh and getattr(veh, "targeta_combustible_bloquejada", False):
                veh.targeta_combustible_bloquejada = False

        # Actualitzar o crear apunt a DespesaComptable
        despesa = (
            await db.execute(
                select(DespesaComptable).where(
                    DespesaComptable.empresa_id == empresa_id,
                    DespesaComptable.tiquet_id == tiquet.id,
                )
            )
        ).scalar_one_or_none()
        estat_desp = "CONSOLIDADA" if payload.accio == "APROVAT" else "REBUTJADA"
        if despesa:
            despesa.estat = estat_desp
            despesa.ordre_treball_id = tiquet.ordre_treball_id
            despesa.base_imposable = float(tiquet.base_imposable or 0.0)
            despesa.quota_iva = float(tiquet.quota_iva or 0.0)
            despesa.import_total = float(tiquet.import_total or 0.0)
        elif payload.accio == "APROVAT":
            db.add(
                DespesaComptable(
                    id=uuid.uuid4(),
                    empresa_id=empresa_id,
                    ordre_treball_id=tiquet.ordre_treball_id,
                    tiquet_id=tiquet.id,
                    concepte=f"Tiquet {tiquet.categoria} - {tiquet.rao_social or 'Validat /gestio'}",
                    subcompte=tiquet.subcompte_pgc or "629.DESPESA_CAMP",
                    base_imposable=float(tiquet.base_imposable or 0.0),
                    quota_iva=float(tiquet.quota_iva or 0.0),
                    import_total=float(tiquet.import_total or 0.0),
                    estat=estat_desp,
                    origen="OCR_TIQUET_CAMP",
                )
            )

        await cls.registrar_esdeveniment_sif(
            db, empresa_id, usuari_id, "EV-03", f"Auditoria tiquet {tiquet.id}: {payload.accio}"
        )
        await db.commit()
        return tiquet

    # --- CONCILIACIÓ NORMA 43 IDEMPOTENT (RF-22, RF-23) ---
    @classmethod
    async def conciliar_norma43(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        contingut_c43: str,
        confirmar_hitl: bool = False,
    ) -> List[Norma43MovimentDTO]:
        moviments_out: List[Norma43MovimentDTO] = []
        data_op_actual = date.today()

        for raw_line in contingut_c43.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("22"):
                # Format estàndard AEB43 registre 22 (simplificat i tolerant)
                try:
                    aa = int(line[10:12])
                    mm = int(line[12:14])
                    dd = int(line[14:16])
                    data_op_actual = date(2000 + aa, mm, dd)
                    signe = Decimal("-1") if line[27:28] == "1" else Decimal("1")
                    centims = Decimal(line[28:42].strip() or "0") / Decimal("100")
                    import_mov = q2(signe * centims)
                    concepte = line[52:80].strip() or "Moviment CSB 43"
                except (ValueError, IndexError):
                    import_mov = Decimal("0.00")
                    concepte = line[:80]
                saldo_res = import_mov
            elif "|" in line:
                # Format CSV/Pipe auxiliar per a càrregues estructurades
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 4:
                    continue
                data_op_actual = date.fromisoformat(parts[0])
                concepte = parts[1][:500]
                import_mov = q2(Decimal(parts[2]))
                saldo_res = q2(Decimal(parts[3]))
            else:
                continue

            raw_hash = f"{empresa_id}|{data_op_actual.isoformat()}|{import_mov}|EUR|{saldo_res}"
            huella = hashlib.sha256(raw_hash.encode("utf-8")).hexdigest()

            existent = (
                await db.execute(
                    select(ApuntBancariNorma43).where(
                        ApuntBancariNorma43.empresa_id == empresa_id,
                        ApuntBancariNorma43.huella_sha256 == huella,
                    )
                )
            ).scalar_one_or_none()

            if existent:
                moviments_out.append(
                    Norma43MovimentDTO(
                        data_operacio=existent.data_operacio,
                        concepte=existent.concepte,
                        import_moviment=q2(Decimal(str(existent.import_moviment))),
                        saldo_resultant=q2(Decimal(str(existent.saldo_resultant))),
                        huella_sha256=huella,
                        duplicat_rebutjat=True,
                        factura_suggerida_id=existent.factura_conciliada_id,
                    )
                )
                continue

            # Cerca factura pendent per import exacte
            factura_match = None
            if import_mov > Decimal("0.00"):
                cand = (
                    await db.execute(
                        select(FacturaCapcalera).where(
                            FacturaCapcalera.empresa_id == empresa_id,
                            FacturaCapcalera.estat_cobrament.in_(["PENDENT", "PARCIAL"]),
                            FacturaCapcalera.liquid_exigible == float(import_mov),
                        )
                    )
                ).scalars().first()
                if cand:
                    factura_match = cand.id
                    if confirmar_hitl:
                        cand.estat_cobrament = "COBRADA"
                        cand.import_cobrat = float(import_mov)
                        cand.data_cobrament_real = data_op_actual

            nou_apunt = ApuntBancariNorma43(
                empresa_id=empresa_id,
                data_operacio=data_op_actual,
                concepte=concepte,
                import_moviment=float(import_mov),
                divisa="EUR",
                saldo_resultant=float(saldo_res),
                huella_sha256=huella,
                conciliat=bool(confirmar_hitl and factura_match),
                factura_conciliada_id=factura_match,
            )
            db.add(nou_apunt)
            moviments_out.append(
                Norma43MovimentDTO(
                    data_operacio=data_op_actual,
                    concepte=concepte,
                    import_moviment=import_mov,
                    saldo_resultant=saldo_res,
                    huella_sha256=huella,
                    duplicat_rebutjat=False,
                    factura_suggerida_id=factura_match,
                )
            )

        await db.commit()
        return moviments_out

    # --- DASHBOARD ECONÒMIC GLOBAL (5 BLOCS KPI + 5 GRÀFIQUES) (RF-26 a RF-30, RF-42) ---
    @classmethod
    async def obtenir_dashboard_economic(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        criteri_caixa: bool = False,
        avui: Optional[date] = None,
        periode: Optional[str] = None,
    ) -> DashboardEconomicResponseDTO:
        avui = avui or date.today()
        periode_norm = (periode or "").strip().upper()
        data_inici_periode: Optional[date] = None
        mesos_periode = 1
        if periode_norm == "MES_ACTUAL":
            data_inici_periode = avui.replace(day=1)
            mesos_periode = 1
        elif periode_norm == "TRIMESTRE_ACTUAL":
            mes_inici_trim = ((avui.month - 1) // 3) * 3 + 1
            data_inici_periode = date(avui.year, mes_inici_trim, 1)
            mesos_periode = max(1, (avui.month - mes_inici_trim) + 1)
        elif periode_norm in ("YTD", "EXERCICI_FISCAL"):
            data_inici_periode = date(avui.year, 1, 1)
            mesos_periode = max(1, avui.month)

        factures_totes = (
            (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.empresa_id == empresa_id,
                        FacturaCapcalera.estat_document == "EMESA",
                        func.coalesce(FacturaCapcalera.estat_anulacio, "ACTIVA") != "ANULADA_VERIFACTU",
                    )
                )
            )
            .scalars()
            .all()
        )
        if data_inici_periode is not None:
            dt_inici = datetime.combine(
                data_inici_periode, datetime.min.time(), tzinfo=timezone.utc
            )
            factures = [
                f
                for f in factures_totes
                if (
                    f.data_emissio
                    if isinstance(f.data_emissio, datetime)
                    else datetime.combine(f.data_emissio, datetime.min.time(), tzinfo=timezone.utc)
                )
                >= dt_inici
            ]
        else:
            factures = list(factures_totes)

        def _base_computable(f: FacturaCapcalera) -> Decimal:
            base = Decimal(str(f.base_imposable or 0))
            if not criteri_caixa:
                return base
            if f.estat_cobrament == "COBRADA":
                return base
            if f.estat_cobrament == "PARCIAL":
                liq = Decimal(str(f.liquid_exigible or 0))
                cob = Decimal(str(f.import_cobrat or 0))
                if liq > Decimal("0.00") and cob > Decimal("0.00"):
                    ratio = min(Decimal("1.00"), cob / liq)
                    return q2(base * ratio)
            return Decimal("0.00")

        if criteri_caixa:
            factures_computables = [
                f for f in factures if f.estat_cobrament in ("COBRADA", "PARCIAL") and _base_computable(f) > Decimal("0.00")
            ]
            factures_computables_totes = [
                f for f in factures_totes if f.estat_cobrament in ("COBRADA", "PARCIAL") and _base_computable(f) > Decimal("0.00")
            ]
        else:
            factures_computables = list(factures)
            factures_computables_totes = list(factures_totes)

        facturacio_neta = q2(
            sum((_base_computable(f) for f in factures_computables), Decimal("0.00"))
        )
        iva_repercutit = q2(
            sum((Decimal(str(f.quota_iva or 0)) for f in factures), Decimal("0.00"))
        )

        fact_ids = [f.id for f in factures]
        if fact_ids:
            stmt_lin = select(FacturaLinia).where(
                FacturaLinia.empresa_id == empresa_id,
                FacturaLinia.factura_id.in_(fact_ids),
            )
            linies = (await db.execute(stmt_lin)).scalars().all()
        else:
            linies = []
        cost_materials_linies = q2(
            sum(
                (
                    (Decimal(str(lin.quantitat or 0)) + Decimal(str(lin.quantitat_merma or 0)))
                    * Decimal(str(lin.cost_unitari_historic or 0))
                    for lin in linies
                ),
                Decimal("0.00"),
            )
        )

        # Mermes de magatzem consolidades a DespesaComptable (comptes 600/659, sense duplicar tiquets)
        stmt_mermes_dc = select(DespesaComptable).where(
            DespesaComptable.empresa_id == empresa_id,
            DespesaComptable.origen == "MAGATZEM_MERMA",
            DespesaComptable.estat == "CONSOLIDADA",
        )
        if data_inici_periode is not None:
            dt_inici_merma = datetime.combine(
                data_inici_periode, datetime.min.time(), tzinfo=timezone.utc
            )
            stmt_mermes_dc = stmt_mermes_dc.where(DespesaComptable.created_at >= dt_inici_merma)
        despeses_merma = (await db.execute(stmt_mermes_dc)).scalars().all()
        cost_mermes_dc = q2(
            sum(
                (Decimal(str(dm.base_imposable or dm.import_total or 0)) for dm in despeses_merma),
                Decimal("0.00"),
            )
        )
        cost_materials_i_merma = q2(cost_materials_linies + cost_mermes_dc)

        stmt_tiq = select(TiquetDespesa).where(TiquetDespesa.empresa_id == empresa_id)
        if data_inici_periode is not None:
            stmt_tiq = stmt_tiq.where(TiquetDespesa.data_tiquet >= data_inici_periode)
        tiquets = (await db.execute(stmt_tiq)).scalars().all()
        cost_tiquets = q2(sum((Decimal(str(t.import_total or 0)) for t in tiquets), Decimal("0.00")))
        iva_tiquets_deduible = q2(
            sum(
                (Decimal(str(t.quota_iva or 0)) for t in tiquets if t.estat_fiscal == "DEDUIBLE"),
                Decimal("0.00"),
            )
        )

        usuaris = (
            (
                await db.execute(
                    select(Usuari).where(Usuari.empresa_id == empresa_id, Usuari.estat == "ACTIU")
                )
            )
            .scalars()
            .all()
        )
        factor_mesos = Decimal(str(mesos_periode))
        cost_nomines_total = q2(
            sum(
                (
                    Decimal(str(u.salari_mensual_brut or 0)) + Decimal(str(u.cost_ss_mensual or 0))
                    for u in usuaris
                ),
                Decimal("0.00"),
            )
            * factor_mesos
        )
        cost_hora_by_uid = {
            u.id: Decimal(
                str(
                    u.cost_hora_eur
                    if u.cost_hora_eur is not None
                    else (u.cost_hora_referencia or 0)
                )
            )
            for u in usuaris
        }
        ops_costs = [
            cost_hora_by_uid[u.id]
            for u in usuaris
            if u.rol in ("OPERARI", "CAP_DE_COLLA", "CAPATAZ") and cost_hora_by_uid[u.id] > Decimal("0.00")
        ]
        avg_cost_hora_op = (
            sum(ops_costs, Decimal("0.00")) / Decimal(len(ops_costs))
            if ops_costs
            else Decimal("0.00")
        )

        if cost_nomines_total > Decimal("0.00"):
            cost_ma_obra_directa = q2(cost_nomines_total * Decimal("0.70"))
            cost_nomines_estructura = q2(cost_nomines_total * Decimal("0.30"))
        else:
            # Fallback honest amb hores reals imputades a OTs del període × cost_hora_eur
            stmt_trams = select(OrdreTreballTramTemps).where(
                OrdreTreballTramTemps.empresa_id == empresa_id
            )
            if data_inici_periode is not None:
                dt_inici_trams = datetime.combine(
                    data_inici_periode, datetime.min.time(), tzinfo=timezone.utc
                )
                stmt_trams = stmt_trams.where(OrdreTreballTramTemps.hora_inici >= dt_inici_trams)
            trams_per = (await db.execute(stmt_trams)).scalars().all()
            cost_hores_reals = Decimal("0.00")
            ot_ids_amb_trams_per: set[uuid.UUID] = set()
            for t in trams_per:
                ot_ids_amb_trams_per.add(t.ordre_treball_id)
                segons = int(t.durada_segons or 0)
                if segons <= 0 and t.hora_inici and t.hora_fi:
                    segons = max(0, int((t.hora_fi - t.hora_inici).total_seconds()))
                if segons > 0:
                    ch = cost_hora_by_uid.get(t.operari_id, avg_cost_hora_op) if t.operari_id else avg_cost_hora_op
                    cost_hores_reals += (Decimal(segons) / Decimal("3600")) * ch

            stmt_ots_h = select(OrdreTreball).where(
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.hores_imputades_facturables > 0,
            )
            if data_inici_periode is not None:
                stmt_ots_h = stmt_ots_h.where(
                    func.coalesce(OrdreTreball.data_finalitzacio_camp, OrdreTreball.data_planificacio)
                    >= data_inici_periode
                )
            ots_h = (await db.execute(stmt_ots_h)).scalars().all()
            for ot in ots_h:
                if ot.id in ot_ids_amb_trams_per:
                    continue
                if ot.cost_ma_obra_real and float(ot.cost_ma_obra_real) > 0:
                    cost_hores_reals += Decimal(str(ot.cost_ma_obra_real))
                else:
                    ch = (
                        cost_hora_by_uid.get(ot.cap_de_colla_id, avg_cost_hora_op)
                        if ot.cap_de_colla_id
                        else avg_cost_hora_op
                    )
                    cost_hores_reals += Decimal(str(ot.hores_imputades_facturables or 0)) * ch

            cost_ma_obra_directa = q2(cost_hores_reals)
            cost_nomines_estructura = Decimal("0.00")

        # Cost de flota real (quotes mensuals + taller real a MantenimentVehicle + km reals)
        vehicles = (
            (await db.execute(select(Vehicle).where(Vehicle.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
        stmt_mant = select(MantenimentVehicle).where(MantenimentVehicle.empresa_id == empresa_id)
        if data_inici_periode is not None:
            dt_inici_mant = datetime.combine(
                data_inici_periode, datetime.min.time(), tzinfo=timezone.utc
            )
            stmt_mant = stmt_mant.where(MantenimentVehicle.data_manteniment >= dt_inici_mant)
        manteniments_veh = (await db.execute(stmt_mant)).scalars().all()
        cost_taller_manteniments = q2(
            sum((Decimal(str(m.cost_euros or 0)) for m in manteniments_veh), Decimal("0.00"))
        )
        cost_quotes_flota = q2(
            sum((Decimal(str(v.quota_mensual_eur or 0)) for v in vehicles), Decimal("0.00"))
            * factor_mesos
        )
        cost_taller_legacy = q2(
            sum((Decimal(str(v.despeses_taller_mes or 0)) for v in vehicles), Decimal("0.00"))
            * factor_mesos
        )
        cost_taller_flota = (
            cost_taller_manteniments
            if cost_taller_manteniments > Decimal("0.00")
            else cost_taller_legacy
        )
        cost_flota_total = q2(cost_quotes_flota + cost_taller_flota)

        total_km_mes = sum(
            (
                max(0, int(v.odometre_acumulat or 0) - int(v.km_inicials_mes or 0))
                for v in vehicles
                if int(v.km_inicials_mes or 0) > 0
            ),
            0,
        )
        if total_km_mes == 0:
            stmt_km_ots = select(func.coalesce(func.sum(OrdreTreball.km_imputats), 0)).where(
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.km_imputats > 0,
            )
            if data_inici_periode is not None:
                stmt_km_ots = stmt_km_ots.where(
                    func.coalesce(OrdreTreball.data_finalitzacio_camp, OrdreTreball.data_planificacio)
                    >= data_inici_periode
                )
            total_km_mes = int((await db.execute(stmt_km_ots)).scalar_one() or 0)

        cost_flota_eur_km = (
            q2(cost_flota_total / Decimal(total_km_mes)) if total_km_mes > 0 else Decimal("0.00")
        )

        # Invariant P&L sense doble comptabilització: flota i tiquets formen part del cost operatiu directe
        cost_tiquets_i_flota = q2(cost_tiquets + cost_flota_total)
        cost_directe_obra = q2(cost_materials_i_merma + cost_ma_obra_directa + cost_tiquets_i_flota)
        marge_brut_eur = q2(facturacio_neta - cost_directe_obra)
        marge_brut_pct = (
            q2((marge_brut_eur / facturacio_neta) * Decimal("100.00"))
            if facturacio_neta > Decimal("0.00")
            else Decimal("0.00")
        )

        fixes = (
            (
                await db.execute(
                    select(DespesaFixaRecurrent).where(
                        DespesaFixaRecurrent.empresa_id == empresa_id,
                        DespesaFixaRecurrent.actiu.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        fixes_recurrents_eur = q2(
            sum(
                (
                    cls._normalitzar_mensual_despesa_fixa(
                        Decimal(str(df.import_base or 0)), df.periodicitat
                    )
                    for df in fixes
                ),
                Decimal("0.00"),
            )
            * factor_mesos
        )
        iva_fixes_deduible = q2(
            sum(
                (
                    cls._normalitzar_mensual_despesa_fixa(
                        Decimal(str(df.quota_iva or 0)), df.periodicitat
                    )
                    for df in fixes
                ),
                Decimal("0.00"),
            )
            * factor_mesos
        )
        # Només estructura fixa + 30% nòmines estructura (sense duplicar cost_flota_total)
        despeses_fixes_eur = q2(fixes_recurrents_eur + cost_nomines_estructura)

        ebitda_eur = q2(marge_brut_eur - despeses_fixes_eur)
        ebitda_pct = (
            q2((ebitda_eur / facturacio_neta) * Decimal("100.00"))
            if facturacio_neta > Decimal("0.00")
            else Decimal("0.00")
        )

        ratio_mb = marge_brut_pct / Decimal("100.00")
        break_even_eur = (
            q2(despeses_fixes_eur / ratio_mb) if ratio_mb > Decimal("0.00") else Decimal("0.00")
        )
        break_even_assolit = facturacio_neta >= break_even_eur and break_even_eur > Decimal("0.00")

        # Erosió de marge i capital immobilitzat >90d (sobre estoc físic real, mai estoc_optim)
        articles = (
            (
                await db.execute(
                    select(Article).where(Article.empresa_id == empresa_id, Article.actiu.is_(True))
                )
            )
            .scalars()
            .all()
        )
        estoc_rows = (
            await db.execute(
                select(
                    EstocMagatzem.article_id,
                    func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
                )
                .where(EstocMagatzem.empresa_id == empresa_id)
                .group_by(EstocMagatzem.article_id)
            )
        ).all()
        estoc_fisic_by_article: Dict[uuid.UUID, Decimal] = {
            aid: Decimal(str(qty or 0)) for aid, qty in estoc_rows
        }

        alertes_erosio: List[AlertaErosioMargeDTO] = []
        capital_immobilitzat = Decimal("0.00")

        for a in articles:
            p_venda = Decimal(str(a.preu_venda or 0))
            p_ultim = Decimal(str(a.preu_cost_ultim or 0))
            p_mitja = Decimal(str(a.pmp_actual or a.preu_cost_mitja or a.preu_cost or 0))
            llindar = Decimal(str(a.llindar_marge_minim_pct or 25))
            if p_venda > Decimal("0.00"):
                marge_ultim_pct = q2(((p_venda - p_ultim) / p_venda) * Decimal("100.00"))
                if p_ultim > p_mitja and marge_ultim_pct < llindar:
                    alertes_erosio.append(
                        AlertaErosioMargeDTO(
                            article_id=a.id,
                            referencia=a.referencia_inventari,
                            nom=a.nom,
                            preu_cost_mitja=q2(p_mitja),
                            preu_cost_ultim=q2(p_ultim),
                            preu_venda_tarifa=q2(p_venda),
                            marge_actual_pct=marge_ultim_pct,
                            llindar_minim_pct=q2(llindar),
                        )
                    )
            if not a.es_diposit_proveidor:
                estoc_fisic = (
                    estoc_fisic_by_article[a.id]
                    if a.id in estoc_fisic_by_article
                    else Decimal(str(a.estoc_total_actual or 0))
                )
                if estoc_fisic > Decimal("0.00"):
                    data_ref = a.darrer_moviment_sortida or (
                        a.created_at.date() if isinstance(a.created_at, datetime) else a.created_at
                    )
                    dies_sense_mov = (avui - data_ref).days if data_ref else 999
                    if dies_sense_mov > 90:
                        capital_immobilitzat += q2(estoc_fisic * p_mitja)

        # Factures proveïdors i Guardacaixa IVA
        stmt_fp = select(FacturaProveidor).where(FacturaProveidor.empresa_id == empresa_id)
        if data_inici_periode is not None:
            stmt_fp = stmt_fp.where(FacturaProveidor.data_factura >= data_inici_periode)
        factures_prov = (await db.execute(stmt_fp)).scalars().all()
        iva_prov_deduible = q2(
            sum(
                (
                    Decimal(str(fp.quota_iva or 0))
                    for fp in factures_prov
                    if not fp.es_recc_passiu_4729 or fp.pagada
                ),
                Decimal("0.00"),
            )
        )
        guardacaixa_iva = max(
            Decimal("0.00"),
            q2(iva_repercutit - (iva_prov_deduible + iva_tiquets_deduible + iva_fixes_deduible)),
        )

        aging = {
            "AL_DIA": Decimal("0.00"),
            "1_30_DIES": Decimal("0.00"),
            "31_60_DIES": Decimal("0.00"),
            "CRITIC_MES_90": Decimal("0.00"),
        }
        total_cobrat_mes = sum((Decimal(str(f.import_cobrat or 0)) for f in factures), Decimal("0.00"))
        total_pagat_mes = (
            sum((Decimal(str(fp.import_pagat or 0)) for fp in factures_prov), Decimal("0.00"))
            + cost_tiquets
        )
        cash_flow_real = q2(total_cobrat_mes - total_pagat_mes)

        dies_dso_list: List[int] = []
        cobraments_30d = Decimal("0.00")
        cobraments_60d = Decimal("0.00")
        cobraments_90d = Decimal("0.00")

        for f in factures_totes:
            data_em = f.data_emissio.date() if isinstance(f.data_emissio, datetime) else f.data_emissio
            data_venc = f.data_venciment or data_em
            if f.estat_cobrament == "COBRADA" and f.data_cobrament_real:
                dies_dso_list.append(max(0, (f.data_cobrament_real - data_em).days))
            pendent = max(
                Decimal("0.00"),
                Decimal(str(f.liquid_exigible or 0)) - Decimal(str(f.import_cobrat or 0)),
            )
            if pendent > Decimal("0.00"):
                retard = (avui - data_venc).days
                if retard <= 0:
                    aging["AL_DIA"] += pendent
                elif retard <= 30:
                    aging["1_30_DIES"] += pendent
                elif retard <= 60:
                    aging["31_60_DIES"] += pendent
                else:
                    aging["CRITIC_MES_90"] += pendent

                dies_a_venciment = (data_venc - avui).days
                if dies_a_venciment <= 30:
                    cobraments_30d += pendent
                elif dies_a_venciment <= 60:
                    cobraments_60d += pendent
                else:
                    cobraments_90d += pendent

        dso_mitja = (
            q2(Decimal(sum(dies_dso_list)) / Decimal(len(dies_dso_list)))
            if dies_dso_list
            else Decimal("0.00")
        )

        venciments_prov_mes = q2(
            sum(
                (
                    Decimal(str(fp.total or 0)) - Decimal(str(fp.import_pagat or 0))
                    for fp in factures_prov
                    if not fp.pagada
                ),
                Decimal("0.00"),
            )
        )
        burn_rate = q2(
            despeses_fixes_eur
            + cost_ma_obra_directa
            + venciments_prov_mes
            + cost_tiquets
            + cost_flota_total
        )

        mrr_list = await cls.auditar_contractes_mrr(db, empresa_id)
        mrr_total = q2(sum((c.quota_mensual_mrr for c in mrr_list), Decimal("0.00")))
        cobertura_mrr = (
            q2((mrr_total / despeses_fixes_eur) * Decimal("100.00"))
            if despeses_fixes_eur > Decimal("0.00")
            else Decimal("0.00")
        )

        fact_per_client: Dict[uuid.UUID, Decimal] = {}
        for f in factures_computables:
            fact_per_client[f.client_id] = fact_per_client.get(f.client_id, Decimal("0.00")) + _base_computable(f)
        alerta_pareto = (
            any((imp / facturacio_neta) > Decimal("0.25") for imp in fact_per_client.values())
            if facturacio_neta > Decimal("0.00") and len(fact_per_client) > 1
            else False
        )

        total_ret_4308 = q2(
            sum((Decimal(str(f.import_retencio_garantia_4308 or 0)) for f in factures), Decimal("0.00"))
        )

        # Sèrie de 12 mesos exactes de calendari amb ingressos i despeses reals per mes (Zero Mock Data)
        def _shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
            total = year * 12 + (month - 1) + delta
            return total // 12, (total % 12) + 1

        mesos_12_keys: List[str] = []
        y0, m0 = _shift_month(avui.year, avui.month, -11)
        data_inici_12m = date(y0, m0, 1)
        dt_inici_12m = datetime.combine(data_inici_12m, datetime.min.time(), tzinfo=timezone.utc)
        for offset in range(-11, 1):
            yy, mm = _shift_month(avui.year, avui.month, offset)
            mesos_12_keys.append(f"{yy:04d}-{mm:02d}")
        mes_actual_key = mesos_12_keys[-1]

        fact_mes_map: Dict[uuid.UUID, str] = {}
        for f in factures_totes:
            dt_em = f.data_emissio.date() if isinstance(f.data_emissio, datetime) else f.data_emissio
            fact_mes_map[f.id] = dt_em.strftime("%Y-%m")

        linies_12m: Sequence[FacturaLinia] = []
        fact_ids_12m = [fid for fid, mk in fact_mes_map.items() if mk in mesos_12_keys]
        if fact_ids_12m:
            linies_12m = (
                await db.execute(
                    select(FacturaLinia).where(
                        FacturaLinia.empresa_id == empresa_id,
                        FacturaLinia.factura_id.in_(fact_ids_12m),
                    )
                )
            ).scalars().all()

        tiquets_12m = (
            await db.execute(
                select(TiquetDespesa).where(
                    TiquetDespesa.empresa_id == empresa_id,
                    TiquetDespesa.data_tiquet >= data_inici_12m,
                )
            )
        ).scalars().all()
        mermes_12m = (
            await db.execute(
                select(DespesaComptable).where(
                    DespesaComptable.empresa_id == empresa_id,
                    DespesaComptable.origen == "MAGATZEM_MERMA",
                    DespesaComptable.estat == "CONSOLIDADA",
                    DespesaComptable.created_at >= dt_inici_12m,
                )
            )
        ).scalars().all()
        mant_12m = (
            await db.execute(
                select(MantenimentVehicle).where(
                    MantenimentVehicle.empresa_id == empresa_id,
                    MantenimentVehicle.data_manteniment >= dt_inici_12m,
                )
            )
        ).scalars().all()
        trams_12m = (
            await db.execute(
                select(OrdreTreballTramTemps).where(
                    OrdreTreballTramTemps.empresa_id == empresa_id,
                    OrdreTreballTramTemps.hora_inici >= dt_inici_12m,
                )
            )
        ).scalars().all()

        desp_var_by_mes: Dict[str, Decimal] = {k: Decimal("0.00") for k in mesos_12_keys}
        for lin in linies_12m:
            mk = fact_mes_map.get(lin.factura_id)
            if mk in desp_var_by_mes:
                desp_var_by_mes[mk] += (
                    Decimal(str(lin.quantitat or 0)) + Decimal(str(lin.quantitat_merma or 0))
                ) * Decimal(str(lin.cost_unitari_historic or 0))
        for tiq in tiquets_12m:
            mk = tiq.data_tiquet.strftime("%Y-%m")
            if mk in desp_var_by_mes:
                desp_var_by_mes[mk] += Decimal(str(tiq.import_total or 0))
        for dm in mermes_12m:
            mk = dm.created_at.strftime("%Y-%m")
            if mk in desp_var_by_mes:
                desp_var_by_mes[mk] += Decimal(str(dm.base_imposable or dm.import_total or 0))
        for m_veh in mant_12m:
            mk = m_veh.data_manteniment.strftime("%Y-%m")
            if mk in desp_var_by_mes:
                desp_var_by_mes[mk] += Decimal(str(m_veh.cost_euros or 0))

        nomina_mensual_unit = q2(
            sum(
                (
                    Decimal(str(u.salari_mensual_brut or 0)) + Decimal(str(u.cost_ss_mensual or 0))
                    for u in usuaris
                ),
                Decimal("0.00"),
            )
        )
        if nomina_mensual_unit == Decimal("0.00"):
            for tr in trams_12m:
                mk = tr.hora_inici.strftime("%Y-%m")
                if mk in desp_var_by_mes:
                    segons = int(tr.durada_segons or 0)
                    if segons <= 0 and tr.hora_inici and tr.hora_fi:
                        segons = max(0, int((tr.hora_fi - tr.hora_inici).total_seconds()))
                    if segons > 0:
                        ch = cost_hora_by_uid.get(tr.operari_id, avg_cost_hora_op) if tr.operari_id else avg_cost_hora_op
                        desp_var_by_mes[mk] += (Decimal(segons) / Decimal("3600")) * ch

        evolucio_12m: List[Dict[str, object]] = []
        for label in mesos_12_keys:
            ing_mes = q2(
                sum(
                    (
                        _base_computable(f)
                        for f in factures_computables_totes
                        if fact_mes_map.get(f.id) == label
                    ),
                    Decimal("0.00"),
                )
            )
            # Despeses fixes i quotes mensuals actives a partir del mes d'alta (o del mes actual)
            fixes_mes = Decimal("0.00")
            for df in fixes:
                df_mk = (df.created_at or datetime.now(timezone.utc)).strftime("%Y-%m")
                if label >= df_mk or label == mes_actual_key:
                    fixes_mes += cls._normalitzar_mensual_despesa_fixa(
                        Decimal(str(df.import_base or 0)), df.periodicitat
                    )
            flota_quota_mes = Decimal("0.00")
            for v in vehicles:
                v_mk = (v.created_at or datetime.now(timezone.utc)).strftime("%Y-%m")
                if label >= v_mk or label == mes_actual_key:
                    flota_quota_mes += Decimal(str(v.quota_mensual_eur or 0))
            nomina_mes = Decimal("0.00")
            if nomina_mensual_unit > Decimal("0.00"):
                for u in usuaris:
                    u_sal = Decimal(str(u.salari_mensual_brut or 0)) + Decimal(str(u.cost_ss_mensual or 0))
                    if u_sal > Decimal("0.00"):
                        u_mk = (u.created_at or datetime.now(timezone.utc)).strftime("%Y-%m")
                        if label >= u_mk or label == mes_actual_key:
                            nomina_mes += u_sal

            desp_mes = q2(desp_var_by_mes[label] + fixes_mes + flota_quota_mes + nomina_mes)
            ebitda_mes_pct = (
                q2(((ing_mes - desp_mes) / ing_mes) * Decimal("100.00"))
                if ing_mes > Decimal("0.00")
                else Decimal("0.00")
            )
            evolucio_12m.append(
                {
                    "mes": label,
                    "ingressos": float(ing_mes),
                    "despeses": float(desp_mes),
                    "ebitda_pct": float(ebitda_mes_pct),
                }
            )

        # Marges per vertical reals (ingressos facturats/pressupostats - tots els costos analítics de l'OT)
        stmt_ots_v = select(OrdreTreball).where(OrdreTreball.empresa_id == empresa_id)
        if data_inici_periode is not None:
            stmt_ots_v = stmt_ots_v.where(
                func.coalesce(OrdreTreball.data_finalitzacio_camp, OrdreTreball.data_planificacio)
                >= data_inici_periode
            )
        ots_all = (await db.execute(stmt_ots_v)).scalars().all()
        verticals: Dict[str, Decimal] = {}
        for ot in ots_all:
            v_name = ot.vertical or "INSTAL_LACIONS"
            analitic = await calcular_cost_i_marge_analitic_ot(
                db=db,
                empresa_id=empresa_id,
                ordre_treball_id=ot.id,
            )
            marge_ot = Decimal(str(analitic["marge_brut_eur"]))
            verticals[v_name] = verticals.get(v_name, Decimal("0.00")) + marge_ot

        marges_vertical_list = [
            {"vertical": k, "marge_eur": float(q2(v))} for k, v in verticals.items()
        ]

        return DashboardEconomicResponseDTO(
            facturacio_neta=facturacio_neta,
            cost_directe_obra=cost_directe_obra,
            marge_brut_eur=marge_brut_eur,
            marge_brut_pct=marge_brut_pct,
            despeses_fixes_estructura=despeses_fixes_eur,
            ebitda_operatiu_eur=ebitda_eur,
            ebitda_operatiu_pct=ebitda_pct,
            break_even_facturacio_necessaria=break_even_eur,
            break_even_assolit=break_even_assolit,
            alertes_erosio_marge=alertes_erosio,
            capital_immobilitzat_90d_eur=capital_immobilitzat,
            cash_flow_operatiu_real=cash_flow_real,
            burn_rate_mes_seguent=burn_rate,
            guardacaixa_fiscal_iva_303=guardacaixa_iva,
            projeccio_tresoreria_30d=q2(cash_flow_real + cobraments_30d - burn_rate),
            projeccio_tresoreria_60d=q2(
                cash_flow_real + cobraments_30d + cobraments_60d - (burn_rate * 2)
            ),
            projeccio_tresoreria_90d=q2(
                cash_flow_real + cobraments_30d + cobraments_60d + cobraments_90d - (burn_rate * 3)
            ),
            dso_dies_mitjana_cobrament=dso_mitja,
            aging_impagats=aging,
            total_retencions_garantia_4308_excloses_aging=total_ret_4308,
            cost_flota_eur_km_mitja=cost_flota_eur_km,
            mrr_mensual_actiu=mrr_total,
            cobertura_estructura_mrr_pct=cobertura_mrr,
            alerta_concentracio_pareto_25pct=alerta_pareto,
            waterfall_mensual={
                "facturacio_bruta": facturacio_neta,
                "cost_materials_i_merma": -cost_materials_i_merma,
                "cost_ma_obra_directa": -cost_ma_obra_directa,
                "cost_tiquets_i_flota": -cost_tiquets_i_flota,
                "despeses_fixes": -despeses_fixes_eur,
                "benefici_net_ebitda": ebitda_eur,
            },
            evolucio_12m=evolucio_12m,
            marges_per_vertical=marges_vertical_list,
        )
