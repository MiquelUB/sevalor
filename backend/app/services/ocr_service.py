"""Serveis de Digitalització OCR 'Zero Data Entry' connectats a IA Local i PyMuPDF.

Suporta processament multimodal mitjançant el node d'IA local (LM Studio Qwen2.5-VL)
i extracció documental amb PyMuPDF. Compliment estricte de la Constitució §2.II i Zero Mock Data.
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("ocr_service")

ESTAT_REVISIO_MANUAL = "PENDENT_REVISIO_MANUAL"
ESTAT_EXTRET_AUTOMATIC = "EXTRET_AUTOMATIC"


def _extreure_text_de_fitxer(file_bytes: bytes) -> str:
    """Extreu el text contingut si és un document PDF o text descodificable."""
    if file_bytes.startswith(b"%PDF"):
        try:
            import pymupdf

            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            text = "".join(doc[i].get_text() for i in range(len(doc)))
            if text.strip():
                return text.strip()
        except Exception as e:
            logger.warning(f"Error extraient text de PDF amb PyMuPDF: {e}")

    try:
        decoded = file_bytes.decode("utf-8")
        if any(w in decoded.lower() for w in ("total", "nif", "cif", "albarà", "data", "litres", "eur", "factura")):
            return decoded.strip()
    except Exception:
        pass

    return ""


async def _cridar_ia_vision(
    prompt_sistema: str,
    text_contingut: str = "",
    imatge_b64: Optional[str] = None,
    max_tokens: int = 2000,
) -> Optional[Dict[str, Any]]:
    """Crida el node local LM Studio (Qwen2.5-VL / compatible OpenAI) per extreure dades estructurades."""
    lm_url = getattr(settings, "LM_STUDIO_URL", None) or "http://127.0.0.1:1234/v1"
    base_url = lm_url.rstrip("/")
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    model_name = getattr(settings, "LM_STUDIO_MODEL", "qwen2.5-vl-7b-instruct")
    api_key = getattr(settings, "LM_STUDIO_API_KEY", "lm-studio")

    user_content: Any = text_contingut
    if imatge_b64:
        user_content = [
            {"type": "text", "text": text_contingut or "Extreu les dades estructurades d'aquest document en format JSON."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imatge_b64}"}},
        ]

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content_str = choices[0].get("message", {}).get("content", "").strip()
                    # Extreure bloc JSON si el model l'envolta en ```json ... ```
                    json_match = re.search(r"\{[\s\S]*\}", content_str)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        if isinstance(parsed, dict):
                            return parsed
    except Exception as e:
        logger.info(f"Node d'IA local no disponible per a OCR ({e}). S'aplica extracció directa.")

    return None



async def processar_dni_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR de DNI / NIE."""
    text = _extreure_text_de_fitxer(file_bytes)
    raw_data: Dict[str, Optional[str]] = {
        "nif": None,
        "nom": None,
        "cognoms": None,
        "data_naixement": None,
        "data_caducitat": None,
    }

    # Intent d'extracció directa per patrons (DNI/NIE espanyol)
    if text:
        nif_m = re.search(r"\b([0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])\b", text.upper())
        if nif_m:
            raw_data["nif"] = nif_m.group(1)

        titular_m = re.search(r"(?:Titular|Nom|Nombre)[\s:]*([A-Za-zÀ-ÿ\s]+)", text)
        if titular_m:
            parts = titular_m.group(1).strip().split()
            if len(parts) >= 2:
                raw_data["nom"] = parts[0]
                raw_data["cognoms"] = " ".join(parts[1:])
            elif len(parts) == 1:
                raw_data["nom"] = parts[0]

        dates = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b", text)
        if len(dates) >= 1:
            raw_data["data_caducitat"] = dates[-1]

    # Si cal suport d'IA local
    if not raw_data["nif"]:
        prompt = (
            "Ets un extractor OCR de DNI/NIE espanyol. "
            "Retorna únicament un JSON amb les claus: nif, nom, cognoms, data_naixement, data_caducitat."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64)
        if ai_res:
            for k in raw_data:
                if ai_res.get(k):
                    raw_data[k] = str(ai_res[k])

    trobat = bool(raw_data.get("nif") or raw_data.get("nom"))
    return {
        "status": ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL,
        "confidence": 0.95 if trobat else 0.0,
        "raw_data": raw_data,
    }


async def processar_albara_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR d'Albarà de proveïdor o material."""
    text = _extreure_text_de_fitxer(file_bytes)
    resultat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "proveidor_nif": None,
        "proveidor_nom": None,
        "numero_albara": None,
        "data_albara": None,
        "linies": [],
    }

    # 1. Extracció directa determinista sobre text de PDF
    if text:
        # NIF / CIF del proveïdor
        prov_block = re.search(r"DADES DEL PROVE[ÏI]DOR[\s:\n\r]+([^\n\r]+(?:\n[^\n\r]+)?)", text, re.IGNORECASE)
        if prov_block:
            p_lines = [line.strip() for line in prov_block.group(1).splitlines() if line.strip() and not line.strip().upper().startswith("NIF")]
            if p_lines:
                resultat["proveidor_nom"] = p_lines[0]
            nif_in_block = re.search(r"NIF:?\s*([A-Z0-9-]{8,11})", prov_block.group(0), re.IGNORECASE)
            if nif_in_block:
                resultat["proveidor_nif"] = nif_in_block.group(1).strip()

        if not resultat["proveidor_nif"]:
            nif_m = re.search(r"\b([A-HJ-NP-SU-W][0-9]{7}[0-9A-J]|[0-9]{8}[A-Z])\b", text.upper()) or re.search(
                r"\b[A-Z]-?[0-9]{8}\b", text.upper()
            )
            if nif_m:
                resultat["proveidor_nif"] = nif_m.group(0).replace(" ", "")

        # Número d'albarà (evitar confondre amb NIF o codis de referència de l'article)
        num_m = re.search(
            r"(?:Núm\.?\s*Albar[àa]|Albar[àa]\s*n[úu]m\.?|Albar[àa]|N[úu]m\.?\s*Document|Codi\s*Albar[àa])[\s:]*([A-Z0-9\-_/]+)",
            text,
            re.IGNORECASE,
        ) or re.search(r"\b(ALB-[0-9]{4}-[0-9A-Z]+)\b", text, re.IGNORECASE)
        if num_m:
            resultat["numero_albara"] = num_m.group(1).strip()

        # Data
        data_m = re.search(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b", text)
        if data_m:
            resultat["data_albara"] = f"{data_m.group(3)}-{data_m.group(2)}-{data_m.group(1)}"
        else:
            data_iso = re.search(r"\b(\d{4})[/.-](\d{2})[/.-](\d{2})\b", text)
            if data_iso:
                resultat["data_albara"] = f"{data_iso.group(1)}-{data_iso.group(2)}-{data_iso.group(3)}"

        # Nom del proveïdor (evitar paraules reservades com REF, ALBARÀ, NIF, TOTAL)
        linies_prohibides = ("albarà", "albara", "factura", "ref", "nº", "núm", "num", "data", "fecha", "cif", "nif", "pàgina", "pagina", "client", "destinatari", "adreça", "adreca", "total", "subtotal", "iva")
        if not resultat["proveidor_nom"]:
            prov_m = re.search(r"(?:Proveïdor|Proveedor|Empresa|Emissor)[\s:]+([^(\n\r]+)", text, re.IGNORECASE)
            if prov_m and len(prov_m.group(1).strip()) > 3:
                cand = prov_m.group(1).strip()
                if not any(cand.lower().startswith(p) for p in linies_prohibides):
                    resultat["proveidor_nom"] = cand

        if not resultat["proveidor_nom"]:
            # Cercar línia amb forma jurídica
            for linia in text.splitlines():
                l_str = linia.strip()
                if not l_str or any(l_str.lower().startswith(p) for p in linies_prohibides):
                    continue
                if re.search(r"\b(S\.?L\.?|S\.?A\.?|S\.?L\.?U\.?|S\.?C\.?P\.?|COOP)\b", l_str, re.IGNORECASE):
                    resultat["proveidor_nom"] = l_str
                    break

        if not resultat["proveidor_nom"]:
            # Fallback primera línia vàlida que no sigui capçalera
            for linia in text.splitlines():
                l_str = linia.strip()
                if len(l_str) > 3 and not any(l_str.lower().startswith(p) for p in linies_prohibides):
                    resultat["proveidor_nom"] = l_str
                    break

        # ── Extracció de línies d'articles ─────────────────────────────────
        linies: List[Dict[str, Any]] = []

        # Intent A: Format delimitat per canonades / pipes (sense caure en peus de pàgina)
        capcaleres_taula = ("codi", "ref", "referencia", "referència", "article", "item", "pos", "posicio", "posició")
        descripcions_capcalera = ("descripcio", "descripció", "concepte", "nom", "article", "producte")

        for line in text.splitlines():
            line_str = line.strip()
            if "|" in line_str and not any(k in line_str.lower() for k in ("registre mercantil", "reg. mercantil", "pàgina", "pagina", "subtotal", "base imposable")):
                clean = line_str.lstrip("-*• ")
                parts = [p.strip() for p in clean.split("|")]
                if len(parts) >= 3:
                    ref = parts[0].strip()
                    nom = parts[1].strip()

                    # Saltar files que són la capçalera de la taula
                    if ref.lower() in capcaleres_taula or nom.lower() in descripcions_capcalera:
                        continue

                    q_m = re.search(r"(\d+(?:[.,]\d+)?)", parts[2])
                    qty = float(q_m.group(1).replace(",", ".")) if q_m else 1.0
                    p_m = re.search(r"(\d+(?:[.,]\d+)?)", parts[3]) if len(parts) > 3 else None
                    preu = float(p_m.group(1).replace(",", ".")) if p_m else 0.0


                    dte = 0.0
                    if len(parts) > 4:
                        dte_m = re.search(r"(\d+(?:[.,]\d+)?)", parts[4])
                        if dte_m:
                            val_dte = float(dte_m.group(1).replace(",", "."))
                            if 0.0 <= val_dte <= 100.0:
                                dte = val_dte
                    elif len(parts) > 3 and "%" in parts[3]:
                        dte_m = re.search(r"(\d+(?:[.,]\d+)?)", parts[3])
                        if dte_m:
                            val_dte = float(dte_m.group(1).replace(",", "."))
                            if 0.0 <= val_dte <= 100.0:
                                dte = val_dte

                    tipus = "MATERIAL"
                    if any(k in nom.lower() or k in ref.lower() for k in ("eina", "pinça", "pinca", "clau", "tornavís", "tornavis", "càmera", "camera", "mesurador", "pelacables", "arnès", "arnes", "trepant", "radial", "bomba")):
                        tipus = "EINA"

                    if ref and nom:
                        linies.append({
                            "referencia": ref,
                            "nom": nom,
                            "quantitat": qty,
                            "preu": preu,
                            "descompte_percent": dte,
                            "tipus": tipus,
                        })

        # Intent B: Format columnar / tabular de documents PDF (PyMuPDF word clustering)
        if not linies and len(file_bytes) > 0:
            try:
                import fitz
                doc_pdf = fitz.open(stream=file_bytes, filetype="pdf")
                num_re = r"\d+(?:\.\d{3})*(?:,\d+)?"
                num_pattern = re.compile(
                    rf"(?P<qtat>{num_re})\s*(?:un\.?|kit|par|bob\.?|m|kg|l|joc|uds\.?|u\.?|bid\.?|pcs|capsa)?\s+(?P<preu>{num_re})\s*(?:€|eur)?\s*(?:(?P<dte>{num_re})\s*%?\s+)?(?P<total>{num_re})?\s*(?:€|eur)?",
                    re.IGNORECASE,
                )

                for page in doc_pdf:
                    words = page.get_text("words")
                    header_y = next((w[1] for w in words if w[4].upper() in ("CODI", "REF", "REFERENCIA", "ARTICLE", "DESCRIPCIO", "DESCRIPCIÓ")), 150)
                    footer_y = next((w[1] for w in words if w[1] > header_y + 40 and w[4].upper() in ("OBSERVACIONS", "SUBTOTAL", "BASE", "TOTAL")), 700)
                    table_words = [w for w in words if header_y + 10 < w[1] < footer_y - 5]
                    table_words.sort(key=lambda w: (w[1], w[0]))

                    lines_grouped = []
                    curr_line = []
                    curr_y = None
                    for w in table_words:
                        if curr_y is None or abs(w[1] - curr_y) < 7:
                            curr_line.append(w)
                            curr_y = w[1] if curr_y is None else (curr_y + w[1]) / 2
                        else:
                            curr_line.sort(key=lambda x: x[0])
                            lines_grouped.append((curr_y, " ".join([x[4] for x in curr_line])))
                            curr_line = [w]
                            curr_y = w[1]
                    if curr_line:
                        curr_line.sort(key=lambda x: x[0])
                        lines_grouped.append((curr_y, " ".join([x[4] for x in curr_line])))

                    unconsumed_desc = ""
                    for y, lstr in lines_grouped:
                        m = num_pattern.search(lstr)
                        if m:
                            qtat_str = m.group("qtat").replace(".", "").replace(",", ".")
                            qtat = float(qtat_str) if qtat_str else 1.0
                            preu_str = m.group("preu").replace(".", "").replace(",", ".")
                            preu = float(preu_str) if preu_str else 0.0
                            dte = 0.0
                            if m.group("dte"):
                                dte_val = float(m.group("dte").replace(",", "."))
                                if 0.0 <= dte_val <= 100.0:
                                    dte = dte_val

                            pre_text = lstr[:m.start()].strip()
                            if unconsumed_desc:
                                pre_text = f"{unconsumed_desc} {pre_text}".strip()
                                unconsumed_desc = ""

                            # Extreure codi d'article (ex: MOD-450B, INV-HY-06, CAM-TER-IR, TUB-PE-32)
                            code_m = re.search(r"\b([A-Z0-9]{2,8}(?:-[A-Z0-9]{2,8})+)\b", pre_text)
                            if code_m:
                                code = code_m.group(1)
                                nom = re.sub(rf"\b{re.escape(code)}\b", "", pre_text).strip()
                                nom = re.sub(r"\s+", " ", nom)
                            else:
                                tokens = pre_text.split()
                                if len(tokens) >= 2 and tokens[0].endswith("-"):
                                    code = tokens[0] + tokens[1]
                                    nom = " ".join(tokens[2:])
                                elif tokens:
                                    code = tokens[0]
                                    nom = " ".join(tokens[1:])
                                else:
                                    code = f"ART-{len(linies)+1:03d}"
                                    nom = "Article de Material"

                            tipus = "EINA" if any(w in nom.lower() or w in code.lower() for w in ["eina", "pinça", "pinca", "clau", "tornavís", "tornavis", "càmera", "camera", "mesurador", "pelacables", "arnès", "arnes", "trepant", "radial", "bomba"]) else "MATERIAL"
                            linies.append({
                                "referencia": code,
                                "nom": nom or f"Material {code}",
                                "quantitat": qtat,
                                "preu": preu,
                                "descompte_percent": dte,
                                "tipus": tipus,
                            })
                        else:
                            unconsumed_desc = lstr
            except Exception as e:
                logger.info(f"Avís en extracció columnar de PDF: {e}")

        if linies:
            resultat["linies"] = linies

    # 2. Si no s'han obtingut línies o falta NIF, sol·licitar al node d'IA local (Multimodal / Text)
    if not resultat["proveidor_nif"] or not resultat["linies"]:
        prompt = (
            "Ets un extractor OCR industrial d'albarans i factures de proveïdors de Sevalor Suite.\n"
            "Analitza el document i extreu les dades en format JSON pur:\n"
            "{\n"
            '  "proveidor_nom": "Nom oficial de l\'empresa o proveïdor emissor (mai el número d\'albarà)",\n'
            '  "proveidor_nif": "NIF o CIF de l\'emissor (ex: B12345678)",\n'
            '  "numero_albara": "Número o codi del document (ex: ALB-2026-042)",\n'
            '  "data_albara": "YYYY-MM-DD",\n'
            '  "linies": [\n'
            "    {\n"
            '      "referencia": "Codi o referència de l\'article segons el proveïdor (ex: TUB-PE-32-10)",\n'
            '      "nom": "Descripció clara del material o eina",\n'
            '      "quantitat": 10.0,\n'
            '      "preu": 15.50,\n'
            '      "descompte_percent": 5.0,\n'
            '      "tipus": "MATERIAL"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "EXTRACCIÓ RIGUROSA: Extreu TOTS els articles de la taula, amb la quantitat numèrica exacta, el preu unitari i el descompte en percentatge (0.0 si no n'hi ha). Si és eina o màquina, tipus ha de ser 'EINA', sinó 'MATERIAL'."
        )
        b64 = None
        # Si és un PDF, provar de renderitzar la primera pàgina a imatge JPEG per a l'IA multimodal
        if file_bytes.startswith(b"%PDF"):
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(dpi=150)
                    b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            except Exception:
                pass
        elif len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")

        ai_res = await _cridar_ia_vision(prompt, text, b64, max_tokens=2000)
        if ai_res:
            for k in ("proveidor_nif", "proveidor_nom", "numero_albara", "data_albara"):
                if ai_res.get(k) and not resultat.get(k):
                    resultat[k] = ai_res[k]
            if ai_res.get("linies") and not resultat["linies"]:
                resultat["linies"] = ai_res["linies"]

    trobat = bool(resultat.get("proveidor_nif") or resultat.get("numero_albara") or resultat.get("linies"))
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat



async def processar_ocr_document_vehicle(file_path: str) -> Dict[str, Any]:
    """Extracció OCR de Permís de Circulació / Targeta ITV de vehicle."""
    file_bytes = b""
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
    except Exception as e:
        logger.warning(f"No s'ha pogut llegir el fitxer del vehicle a {file_path}: {e}")

    text = _extreure_text_de_fitxer(file_bytes)
    resultat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "matricula": None,
        "bastidor": None,
        "marca": None,
        "model": None,
        "titular": None,
        "data_matriculacio": None,
    }

    if text:
        # Matrícula espanyola: 4 dígits + 3 lletres o format antic
        mat_m = re.search(r"\b([0-9]{4}[ -]?[A-Z]{3})\b", text.upper())
        if mat_m:
            resultat["matricula"] = mat_m.group(1).replace(" ", "-")

        # VIN / Bastidor (17 caràcters alfanumèrics)
        vin_m = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text.upper())
        if vin_m:
            resultat["bastidor"] = vin_m.group(1)

        # Marca i Model
        marca_m = re.search(r"(?:Marca|Marca\/Model)[\s:]*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if marca_m:
            resultat["marca"] = marca_m.group(1).strip()

        model_m = re.search(r"(?:Model)[\s:]*([A-Za-z0-9\-\s]+)", text, re.IGNORECASE)
        if model_m:
            resultat["model"] = model_m.group(1).strip().splitlines()[0]

        # Titular
        titular_m = re.search(r"(?:Titular)[\s:]*([A-Za-z0-9À-ÿ\s\.,\-]+)", text, re.IGNORECASE)
        if titular_m:
            resultat["titular"] = titular_m.group(1).strip().splitlines()[0]

        # Dates
        dates = re.findall(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b", text)
        if dates:
            resultat["data_matriculacio"] = dates[0]

    # Suport d'IA si manca bastidor o matrícula
    if not resultat["matricula"] or not resultat["bastidor"]:
        prompt = (
            "Ets un extractor OCR de fitxes tècniques i permisos de circulació de vehicles a Espanya. "
            "Retorna ÚNICAMENT un JSON: matricula, bastidor (VIN de 17 caràcters), marca, model, titular, data_matriculacio."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64)
        if ai_res:
            for k in ("matricula", "bastidor", "marca", "model", "titular", "data_matriculacio"):
                if ai_res.get(k) and not resultat.get(k):
                    resultat[k] = ai_res[k]

    trobat = bool(resultat.get("matricula") or resultat.get("bastidor"))
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat


async def processar_ocr_proveidor(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR per a alta ràpida de proveïdors a 1-clic."""
    text = _extreure_text_de_fitxer(file_bytes)
    resultat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "nif": None,
        "rao_social": None,
        "adreca": None,
        "telefon": None,
        "email": None,
    }

    if text:
        nif_m = re.search(r"\b([A-HJ-NP-SU-W][0-9]{7}[0-9A-J]|[0-9]{8}[A-Z])\b", text.upper()) or re.search(
            r"\b[A-Z]-?[0-9]{8}\b", text.upper()
        )
        if nif_m:
            resultat["nif"] = nif_m.group(0).replace(" ", "")

        tel_m = re.search(r"\b(?:\+34\s*)?[689][0-9]{8}\b", text)
        if tel_m:
            resultat["telefon"] = tel_m.group(0)

        email_m = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
        if email_m:
            resultat["email"] = email_m.group(0)

        prov_m = re.search(r"(?:Raó Social|Rao Social|Proveïdor|Distribució|Companyia)[\s:]*([^(\n\r]+)", text, re.IGNORECASE)
        if prov_m:
            resultat["rao_social"] = prov_m.group(1).strip()
        else:
            primeres = [linia.strip() for linia in text.splitlines() if linia.strip()]
            if primeres:
                resultat["rao_social"] = primeres[0]

        adreca_m = re.search(r"(?:Adreça|Dirección|Domicili)[\s:]*([^(\n\r]+)", text, re.IGNORECASE)
        if adreca_m:
            resultat["adreca"] = adreca_m.group(1).strip()

    if not resultat["nif"] or not resultat["rao_social"]:
        prompt = (
            "Extreu dades fiscals d'empresa o proveïdor en JSON: "
            "nif, rao_social, adreca, telefon, email."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64)
        if ai_res:
            for k in ("nif", "rao_social", "adreca", "telefon", "email"):
                if ai_res.get(k) and not resultat.get(k):
                    resultat[k] = ai_res[k]

    trobat = bool(resultat.get("nif") or resultat.get("rao_social"))
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat


async def processar_tiquet_ocr(file_bytes: bytes) -> Dict[str, Any]:
    """Extracció OCR de tiquets de carburant i despeses de camp."""
    text = _extreure_text_de_fitxer(file_bytes)
    resultat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "import_euros": None,
        "litres": None,
        "data_tiquet": None,
        "nif_emissor": None,
    }

    if text:
        # NIF benzinera
        nif_m = re.search(r"\b([A-HJ-NP-SU-W][0-9]{7}[0-9A-J]|[0-9]{8}[A-Z])\b", text.upper())
        if nif_m:
            resultat["nif_emissor"] = nif_m.group(1)

        # Import total en euros (ex: Total: 65.40 €)
        imp_m = re.search(r"(?:Total|Import|Importe)[\s:]*(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR)?", text, re.IGNORECASE)
        if imp_m:
            resultat["import_euros"] = float(imp_m.group(1).replace(",", "."))

        # Litres de combustible (ex: 45.20 L)
        litres_m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:L|litres|litros)\b", text, re.IGNORECASE)
        if litres_m:
            resultat["litres"] = float(litres_m.group(1).replace(",", "."))

        # Data
        data_m = re.search(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b", text)
        if data_m:
            resultat["data_tiquet"] = f"{data_m.group(3)}-{data_m.group(2)}-{data_m.group(1)}"

    # Si cal suport visual d'IA (foto del tiquet des del mòbil de l'operari)
    if resultat["import_euros"] is None:
        prompt = (
            "Ets un extractor OCR de tiquets de benzina i despeses. "
            "Retorna únicament un JSON amb: import_euros (float), litres (float o null), data_tiquet (YYYY-MM-DD), nif_emissor (str)."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64)
        if ai_res:
            if ai_res.get("import_euros") is not None:
                try:
                    resultat["import_euros"] = float(ai_res["import_euros"])
                except Exception:
                    pass
            if ai_res.get("litres") is not None:
                try:
                    resultat["litres"] = float(ai_res["litres"])
                except Exception:
                    pass
            if ai_res.get("data_tiquet"):
                resultat["data_tiquet"] = str(ai_res["data_tiquet"])
            if ai_res.get("nif_emissor"):
                resultat["nif_emissor"] = str(ai_res["nif_emissor"])

    trobat = bool(resultat.get("import_euros") is not None or resultat.get("nif_emissor"))
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat
