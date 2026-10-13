"""Subagent de Planificació, Agenda i Equip de Treball (T063)."""

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
    Client,
    Finca,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
    Vehicle,
)
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_PLANIFICACIO_EQUIP


class SubagentPlanificacioEquip(BaseSubagent):
    id = "subagent_planificacio_equip"
    nom = "Subagent de Planificació i Equip"
    descripcio = "Especialista en l'agenda de feines, assignació d'ordres de treball, fitxatges de la jornada i incidències operatives."
    allowed_roles = ["SECRETARIA", "ENGINYER", "BOSS", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_PLANIFICACIO_EQUIP
    system_prompt = (
        "Ets l'assistent expert en Planificació, Agenda i Equip de Treball de SEVALOR. "
        "Gestiones la consulta d'ordres de treball (OTs), planificació diària i setmanal, "
        "estat de la jornada de l'equip i incidències de camp. "
        "Respon sempre en català de forma concisa, professional i fonamentant-te en les dades reals de la base de dades."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "feina",
            "feines",
            "ordre de treball",
            "ordres de treball",
            " ot",
            "ot-",
            "agenda",
            "planificació",
            "planificacio",
            "calendari",
            "horari",
            "fitxatge",
            "fitxatges",
            "fitxat",
            "fitxar",
            "jornada",
            "hores treballades",
            "equip",
            "qui treballa",
            "qui hi ha avui",
            "incidència",
            "incidències",
            "incidencia",
            "incidencies",
            "treball d'avui",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> dict:
        c_role = caller_role or args.get("_caller_role")
        c_user_id = caller_user_id or args.get("_caller_user_id")

        if tool_name == "get_work_orders":
            return await self.tool_get_work_orders(
                db,
                empresa_id,
                data=args.get("data"),
                estat=args.get("estat"),
                operari_nom=args.get("operari_nom"),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        elif tool_name == "get_work_order_detail":
            return await self.tool_get_work_order_detail(
                db,
                empresa_id,
                codi_ot=args.get("codi_ot", ""),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        elif tool_name == "get_team_today":
            return await self.tool_get_team_today(
                db,
                empresa_id,
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        elif tool_name == "get_timesheet":
            return await self.tool_get_timesheet(
                db,
                empresa_id,
                data=args.get("data"),
                operari_nom=args.get("operari_nom"),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        elif tool_name == "get_open_incidents":
            return await self.tool_get_open_incidents(
                db,
                empresa_id,
                codi_ot=args.get("codi_ot"),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        return {"error": f"Eina no suportada pel subagent de planificacio: {tool_name}"}


    async def tool_get_work_orders(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        data: Optional[str] = None,
        estat: Optional[str] = None,
        operari_nom: Optional[str] = None,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        stmt = (
            select(
                OrdreTreball,
                Client.rao_social,
                Finca.nom.label("finca_nom"),
                Usuari.nom.label("u_nom"),
                Usuari.cognoms.label("u_cognoms"),
            )
            .outerjoin(Client, OrdreTreball.client_id == Client.id)
            .outerjoin(Finca, OrdreTreball.finca_id == Finca.id)
            .outerjoin(Usuari, OrdreTreball.cap_de_colla_id == Usuari.id)
            .where(OrdreTreball.empresa_id == empresa_id)
        )

        # Regla de seguretat FR-021: operari només veu les seves OTs
        if caller_role in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA") and caller_user_id:
            stmt = stmt.where(OrdreTreball.cap_de_colla_id == caller_user_id)

        # Filtre de data
        avui = date.today()
        if data:
            d_str = data.strip().lower()
            if d_str in ("avui", "today"):
                stmt = stmt.where(OrdreTreball.data_planificacio == avui)
            elif d_str in ("dema", "demà", "tomorrow"):
                stmt = stmt.where(OrdreTreball.data_planificacio == avui + timedelta(days=1))
            else:
                try:
                    d_parsed = datetime.strptime(d_str, "%Y-%m-%d").date()
                    stmt = stmt.where(OrdreTreball.data_planificacio == d_parsed)
                except ValueError:
                    pass

        if estat:
            stmt = stmt.where(OrdreTreball.estat.ilike(f"%{estat.strip()}%"))

        if operari_nom and caller_role not in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA"):
            terme = f"%{operari_nom.strip()}%"
            stmt = stmt.where(
                or_(
                    Usuari.nom.ilike(terme),
                    Usuari.cognoms.ilike(terme),
                )
            )

        stmt = stmt.order_by(OrdreTreball.data_planificacio.desc(), OrdreTreball.created_at.desc()).limit(15)
        res = await db.execute(stmt)
        rows = res.all()

        ots = []
        for ot, cl_nom, f_nom, u_n, u_c in rows:
            tecnic = f"{u_n or ''} {u_c or ''}".strip() or "Sense assignar"
            ots.append({
                "codi": ot.codi,
                "titol": ot.titol,
                "estat": ot.estat,
                "data_planificacio": str(ot.data_planificacio) if ot.data_planificacio else "Pendent",
                "client": cl_nom or "Client no indicat",
                "finca": f_nom or "Finca no indicada",
                "tecnic": tecnic,
                "adreca": ot.adreca or "",
            })

        total = len(ots)
        if total == 0:
            missatge = "No s'ha trobat cap ordre de treball amb els filtres especificats."
        else:
            linies = [f"S'han trobat {total} ordres de treball:"]
            for o in ots:
                linies.append(
                    f"• {o['codi']} - {o['titol']} (Estat: {o['estat']}, Data: {o['data_planificacio']}, Tècnic: {o['tecnic']}, Client: {o['client']})"
                )
            missatge = "\n".join(linies)

        return {
            "trobat": total > 0,
            "total": total,
            "ordres": ots,
            "ordres_treball": ots,
            "missatge": missatge,
        }


    async def tool_get_work_order_detail(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        codi_ot: str,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        terme = codi_ot.strip()
        stmt = (
            select(
                OrdreTreball,
                Client.rao_social,
                Client.telefon.label("cl_tel"),
                Finca.nom.label("finca_nom"),
                Finca.adreca.label("finca_adreca"),
                Usuari.nom.label("u_nom"),
                Usuari.cognoms.label("u_cognoms"),
                Vehicle.matricula.label("v_mat"),
                Vehicle.model.label("v_model"),
            )
            .outerjoin(Client, OrdreTreball.client_id == Client.id)
            .outerjoin(Finca, OrdreTreball.finca_id == Finca.id)
            .outerjoin(Usuari, OrdreTreball.cap_de_colla_id == Usuari.id)
            .outerjoin(Vehicle, OrdreTreball.vehicle_id == Vehicle.id)
            .where(OrdreTreball.empresa_id == empresa_id)

        )
        try:
            ot_uuid = uuid.UUID(terme)
            stmt = stmt.where(OrdreTreball.id == ot_uuid)
        except (ValueError, AttributeError):
            stmt = stmt.where(
                or_(
                    OrdreTreball.codi.ilike(f"%{terme}%"),
                    OrdreTreball.titol.ilike(f"%{terme}%"),
                )
            )


        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat cap ordre de treball coincident amb '{codi_ot}'.",
            }

        ot, cl_nom, cl_tel, f_nom, f_adr, u_n, u_c, v_mat, v_mod = row

        # FR-021: operari no pot veure OTs que no són seves
        if (
            caller_role in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA")
            and caller_user_id
            and ot.cap_de_colla_id != caller_user_id
        ):
            return {
                "trobat": False,
                "missatge": "No tens permisos per consultar aquesta ordre de treball.",
            }

        # Materials de picking
        materials = []
        stmt_pick = (
            select(LiniaPicking, Article.nom, Article.referencia_inventari)
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id == ot.id,
                FullaPicking.empresa_id == empresa_id,
            )
        )
        res_pick = await db.execute(stmt_pick)
        for lp, a_nom, a_ref in res_pick.all():
            materials.append({
                "article": a_nom,
                "referencia": a_ref,
                "previst": float(lp.quantitat_prevista),
                "carregat": float(lp.quantitat_carregada_pick_in),
            })

        tecnic = f"{u_n or ''} {u_c or ''}".strip() or "Sense assignar"
        vehicle_txt = f"{v_mat} ({v_mod})" if v_mat else "Sense vehicle assignat"

        txt = (
            f"Fitxa de l'Ordre de Treball {ot.codi}:\n"
            f"• Títol: {ot.titol}\n"
            f"• Estat: {ot.estat}\n"
            f"• Data planificada: {ot.data_planificacio or 'Pendent'}\n"
            f"• Client: {cl_nom or 'N/A'} (Tel: {cl_tel or 'N/A'})\n"
            f"• Finca / Adreça: {f_nom or ''} - {ot.adreca or f_adr or 'N/A'}\n"
            f"• Tècnic assignat: {tecnic}\n"
            f"• Vehicle: {vehicle_txt}\n"
            f"• Materials assignats ({len(materials)}): "
            + (", ".join([f"{m['article']} ({m['previst']} unitats)" for m in materials]) or "Cap material de picking associat")
        )

        return {
            "trobat": True,
            "codi": ot.codi,
            "titol": ot.titol,
            "estat": ot.estat,
            "data_planificacio": str(ot.data_planificacio) if ot.data_planificacio else None,
            "client": cl_nom,
            "tecnic": tecnic,
            "operari_assignat": tecnic,
            "vehicle": vehicle_txt,
            "materials": materials,

            "missatge": txt,
        }

    async def tool_get_team_today(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        avui = date.today()
        stmt = (
            select(
                Usuari,
                RegistreJornadaLaboral.hora_inici,
                RegistreJornadaLaboral.hora_fi,
                RegistreJornadaLaboral.estat.label("reg_estat"),
                Vehicle.matricula.label("v_mat"),
            )
            .outerjoin(
                RegistreJornadaLaboral,
                (Usuari.id == RegistreJornadaLaboral.usuari_id)
                & (RegistreJornadaLaboral.data_jornada == avui),
            )
            .outerjoin(Vehicle, Usuari.vehicle_assignat_id == Vehicle.id)
            .where(
                Usuari.empresa_id == empresa_id,
                Usuari.estat == "ACTIU",
            )
        )

        if caller_role in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA") and caller_user_id:
            stmt = stmt.where(Usuari.id == caller_user_id)

        res = await db.execute(stmt)
        rows = res.all()

        actius = []
        sense_fitxar = []
        for u, h_inici, h_fi, reg_estat, v_mat in rows:
            nom_comp = f"{u.nom} {u.cognoms or ''}".strip()
            v_info = f" (Vehicle: {v_mat})" if v_mat else ""
            if h_inici and not h_fi:
                actius.append(f"{nom_comp} [En jornada des de {h_inici.strftime('%H:%M')}]{v_info}")
            elif h_inici and h_fi:
                actius.append(f"{nom_comp} [Jornada tancada {h_inici.strftime('%H:%M')} - {h_fi.strftime('%H:%M')}]{v_info}")
            else:
                sense_fitxar.append(f"{nom_comp}{v_info}")

        linies = [f"Estat de l'equip per a avui ({avui}):"]
        if actius:
            linies.append(f"• Amb registre actiu ({len(actius)}): " + ", ".join(actius))
        else:
            linies.append("• Cap membre de l'equip ha iniciat jornada avui.")
        if sense_fitxar and caller_role not in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA"):
            linies.append(f"• Pendent de fitxar ({len(sense_fitxar)}): " + ", ".join(sense_fitxar))

        equip_data = [
            {
                "id": str(u.id),
                "nom": f"{u.nom} {u.cognoms or ''}".strip(),
                "rol": u.rol,
                "jornada_activa": bool(h_inici and not h_fi),
                "hora_inici": h_inici.strftime("%H:%M") if h_inici else None,
                "hora_fi": h_fi.strftime("%H:%M") if h_fi else None,
                "vehicle": v_mat,
            }
            for u, h_inici, h_fi, reg_estat, v_mat in rows
        ]

        return {
            "trobat": True,
            "data": str(avui),
            "total_operaris": len(rows),
            "total_plantilla": len(rows),
            "equip": equip_data,
            "actius": actius,
            "missatge": "\n".join(linies),
        }


    async def tool_get_timesheet(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        data: Optional[str] = None,
        operari_nom: Optional[str] = None,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        stmt = (
            select(RegistreJornadaLaboral, Usuari.nom, Usuari.cognoms)
            .join(Usuari, RegistreJornadaLaboral.usuari_id == Usuari.id)
            .where(RegistreJornadaLaboral.empresa_id == empresa_id)
        )

        if caller_role in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA") and caller_user_id:
            stmt = stmt.where(RegistreJornadaLaboral.usuari_id == caller_user_id)
        elif operari_nom:
            terme = f"%{operari_nom.strip()}%"
            stmt = stmt.where(or_(Usuari.nom.ilike(terme), Usuari.cognoms.ilike(terme)))

        avui = date.today()
        if data:
            d_str = data.strip().lower()
            if d_str in ("avui", "today"):
                stmt = stmt.where(RegistreJornadaLaboral.data_jornada == avui)
            else:
                try:
                    d_parsed = datetime.strptime(d_str, "%Y-%m-%d").date()
                    stmt = stmt.where(RegistreJornadaLaboral.data_jornada == d_parsed)
                except ValueError:
                    stmt = stmt.where(RegistreJornadaLaboral.data_jornada >= avui - timedelta(days=7))
        else:
            stmt = stmt.where(RegistreJornadaLaboral.data_jornada >= avui - timedelta(days=7))

        stmt = stmt.order_by(RegistreJornadaLaboral.data_jornada.desc()).limit(15)
        res = await db.execute(stmt)
        rows = res.all()

        if not rows:
            return {
                "trobat": False,
                "missatge": "No s'han trobat registres de jornada per als criteris sol·licitats.",
            }

        linies = [f"Registres de fitxatge ({len(rows)} trobats):"]
        for r, u_n, u_c in rows:
            h_ini = r.hora_inici.strftime("%H:%M") if r.hora_inici else "--:--"
            h_fi = r.hora_fi.strftime("%H:%M") if r.hora_fi else "En curs"
            h_ord = float(r.hores_ordinaries or 0.0)
            linies.append(
                f"• {r.data_jornada} | {u_n} {u_c}: {h_ini} - {h_fi} (Ordinàries: {h_ord}h, Estat: {r.estat})"
            )
        total_hores = sum(

            float(r.hores_ordinaries or 0.0) + float(r.hores_extraordinaries or 0.0)
            for r, _, _ in rows
        )
        registres_data = [
            {
                "id": str(r.id),
                "usuari": f"{u_n or ''} {u_c or ''}".strip(),
                "data": str(r.data_jornada),
                "hora_inici": r.hora_inici.strftime("%H:%M") if r.hora_inici else None,
                "hora_fi": r.hora_fi.strftime("%H:%M") if r.hora_fi else None,
                "hores_ordinaries": float(r.hores_ordinaries or 0.0),
                "hores_extraordinaries": float(r.hores_extraordinaries or 0.0),
                "estat": r.estat,
            }
            for r, u_n, u_c in rows
        ]

        return {
            "trobat": True,
            "total": len(rows),
            "total_hores": total_hores,
            "registres": registres_data,
            "missatge": "\n".join(linies),
        }


    async def tool_get_open_incidents(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        codi_ot: Optional[str] = None,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        stmt = (
            select(Incidencia, OrdreTreball.codi, Usuari.nom, Usuari.cognoms)
            .outerjoin(OrdreTreball, Incidencia.ordre_treball_id == OrdreTreball.id)
            .outerjoin(Usuari, Incidencia.operari_id == Usuari.id)
            .where(
                Incidencia.empresa_id == empresa_id,
                Incidencia.estat != "RESOLTA",
            )
        )

        if caller_role in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA") and caller_user_id:
            stmt = stmt.where(Incidencia.operari_id == caller_user_id)

        if codi_ot:
            stmt = stmt.where(OrdreTreball.codi.ilike(f"%{codi_ot.strip()}%"))

        stmt = stmt.order_by(Incidencia.created_at.desc()).limit(10)
        res = await db.execute(stmt)
        rows = res.all()

        if not rows:
            return {
                "trobat": False,
                "total": 0,
                "missatge": "No hi ha cap incidència tècnica oberta pendent de resolució.",
            }

        linies = [f"Incidències tècniques obertes ({len(rows)}):"]
        for inc, ot_codi, u_n, u_c in rows:
            autor = f"{u_n} {u_c or ''}".strip() if u_n else "Operari"
            ot_txt = f" (OT: {ot_codi})" if ot_codi else ""
            desc = inc.text_observacions or "Sense observacions detallades"
            linies.append(f"• [{inc.ambit}] Estat: {inc.estat}{ot_txt} - {autor}: {desc}")

        incidencies_data = [
            {
                "id": str(inc.id),
                "ambit": inc.ambit,
                "estat": inc.estat,
                "ordre_treball": ot_codi,
                "operari": f"{u_n or ''} {u_c or ''}".strip(),
                "observacions": inc.text_observacions,
            }
            for inc, ot_codi, u_n, u_c in rows
        ]

        return {
            "trobat": True,
            "total": len(rows),
            "incidencies": incidencies_data,
            "missatge": "\n".join(linies),
        }


    async def run_sovereign(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        q = pregunta.lower()
        enllacos = [{"titol": "Ordres de Treball", "url": "/gestio"}]


        # 1. Cerca d'OT específica
        ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
        if ot_match or any(k in q for k in ["detall de la feina", "fitxa de l'ot", "detall ot"]):
            codi = ot_match.group(0).upper() if ot_match else pregunta
            tool_name = "get_work_order_detail"
            tool_args = {"codi_ot": codi}
            tool_res = await self.tool_get_work_order_detail(db, empresa_id, codi)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # 2. Equip i fitxatge d'avui
        if any(k in q for k in ["qui treballa", "qui hi ha", "equip avui", "jornada d'avui", "ha fitxat avui", "qui ha fitxat"]):
            tool_name = "get_team_today"
            tool_args = {}
            tool_res = await self.tool_get_team_today(db, empresa_id)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # 3. Fitxatges i hores (timesheet)
        if any(k in q for k in ["fitxatge", "hores treballades", "hores d'", "hores de"]):
            tool_name = "get_timesheet"
            tool_args = {"data": "avui" if "avui" in q else None}
            tool_res = await self.tool_get_timesheet(db, empresa_id, data=tool_args["data"])
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # 4. Incidències obertes
        if any(k in q for k in ["incidència", "incidències", "incidencia", "incidencies", "avaria", "obertes"]):
            tool_name = "get_open_incidents"
            tool_args = {}
            tool_res = await self.tool_get_open_incidents(db, empresa_id)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # 5. Llistat d'ordres de treball (per defecte d'agenda)
        tool_name = "get_work_orders"
        d_val = "avui" if any(k in q for k in ["avui", "today", "del dia"]) else None
        tool_args = {"data": d_val}
        tool_res = await self.tool_get_work_orders(db, empresa_id, data=d_val)
        return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos
