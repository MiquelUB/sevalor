"""Subagent de Digitalització OCR 'Zero Data Entry' i Reconeixement Documental (Disc Sobirà de l'Empresa)."""

import re
import uuid
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_OCR_VISION


class SubagentOcrVision(BaseSubagent):
    id = "subagent_ocr_vision"
    nom = "Subagent de Digitalització OCR Zero Data Entry"
    descripcio = (
        "Especialista en extracció de dades d'albarans, fitxes tècniques de vehicles i tiquets de benzina."
    )
    allowed_roles = [
        "OPERARI",
        "CAP_DE_MAGATZEM",
        "CAP_DE_COLLA",
        "SECRETARIA",
        "ENGINYER",
        "BOSS",
        "ADMIN",
    ]
    tools_schema = SCHEMAS_OCR_VISION
    system_prompt = (
        "Ets el digitalitzador OCR de SEVALOR Suite. "
        "La teva missió és extreure dades estructurades de documents (albarans de proveïdor, "
        "tiquets de benzina, targetes d'ITV) contrastant amb les fitxes del disc dur dedicat de l'empresa "
        "per eliminar l'entrada manual de dades. Respon sempre en català de forma clara i precisa."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "ocr",
            "albarà",
            "albara",
            "tiquet",
            "gasolina",
            "combustible",
            "fitxa tècnica",
            "fitxa tecnica",
            "digitalitzar",
            "escanejar",
            "llegir document",
            "extreu",
            "extreure",
            "línies",
            "linies",
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
        # Seguretat (OWASP LLM01/LLM05): mai llegir fitxer_path del LLM; només text de sessió o text_ocr validat
        text_ocr = str(kwargs.get("uploaded_text_ocr") or args.get("text_ocr") or "")
        if tool_name == "extract_albara_lines":
            return await self.tool_extract_albara_lines(db, empresa_id, text_ocr)
        if tool_name == "extract_vehicle_tech_card":
            return await self.tool_extract_vehicle_tech_card(db, empresa_id, text_ocr)
        if tool_name == "extract_fuel_receipt":
            return await self.tool_extract_fuel_receipt(db, empresa_id, text_ocr)
        return {"error": f"Eina no suportada pel subagent OCR: {tool_name}"}

    async def tool_extract_albara_lines(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        nif_match = re.search(r"\b[A-Z0-9]{8,9}\b", text_ocr or "")
        nif_detectat = nif_match.group(0) if nif_match else None

        proveidor_nom = "Desconegut"
        if nif_detectat:
            proveidors = await self.read_sovereign_category(db, empresa_id, "proveidors")
            nif_low = nif_detectat.lower()
            prov = next(
                (p for p in proveidors if nif_low in str(p.get("nif") or "").lower()),
                None,
            )
            if prov and prov.get("rao_social"):
                proveidor_nom = str(prov["rao_social"])

        data_match = re.search(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", text_ocr or "") or re.search(
            r"\b\d{4}[/-]\d{2}[/-]\d{2}\b", text_ocr or ""
        )
        data_doc = data_match.group(0) if data_match else None
        imports = re.findall(r"\b\d+(?:[.,]\d{1,2})?\s*(?:€|EUR)?\b", text_ocr or "")

        res_payload = {
            "tipus_document": "ALBARA_PROVEIDOR",
            "proveidor_nif": nif_detectat,
            "proveidor_nom": proveidor_nom,
            "data_document": data_doc,
            "imports_detectats": imports,
            "estat": "ESBORRANY_OCR",
            "missatge": (
                f"Albarà processat amb èxit ({proveidor_nom}). Formulat llest per a validació humana (HITL)."
            ),
        }
        if nif_detectat or data_doc or imports:
            doc_id = f"ocr_alb_{uuid.uuid4().hex[:10]}"
            await self.save_sovereign_entity(
                db, empresa_id, "albarans", doc_id, {"id": doc_id, **res_payload}
            )
            res_payload["albara_esborrany_id"] = doc_id

        return res_payload

    async def tool_extract_vehicle_tech_card(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        mat_match = re.search(r"\b[0-9]{4}[ -]?[A-Z]{3}\b", (text_ocr or "").upper())
        matricula = mat_match.group(0).replace(" ", "-") if mat_match else None

        vin_match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", (text_ocr or "").upper())
        vin = vin_match.group(0) if vin_match else None

        vehicle_existent = False
        if matricula:
            vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
            vehicle_existent = any(
                str(v.get("matricula") or "").upper().replace(" ", "-") == matricula
                for v in vehs
            )

        return {
            "tipus_document": "TARGETA_ITV_VEHICLE",
            "matricula": matricula,
            "vin_bastidor": vin,
            "vehicle_ja_registrat_al_disc": vehicle_existent,
            "missatge": (
                f"Targeta d'inspecció tècnica processada: Matrícula {matricula or 'Pendent'}, "
                f"VIN {vin or 'Pendent'}."
            ),
        }

    async def tool_extract_fuel_receipt(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        litres_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(?:L|litres|litros)", text_ocr or "", re.IGNORECASE
        )
        litres = float(litres_match.group(1).replace(",", ".")) if litres_match else 0.0

        total_match = re.search(
            r"TOTAL\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*€?", text_ocr or "", re.IGNORECASE
        )
        total = float(total_match.group(1).replace(",", ".")) if total_match else 0.0

        res_payload = {
            "tipus_document": "TIQUET_COMBUSTIBLE",
            "litres": litres,
            "import_total": total,
            "estat": "ESBORRANY_OCR",
            "missatge": f"Tiquet de combustible processat: {litres} litres, {total:.2f} €.",
        }
        if litres > 0 or total > 0:
            doc_id = f"ocr_tiq_{uuid.uuid4().hex[:10]}"
            await self.save_sovereign_entity(
                db, empresa_id, "tiquets_despesa", doc_id, {"id": doc_id, **res_payload}
            )
            res_payload["tiquet_esborrany_id"] = doc_id

        return res_payload

    async def run_sovereign(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Digitalització de Documents", "url": "/gestio/magatzem"}]

        if any(w in pregunta.lower() for w in ["benzina", "gasolina", "combustible"]):
            tool_name = "extract_fuel_receipt"
            tool_args = {"text_ocr": pregunta}
            tool_res = await self.tool_extract_fuel_receipt(db, empresa_id, pregunta)
        elif any(w in pregunta.lower() for w in ["vehicle", "cotxe", "targeta itv", "fitxa"]):
            tool_name = "extract_vehicle_tech_card"
            tool_args = {"text_ocr": pregunta}
            tool_res = await self.tool_extract_vehicle_tech_card(db, empresa_id, pregunta)
        else:
            tool_name = "extract_albara_lines"
            tool_args = {"text_ocr": pregunta}
            tool_res = await self.tool_extract_albara_lines(db, empresa_id, pregunta)

        resposta = tool_res.get("missatge", "Document OCR extret.")
        return resposta, tool_name, tool_args, tool_res, enllacos
