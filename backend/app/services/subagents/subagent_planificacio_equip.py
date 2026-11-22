"""Subagent de Planificació, Agenda i Equip de Treball (Lectura Exclusiva al Disc Sobirà de l'Empresa)."""

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_PLANIFICACIO_EQUIP

_ROLES_OPERARI = ("OPERARI", "CAPATAZ", "CAP_DE_COLLA")


def _parse_date(val: Any) -> Optional[date]:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if not isinstance(val, str) or not val.strip():
        return None
    raw = val.strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _format_hhmm(val: Any) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    m = re.search(r"(\d{2}:\d{2})", s)
    return m.group(1) if m else s[:5]


class SubagentPlanificacioEquip(BaseSubagent):
    id = "subagent_planificacio_equip"
    nom = "Subagent de Planificació i Equip"
    descripcio = (
        "Especialista en l'agenda de feines, assignació d'ordres de treball, fitxatges de la jornada i incidències operatives."
    )
    allowed_roles = ["SECRETARIA", "ENGINYER", "BOSS", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_PLANIFICACIO_EQUIP
    system_prompt = (
        "Ets l'assistent expert en Planificació, Agenda i Equip de Treball de SEVALOR. "
        "Gestiones la consulta d'ordres de treball (OTs), planificació diària i setmanal, "
        "plantilla total de treballadors de l'empresa, estat de la jornada de l'equip i incidències de camp al disc dur de l'empresa. "
        "Respon sempre en català de forma concisa, professional i fonamentant-te en les dades del disc."
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
            "plantilla",
            "total plantilla",
            "cens",
            "treballadors",
            "operaris",
            "quants som",
            "qui treballa",
            "qui hi ha avui",
            "incidència",
            "incidències",
            "incidencia",
            "incidencies",
            "treball d'avui",
            "carnet",
            "carnets",
            "caducitat",
            "caducar",
            "prl",
            "documentació operari",
            "documents operari",
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
                limit=int(args.get("limit", 10)),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        if tool_name == "get_work_order_detail":
            return await self.tool_get_work_order_detail(
                db,
                empresa_id,
                codi_ot=args.get("codi_ot", ""),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        if tool_name == "get_team_today":
            return await self.tool_get_team_today(
                db,
                empresa_id,
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        if tool_name == "get_timesheet":
            return await self.tool_get_timesheet(
                db,
                empresa_id,
                data=args.get("data"),
                operari_nom=args.get("operari_nom"),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        if tool_name == "get_open_incidents":
            return await self.tool_get_open_incidents(
                db,
                empresa_id,
                codi_ot=args.get("codi_ot"),
                caller_role=c_role,
                caller_user_id=c_user_id,
            )
        return {"error": f"Eina no suportada pel subagent de planificacio: {tool_name}"}

    async def _load_all_ots(self, db: AsyncSession, empresa_id: uuid.UUID) -> List[Dict[str, Any]]:
        act = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        hist = await self.read_sovereign_category(db, empresa_id, "ots_historic")
        vistes: set[str] = set()
        totes: List[Dict[str, Any]] = []
        for o in [*act, *hist]:
            oid = str(o.get("id") or o.get("codi") or "")
            if oid and oid in vistes:
                continue
            if oid:
                vistes.add(oid)
            totes.append(o)
        return totes

    async def tool_get_work_orders(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        data: Optional[str] = None,
        estat: Optional[str] = None,
        operari_nom: Optional[str] = None,
        limit: int = 10,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        ots_raw = await self._load_all_ots(db, empresa_id)
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        finques = await self.read_sovereign_category(db, empresa_id, "finques")
        operaris = await self.read_sovereign_category(db, empresa_id, "operaris")

        clients_map = {str(c.get("id")): c.get("rao_social") for c in clients if c.get("id")}
        finques_map = {str(f.get("id")): f.get("nom") for f in finques if f.get("id")}
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris
            if u.get("id")
        }

        target_date: Optional[date] = None
        avui = date.today()
        if data:
            d_str = data.strip().lower()
            if d_str in ("avui", "today"):
                target_date = avui
            elif d_str in ("dema", "demà", "tomorrow"):
                target_date = avui + timedelta(days=1)
            else:
                target_date = _parse_date(d_str)

        ots_filtrades: List[Dict[str, Any]] = []
        for o in ots_raw:
            if caller_role in _ROLES_OPERARI and caller_user_id:
                if str(o.get("cap_de_colla_id")) != str(caller_user_id):
                    continue

            if target_date is not None:
                o_date = _parse_date(o.get("data_planificacio"))
                if o_date != target_date:
                    continue

            if estat and estat.strip().lower() not in str(o.get("estat") or "").lower():
                continue

            tecnic = (
                op_map.get(str(o.get("cap_de_colla_id")))
                or str(o.get("tecnic") or "").strip()
                or "Sense assignar"
            )
            if operari_nom and caller_role not in _ROLES_OPERARI:
                if operari_nom.strip().lower() not in tecnic.lower():
                    continue

            cl_nom = clients_map.get(str(o.get("client_id"))) or o.get("client_nom") or "Client no indicat"
            f_nom = finques_map.get(str(o.get("finca_id"))) or o.get("finca_nom") or "Finca no indicada"
            d_plan = _parse_date(o.get("data_planificacio"))

            ots_filtrades.append(
                {
                    "codi": o.get("codi"),
                    "titol": o.get("titol"),
                    "estat": o.get("estat"),
                    "data_planificacio": str(d_plan) if d_plan else "Pendent",
                    "client": cl_nom,
                    "finca": f_nom,
                    "tecnic": tecnic,
                    "adreca": o.get("adreca") or "",
                }
            )
            if len(ots_filtrades) >= max(1, min(int(limit or 10), 50)):
                break

        total = len(ots_filtrades)
        if total == 0:
            missatge = "No s'ha trobat cap ordre de treball amb els filtres especificats."
        else:
            linies = [f"S'han trobat {total} ordres de treball:"]
            for o_item in ots_filtrades:
                linies.append(
                    f"• {o_item['codi']} - {o_item['titol']} (Estat: {o_item['estat']}, Data: {o_item['data_planificacio']}, Tècnic: {o_item['tecnic']}, Client: {o_item['client']})"
                )
            missatge = "\n".join(linies)

        return {
            "trobat": total > 0,
            "total": total,
            "ordres": ots_filtrades,
            "ordres_treball": ots_filtrades,
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
        terme = (codi_ot or "").strip().lower()
        ots_raw = await self._load_all_ots(db, empresa_id)

        matched: Optional[Dict[str, Any]] = None
        for o in ots_raw:
            if (
                str(o.get("id") or "").lower() == terme
                or terme in str(o.get("codi") or "").lower()
                or terme in str(o.get("titol") or "").lower()
            ):
                matched = o
                break

        if not matched:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat cap ordre de treball coincident amb '{codi_ot}'.",
            }

        if (
            caller_role in _ROLES_OPERARI
            and caller_user_id
            and str(matched.get("cap_de_colla_id")) != str(caller_user_id)
        ):
            return {
                "trobat": False,
                "missatge": "No tens permisos per consultar aquesta ordre de treball.",
            }

        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        finques = await self.read_sovereign_category(db, empresa_id, "finques")
        operaris = await self.read_sovereign_category(db, empresa_id, "operaris")
        vehicles = await self.read_sovereign_category(db, empresa_id, "vehicles")
        pickings = await self.read_sovereign_category(db, empresa_id, "picking")

        cl = next((c for c in clients if str(c.get("id")) == str(matched.get("client_id"))), {})
        finca = next((f for f in finques if str(f.get("id")) == str(matched.get("finca_id"))), {})
        op = next((u for u in operaris if str(u.get("id")) == str(matched.get("cap_de_colla_id"))), {})
        veh = next((v for v in vehicles if str(v.get("id")) == str(matched.get("vehicle_id"))), {})

        cl_nom = cl.get("rao_social") or matched.get("client_nom")
        cl_tel = cl.get("telefon")
        f_nom = finca.get("nom") or matched.get("finca_nom")
        f_adr = finca.get("adreca")
        tecnic = (
            f"{op.get('nom') or ''} {op.get('cognoms') or ''}".strip()
            or matched.get("tecnic")
            or "Sense assignar"
        )
        v_mat = veh.get("matricula")
        v_mod = veh.get("model")
        vehicle_txt = f"{v_mat} ({v_mod})" if v_mat else "Sense vehicle assignat"

        ot_id_str = str(matched.get("id") or "")
        materials: List[Dict[str, Any]] = []
        for p in pickings:
            if str(p.get("ordre_treball_id")) != ot_id_str and str(p.get("ordre_treball_codi")) != str(
                matched.get("codi")
            ):
                continue
            materials.append(
                {
                    "article": p.get("article_nom") or p.get("article") or "Article",
                    "referencia": p.get("referencia"),
                    "previst": float(p.get("quantitat_prevista") or p.get("quantitat_solicitada") or 0.0),
                    "carregat": float(p.get("quantitat_carregada_pick_in") or p.get("quantitat_retirada") or 0.0),
                }
            )

        d_plan = _parse_date(matched.get("data_planificacio"))
        txt = (
            f"Fitxa de l'Ordre de Treball {matched.get('codi')}:\n"
            f"• Títol: {matched.get('titol')}\n"
            f"• Estat: {matched.get('estat')}\n"
            f"• Data planificada: {d_plan or 'Pendent'}\n"
            f"• Client: {cl_nom or 'N/A'} (Tel: {cl_tel or 'N/A'})\n"
            f"• Finca / Adreça: {f_nom or ''} - {matched.get('adreca') or f_adr or 'N/A'}\n"
            f"• Tècnic assignat: {tecnic}\n"
            f"• Vehicle: {vehicle_txt}\n"
            f"• Materials assignats ({len(materials)}): "
            + (
                ", ".join([f"{m['article']} ({m['previst']} unitats)" for m in materials])
                or "Cap material de picking associat"
            )
        )

        return {
            "trobat": True,
            "codi": matched.get("codi"),
            "titol": matched.get("titol"),
            "estat": matched.get("estat"),
            "data_planificacio": str(d_plan) if d_plan else None,
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
        operaris_raw = await self.read_sovereign_category(db, empresa_id, "operaris")
        jornades_raw = await self.read_sovereign_category(db, empresa_id, "jornades")
        vehicles_raw = await self.read_sovereign_category(db, empresa_id, "vehicles")

        veh_map = {
            str(v.get("id")): v.get("matricula")
            for v in vehicles_raw
            if v.get("id") and v.get("matricula") and not v.get("tipus_document") and not v.get("data_manteniment")
        }
        jornada_avui: Dict[str, Dict[str, Any]] = {}
        for j in jornades_raw:
            uid = str(j.get("usuari_id") or "")
            if uid and _parse_date(j.get("data_jornada")) == avui:
                jornada_avui[uid] = j

        actius: List[str] = []
        sense_fitxar: List[str] = []
        rols_count: Dict[str, int] = {}
        llista_membres: List[str] = []
        alertes_carnets_prl: List[str] = []
        avisos_manca_docs: List[str] = []
        equip_data: List[Dict[str, Any]] = []

        for u in operaris_raw:
            if str(u.get("estat") or "ACTIU").upper() != "ACTIU":
                continue
            uid = str(u.get("id") or "")
            if caller_role in _ROLES_OPERARI and caller_user_id and uid != str(caller_user_id):
                continue

            nom_comp = f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip() or str(u.get("email") or "Operari")
            r = str(u.get("rol") or "OPERARI")
            rols_count[r] = rols_count.get(r, 0) + 1
            llista_membres.append(f"{nom_comp} ({r})")

            v_mat = veh_map.get(str(u.get("vehicle_assignat_id")))
            v_info = f" (Vehicle: {v_mat})" if v_mat else ""
            j = jornada_avui.get(uid, {})
            h_inici = _format_hhmm(j.get("hora_inici"))
            h_fi = _format_hhmm(j.get("hora_fi"))

            if h_inici and not h_fi:
                actius.append(f"{nom_comp} [En jornada des de {h_inici}]{v_info}")
            elif h_inici and h_fi:
                actius.append(f"{nom_comp} [Jornada tancada {h_inici} - {h_fi}]{v_info}")
            else:
                sense_fitxar.append(f"{nom_comp}{v_info}")

            c_cad = _parse_date(u.get("carnet_caducitat"))
            prl_vig = _parse_date(u.get("prl_certificat_vigencia"))

            if r in ("OPERARI", "CAP_DE_COLLA"):
                if c_cad:
                    dies_c = (c_cad - avui).days
                    if dies_c < 0:
                        alertes_carnets_prl.append(
                            f"⚠️ {nom_comp}: Carnet de conduir ({u.get('carnet_conduir') or 'B'}) CADUCAT des del {c_cad.isoformat()} ({abs(dies_c)} dies vençut)."
                        )
                    elif dies_c <= 30:
                        alertes_carnets_prl.append(
                            f"⚠️ {nom_comp}: Carnet de conduir ({u.get('carnet_conduir') or 'B'}) caduca en {dies_c} dies ({c_cad.isoformat()})."
                        )
                else:
                    avisos_manca_docs.append(f"{nom_comp} (manca data carnet conduir)")

                if prl_vig:
                    dies_p = (prl_vig - avui).days
                    if dies_p < 0:
                        alertes_carnets_prl.append(
                            f"⚠️ {nom_comp}: Certificat PRL CADUCAT des del {prl_vig.isoformat()} ({abs(dies_p)} dies vençut)."
                        )
                    elif dies_p <= 30:
                        alertes_carnets_prl.append(
                            f"⚠️ {nom_comp}: Certificat PRL caduca en {dies_p} dies ({prl_vig.isoformat()})."
                        )
                else:
                    avisos_manca_docs.append(f"{nom_comp} (manca vigència PRL)")

            equip_data.append(
                {
                    "id": uid,
                    "nom": nom_comp,
                    "rol": r,
                    "jornada_activa": bool(h_inici and not h_fi),
                    "hora_inici": h_inici,
                    "hora_fi": h_fi,
                    "vehicle": v_mat,
                    "carnet_conduir": u.get("carnet_conduir"),
                    "carnet_caducitat": c_cad.isoformat() if c_cad else None,
                    "prl_certificat_vigencia": prl_vig.isoformat() if prl_vig else None,
                }
            )

        rols_txt = ", ".join(
            [f"{count} {r.lower()}s" if count > 1 else f"1 {r.lower()}" for r, count in rols_count.items()]
        )
        total_total = len(equip_data)

        linies = [
            f"La plantilla total de l'empresa és de {total_total} treballadors actius ({rols_txt}):",
            "• Equip: " + (", ".join(llista_membres) if llista_membres else "Sense treballadors actius"),
            f"\nEstat de la jornada avui ({avui}):",
        ]
        if actius:
            linies.append(f"• Amb registre actiu ({len(actius)}): " + ", ".join(actius))
        else:
            linies.append("• Cap membre de l'equip ha iniciat jornada avui.")
        if sense_fitxar and caller_role not in _ROLES_OPERARI:
            linies.append(f"• Pendent de fitxar ({len(sense_fitxar)}): " + ", ".join(sense_fitxar))

        if alertes_carnets_prl:
            linies.append("\nAlertes Copilot de Caducitat (Carnets / PRL):")
            for al_txt in alertes_carnets_prl:
                linies.append(f"• {al_txt}")
        if avisos_manca_docs and caller_role not in _ROLES_OPERARI:
            linies.append(
                "• Avís documental (no bloquejant): Manca informar documents de "
                + ", ".join(avisos_manca_docs)
            )

        return {
            "trobat": True,
            "data": str(avui),
            "total_operaris": total_total,
            "total_plantilla": total_total,
            "desglossament_rols": rols_count,
            "equip": equip_data,
            "actius": actius,
            "alertes_carnets_prl": alertes_carnets_prl,
            "avisos_manca_docs": avisos_manca_docs,
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
        jornades_raw = await self.read_sovereign_category(db, empresa_id, "jornades")
        operaris_raw = await self.read_sovereign_category(db, empresa_id, "operaris")
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris_raw
            if u.get("id")
        }

        avui = date.today()
        exact_date: Optional[date] = None
        min_date: Optional[date] = avui - timedelta(days=7)
        if data:
            d_str = data.strip().lower()
            if d_str in ("avui", "today"):
                exact_date = avui
            else:
                parsed = _parse_date(d_str)
                if parsed:
                    exact_date = parsed

        filtrats: List[Dict[str, Any]] = []
        for j in jornades_raw:
            uid = str(j.get("usuari_id") or "")
            if caller_role in _ROLES_OPERARI and caller_user_id and uid != str(caller_user_id):
                continue

            u_nom = op_map.get(uid) or str(j.get("usuari_nom") or j.get("usuari") or "Operari")
            if operari_nom and caller_role not in _ROLES_OPERARI:
                if operari_nom.strip().lower() not in u_nom.lower():
                    continue

            d_j = _parse_date(j.get("data_jornada") or j.get("data"))
            if exact_date is not None:
                if d_j != exact_date:
                    continue
            elif d_j is not None and min_date is not None and d_j < min_date:
                continue

            h_ini = _format_hhmm(j.get("hora_inici"))
            h_fi = _format_hhmm(j.get("hora_fi"))
            h_ord = float(j.get("hores_ordinaries") or 0.0)
            h_ext = float(j.get("hores_extraordinaries") or 0.0)
            filtrats.append(
                {
                    "id": str(j.get("id")),
                    "usuari": u_nom,
                    "data": str(d_j) if d_j else str(j.get("data_jornada") or ""),
                    "hora_inici": h_ini,
                    "hora_fi": h_fi,
                    "hores_ordinaries": h_ord,
                    "hores_extraordinaries": h_ext,
                    "estat": j.get("estat"),
                }
            )
            if len(filtrats) >= 15:
                break

        if not filtrats:
            return {
                "trobat": False,
                "missatge": "No s'han trobat registres de jornada per als criteris sol·licitats.",
            }

        linies = [f"Registres de fitxatge ({len(filtrats)} trobats):"]
        for r in filtrats:
            linies.append(
                f"• {r['data']} | {r['usuari']}: {r['hora_inici'] or '--:--'} - {r['hora_fi'] or 'En curs'} "
                f"(Ordinàries: {r['hores_ordinaries']}h, Estat: {r['estat']})"
            )

        total_hores = sum(r["hores_ordinaries"] + r["hores_extraordinaries"] for r in filtrats)
        return {
            "trobat": True,
            "total": len(filtrats),
            "total_hores": total_hores,
            "registres": filtrats,
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
        inc_raw = await self.read_sovereign_category(db, empresa_id, "incidencies_registres")
        ots_raw = await self._load_all_ots(db, empresa_id)
        operaris_raw = await self.read_sovereign_category(db, empresa_id, "operaris")

        ot_map = {str(o.get("id")): o.get("codi") for o in ots_raw if o.get("id")}
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris_raw
            if u.get("id")
        }

        filtrats: List[Dict[str, Any]] = []
        linies: List[str] = []
        for inc in inc_raw:
            if str(inc.get("estat") or "").upper() == "RESOLTA":
                continue
            if caller_role in _ROLES_OPERARI and caller_user_id:
                if str(inc.get("operari_id")) != str(caller_user_id):
                    continue

            ot_codi = ot_map.get(str(inc.get("ordre_treball_id"))) or inc.get("ordre_treball_codi")
            if codi_ot and codi_ot.strip().lower() not in str(ot_codi or "").lower():
                continue

            autor = op_map.get(str(inc.get("operari_id"))) or str(inc.get("operari_nom") or "Operari")
            obs = inc.get("text_observacions") or inc.get("observacions")
            ot_txt = f" (OT: {ot_codi})" if ot_codi else ""
            linies.append(
                f"• [{inc.get('ambit', 'CAMP')}] Estat: {inc.get('estat')}{ot_txt} - {autor}: {obs or 'Sense observacions detallades'}"
            )
            filtrats.append(
                {
                    "id": str(inc.get("id")),
                    "ambit": inc.get("ambit"),
                    "estat": inc.get("estat"),
                    "ordre_treball": ot_codi,
                    "operari": autor,
                    "observacions": obs,
                }
            )
            if len(filtrats) >= 10:
                break

        if not filtrats:
            return {
                "trobat": False,
                "total": 0,
                "missatge": "No hi ha cap incidència tècnica oberta pendent de resolució.",
            }

        return {
            "trobat": True,
            "total": len(filtrats),
            "incidencies": filtrats,
            "missatge": "\n".join([f"Incidències tècniques obertes ({len(filtrats)}):"] + linies),
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

        ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
        if ot_match or any(k in q for k in ["detall de la feina", "fitxa de l'ot", "detall ot"]):
            codi = ot_match.group(0).upper() if ot_match else pregunta
            tool_name = "get_work_order_detail"
            tool_args: dict[str, Any] = {"codi_ot": codi}
            tool_res = await self.tool_get_work_order_detail(
                db, empresa_id, codi, caller_role=caller_role, caller_user_id=caller_user_id
            )
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        if any(
            k in q
            for k in [
                "plantilla",
                "total plantilla",
                "quants som",
                "quants treballadors",
                "quants operaris",
                "treballadors",
                "operaris",
                "qui treballa",
                "qui hi ha",
                "equip avui",
                "jornada d'avui",
                "ha fitxat avui",
                "qui ha fitxat",
                "cens",
                "equip",
                "carnet",
                "carnets",
                "caducitat",
                "caducar",
                "prl",
            ]
        ):
            tool_name = "get_team_today"
            tool_args = {}
            tool_res = await self.tool_get_team_today(
                db, empresa_id, caller_role=caller_role, caller_user_id=caller_user_id
            )
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        if any(k in q for k in ["fitxatge", "hores treballades", "hores d'", "hores de"]):
            tool_name = "get_timesheet"
            tool_args = {"data": "avui" if "avui" in q else None}
            tool_res = await self.tool_get_timesheet(
                db,
                empresa_id,
                data=tool_args["data"],
                caller_role=caller_role,
                caller_user_id=caller_user_id,
            )
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        if any(k in q for k in ["incidència", "incidències", "incidencia", "incidencies", "avaria", "obertes"]):
            tool_name = "get_open_incidents"
            tool_args = {}
            tool_res = await self.tool_get_open_incidents(
                db, empresa_id, caller_role=caller_role, caller_user_id=caller_user_id
            )
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        tool_name = "get_work_orders"
        d_val = "avui" if any(k in q for k in ["avui", "today", "del dia"]) else None
        tool_args = {"data": d_val}
        tool_res = await self.tool_get_work_orders(
            db, empresa_id, data=d_val, caller_role=caller_role, caller_user_id=caller_user_id
        )
        return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos
