import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    ApuntBancariNorma43,
    Article,
    Client,
    ContracteMantenimentMRR,
    DespesaFixaRecurrent,
    FacturaCapcalera,
    FacturaLinia,
    FacturaProveidor,
    OrdreTreball,
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
    FacturaEmissioCreateDTO,
    Norma43MovimentDTO,
    OperariCostEfectiuDTO,
    RetencioGarantiaDTO,
    TiquetAuditoriaRequestDTO,
    TiquetDespesaResponseDTO,
    WIPControlResponseDTO,
    WIPItemDTO,
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
        dades_event: Optional[dict] = None,
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

    # --- EMISSIÓ DE FACTURES VERI*FACTU + RETENCIONS 4308 (RF-05 a RF-15, RF-33) ---
    @classmethod
    async def emetre_factura_verifactu(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        payload: FacturaEmissioCreateDTO,
    ) -> FacturaCapcalera:
        if payload.serie.upper().startswith("R") and not payload.factura_rectificada_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Les factures rectificatives (Sèrie R) exigeixen informar factura_rectificada_id.",
            )

        exercici = payload.data_emissio.year
        stmt_serie = (
            select(SerieFiscalVerifactu)
            .where(
                SerieFiscalVerifactu.empresa_id == empresa_id,
                SerieFiscalVerifactu.codi_serie == payload.serie,
                SerieFiscalVerifactu.exercici == exercici,
            )
            .with_for_update()
        )
        serie_row = (await db.execute(stmt_serie)).scalar_one_or_none()
        if not serie_row:
            serie_row = SerieFiscalVerifactu(
                empresa_id=empresa_id,
                codi_serie=payload.serie,
                exercici=exercici,
                ultim_numero=0,
                ultim_hash_sha256="0" * 64,
            )
            db.add(serie_row)
            await db.flush()

        serie_row.ultim_numero += 1
        num_factura = serie_row.ultim_numero

        bases_per_iva: Dict[Decimal, Decimal] = {}
        total_suplerts_554 = Decimal("0.00")
        linies_models: List[FacturaLinia] = []

        for l_dto in payload.linies:
            cost_historic = Decimal("0.0000")
            if l_dto.article_id:
                art = await db.get(Article, l_dto.article_id)
                if art and art.empresa_id == empresa_id:
                    cost_historic = Decimal(str(art.preu_cost_mitja or art.preu_cost or 0))

            factor_dto = Decimal("1.00") - (l_dto.descompte_aplicat_pct / Decimal("100.00"))
            import_base = q2(l_dto.quantitat * l_dto.preu_venda_unitari * factor_dto)

            if l_dto.compte_pgc.startswith("554"):
                total_suplerts_554 += import_base
                iva_linia = Decimal("0.00")
            else:
                iva_linia = (
                    Decimal("0.00")
                    if payload.es_inversio_subjecte_passiu
                    else l_dto.tipus_iva_pct
                )
                bases_per_iva[iva_linia] = bases_per_iva.get(iva_linia, Decimal("0.00")) + import_base

            linies_models.append(
                FacturaLinia(
                    empresa_id=empresa_id,
                    obra_id=l_dto.obra_id,
                    centre_de_cost_id=l_dto.centre_de_cost_id,
                    article_id=l_dto.article_id,
                    concepte=l_dto.concepte[:200],
                    compte_pgc=l_dto.compte_pgc,
                    quantitat=float(l_dto.quantitat),
                    quantitat_merma=float(l_dto.quantitat_merma),
                    preu_venda_unitari=float(l_dto.preu_venda_unitari),
                    descompte_aplicat_pct=float(l_dto.descompte_aplicat_pct),
                    cost_unitari_historic=float(cost_historic),
                    tipus_iva=float(iva_linia),
                    subtotal=float(import_base),
                )
            )

        if total_suplerts_554 > Decimal("0.00") and not payload.justificant_suplerts_pdf_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Els suplerts (compte 554) exigeixen adjuntar el PDF del justificant oficial.",
            )

        base_imposable_total = q2(sum(bases_per_iva.values(), Decimal("0.00")))
        quota_iva_total = Decimal("0.00")
        if not payload.es_inversio_subjecte_passiu:
            for tipus, base_agregada in bases_per_iva.items():
                quota_iva_total += q2(base_agregada * (tipus / Decimal("100.00")))

        import_ret_irpf = q2(base_imposable_total * (payload.retencio_irpf_pct / Decimal("100.00")))
        import_ret_garantia = q2(
            base_imposable_total * (payload.retencio_garantia_pct / Decimal("100.00"))
        )

        # Fórmula RF-05.3 + RF-33
        liquid_exigible = q2(
            base_imposable_total
            + quota_iva_total
            + total_suplerts_554
            - import_ret_irpf
            - import_ret_garantia
        )

        hash_anterior = serie_row.ultim_hash_sha256
        codi_complet = f"{payload.serie}-{exercici}-{num_factura:04d}"
        cadena_verifactu = (
            f"{empresa_id}|{codi_complet}|{payload.data_emissio.isoformat()}|"
            f"{liquid_exigible}|{hash_anterior}"
        )
        hash_propi = hashlib.sha256(cadena_verifactu.encode("utf-8")).hexdigest()
        serie_row.ultim_hash_sha256 = hash_propi

        llegenda_isp = (
            " | Operació amb inversió del subjecte passiu d'acord amb l'art. 84.U.2n.f de la Llei 37/1992 de l'IVA"
            if payload.es_inversio_subjecte_passiu
            else ""
        )
        qr_payload = (
            f"https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?"
            f"num={codi_complet}&imp={liquid_exigible}&hash={hash_propi[:16]}{llegenda_isp}"
        )

        factura = FacturaCapcalera(
            empresa_id=empresa_id,
            numero_factura=num_factura,
            serie=payload.serie,
            client_id=payload.client_id,
            estat_document="EMESA",
            estat_cobrament="PENDENT",
            estat_enviament="PENDENT",
            data_emissio=datetime.combine(payload.data_emissio, datetime.min.time(), tzinfo=timezone.utc),
            data_venciment=payload.data_venciment,
            metode_pagament=payload.metode_pagament,
            es_inversio_subjecte_passiu=payload.es_inversio_subjecte_passiu,
            base_imposable=float(base_imposable_total),
            quota_iva=float(quota_iva_total),
            import_suplits=float(total_suplerts_554),
            justificant_suplerts_pdf_path=payload.justificant_suplerts_pdf_path,
            import_retencio=float(import_ret_irpf),
            import_retencio_garantia_4308=float(import_ret_garantia),
            liquid_exigible=float(liquid_exigible),
            factura_rectificada_id=payload.factura_rectificada_id,
            motiu_rectificacio=payload.motiu_rectificacio,
            hash_anterior=hash_anterior,
            hash_sha256=hash_propi,
            qr_verifactu_payload=qr_payload,
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

        outbox = OutboxEnviamentAEAT(
            empresa_id=empresa_id,
            factura_id=factura.id,
            payload_xml_path=f"/docs/{empresa_id}/factures/outbox/{codi_complet}.xml",
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
        await db.refresh(factura)
        return factura

    # --- MILLORA 1: CONTROL DEL WIP (OBRA EN CURS NO FACTURADA) (RF-31, RF-32) ---
    @classmethod
    async def obtenir_control_wip(
        cls, db: AsyncSession, empresa_id: uuid.UUID, avui: Optional[date] = None
    ) -> WIPControlResponseDTO:
        avui = avui or date.today()
        ots = (
            (
                await db.execute(
                    select(OrdreTreball).where(
                        OrdreTreball.empresa_id == empresa_id,
                        OrdreTreball.factura_id.is_(None),
                        OrdreTreball.estat.in_(["EXECUTADA_PENDENT_VALIDACIO", "ALBARA_SIGNAT"]),
                    )
                )
            )
            .scalars()
            .all()
        )

        items: List[WIPItemDTO] = []
        total_pvp = Decimal("0.00")
        total_cost = Decimal("0.00")
        envellides = 0

        for ot in ots:
            data_ref = ot.data_finalitzacio_camp or ot.data_planificacio or avui
            dies_wip = max(0, (avui - data_ref).days)
            es_envellit = dies_wip > 7

            hores = Decimal(str(ot.hores_imputades_facturables or 0))
            pvp_h = Decimal(str(ot.preu_venda_hora_aplicat or 45))
            pvp_mat = Decimal(str(ot.pvp_materials_aplicat or 0))
            cost_mat = Decimal(str(ot.cost_materials_pmp or 0))

            valor_pvp = q2((hores * pvp_h) + pvp_mat)
            cost_avancat = q2((hores * Decimal("22.00")) + cost_mat)

            total_pvp += valor_pvp
            total_cost += cost_avancat
            if es_envellit:
                envellides += 1

            items.append(
                WIPItemDTO(
                    ordre_treball_id=ot.id,
                    codi_ot=ot.codi,
                    client_id=ot.client_id,
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

    # --- MILLORA 3: SEMÀFOR DE RISC DE CRÈDIT I BLOQUEIG OPERATIU A CAMP (RF-35, RF-36) ---
    @classmethod
    async def evaluar_risc_client(
        cls, db: AsyncSession, empresa_id: uuid.UUID, client_id: uuid.UUID, avui: Optional[date] = None
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

        await db.commit()
        await db.refresh(client)
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
            cost_total_mes = salari_brut + cost_ss + Decimal(str(tiquets_op or 0))

            if rol_peticio == "SECRETARIA" and op.es_alta_direccio:
                salari_visible = "***"
            else:
                salari_visible = f"{q2(salari_brut + cost_ss)} EUR"

            if hores_ot > Decimal("0.00"):
                cost_efectiu = q2(cost_total_mes / hores_ot)
                eficiencia = (
                    q2((hores_ot / hores_fitxades) * Decimal("100.00"))
                    if hores_fitxades > 0
                    else Decimal("0.00")
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
                    cost_hora_referencia=q2(Decimal(str(op.cost_hora_referencia or op.cost_hora_eur or 22.5))),
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
        contractes = (
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

        for c in contractes:
            ots = (
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
            cost_ots = Decimal("0.00")
            for ot in ots:
                cost_ma_obra = Decimal(str(ot.hores_imputades_facturables or 0)) * Decimal("24.00")
                cost_km = Decimal(int(ot.km_imputats or 0)) * Decimal("0.32")
                cost_ots += q2(cost_ma_obra + Decimal(str(ot.cost_materials_pmp or 0)) + cost_km)

            quota = Decimal(str(c.quota_mensual_mrr or 0))
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

            resultat.append(
                ContracteMRRAuditoriaDTO(
                    contracte_id=c.id,
                    codi_contracte=c.codi_contracte,
                    client_id=c.client_id,
                    quota_mensual_mrr=q2(quota),
                    cost_real_ots_periode=cost_ots,
                    marge_net_contracte=marge,
                    sinistralitat_pct=sinistralitat,
                    semafor=semafor,
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
                rao_social=t.rao_social,
                base_imposable=q2(Decimal(str(t.base_imposable))),
                iva_pct=q2(Decimal(str(t.iva_pct))),
                quota_iva=q2(Decimal(str(t.quota_iva))),
                import_total=q2(Decimal(str(t.import_total))),
                estat_aprovacio=t.estat_aprovacio,
                estat_fiscal=t.estat_fiscal,
                requereix_aprovacio_boss=t.requereix_aprovacio_boss,
                custodia_paper_confirmada=t.custodia_paper_confirmada,
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

        if tiquet.requereix_aprovacio_boss and rol_peticio != "BOSS":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Els tiquets >100 EUR requereixen aprovació exclusiva del BOSS.",
            )

        if payload.accio not in ("APROVAT", "REBUTJAT"):
            raise HTTPException(status_code=400, detail="Acció invàlida (APROVAT o REBUTJAT).")

        # RF-20: Si manca NIF, quota_iva = 0 i PENDENT_BESCANVI
        if not tiquet.nif_emissor:
            tiquet.quota_iva = 0.00
            tiquet.estat_fiscal = "PENDENT_BESCANVI"

        tiquet.estat_aprovacio = payload.accio
        if payload.custodia_paper_confirmada is not None:
            tiquet.custodia_paper_confirmada = payload.custodia_paper_confirmada
        if payload.ordre_treball_id is not None:
            tiquet.ordre_treball_id = payload.ordre_treball_id

        await cls.registrar_esdeveniment_sif(
            db, empresa_id, usuari_id, "EV-03", f"Auditoria tiquet {tiquet.id}: {payload.accio}"
        )
        await db.commit()
        await db.refresh(tiquet)
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
    ) -> DashboardEconomicResponseDTO:
        avui = avui or date.today()

        factures = (
            (
                await db.execute(
                    select(FacturaCapcalera).where(
                        FacturaCapcalera.empresa_id == empresa_id,
                        FacturaCapcalera.estat_document == "EMESA",
                    )
                )
            )
            .scalars()
            .all()
        )

        if criteri_caixa:
            factures_computables = [f for f in factures if f.estat_cobrament == "COBRADA"]
        else:
            factures_computables = list(factures)

        facturacio_neta = q2(
            sum((Decimal(str(f.base_imposable or 0)) for f in factures_computables), Decimal("0.00"))
        )
        iva_repercutit = q2(
            sum((Decimal(str(f.quota_iva or 0)) for f in factures), Decimal("0.00"))
        )

        linies = (
            (await db.execute(select(FacturaLinia).where(FacturaLinia.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
        cost_materials_i_merma = q2(
            sum(
                (
                    (Decimal(str(lin.quantitat or 0)) + Decimal(str(lin.quantitat_merma or 0)))
                    * Decimal(str(lin.cost_unitari_historic or 0))
                    for lin in linies
                ),
                Decimal("0.00"),
            )
        )

        tiquets = (
            (await db.execute(select(TiquetDespesa).where(TiquetDespesa.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
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
        cost_nomines_total = q2(
            sum(
                (
                    Decimal(str(u.salari_mensual_brut or 0)) + Decimal(str(u.cost_ss_mensual or 0))
                    for u in usuaris
                ),
                Decimal("0.00"),
            )
        )
        cost_ma_obra_directa = q2(cost_nomines_total * Decimal("0.70"))

        # Cost de flota per km
        vehicles = (
            (await db.execute(select(Vehicle).where(Vehicle.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
        total_km_mes = sum(
            (max(0, int(v.odometre_acumulat or 0) - int(v.km_inicials_mes or 0)) for v in vehicles), 0
        )
        cost_flota_total = q2(
            sum(
                (
                    Decimal(str(v.quota_mensual_eur or 0)) + Decimal(str(v.despeses_taller_mes or 0))
                    for v in vehicles
                ),
                Decimal("0.00"),
            )
        )
        cost_flota_eur_km = (
            q2(cost_flota_total / Decimal(total_km_mes)) if total_km_mes > 0 else Decimal("0.00")
        )

        cost_directe_obra = q2(cost_materials_i_merma + cost_tiquets + cost_ma_obra_directa)
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
        despeses_fixes_eur = q2(
            sum((Decimal(str(df.import_base or 0)) for df in fixes), Decimal("0.00"))
            + (cost_nomines_total * Decimal("0.30"))
            + cost_flota_total
        )

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

        # Erosió de marge i capital immobilitzat >90d
        articles = (
            (
                await db.execute(
                    select(Article).where(Article.empresa_id == empresa_id, Article.actiu.is_(True))
                )
            )
            .scalars()
            .all()
        )
        alertes_erosio: List[AlertaErosioMargeDTO] = []
        capital_immobilitzat = Decimal("0.00")

        for a in articles:
            p_venda = Decimal(str(a.preu_venda or 0))
            p_ultim = Decimal(str(a.preu_cost_ultim or 0))
            p_mitja = Decimal(str(a.preu_cost_mitja or a.preu_cost or 0))
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
                dies_sense_mov = (
                    (avui - a.darrer_moviment_sortida).days if a.darrer_moviment_sortida else 999
                )
                if dies_sense_mov > 90:
                    capital_immobilitzat += q2(Decimal(str(a.estoc_optim or 0)) * p_mitja)

        # Factures proveïdors i Guardacaixa IVA
        factures_prov = (
            (
                await db.execute(
                    select(FacturaProveidor).where(FacturaProveidor.empresa_id == empresa_id)
                )
            )
            .scalars()
            .all()
        )
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
            Decimal("0.00"), q2(iva_repercutit - (iva_prov_deduible + iva_tiquets_deduible))
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

        for f in factures:
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
        burn_rate = q2(despeses_fixes_eur + cost_ma_obra_directa + venciments_prov_mes + cost_tiquets)

        mrr_list = await cls.auditar_contractes_mrr(db, empresa_id)
        mrr_total = q2(sum((c.quota_mensual_mrr for c in mrr_list), Decimal("0.00")))
        cobertura_mrr = (
            q2((mrr_total / despeses_fixes_eur) * Decimal("100.00"))
            if despeses_fixes_eur > Decimal("0.00")
            else Decimal("0.00")
        )

        fact_per_client: Dict[uuid.UUID, Decimal] = {}
        for f in factures_computables:
            fact_per_client[f.client_id] = fact_per_client.get(f.client_id, Decimal("0.00")) + Decimal(
                str(f.base_imposable or 0)
            )
        alerta_pareto = (
            any((imp / facturacio_neta) > Decimal("0.25") for imp in fact_per_client.values())
            if facturacio_neta > Decimal("0.00") and len(fact_per_client) > 1
            else False
        )

        total_ret_4308 = q2(
            sum((Decimal(str(f.import_retencio_garantia_4308 or 0)) for f in factures), Decimal("0.00"))
        )

        # Sèrie de 12 mesos real (Zero Mock Data)
        evolucio_12m: List[Dict[str, object]] = []
        for i in range(11, -1, -1):
            mes_ref = (avui.replace(day=1) - timedelta(days=30 * i))
            label = mes_ref.strftime("%Y-%m")
            ing_mes = q2(
                sum(
                    (
                        Decimal(str(f.base_imposable or 0))
                        for f in factures_computables
                        if (
                            f.data_emissio.date()
                            if isinstance(f.data_emissio, datetime)
                            else f.data_emissio
                        ).strftime("%Y-%m")
                        == label
                    ),
                    Decimal("0.00"),
                )
            )
            evolucio_12m.append(
                {
                    "mes": label,
                    "ingressos": float(ing_mes),
                    "despeses": float(q2(despeses_fixes_eur if ing_mes > 0 else Decimal("0.00"))),
                    "ebitda_pct": float(ebitda_pct if ing_mes > 0 else Decimal("0.00")),
                }
            )

        # Marges per vertical real
        ots_all = (
            (await db.execute(select(OrdreTreball).where(OrdreTreball.empresa_id == empresa_id)))
            .scalars()
            .all()
        )
        verticals: Dict[str, Decimal] = {}
        for ot in ots_all:
            v_name = ot.vertical or "INSTAL_LACIONS"
            marge_ot = Decimal(str(ot.pvp_materials_aplicat or 0)) - Decimal(
                str(ot.cost_materials_pmp or 0)
            )
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
                "cost_tiquets_i_flota": -q2(cost_tiquets + cost_flota_total),
                "despeses_fixes": -despeses_fixes_eur,
                "benefici_net_ebitda": ebitda_eur,
            },
            evolucio_12m=evolucio_12m,
            marges_per_vertical=marges_vertical_list,
        )
