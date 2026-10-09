"""Subagent de Digitalització OCR 'Zero Data Entry' i Reconeixement Documental."""

import re
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Proveidor
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_OCR_VISION


class SubagentOcrVision(BaseSubagent):
    id = "subagent_ocr_vision"
    nom = "Subagent de Digitalització OCR Zero Data Entry"
    descripcio = "Especialista en extracció de dades d'albarans, fitxes tècniques de vehicles i tiquets de benzina."
    allowed_roles = ["OPERARI", "CAP_DE_MAGATZEM", "CAP_DE_COLLA", "SECRETARIA", "ENGINYER", "BOSS"]
    tools_schema = SCHEMAS_OCR_VISION
    system_prompt = (
        "Ets el digitalitzador OCR de SEVALOR Suite. "
        "La teva missió és extreure dades estructurades de documents (albarans de proveïdor, "
        "tiquets de benzina, targetes d'ITV) per eliminar l'entrada manual de dades. "
        "Retorna sempre JSON estructurat i precís."
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
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        text_ocr = args.get("text_ocr", "")
        if tool_name == "extract_albara_lines":
            return await self.tool_extract_albara_lines(db, empresa_id, text_ocr)
        elif tool_name == "extract_vehicle_tech_card":
            return await self.tool_extract_vehicle_tech_card(db, empresa_id, text_ocr)
        elif tool_name == "extract_fuel_receipt":
            return await self.tool_extract_fuel_receipt(db, empresa_id, text_ocr)
        return {"error": f"Eina no suportada pel subagent OCR: {tool_name}"}

    async def tool_extract_albara_lines(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        # Detectar NIF
        nif_match = re.search(r"\b[A-Z0-9]{8,9}\b", text_ocr)
        nif_detectat = nif_match.group(0) if nif_match else None

        proveidor_nom = "Desconegut"
        if nif_detectat:
            q_p = select(Proveidor).where(
                Proveidor.empresa_id == empresa_id, Proveidor.nif.ilike(f"%{nif_detectat}%")
            )
            res_p = await db.execute(q_p)
            prov = res_p.scalars().first()
            if prov:
                proveidor_nom = prov.rao_social

        # Detectar data
        data_match = re.search(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", text_ocr) or re.search(
            r"\b\d{4}[/-]\d{2}[/-]\d{2}\b", text_ocr
        )
        data_doc = data_match.group(0) if data_match else None

        # Detectar imports (ex: 125.50 €)
        imports = re.findall(r"\b\d+(?:[.,]\d{1,2})?\s*(?:€|EUR)?\b", text_ocr)

        return {
            "tipus_document": "ALBARA_PROVEIDOR",
            "proveidor_nif": nif_detectat,
            "proveidor_nom": proveidor_nom,
            "data_document": data_doc,
            "imports_detectats": imports,
            "missatge": f"Albarà processat amb èxit ({proveidor_nom}). Formulat llest per a validació a 1-clic.",
        }

    async def tool_extract_vehicle_tech_card(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        mat_match = re.search(r"\b[0-9]{4}[ -]?[A-Z]{3}\b", text_ocr.upper())
        matricula = mat_match.group(0).replace(" ", "-") if mat_match else None

        vin_match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", text_ocr.upper())
        vin = vin_match.group(0) if vin_match else None

        return {
            "tipus_document": "TARGETA_ITV_VEHICLE",
            "matricula": matricula,
            "vin_bastidor": vin,
            "missatge": f"Targeta d'inspecció tècnica processada: Matrícula {matricula or 'Pendent'}, VIN {vin or 'Pendent'}.",
        }

    async def tool_extract_fuel_receipt(
        self, db: AsyncSession, empresa_id: uuid.UUID, text_ocr: str
    ) -> dict:
        litres_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(?:L|litres|litros)", text_ocr, re.IGNORECASE
        )
        litres = float(litres_match.group(1).replace(",", ".")) if litres_match else 0.0

        total_match = re.search(r"TOTAL\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*€?", text_ocr, re.IGNORECASE)
        total = float(total_match.group(1).replace(",", ".")) if total_match else 0.0

        return {
            "tipus_document": "TIQUET_COMBUSTIBLE",
            "litres": litres,
            "import_total": total,
            "missatge": f"Tiquet de combustible processat: {litres} litres, {total:.2f} €.",
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
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
