"""Serveis de Digitalització OCR 'Zero Data Entry' connectats a IA Local i PyMuPDF.

Suporta processament multimodal mitjançant el node d'IA local (LM Studio Qwen2.5-VL)
i extracció documental amb PyMuPDF. Compliment estricte de la Constitució §2.II i Zero Mock Data.
"""

import base64
import hashlib
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.network_utils import resolve_effective_node_url

logger = logging.getLogger("ocr_service")

ESTAT_REVISIO_MANUAL = "PENDENT_REVISIO_MANUAL"
ESTAT_EXTRET_AUTOMATIC = "EXTRET_AUTOMATIC"


def _normalitzar_data_iso_general(data_str: Optional[str]) -> Optional[str]:
    """Normalitza qualsevol data DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY o YYYY-MM-DD a ISO YYYY-MM-DD."""
    if not data_str:
        return None
    s = data_str.strip().replace(".", "/").replace("-", "/")
    m1 = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m1:
        d, m, y = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"
    m2 = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m2:
        y, m, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def _extreure_text_de_fitxer(file_bytes: bytes, filename: Optional[str] = None) -> str:
    """Extreu el text contingut de PDF (.pdf), Word (.docx, .doc), Markdown (.md), Text (.txt) o metadates d'imatge (.jpg, .png)."""
    if not file_bytes:
        return ""

    fname_lower = (filename or "").lower()

    # 1. Document PDF (%PDF)
    if file_bytes.startswith(b"%PDF") or fname_lower.endswith(".pdf"):
        if file_bytes.startswith(b"%PDF"):
            try:
                import pymupdf

                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                text = "\n".join(doc[i].get_text() for i in range(len(doc)))
                if text.strip():
                    return text.strip()
            except Exception as e:
                logger.warning(f"Error extraient text de PDF amb PyMuPDF: {e}")

    # 2. Document Word modern .docx (ZIP amb word/document.xml)
    if file_bytes.startswith(b"PK\x03\x04") or fname_lower.endswith(".docx"):
        if file_bytes.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    if "word/document.xml" in zf.namelist():
                        xml_bytes = zf.read("word/document.xml")
                        root = ET.fromstring(xml_bytes)
                        paragraphs: List[str] = []
                        for elem in root.iter():
                            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                            if tag == "p":
                                texts = [
                                    t.text
                                    for t in elem.iter()
                                    if (t.tag.split("}")[-1] if "}" in t.tag else t.tag) == "t" and t.text
                                ]
                                if texts:
                                    paragraphs.append("".join(texts).strip())
                        if paragraphs:
                            return "\n".join(paragraphs).strip()
            except Exception as e:
                logger.warning(f"Error extraient text de DOCX: {e}")

    # 3. Document Word clàssic .doc (OLE2 binari o RTF)
    if file_bytes.startswith(b"\xd0\xcf\x11\xe0"):
        try:
            # Extracció de cadenes UTF-16LE i ASCII llegibles dins contenidor OLE2 .doc
            utf16_matches = re.findall(rb"(?:[\x20-\x7e\xc0-\xff]\x00){4,}", file_bytes)
            chunks = [m.decode("utf-16le", errors="ignore").strip() for m in utf16_matches]
            ascii_matches = re.findall(rb"[\x20-\x7e\n\r\t]{6,}", file_bytes)
            chunks.extend(m.decode("latin-1", errors="ignore").strip() for m in ascii_matches)
            joined = "\n".join(c for c in chunks if c)
            if joined.strip():
                return joined.strip()
        except Exception:
            pass

    # 4. Fitxers de text pla, Markdown (.md, .txt, .doc textual) o UTF-8 directe
    try:
        decoded = file_bytes.decode("utf-8")
        keywords = (
            "total", "nif", "cif", "dni", "nie", "albarà", "albara", "data", "litres", "eur", "factura",
            "matricula", "matrícula", "bastidor", "vin", "vehicle", "vehiculo", "marca", "model", "modelo", "itv", "permis", "permiso", "dgt",
            "assegurança", "asseguranca", "polissa", "pòlissa", "seguro", "póliza", "poliza", "cobertura", "asseguradora", "aseguradora", "companyia",
            "reparacio", "reparació", "manteniment", "oli", "taller",
            "nom", "nombre", "cognoms", "apellidos", "operari", "treballador", "carnet", "prl", "cap",
            "naixement", "nacimiento", "caducitat", "caducidad", "validesa", "vigencia", "vigència",
            "telefon", "telèfon", "email", "correu", "especialitat", "contracte", "seguretat social", "tgss"
        )
        if (
            fname_lower.endswith((".md", ".txt", ".markdown", ".csv", ".doc", ".docx"))
            or any(w in decoded.lower() for w in keywords)
            or ("\n" in decoded and "\x00" not in decoded)
            or ("\x00" not in decoded and len(decoded.strip()) >= 4)
        ):
            return decoded.strip()
    except Exception:
        pass

    # 5. Si és una imatge (.jpg, .png) amb comentaris/tEXt incrustats (p.ex. escenaris de test o EXIF)
    if file_bytes.startswith((b"\xff\xd8\xff", b"\x89PNG")):
        try:
            latin_text = file_bytes.decode("latin-1", errors="ignore")
            m_txt = re.findall(r"[A-Za-zÀ-ÿ0-9_:\-\./\s,@\+]{12,}", latin_text)
            filtered = [
                seg.strip()
                for seg in m_txt
                if any(
                    k in seg.lower()
                    for k in ("nif", "dni", "nom", "cognoms", "carnet", "prl", "caducitat", "permis", "permiso", "titular")
                )
            ]
            if filtered:
                return "\n".join(filtered)
        except Exception:
            pass

    return ""


async def _cridar_ia_vision(
    prompt_sistema: str,
    text_contingut: str = "",
    imatge_b64: Optional[str] = None,
    max_tokens: int = 2000,
    node_ia_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Crida el node local dedicat de l'empresa per extreure dades estructurades. Zero fallback a Hetzner."""
    lm_url = resolve_effective_node_url(node_ia_url)
    if not lm_url:
        logger.info("Empresa sense node d'IA dedicat actiu. Zero egress d'IA a Hetzner (Constitució §2.V).")
        return None

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



ORDRE_JERARQUIA_CARNETS_OCR = {"AM": 1, "B": 2, "B+E": 3, "C": 4, "C+E": 5}


async def processar_ocr_document_operari(
    file_input: bytes | str,
    node_ia_url: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Extracció OCR d'un document d'operari (.md, .pdf, .jpg, .png, .txt, .doc, .docx):
    DNI/NIE, Permís de Conduir, Certificat PRL, Certificat CAP o Fitxa/Contracte RRHH.
    """
    file_bytes = b""
    if isinstance(file_input, bytes):
        file_bytes = file_input
    elif isinstance(file_input, str):
        try:
            with open(file_input, "rb") as f:
                file_bytes = f.read()
            if not filename:
                filename = file_input.rsplit("/", 1)[-1]
        except Exception as e:
            logger.warning(f"No s'ha pogut llegir el fitxer d'operari a {file_input}: {e}")

    hash_sha256 = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""
    text = _extreure_text_de_fitxer(file_bytes, filename=filename)
    fname_lower = (filename or "").lower()
    text_lower = text.lower()

    # 1. Classificació del tipus de document de RRHH
    tipus_document = "DNI_NIE"
    if any(k in fname_lower or k in text_lower for k in ("prl", "prevenció", "prevencio", "riscos laborals", "riesgos laborales", "recurs preventiu", "grua", "alçada", "alcada", "risc elèctric", "riesgo electrico")):
        tipus_document = "CERTIFICAT_PRL"
    elif any(k in fname_lower or k in text_lower for k in ("cap", "aptitud professional", "aptitud profesional", "codi 95", "código 95", "codigo 95")) and not any(k in text_lower for k in ("permís de conduir", "permiso de conducción")):
        tipus_document = "CERTIFICAT_CAP"
    elif any(k in fname_lower or k in text_lower for k in ("carnet", "conduir", "conducción", "conduccion", "permís de conduir", "permiso de conducir", "dgt", "4b.")):
        tipus_document = "CARNET_CONDUIR"
    elif any(k in fname_lower or k in text_lower for k in ("contracte", "contrato", "tgss", "seguretat social", "seguridad social", "fitxa operari", "alta laboral", "rrhh")):
        tipus_document = "CONTRACTE_RRHH"
    elif any(k in fname_lower or k in text_lower for k in ("dni", "nie", "identitat", "identidad", "document nacional")):
        tipus_document = "DNI_NIE"

    res: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "nom_fitxer": filename or f"{tipus_document.lower()}.pdf",
        "tipus_document": tipus_document,
        "hash_sha256": hash_sha256,
        "nif": None,
        "nom": None,
        "cognoms": None,
        "data_naixement": None,
        "dni_caducitat": None,
        "data_caducitat": None,
        "telefon": None,
        "email": None,
        "rol": None,
        "especialitat": None,
        "cost_hora_eur": None,
        "carnet_conduir": None,
        "carnet_caducitat": None,
        "te_cap_vigent": False,
        "cap_caducitat": None,
        "prl_certificat_vigencia": None,
        "certificats_prl": [],
    }

    if text:
        # Clean markdown bold/list markers for regex matching
        clean_text = re.sub(r"\*\*|__", "", text)

        # A. NIF / NIE (amb o sense guió: 47821948B, 47821948-B, X-1234567-L)
        nif_m = re.search(
            r"\b([0-9]{8}[-\s]?[A-Z]|[XYZ][-\s]?[0-9]{7}[-\s]?[A-Z])\b",
            clean_text.upper(),
        )
        if nif_m:
            res["nif"] = re.sub(r"[-\s]", "", nif_m.group(1))

        # B. Nom i Cognoms (suportant camps separats o camp únic Titular/Treballador)
        cognoms_m = re.search(
            r"(?:1\.?\s*)?(?:Cognoms\s*/\s*Apellidos|Apellidos\s*/\s*Cognoms|Cognoms|Apellidos|Primer\s+i\s+segon\s+cognom)[\s:]+([^\n\r|]+)",
            clean_text,
            re.IGNORECASE,
        )
        nom_m = re.search(
            r"(?:2\.?\s*)?(?:Nom\s*/\s*Nombre|Nombre\s*/\s*Nom|Nom\s+propi|Nom(?!\s*(?:complet|i\s+cognoms|del?\s+curs|empresa|fitxer))|Nombre(?!\s*completo))[\s:]+([^\n\r|]+)",
            clean_text,
            re.IGNORECASE,
        )
        if cognoms_m:
            c_val = cognoms_m.group(1).strip(" -*•\t")
            if c_val and not any(k in c_val.lower() for k in ("nif", "dni", "data", "fecha")):
                res["cognoms"] = c_val
        if nom_m:
            n_val = nom_m.group(1).strip(" -*•\t")
            if n_val and not any(k in n_val.lower() for k in ("nif", "dni", "data", "fecha")):
                res["nom"] = n_val

        # Si ve com a "Nom complet / Titular / Treballador / Operari / Alumne: ..."
        if not res["nom"]:
            titular_m = re.search(
                r"(?:Titular|Treballador/?a?|Operari/?a?|Alumne/?a?|Nom\s+complet|Nom\s+i\s+cognoms|Nombre\s+y\s+apellidos|Nombre\s+completo)[\s:]+([A-Za-zÀ-ÿ'\-\s]+)",
                clean_text,
                re.IGNORECASE,
            )
            if titular_m:
                full_line = titular_m.group(1).splitlines()[0].strip(" -*•\t")
                # Si ve en format "COGNOMS, NOM"
                if "," in full_line:
                    parts_comma = [p.strip() for p in full_line.split(",", 1)]
                    res["cognoms"] = parts_comma[0]
                    res["nom"] = parts_comma[1]
                else:
                    parts = full_line.split()
                    if len(parts) >= 3:
                        res["nom"] = parts[0]
                        res["cognoms"] = " ".join(parts[1:])
                    elif len(parts) == 2:
                        res["nom"] = parts[0]
                        res["cognoms"] = parts[1]
                    elif len(parts) == 1:
                        res["nom"] = parts[0]

        if res["nom"] and not res["cognoms"]:
            parts_n = res["nom"].split()
            if len(parts_n) >= 2:
                res["nom"] = parts_n[0]
                res["cognoms"] = " ".join(parts_n[1:])

        # C. Telèfon i Email
        tel_m = re.search(
            r"(?:Tel[èe]fon|Tel|M[òo]bil|Móvil|Phone|SMS)[\s:]*(\+?\d[\d\s\-]{7,14}\d)",
            clean_text,
            re.IGNORECASE,
        ) or re.search(r"(\+34[\s\-]?[6789]\d{2}[\s\-]?\d{3}[\s\-]?\d{3}|\b[67]\d{8}\b)", clean_text)
        if tel_m:
            res["telefon"] = re.sub(r"[\s\-]", "", tel_m.group(1))

        email_m = re.search(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", clean_text)
        if email_m:
            res["email"] = email_m.group(1).lower()

        # D. Rol, Especialitat i Cost/Hora
        if re.search(r"\b(CAP[\s_]+DE[\s_]+COLLA|CAPATAZ|ENCARREGAT)\b", clean_text, re.IGNORECASE):
            res["rol"] = "CAP_DE_COLLA"
        elif re.search(r"\b(OPERARI|OFICIAL|PE[ÓO]|AJUDANT|T[ÈE]CNIC)\b", clean_text, re.IGNORECASE):
            res["rol"] = "OPERARI"

        if any(k in clean_text.lower() for k in ("electricitat", "elèctric", "electrico", "baixa tensió", "rebt")):
            res["especialitat"] = "ELECTRICITAT"
        elif any(k in clean_text.lower() for k in ("obra civil", "paleta", "construcció", "excavació", "rasa")):
            res["especialitat"] = "OBRA_CIVIL"
        elif any(k in clean_text.lower() for k in ("maquinària", "maquinaria", "tractor", "excavadora", "camió grua")):
            res["especialitat"] = "CONDUCTOR_MAQUINARIA"
        elif any(k in clean_text.lower() for k in ("fontaneria", "hidràulic", "hidraulica", "canonada")):
            res["especialitat"] = "FONTANERIA"
        elif any(k in clean_text.lower() for k in ("reg", "agricultura", "degoteig", "hidrant", "bombeig")):
            res["especialitat"] = "SISTEMES_REG"

        cost_m = re.search(
            r"(?:Cost\s*/?\s*hora|Tarifa\s+hor[àa]ria|Cost\s+horari)[\s:]*(\d+(?:[.,]\d+)?)\s*(?:€|eur)?",
            clean_text,
            re.IGNORECASE,
        )
        if cost_m:
            res["cost_hora_eur"] = float(cost_m.group(1).replace(",", "."))

        # E. Permís de conduir (Categories AM, B, B+E, C, C+E)
        carnets_trobats: List[str] = []
        if re.search(r"(?:Categories|Categoria|Perm[íi]s(?:os)?|Carnet(?:\s+de\s+conduir)?|9\.)[\s:]*([^\n\r]+)", clean_text, re.IGNORECASE):
            for m_cat in re.finditer(
                r"(?:Categories|Categoria|Perm[íi]s(?:os)?|Carnet(?:\s+de\s+conduir)?|9\.|Classe)[\s:]*([^\n\r]+)",
                clean_text,
                re.IGNORECASE,
            ):
                linia_cat = m_cat.group(1).upper()
                if re.search(r"\bC\s*\+\s*E\b", linia_cat):
                    carnets_trobats.append("C+E")
                if re.search(r"\bB\s*\+\s*E\b", linia_cat):
                    carnets_trobats.append("B+E")
                if re.search(r"\bC1?E?\b", linia_cat) and "C+E" not in carnets_trobats:
                    if re.search(r"\bC\b", linia_cat):
                        carnets_trobats.append("C")
                if re.search(r"\bB\b", linia_cat):
                    carnets_trobats.append("B")
                if re.search(r"\bAM\b", linia_cat):
                    carnets_trobats.append("AM")

        if carnets_trobats:
            carnets_trobats.sort(key=lambda c: ORDRE_JERARQUIA_CARNETS_OCR.get(c, 0), reverse=True)
            res["carnet_conduir"] = carnets_trobats[0]

        # F. CAP (Certificat d'Aptitud Professional / Codi 95)
        if re.search(r"\b(CAP\s+VIGENT|CERTIFICAT\s+D'APTITUD\s+PROFESSIONAL|APTITUD\s+PROFESIONAL|CODI\s*95|C[ÓO]DIGO\s*95|TARJETA\s+DE\s+CUALIFICACI[ÓO]N)\b", clean_text, re.IGNORECASE):
            res["te_cap_vigent"] = True

        # G. Certificats PRL específics
        prl_set = set()
        if re.search(r"\b(OPERADOR[_\s]+(?:DE\s+)?GRUA|GRUA\s+AUTOCARREGANT|GRUA\s+CAMI[ÓO]|CAMI[ÓO]\s+PLOMA)\b", clean_text, re.IGNORECASE):
            prl_set.add("OPERADOR_GRUA_CAMIO")
        if re.search(r"\b(TREBALLS?\s+(?:EN\s+)?AL[ÇC]ADA|TRABAJOS?\s+EN\s+ALTURA|PLATAFORMES\s+ELEVADORES|PEMP)\b", clean_text, re.IGNORECASE):
            prl_set.add("TREBALLS_ALCADA")
        if re.search(r"\b(RISC\s+EL[ÈE]CTRIC|RIESGO\s+EL[ÉE]CTRICO|BAIXA\s+TENSI[ÓO]\s+PRL| ALTA\s+TENSI[ÓO])\b", clean_text, re.IGNORECASE):
            prl_set.add("RISC_ELECTRIC_BT")
        if re.search(r"\b(60\s*H(?:ORES)?|RECURS\s+PREVENTIU|RECURSO\s+PREVENTIVO)\b", clean_text, re.IGNORECASE):
            prl_set.add("PRL_60H_RECURS_PREVENTIU")
        if re.search(r"\b(20\s*H(?:ORES)?|CONSTRUCCI[ÓO]|ALBA[ÑN]ILER[ÍI]A|MOVIMENT\s+DE\s+TERRES)\b", clean_text, re.IGNORECASE):
            prl_set.add("PRL_20H_CONSTRUCCIO")
        if re.search(r"\b(FITOSANITARIS?|APLICADOR\s+FITOSANITARI)\b", clean_text, re.IGNORECASE):
            prl_set.add("APLICADOR_FITOSANITARIS")
        if tipus_document == "CERTIFICAT_PRL" and not prl_set:
            prl_set.add("PRL_BASICA_SECTORIAL")
        res["certificats_prl"] = sorted(prl_set)

        # H. Extracció semàntica de Dates (Naixement, Caducitat DNI, Caducitat Carnet, Vigència PRL, CAP)
        date_pat = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{4}[/.-]\d{1,2}[/.-]\d{1,2})"

        naix_m = re.search(
            rf"(?:Naixement|Nacimiento|Data\s+de\s+naixement|Fecha\s+de\s+nacimiento|3\.)[\s:]*{date_pat}",
            clean_text,
            re.IGNORECASE,
        )
        if naix_m:
            res["data_naixement"] = _normalitzar_data_iso_general(naix_m.group(1))

        # Caducitat específica de Carnet de Conduir
        carnet_cad_m = re.search(
            rf"(?:Caducitat\s+(?:del\s+)?(?:carnet|perm[íi]s)|Validesa\s+(?:del\s+)?(?:carnet|perm[íi]s)|4b\.?(?:\s*Validesa|\s*Caducitat)?|Venciment\s+carnet)[\s:]*{date_pat}",
            clean_text,
            re.IGNORECASE,
        )
        if carnet_cad_m:
            res["carnet_caducitat"] = _normalitzar_data_iso_general(carnet_cad_m.group(1))

        # Caducitat / Vigència específica de PRL
        prl_cad_m = re.search(
            rf"(?:Vig[èe]ncia\s+PRL|Caducitat\s+PRL|Validesa\s+PRL|V[àa]lid\s+fins(?:\s+al)?|Data\s+venciment\s+PRL|Renovaci[óo]\s+PRL)[\s:]*{date_pat}",
            clean_text,
            re.IGNORECASE,
        )
        if prl_cad_m:
            res["prl_certificat_vigencia"] = _normalitzar_data_iso_general(prl_cad_m.group(1))

        # Caducitat específica de CAP
        cap_cad_m = re.search(
            rf"(?:Caducitat\s+CAP|Vig[èe]ncia\s+CAP|Validesa\s+CAP)[\s:]*{date_pat}",
            clean_text,
            re.IGNORECASE,
        )
        if cap_cad_m:
            res["cap_caducitat"] = _normalitzar_data_iso_general(cap_cad_m.group(1))

        # Caducitat genèrica del document segons el tipus_document
        gen_cad_m = re.search(
            rf"(?:Caducitat|Caducidad|Validesa|Validez|Venciment|Vencimiento| Vig[èe]ncia|Data\s+l[íi]mit|Expira)[\s:]*{date_pat}",
            clean_text,
            re.IGNORECASE,
        )
        gen_cad_iso = _normalitzar_data_iso_general(gen_cad_m.group(1)) if gen_cad_m else None

        if not gen_cad_iso:
            all_dates = [
                _normalitzar_data_iso_general(d)
                for d in re.findall(r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{4}[/.-]\d{1,2}[/.-]\d{1,2})\b", clean_text)
            ]
            valid_dates = [d for d in all_dates if d and d != res["data_naixement"]]
            if valid_dates:
                gen_cad_iso = max(valid_dates)

        if gen_cad_iso:
            res["data_caducitat"] = gen_cad_iso
            if tipus_document == "CARNET_CONDUIR" and not res["carnet_caducitat"]:
                res["carnet_caducitat"] = gen_cad_iso
            elif tipus_document == "CERTIFICAT_PRL" and not res["prl_certificat_vigencia"]:
                res["prl_certificat_vigencia"] = gen_cad_iso
            elif tipus_document == "CERTIFICAT_CAP" and not res["cap_caducitat"]:
                res["cap_caducitat"] = gen_cad_iso
            elif tipus_document == "DNI_NIE":
                res["dni_caducitat"] = gen_cad_iso

    # 2. Suport d'IA Multimodal (LM Studio Qwen2.5-VL) per a imatges (.jpg, .png) o PDFs escanejats
    if (not res["nif"] and not res["nom"]) and node_ia_url:
        prompt = (
            "Ets un extractor OCR de RRHH de Sevalor Suite (DNI/NIE, Carnet de Conduir, Certificat PRL, CAP).\n"
            "Retorna únicament un JSON amb les claus: tipus_document (DNI_NIE, CARNET_CONDUIR, CERTIFICAT_PRL, CERTIFICAT_CAP, CONTRACTE_RRHH), "
            "nif, nom, cognoms, data_naixement (YYYY-MM-DD), dni_caducitat (YYYY-MM-DD), telefon, email, "
            "carnet_conduir (AM, B, B+E, C, C+E), carnet_caducitat (YYYY-MM-DD), te_cap_vigent (bool), "
            "prl_certificat_vigencia (YYYY-MM-DD), certificats_prl (llista de codis)."
        )
        b64 = None
        if file_bytes.startswith(b"%PDF"):
            try:
                import fitz  # type: ignore[import-untyped]
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(dpi=150)
                    b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            except Exception:
                pass
        elif len(file_bytes) > 0 and not text:
            b64 = base64.b64encode(file_bytes).decode("utf-8")

        ai_res = await _cridar_ia_vision(prompt, text, b64, node_ia_url=node_ia_url)
        if ai_res and isinstance(ai_res, dict):
            for k in (
                "tipus_document", "nif", "nom", "cognoms", "data_naixement", "dni_caducitat",
                "data_caducitat", "telefon", "email", "rol", "especialitat", "carnet_conduir",
                "carnet_caducitat", "prl_certificat_vigencia", "cap_caducitat"
            ):
                if ai_res.get(k) and not res.get(k):
                    val = str(ai_res[k]).strip()
                    if "caducitat" in k or "vigencia" in k or "naixement" in k:
                        val = _normalitzar_data_iso_general(val) or val
                    res[k] = val
            if ai_res.get("te_cap_vigent") is True:
                res["te_cap_vigent"] = True
            if isinstance(ai_res.get("certificats_prl"), list) and not res["certificats_prl"]:
                res["certificats_prl"] = [str(x) for x in ai_res["certificats_prl"]]

    if res["dni_caducitat"] and not res["data_caducitat"]:
        res["data_caducitat"] = res["dni_caducitat"]

    trobat = bool(
        res.get("nif")
        or res.get("nom")
        or res.get("carnet_conduir")
        or res.get("carnet_caducitat")
        or res.get("prl_certificat_vigencia")
        or res.get("certificats_prl")
    )
    res["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    res["confidence"] = 0.96 if trobat else 0.0
    return res


def consolidar_i_validar_ocr_operari(
    docs: List[Dict[str, Any]],
    data_referencia: Optional[date] = None,
) -> Dict[str, Any]:
    """Consolida múltiples documents d'un operari (DNI, Carnet, PRL, CAP, Contracte),
    genera les alertes del Copilot per caducitat (caducat o a <= 30 dies / 1 mes de caducar)
    i informa de la manca de documents SENSE bloquejar mai l'alta de l'operari.
    """
    avui = data_referencia or date.today()

    consolidat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "nif": None,
        "nom": None,
        "cognoms": None,
        "data_naixement": None,
        "dni_caducitat": None,
        "data_caducitat": None,
        "telefon": None,
        "email": None,
        "rol": "OPERARI",
        "especialitat": "SISTEMES_REG",
        "cost_hora_eur": 22.50,
        "carnet_conduir": "B",
        "carnet_caducitat": None,
        "te_cap_vigent": False,
        "cap_caducitat": None,
        "prl_certificat_vigencia": None,
        "certificats_prl": [],
        "apte_alta_operari": True,
        "bloqueja_alta": False,
        "documents_aportats": [],
        "documents_pendents": [],
        "alertes_copilot": [],
        "documents_processats": [],
    }

    nifs_detectats: set[str] = set()
    tipus_aportats: set[str] = set()
    prl_acumulats: set[str] = set()
    millor_carnet = "B"
    millor_nivell_carnet = 0
    algun_extret = False

    for doc in docs:
        if doc.get("status") == ESTAT_EXTRET_AUTOMATIC:
            algun_extret = True
        t_doc = str(doc.get("tipus_document") or "DNI_NIE").upper()
        tipus_aportats.add(t_doc)

        if doc.get("nif"):
            nif_clean = str(doc["nif"]).strip().upper()
            nifs_detectats.add(nif_clean)
            if not consolidat["nif"]:
                consolidat["nif"] = nif_clean

        for camp in ("nom", "cognoms", "data_naixement", "dni_caducitat", "telefon", "email", "carnet_caducitat", "prl_certificat_vigencia", "cap_caducitat"):
            if doc.get(camp) and not consolidat.get(camp):
                consolidat[camp] = doc[camp]

        if doc.get("rol"):
            consolidat["rol"] = doc["rol"]
        if doc.get("especialitat"):
            consolidat["especialitat"] = doc["especialitat"]
        if doc.get("cost_hora_eur") is not None:
            consolidat["cost_hora_eur"] = float(doc["cost_hora_eur"])

        if doc.get("carnet_conduir"):
            c_doc = str(doc["carnet_conduir"]).upper().strip()
            niv = ORDRE_JERARQUIA_CARNETS_OCR.get(c_doc, 2)
            if niv > millor_nivell_carnet:
                millor_nivell_carnet = niv
                millor_carnet = c_doc
            # Inferència de tipus documental si el document aporta explícitament carnet
            if doc.get("carnet_caducitat"):
                tipus_aportats.add("CARNET_CONDUIR")

        if doc.get("prl_certificat_vigencia") or doc.get("certificats_prl"):
            tipus_aportats.add("CERTIFICAT_PRL")

        if doc.get("te_cap_vigent"):
            consolidat["te_cap_vigent"] = True
            tipus_aportats.add("CERTIFICAT_CAP")

        for prl_item in doc.get("certificats_prl") or []:
            prl_acumulats.add(str(prl_item))

        consolidat["documents_processats"].append(
            {
                "nom_fitxer": doc.get("nom_fitxer") or f"{t_doc.lower()}.pdf",
                "tipus_document": t_doc,
                "hash_sha256": doc.get("hash_sha256") or "",
                "data_caducitat": (
                    doc.get("carnet_caducitat")
                    or doc.get("prl_certificat_vigencia")
                    or doc.get("dni_caducitat")
                    or doc.get("data_caducitat")
                ),
                "accio_persistencia": "ARXIVAR_SOVEREIGN_STORAGE",
            }
        )

    if millor_nivell_carnet > 0:
        consolidat["carnet_conduir"] = millor_carnet
    consolidat["certificats_prl"] = sorted(prl_acumulats)
    consolidat["data_caducitat"] = (
        consolidat["dni_caducitat"]
        or consolidat["carnet_caducitat"]
        or consolidat["prl_certificat_vigencia"]
    )
    consolidat["documents_aportats"] = sorted(tipus_aportats)

    # 1. Validació de discrepància de NIF entre documents (no bloquejant però alerta Copilot)
    alertes: List[Dict[str, Any]] = []
    if len(nifs_detectats) > 1:
        alertes.append(
            {
                "codi": "DISCREPANCIA_NIF_DOCUMENTS",
                "severitat": "WARNING",
                "estat": "REVISIO_IDENTITAT",
                "concepte": "Identitat NIF/NIE",
                "bloquejant_alta": False,
                "missatge": f"S'han detectat NIFs diferents entre els documents adjuntats ({', '.join(sorted(nifs_detectats))}). Revisa que pertanyin al mateix operari.",
            }
        )

    # 2. Alertes del Copilot per caducitat (caducat o a <= 30 dies / 1 mes vista)
    venciments_check = [
        ("CARNET", "Carnet de Conduir", consolidat.get("carnet_caducitat")),
        ("PRL", "Certificat PRL", consolidat.get("prl_certificat_vigencia")),
        ("DNI", "DNI / NIE", consolidat.get("dni_caducitat")),
        ("CAP", "Certificat CAP", consolidat.get("cap_caducitat")),
    ]
    for prefix, nom_concepte, data_iso in venciments_check:
        if data_iso:
            try:
                d_venc = date.fromisoformat(str(data_iso)[:10])
                dies_restants = (d_venc - avui).days
                if dies_restants < 0:
                    alertes.append(
                        {
                            "codi": f"{prefix}_CADUCAT",
                            "severitat": "CRITICAL",
                            "estat": "CADUCAT",
                            "concepte": nom_concepte,
                            "data_caducitat": d_venc.isoformat(),
                            "dies_restants": dies_restants,
                            "bloquejant_alta": False,
                            "missatge": (
                                f"Alerta Copilot: El {nom_concepte} està CADUCAT des del {d_venc.isoformat()} "
                                f"({abs(dies_restants)} dies vençut). No bloqueja l'alta de l'operari, però cal renovar-lo."
                            ),
                        }
                    )
                elif dies_restants <= 30:
                    alertes.append(
                        {
                            "codi": f"{prefix}_PROPER_CADUCAR",
                            "severitat": "WARNING",
                            "estat": "PROPER_A_CADUCAR",
                            "concepte": nom_concepte,
                            "data_caducitat": d_venc.isoformat(),
                            "dies_restants": dies_restants,
                            "bloquejant_alta": False,
                            "missatge": (
                                f"Alerta Copilot: El {nom_concepte} caduca en menys d'un mes ({dies_restants} dies restants, "
                                f"venciment {d_venc.isoformat()})."
                            ),
                        }
                    )
            except Exception:
                pass

    # 3. Control de manca de documents (NO BLOQUEJANT per a l'alta de l'operari)
    docs_recomanats = [
        ("DNI_NIE", "DNI / NIE"),
        ("CARNET_CONDUIR", "Carnet de Conduir"),
        ("CERTIFICAT_PRL", "Certificat PRL"),
    ]
    pendents_codis: List[str] = []
    pendents_noms: List[str] = []
    for codi_doc, label_doc in docs_recomanats:
        if codi_doc not in tipus_aportats:
            pendents_codis.append(codi_doc)
            pendents_noms.append(label_doc)

    consolidat["documents_pendents"] = pendents_codis
    if pendents_codis:
        alertes.append(
            {
                "codi": "MANCA_DOCUMENTACIO_RRHH",
                "severitat": "INFO",
                "estat": "DOCUMENTACIO_INCOMPLETA_NO_BLOQUEJANT",
                "concepte": "Expedient Documental RRHH",
                "documents_pendents": pendents_codis,
                "bloquejant_alta": False,
                "missatge": (
                    f"Avís Copilot (No bloquejant): Manca adjuntar {', '.join(pendents_noms)}. "
                    "Pots completar l'alta de l'operari ara i pujar la resta de documents més endavant."
                ),
            }
        )

    consolidat["alertes_copilot"] = alertes
    consolidat["status"] = ESTAT_EXTRET_AUTOMATIC if algun_extret else ESTAT_REVISIO_MANUAL
    consolidat["confidence"] = 0.96 if algun_extret else 0.0
    consolidat["raw_data"] = {
        "nif": consolidat["nif"],
        "nom": consolidat["nom"],
        "cognoms": consolidat["cognoms"],
        "data_naixement": consolidat["data_naixement"],
        "data_caducitat": consolidat["data_caducitat"],
        "carnet_conduir": consolidat["carnet_conduir"],
        "carnet_caducitat": consolidat["carnet_caducitat"],
        "prl_certificat_vigencia": consolidat["prl_certificat_vigencia"],
    }
    return consolidat


async def processar_dni_ocr(
    file_bytes: bytes,
    node_ia_url: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Extracció OCR de DNI / NIE i documentació d'operari amb compatibilitat retroactiva."""
    doc_extret = await processar_ocr_document_operari(
        file_bytes, node_ia_url=node_ia_url, filename=filename
    )
    return consolidar_i_validar_ocr_operari([doc_extret])


async def processar_albara_ocr(file_bytes: bytes, node_ia_url: Optional[str] = None) -> Dict[str, Any]:
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
                import fitz  # type: ignore[import-untyped]
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
    if (not resultat["proveidor_nif"] or not resultat["linies"]) and node_ia_url:
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
                import fitz  # type: ignore[import-untyped]
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(dpi=150)
                    b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            except Exception:
                pass
        elif len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")

        ai_res = await _cridar_ia_vision(prompt, text, b64, max_tokens=2000, node_ia_url=node_ia_url)
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



def _normalitzar_data_iso(data_str: Optional[str]) -> Optional[str]:
    """Normalitza una data en format DD/MM/YYYY o YYYY/MM/DD a format estàndard ISO YYYY-MM-DD."""
    if not data_str:
        return None
    data_str = data_str.strip().replace(".", "/").replace("-", "/")
    m1 = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", data_str)
    if m1:
        d, m, y = m1.group(1), m1.group(2), m1.group(3)
        return f"{y}-{int(m):02d}-{int(d):02d}"
    m2 = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", data_str)
    if m2:
        y, m, d = m2.group(1), m2.group(2), m2.group(3)
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return None


MARQUES_VEHICLES_CONEGUDES = [
    "MERCEDES-BENZ", "MERCEDES", "VOLKSWAGEN", "RENAULT", "FORD", "PEUGEOT",
    "CITROEN", "CITROËN", "IVECO", "FIAT", "TOYOTA", "NISSAN", "OPEL", "SEAT",
    "SKODA", "ŠKODA", "HYUNDAI", "KIA", "BMW", "AUDI", "VOLVO", "MAN", "SCANIA",
    "DAF", "ISUZU", "MITSUBISHI", "SUZUKI", "DACIA", "JEEP", "LAND ROVER",
    "KUBOTA", "JOHN DEERE", "CATERPILLAR", "JCB", "BOBCAT", "NEW HOLLAND",
    "KOMATSU", "LIEBHERR", "CASE", "YANMAR"
]

COMPANYIES_ASSEGURANCES_CONEGUDES = [
    "MAPFRE", "ALLIANZ", "AXA", "MUTUA MADRILEÑA", "MUTUA MADRILENYA", "GENERALI",
    "ZURICH", "CATALANA OCCIDENTE", "OCCIDENT", "REALE", "PELAYO", "LINEA DIRECTA",
    "LÍNEA DIRECTA", "LIBERTY", "FIATC", "HELVETIA", "CASER", "SANTA LUCIA", "SANTALUCIA"
]


async def processar_ocr_document_vehicle(file_input: bytes | str, node_ia_url: Optional[str] = None) -> Dict[str, Any]:
    """Extracció OCR completa de Permís de Circulació, Targeta ITV o Pòlissa d'Assegurança de vehicle."""
    file_bytes = b""
    if isinstance(file_input, bytes):
        file_bytes = file_input
    elif isinstance(file_input, str):
        try:
            with open(file_input, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            logger.warning(f"No s'ha pogut llegir el fitxer del vehicle a {file_input}: {e}")
    else:
        logger.warning(f"Tipus d'entrada no suportat per a OCR de vehicle: {type(file_input)}")

    text = _extreure_text_de_fitxer(file_bytes)
    resultat: Dict[str, Any] = {
        "status": ESTAT_REVISIO_MANUAL,
        "confidence": 0.0,
        "matricula": None,
        "bastidor": None,
        "marca": None,
        "model": None,
        "titular": None,
        "titular_nif": None,
        "arrendatari_nif": None,
        "categoria_ue": None,
        "mma_kg": None,
        "tara_kg": None,
        "carrega_util_kg": None,
        "requereix_cap": False,
        "equipament_homologat": [],
        "empresa_renting": None,
        "num_contracte_renting": None,
        "data_venciment_renting": None,
        "dades_pesants": None,
        "tipus": None,
        "distintiu_ambiental": None,
        "odometre_acumulat": None,
        "estat_itv": None,
        "data_proxima_itv": None,
        "data_inspeccio_itv": None,
        "data_matriculacio": None,
        "companyia_asseguradora": None,
        "polissa_asseguranca": None,
        "data_caducitat_asseguranca": None,
        "regim_adquisicio": None,
        "renting_limit_km": None,
        "carnet_necessari": None,
        "tipus_document": None,
    }

    mmr_amb_fre_kg: Optional[int] = None
    dades_pesants_dict: Dict[str, Any] = {}
    equipament_detectat: List[str] = []

    if text:
        # 1. Matrícula espanyola: Codi UE (A) o cerca general
        mat_explicit = re.search(
            r"(?:(?:\(A\)|A\.)\s*Matr[íi]cula|Matr[íi]cula|Matricula|Placa)[\s:]*([0-9]{4}[ -]?[A-Z]{3}|[A-Z]{1,2}[ -]?[0-9]{4}[ -]?[A-Z]{1,2})",
            text,
            re.IGNORECASE,
        )
        if mat_explicit:
            resultat["matricula"] = mat_explicit.group(1).replace(" ", "-").upper()
        else:
            mat_m = re.search(r"\b([0-9]{4}[ -]?[A-Z]{3})\b", text.upper()) or re.search(
                r"\b([A-Z]{1,2}[ -]?[0-9]{4}[ -]?[A-Z]{1,2})\b", text.upper()
            )
            if mat_m:
                resultat["matricula"] = mat_m.group(1).replace(" ", "-").upper()

        # 2. VIN / Bastidor (Codi UE (E) o cerca alfanumèrica ISO)
        vin_explicit = re.search(
            r"(?:(?:\(E\)|E\.)\s*(?:N[úu]m\.?\s*Identificaci[oó]n\s*\(VIN\)|N[º°]\s*Identificaci[oó]n\s*\(VIN\)|VIN|Bastidor)|(?:VIN|Bastidor|N[úu]m\.?\s*Bastidor|N[º°]\s*Bastidor|N[úu]mero\s*de\s*bastidor))[\s:]*([A-HJ-NPR-Z0-9]{11,18})",
            text,
            re.IGNORECASE,
        )
        if vin_explicit:
            resultat["bastidor"] = vin_explicit.group(1).strip().upper()
        else:
            vin_m = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text.upper())
            if vin_m:
                resultat["bastidor"] = vin_m.group(1).upper()

        # 3. Marca i Model (Codi UE D.1 i D.3)
        marca_ue_m = re.search(r"(?:(?:\(D\.1\)|D\.1)\s*Marca)[\s:]*([^\n\r]+)", text, re.IGNORECASE)
        if marca_ue_m:
            raw_marca_line = marca_ue_m.group(1).strip()
            for m_cand in MARQUES_VEHICLES_CONEGUDES:
                if raw_marca_line.upper().startswith(m_cand):
                    resultat["marca"] = m_cand.title()
                    break
            if not resultat["marca"] and raw_marca_line:
                resultat["marca"] = raw_marca_line.split()[0].capitalize()

        if not resultat["marca"]:
            marca_m = re.search(
                r"(?:(?:\([A-Z0-9\.]+\)|[A-Z0-9\.]+\s*)?Marca\s*(?:[\/\&\|\-]\s*(?:Model|Modelo)|y\s*Modelo|i\s*Model)?|(?:\([A-Z0-9\.]+\)|[A-Z0-9\.]+\s*)?Marca)[\s:]*([^\n\r]+)",
                text,
                re.IGNORECASE,
            )
            if marca_m:
                raw_marca_line = marca_m.group(1).strip()
                raw_marca_line = re.sub(r"^(?:y|i|\/)?\s*(?:Model|Modelo)[\s:]*", "", raw_marca_line, flags=re.IGNORECASE).strip()
                for m_cand in MARQUES_VEHICLES_CONEGUDES:
                    if raw_marca_line.upper().startswith(m_cand):
                        resultat["marca"] = m_cand.title()
                        rest = raw_marca_line[len(m_cand):].strip(" -/,").strip()
                        if rest:
                            resultat["model"] = rest
                        break
                if not resultat["marca"]:
                    parts = raw_marca_line.split()
                    if parts:
                        resultat["marca"] = parts[0].capitalize()
                        if len(parts) > 1 and not resultat["model"]:
                            resultat["model"] = " ".join(parts[1:])

        # Prioritzar D.3 Denominación comercial explícita per sobre de D.2 Versión
        model_d3_m = re.search(
            r"(?:(?:\(D\.3\)|D\.3)\s*Denominaci[oó]n\s*comercial|Denominaci[oó]n\s*comercial|Denominaci[oó]\s*comercial)[\s:]*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if model_d3_m:
            cand_model = model_d3_m.group(1).strip().splitlines()[0]
            cand_model = re.sub(r"^[oO]\s*:\s*", "", cand_model).strip()
            if resultat.get("marca") and cand_model.upper().startswith(resultat["marca"].upper()):
                cand_model = cand_model[len(resultat["marca"]):].strip(" -/,")
            if cand_model:
                resultat["model"] = cand_model
        else:
            model_m = re.search(
                r"(?:Model\s*&\s*Versi[oó]|Modelo|Model|(?:(?:\(D\.2\)|D\.2)\s*)?(?:Tipo\s*\/\s*Variante\s*\/\s*Versi[oó]n|Versi[oó]n|Versi[oó]))[\s:]*([^\n\r]+)",
                text,
                re.IGNORECASE,
            )
            if model_m:
                cand_model = model_m.group(1).strip().splitlines()[0]
                cand_model = re.sub(r"^[oO]\s*:\s*", "", cand_model).strip()
                if resultat.get("marca") and cand_model.upper().startswith(resultat["marca"].upper()):
                    cand_model = cand_model[len(resultat["marca"]):].strip(" -/,")
                if cand_model:
                    resultat["model"] = cand_model

        # 4. Tipus de Propulsió (Combustible Codi UE P.3)
        comb_m = re.search(r"(?:(?:\(P\.3\)|P\.3)\s*Combustible|Combustible|Carburant|Propulsi[oó]|Propulsion|Motor)[\s:]*([^\n\r]+)", text, re.IGNORECASE)
        comb_str = (comb_m.group(1) if comb_m else "") + " " + text
        if re.search(r"\b(di[eè]sel|gasoil|gas[oó]leo|ga\b)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "DIESEL"
        elif re.search(r"\b(gasolina|benzina)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "GASOLINA"
        elif re.search(r"\b(el[eè]ctric|electric|ev\b|bev\b|100%\s*el[eè]ctric)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "EV"
        elif re.search(r"\b(h[ií]brid|phev|hev|glp|gnc|enchufable)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "PHEV"
        elif re.search(r"\b(maquin[aà]ria|tractor|excavadora|dumper|elevadora)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "MAQUINARIA"
        elif re.search(r"\b(remolc|semiremolc|trailer)\b", comb_str, re.IGNORECASE):
            resultat["tipus"] = "REMOLC"

        # 5. Distintiu Ambiental DGT
        dist_m = re.search(r"(?:Distintiu|Etiqueta|DGT|Ambiental)[\s:]*([A-Z0-9]+)", text, re.IGNORECASE)
        if dist_m:
            val = dist_m.group(1).upper()
            if val in ("0", "ZERO", "CERO"):
                resultat["distintiu_ambiental"] = "ZERO"
            elif val == "ECO":
                resultat["distintiu_ambiental"] = "ECO"
            elif val == "C":
                resultat["distintiu_ambiental"] = "C"
            elif val == "B":
                resultat["distintiu_ambiental"] = "B"
            elif val in ("SENSE", "SIN"):
                resultat["distintiu_ambiental"] = "SENSE"

        if not resultat["distintiu_ambiental"]:
            if resultat.get("tipus") == "EV":
                resultat["distintiu_ambiental"] = "ZERO"
            elif resultat.get("tipus") == "PHEV":
                resultat["distintiu_ambiental"] = "ECO"
            elif resultat.get("tipus") in ("DIESEL", "GASOLINA"):
                resultat["distintiu_ambiental"] = "C"

        # 6. Classificació i Categoria UE (Codi UE J)
        cat_m = re.search(
            r"(?:(?:\(J\)|J\.)\s*Categor[íi]a\s*(?:del\s*veh[íi]culo)?|Categor[íi]a\s*(?:del\s*veh[íi]culo)?|Categoria)[\s:]*([MNOL][1-5]|N[123]|M[123]|O[1-4])",
            text,
            re.IGNORECASE,
        )
        if cat_m:
            resultat["categoria_ue"] = cat_m.group(1).upper()

        # 7. Masses i Pesos Harmonitzats: MMA (F.2/F.1), Tara (G), Càrrega Útil i MMR amb fre (O.1.2)
        mma_m = re.search(
            r"(?:(?:\(F\.2\)|F\.2)[^\n\r:]*|(?:\(F\.1\)|F\.1)[^\n\r:]*|(?:MMA|PMA\s*\(MMA\)|PMA|Masa\s*M[aá]xima\s*Autorizada|Pes\s*M[aà]xim\s*Autoritzat)[^\n\r:]*)[\s:]+([0-9\.\, ]+)\s*(?:kg)?",
            text,
            re.IGNORECASE,
        )
        if mma_m:
            clean_mma = re.sub(r"[^\d]", "", mma_m.group(1))
            if clean_mma:
                try:
                    resultat["mma_kg"] = int(clean_mma)
                except ValueError:
                    pass

        tara_m = re.search(
            r"(?:(?:\(G\)|G\.)[^\n\r:]*|(?:Masa\s*en\s*servicio|Masa\s*en\s*orden\s*de\s*marcha|Tara)[^\n\r:]*)[\s:]+([0-9\.\, ]+)\s*(?:kg)?",
            text,
            re.IGNORECASE,
        )
        if tara_m:
            clean_tara = re.sub(r"[^\d]", "", tara_m.group(1))
            if clean_tara:
                try:
                    resultat["tara_kg"] = int(clean_tara)
                except ValueError:
                    pass

        util_m = re.search(
            r"(?:Carga\s*[uú]til\s*(?:m[aá]xima)?|C[aà]rrega\s*[uú]til\s*(?:m[aà]xima)?|Capacitat\s*de\s*c[aà]rrega\s*[uú]til)[\s:]*([0-9\.\, ]+)\s*(?:kg)?",
            text,
            re.IGNORECASE,
        )
        if util_m:
            clean_util = re.sub(r"[^\d]", "", util_m.group(1))
            if clean_util:
                try:
                    resultat["carrega_util_kg"] = int(clean_util)
                except ValueError:
                    pass

        mmr_m = re.search(
            r"(?:(?:\(O\.1(?:\.2)?\)|O\.1(?:\.2)?)\s*(?:MMR\s*c\/f|MMR\s*con\s*freno)|MMR\s*c\/f)[\s:]*([0-9\.\, ]+)\s*(?:kg)?",
            text,
            re.IGNORECASE,
        )
        if mmr_m:
            clean_mmr = re.sub(r"[^\d]", "", mmr_m.group(1))
            if clean_mmr:
                try:
                    mmr_amb_fre_kg = int(clean_mmr)
                except ValueError:
                    pass

        # 8. Estat ITV Actual
        res_itv = re.search(r"(?:Resultat|Resultado|Estat\s*ITV|Veredicte)[\s:]*([^\n\r]+)", text, re.IGNORECASE)
        res_str = res_itv.group(1).upper() if res_itv else text.upper()
        if "FAVORABLE AMB DEFECTES LLEUS" in res_str or "DEFECTES LLEUS" in res_str or "DEFECTOS LEVES" in res_str or "LEVE" in res_str:
            resultat["estat_itv"] = "FAVORABLE_LEUS"
        elif "DESFAVORABLE" in res_str or "NO APTE" in res_str or "NO APTO" in res_str:
            resultat["estat_itv"] = "DESFAVORABLE"
        elif "NEGATIVA" in res_str or "INACTIVAT" in res_str:
            resultat["estat_itv"] = "NEGATIVA"
        elif "FAVORABLE" in res_str or "APTE" in res_str or "APTO" in res_str:
            resultat["estat_itv"] = "FAVORABLE"

        # 9. Data Pròxima ITV
        prox_matches = re.findall(
            r"(?:Pr[oò]xima\s*ITV|Propera\s*ITV|Venciment\s*ITV|Proper\s*venciment|Validesa\s*fins|V[aá]lida\s*hasta|V[aá]lida\s*fins|Pr[oó]xima\s*inspecci[oó]n|Caducitat\s*ITV|Data\s*(?:de\s*)?caducitat\s*(?:propera\s*)?itv)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if prox_matches:
            valid_dates: List[str] = [d for m in prox_matches if (d := _normalitzar_data_iso(m)) is not None]
            if valid_dates:
                resultat["data_proxima_itv"] = max(valid_dates)

        # 10. Data Inspecció ITV i Data Matriculació (Codi UE B)
        insp_m = re.search(
            r"(?:Data\s*Inspecci[oó]|Data\s*d'inspecci[oó]|Fecha\s*inspecci[oó]n)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if insp_m:
            resultat["data_inspeccio_itv"] = _normalitzar_data_iso(insp_m.group(1))

        matr_m = re.search(
            r"(?:(?:\(B\)|B\.)\s*(?:Fecha\s*(?:de\s*)?(?:primera|1[aª])\s*matr[íi]cula|Data\s*(?:de\s*)?(?:primera|1[aª])\s*matr[íi]cula)|(?:\([A-Z0-9\.]+\)|[A-Z0-9\.]+\s*)?(?:Data\s*Matriculaci[oó]|Data\s*1[aª]\s*matriculaci[oó]|Fecha\s*matriculaci[oó]n|Fecha\s*1[aª]\s*matriculaci[oó]n|Fecha\s*de\s*primera\s*matr[íi]cula))[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if matr_m:
            resultat["data_matriculacio"] = _normalitzar_data_iso(matr_m.group(1))

        # 11. Odòmetre / Quilometratge
        km_matches = re.findall(
            r"(?:Lectura\s*km|Quilometratge|Kilometraje|Od[oò]metre|Odometro|Lectura\s*od[oò]metre|(?:(?<!desde\s)(?<!des de\s)\bKm\b))[\s:]*([0-9\.\, ]+)",
            text,
            re.IGNORECASE,
        )
        if km_matches:
            km_vals: List[int] = []
            for km_str in km_matches:
                clean_km = re.sub(r"[^\d]", "", km_str)
                if clean_km:
                    try:
                        val_km = int(clean_km)
                        if val_km > 0 and not ("desde km" in text.lower() and val_km == 0):
                            km_vals.append(val_km)
                    except ValueError:
                        pass
            if km_vals:
                resultat["odometre_acumulat"] = max(km_vals)

        # 12. Assegurança (Companyia, Pòlissa, Caducitat)
        comp_m = re.search(
            r"(?:Companyia\s*asseguradora|Entitat\s*asseguradora|Companyia|Asseguradora|Aseguradora)[\s:]*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if comp_m:
            cand_comp = comp_m.group(1).strip()
            cand_comp = re.sub(r"^(?:Asseguradora|Aseguradora|Companyia)[\s:]*", "", cand_comp, flags=re.IGNORECASE).strip()
            for c_cand in COMPANYIES_ASSEGURANCES_CONEGUDES:
                if re.search(r"\b" + re.escape(c_cand) + r"\b", cand_comp, re.IGNORECASE):
                    cand_comp = c_cand.title()
                    break
            if len(cand_comp) > 2:
                resultat["companyia_asseguradora"] = cand_comp

        if not resultat["companyia_asseguradora"]:
            for c_cand in COMPANYIES_ASSEGURANCES_CONEGUDES:
                if re.search(r"\b" + re.escape(c_cand) + r"\b", text, re.IGNORECASE):
                    resultat["companyia_asseguradora"] = c_cand.title()
                    break

        pol_m = re.search(
            r"(?:(?:N[úu]m\.?|N[úu]mero|Nº)\s*(?:de\s*)?)?P[oòó]li(?:ss|[sz])a(?:\s*(?:de\s*)?(?:flota|colectiva|individual|n[úu]m\.?|nº|numero))?[\s:]+([A-Z0-9\-_/]{5,})",
            text,
            re.IGNORECASE,
        )
        if pol_m:
            cand_pol = pol_m.group(1).strip()
            if cand_pol.upper() not in ("FLOTA", "COLECTIVA", "INDIVIDUAL", "SEGUROS"):
                resultat["polissa_asseguranca"] = cand_pol

        cad_m = re.search(
            r"(?:Vencimiento\s*(?:de\s*la\s*anualidad)?|Venciment\s*(?:de\s*l'anualitat)?|Venciment\s*(?:asseguran[cç]a)?|Caducitat\s*(?:asseguran[cç]a)?|Vencimiento|Validesa\s*fins|Efecte\s*fins|Data\s*(?:de\s*)?venciment|Data\s*(?:de\s*)?caducitat)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if cad_m:
            resultat["data_caducitat_asseguranca"] = _normalitzar_data_iso(cad_m.group(1))

        # 13. Servei DGT i Règim d'Adquisició
        servei_dgt_m = re.search(r"(?:Servicio\s*(?:al\s*que\s*se\s*destina)?|C[oó]digo\s*DGT)[\s:]*([A-Z0-9]{3})", text, re.IGNORECASE)
        if servei_dgt_m:
            codi_srv = servei_dgt_m.group(1).upper()
            if codi_srv == "A12":
                resultat["regim_adquisicio"] = "RENTING"
            elif codi_srv in ("B00", "B09"):
                resultat["regim_adquisicio"] = "PROPIETAT"

        if not resultat["regim_adquisicio"]:
            if re.search(
                r"\b(l[ií]sing|leasing)\b|(?:arrendament\s*financer|arrendamiento\s*financiero|opci[oó]\s*de\s*compra|opci[oó]n\s*de\s*compra|valor\s*residual)",
                text,
                re.IGNORECASE,
            ) and not re.search(r"\b(renting|r[eèé]nting)\b", text, re.IGNORECASE):
                resultat["regim_adquisicio"] = "LEASING"
            elif re.search(
                r"\b(renting|leasing|l[ií]sing|arval|alphabet|leaseplan|ald\s*automotive|santander\s*consumer\s*renting|santander\s*renting|bbva\s*autorenting|bansacar|caixarenting|northgate|ayvens)\b|"
                r"(?:arrendament\s*financer|arrendamiento\s*financiero|arrendament\s*(?:operatiu\s*)?a\s*llarg\s*termini|arrendamiento\s*(?:operativo\s*)?a\s*largo\s*plazo|arrendament\s*sense\s*conductor|arrendamiento\s*sin\s*conductor|arrendatari\s*a\s*llarg\s*termini|arrendatario\s*largo\s*plazo|quota\s*(?:de\s*)?r[eèé]nting|cuota\s*(?:de\s*)?renting|contracte\s*de\s*r[eèé]nting|contrato\s*de\s*renting)",
                text,
                re.IGNORECASE,
            ):
                resultat["regim_adquisicio"] = "RENTING"
            elif re.search(
                r"\b(lloguer|alquiler|rent\s*a\s*car|rentacar|sixt|europcar|hertz|avis|enterprise|goldcar|centauro|record\s*go|budget|ok\s*mobility)\b|"
                r"(?:alquiler\s*sin\s*conductor|lloguer\s*sense\s*conductor|contracte\s*de\s*lloguer|contrato\s*de\s*alquiler|vehicle\s*de\s*lloguer|veh[íi]culo\s*de\s*alquiler)",
                text,
                re.IGNORECASE,
            ):
                resultat["regim_adquisicio"] = "LLOGUER"
            elif re.search(
                r"(?:regim|r[eèé]gimen)[\s:]*(?:substituci[oó]|sustituci[oó]n)|\b(vehicle\s*de\s*substituci[oó]\s*temporal|veh[íi]culo\s*de\s*sustituci[oó]n\s*temporal|vehicle\s*de\s*cortesia|veh[íi]culo\s*de\s*cortes[íi]a)\b",
                text,
                re.IGNORECASE,
            ):
                resultat["regim_adquisicio"] = "SUBSTITUCIO"
            elif re.search(
                r"(?:es\s*el\s*propietario|propietari\s*del\s*vehicle|propietario\s*del\s*veh[íi]culo|compraventa|compra-venda|factura\s*de\s*compra|adquisici[oó]n\s*en\s*propiedad|adquisici[oó]\s*en\s*propietat|adquirido\s*en\s*propiedad|adquirit\s*en\s*propietat|en\s*propiedad|en\s*propietat|compra\s*directa|tomador\s*(?:y|i|\/)\s*propietario)|\b(compra|propietat|propiedad)\b",
                text,
                re.IGNORECASE,
            ):
                resultat["regim_adquisicio"] = "PROPIETAT"

        # LÍMIT DE QUILÒMETRES CONTRACTUAL
        if resultat["regim_adquisicio"] in ("RENTING", "LEASING", "LLOGUER"):
            lim_m = re.search(
                r"(?:L[ií]mit\s*(?:contractual|de\s*km|anual)?|L[ií]mite\s*(?:contractual|de\s*km|anual)?|Km\s*(?:m[aá]ximos|contractuales))[\s\w]*(?:km)?[\s:]*([0-9\.\, ]+)",
                text,
                re.IGNORECASE,
            )
            if lim_m:
                try:
                    clean_lim = re.sub(r"[^\d]", "", lim_m.group(1))
                    if clean_lim and int(clean_lim) >= 1000:
                        resultat["renting_limit_km"] = int(clean_lim)
                except ValueError:
                    pass
        else:
            resultat["renting_limit_km"] = None

        # 14. Detalls de Rènting Estès
        if resultat.get("regim_adquisicio") == "RENTING" or re.search(r"\b(arval|alphabet|leaseplan|ald\s*automotive|bansacar|northgate)\b", text, re.IGNORECASE):
            if re.search(r"\barval\b", text, re.IGNORECASE):
                resultat["empresa_renting"] = "Arval Service Lease"
            elif re.search(r"\balphabet\b", text, re.IGNORECASE):
                resultat["empresa_renting"] = "Alphabet"
            elif re.search(r"\bleaseplan\b", text, re.IGNORECASE):
                resultat["empresa_renting"] = "LeasePlan"
            elif re.search(r"\bbansacar\b", text, re.IGNORECASE):
                resultat["empresa_renting"] = "Bansacar"

            contracte_m = re.search(
                r"(?:ANEXO\s*CONTRATO\s*VEH[ÍI]CULO|ANEXO\s*CONTRATO|CONTRATO\s*VEH[ÍI]CULO)[\s:]*([A-Z0-9\-_]{5,})",
                text,
                re.IGNORECASE,
            ) or re.search(
                r"(?:REFERENCIA\s*CONTRATO\s*MAESTRO|REFERENCIA\s*CONTRATO|N[ÚU]M(?:\.|ERO)?\s*CONTRATO)[\s:]*([A-Z0-9\-_]{5,})",
                text,
                re.IGNORECASE,
            )
            if contracte_m:
                resultat["num_contracte_renting"] = contracte_m.group(1).strip()

            venc_rent_m = re.search(
                r"(?:FECHA\s*DE\s*FINALIZACI[OÓ]N\s*CONTRATO|Venciment\s*contracte|vencen\s*el\s*pr[oó]ximo)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
                text,
                re.IGNORECASE,
            )
            if venc_rent_m:
                resultat["data_venciment_renting"] = _normalitzar_data_iso(venc_rent_m.group(1))

        # 15. Titular (Codi UE C.1.1), Titular NIF (Codi UE C.1.2) i Arrendatari NIF
        titular_m = re.search(
            r"(?:(?:\(C\.1(?:\.1)?\)|C\.1(?:\.1)?)\s*(?:Apellidos\s*o\s*raz[oó]n\s*social|Cognoms\s*o\s*ra[oó]\s*social)|(?:\([A-Z0-9\.]+\)|[A-Z0-9\.]+\s*)?(?:Apellidos\s*o\s*raz[oó]n\s*social|Cognoms\s*o\s*ra[oó]\s*social|Tomador\s*(?:\/|\s*y\s*|\s*i\s*)\s*Asegurado|Tomador|Titular))[\s:]+([A-Za-z0-9À-ÿ\s\.,\-]+)",
            text,
            re.IGNORECASE,
        )
        if titular_m:
            cand_tit = titular_m.group(1).strip().splitlines()[0].strip("[](){}:;").strip()
            if len(cand_tit) > 3 and not any(cand_tit.lower().startswith(x) for x in ("ford", "renault", "iveco", "data", "nif", "cif", "datos")):
                resultat["titular"] = cand_tit

        nif_tit_m = re.search(
            r"(?:(?:\(C\.1\.2\)|C\.1\.2)\s*(?:Nombre\s*\/)?\s*NIF|(?:(?:Tomador|Propietari[ao]|Titular)[^\n\r]*?NIF[^\n\r]*?|NIF\s*\/\s*CIF[^\n\r]*?(?:Tomador|Propietari|Titular)))[\s:]*([A-HJ-NP-SU-W0-9][0-9]{7}[A-Z0-9]|[A-Z]-[0-9]{7,8}-[A-Z0-9]|[0-9]{8}[A-Z])",
            text,
            re.IGNORECASE,
        )
        if nif_tit_m:
            resultat["titular_nif"] = nif_tit_m.group(1).strip().replace(" ", "")

        nif_arr_m = re.search(
            r"(?:"
            r"ARRENDATARIO\s*(?:A\s*LARGO\s*PLAZO|LARGO\s*PLAZO)[\s:]*"
            r"|NIF\s*(?:\/\s*CIF)?\s*(?:del\s*)?Arrendatari[ao]?[\s:\-]+"
            r"|Arrendatari[ao]?[^\n\r:]*?(?:NIF|CIF)[\s:\-]+"
            r"|Arrendatari[ao]?[^\n\r]*\n\s*(?:-\s*)?(?:NIF|CIF|NIF\s*\/\s*CIF)[\s:\-]+"
            r")"
            r"([A-HJ-NP-SU-W0-9][0-9]{7}[A-Z0-9]|[0-9]{8}[A-Z])",
            text,
            re.IGNORECASE,
        )
        if nif_arr_m:
            resultat["arrendatari_nif"] = nif_arr_m.group(1).strip().replace(" ", "")

        # 16. Dades Pesants (Tacògraf, Targeta de transport REAT/MITMA, Visat)
        targeta_trans_m = re.search(
            r"(?:CLAU\s*I\s*N[ÚU]MERO\s*D'AUTORITZACI[OÓ]|AUTORIZACI[OÓ]N\s*DE\s*TRANSPORTE|TARGETA\s*MPC|TARJETA\s*MPC)[\s:]*([A-Z0-9 \-]+)",
            text,
            re.IGNORECASE,
        )
        if targeta_trans_m:
            dades_pesants_dict["targeta_transport_num"] = targeta_trans_m.group(1).strip()

        visat_trans_m = re.search(
            r"(?:DATA\s*PROPER\s*VISAT\s*OBLIGATORI|PR[OÓ]XIMO\s*VISADO\s*OBLIGATORIO)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if visat_trans_m:
            dades_pesants_dict["data_visat_transport"] = _normalitzar_data_iso(visat_trans_m.group(1))

        tac_m = re.search(r"(?:Tac[oó]grafo?\s*(?:Digital)?|Tac[oó]graf)[\s:]*([^\n\r]+)", text, re.IGNORECASE)
        if tac_m:
            cand_tac = tac_m.group(1).strip().splitlines()[0]
            if len(cand_tac) > 2:
                dades_pesants_dict["tacograf_model"] = cand_tac

        calib_tac_m = re.search(
            r"(?:v[aà]lida\s*fins\s*al|calibrado\s*hasta|fecha\s*calibrado|calibratge\s*tac[oó]graf)[\s:]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if calib_tac_m:
            dades_pesants_dict["data_calibratge_tacograf"] = _normalitzar_data_iso(calib_tac_m.group(1))

        if dades_pesants_dict:
            resultat["dades_pesants"] = dades_pesants_dict

        # 17. Equipament Homologat i Reformes Reglamentàries
        if re.search(r"\b(gr[uú]a|palfinger|hiab|fassi)\b", text, re.IGNORECASE):
            equipament_detectat.append("GRUA")
        if re.search(r"\btac[oó]grafo?\b", text, re.IGNORECASE):
            equipament_detectat.append("TACOGRAF")
        if re.search(r"\b(plataforma\s*elevadora|dhollandia|zepro)\b", text, re.IGNORECASE):
            equipament_detectat.append("PLATAFORMA ELEVADORA")
        if re.search(r"\b(enganche|ringfeder|bola\s*remolc|remolc|enganxall)\b", text, re.IGNORECASE):
            equipament_detectat.append("ENGANXALL")
        if re.search(r"\blimitador\s*de\s*velocidad\b", text, re.IGNORECASE):
            equipament_detectat.append("LIMITADOR VELOCITAT")
        if re.search(r"\b(caixa\s*oberta|caja\s*abierta|basculante)\b", text, re.IGNORECASE):
            equipament_detectat.append("CAIXA BASCULANT")

        resultat["equipament_homologat"] = sorted(list(set(equipament_detectat)))

        # 18. Tipus de document detectat
        if re.search(r"REGISTRE\s*REAT|TARGETA\s*MPC|AUTORITZACI[OÓ]\s*DE\s*TRANSPORT", text, re.IGNORECASE):
            resultat["tipus_document"] = "TARGETA_TRANSPORT"
        elif re.search(r"CERTIFICADO\s*DE\s*ARRENDAMIENTO|CONTRATO\s*DE\s*RENTING|RENTING\s*OPERATIVO", text, re.IGNORECASE):
            resultat["tipus_document"] = "CONTRACTE_RENTING"
        elif re.search(r"PERMISO\s*DE\s*CIRCULACI[OÓ]N|PERM[IÍ]S\s*DE\s*CIRCULACI[OÓ]", text, re.IGNORECASE):
            resultat["tipus_document"] = "PERMIS_CIRCULACIO"
        elif re.search(r"P[OÒÓ]LI(?:SS|[SZ])A|ASSEGURAN[CÇ]A|ASEGURADORA|PRIMA|TOMADOR|SEGURO\s*DE\s*VEH[IÍ]CULOS", text, re.IGNORECASE):
            resultat["tipus_document"] = "ASSEGURANCA"
        elif re.search(r"CONTRATO\s*DE\s*ALQUILER|ARRENDAMIENTO", text, re.IGNORECASE):
            resultat["tipus_document"] = "CONTRACTE"
        elif re.search(r"ITV|FITXA\s*T[EÈ]CNICA|INSPECCI[OÓ]|TARGETA\s*ITV", text, re.IGNORECASE):
            resultat["tipus_document"] = "ITV"
        elif re.search(r"REPARACI[OÓ]|TALLER|MANTENIMENT|CANVI\s*D'OLI", text, re.IGNORECASE):
            resultat["tipus_document"] = "MANTENIMENT"
        else:
            resultat["tipus_document"] = "GENERAL"

    # Suport d'IA si manca bastidor o matrícula
    if (not resultat["matricula"] or not resultat["bastidor"]) and node_ia_url:
        prompt = (
            "Ets un extractor OCR especialitzat en documentació de vehicles a Espanya (Fitxa Tècnica eITV, Permís de Circulació DGT, Pòlissa d'Assegurança, Contracte de Rènting i Targeta de Transport REAT/MITMA). "
            "Extreu les dades en un JSON estricte cercant explícitament els codis harmonitzats UE i camps següents (posa null si no es troba): "
            "- matricula: Codi (A) (4 dígits i 3 lletres, ex: '9104-MBB' o '4321-KMN') "
            "- data_matriculacio: Codi (B) 1a matriculació (YYYY-MM-DD) "
            "- titular: Codi (C.1.1) Raó social o cognoms del titular registral "
            "- titular_nif: Codi (C.1.2) NIF/CIF del titular "
            "- arrendatari_nif: NIF/CIF de l'arrendatari en cas de rènting/lloguer "
            "- marca: Codi (D.1) Marca del vehicle (ex: 'IVECO', 'RENAULT', 'FORD') "
            "- model: Codi (D.3) Denominació comercial (ex: 'EUROCARGO ML180E28') "
            "- bastidor: Codi (E) Número VIN de 17 caràcters alfanumèrics (ISO 3779, sense lletres I, O, Q) "
            "- mma_kg: Codi (F.2) Masa màxima autoritzada en kg (enter) "
            "- tara_kg: Codi (G) Masa en servei / tara en kg (enter) "
            "- carrega_util_kg: Capacitat màxima de càrrega útil en kg (enter) "
            "- mmr_amb_fre_kg: Codi (O.1.2) Masa màxima remolcable amb fre en kg (enter) "
            "- categoria_ue: Codi (J) Categoria del vehicle ('M1', 'N1', 'N2', 'N3') "
            "- servei_dgt: Servei al qual es destina ('A12' per a rènting/lloguer, 'B00' o 'B09' per a particular/obres i serveis propis) "
            "- tipus: Propulsió ('DIESEL', 'GASOLINA', 'EV', 'PHEV', 'MAQUINARIA', 'REMOLC') "
            "- distintiu_ambiental: Etiqueta DGT ('ZERO', 'ECO', 'C', 'B', 'SENSE') "
            "- odometre_acumulat: Quilòmetres actuals segons ITV o lectura (enter) "
            "- estat_itv: Resultat ITV ('FAVORABLE', 'FAVORABLE_LEUS', 'DESFAVORABLE', 'NEGATIVA') "
            "- data_proxima_itv: Data límit vigència ITV (YYYY-MM-DD) "
            "- data_inspeccio_itv: Data en què es va fer la inspecció (YYYY-MM-DD) "
            "- companyia_asseguradora: Entitat asseguradora "
            "- polissa_asseguranca: Número de pòlissa d'assegurança "
            "- data_caducitat_asseguranca: Data de venciment de l'assegurança (YYYY-MM-DD) "
            "- regim_adquisicio: ('PROPIETAT', 'RENTING', 'LEASING', 'LLOGUER', 'SUBSTITUCIO') "
            "- empresa_renting: Nom de l'empresa propietària o arrendadora en rènting "
            "- num_contracte_renting: Referència o número de contracte de rènting "
            "- data_venciment_renting: Data de finalització del rènting (YYYY-MM-DD) "
            "- renting_limit_km: Límit contractual de km anuals o totals (enter) "
            "- equipament_homologat: Array de textos amb equipament homologat o reformes (ex: ['GRUA', 'PLATAFORMA ELEVADORA', 'ENGANXALL', 'TACOGRAF']) "
            "- dades_pesants: Objecte amb camps de pesants: {'targeta_transport_num': str, 'data_visat_transport': YYYY-MM-DD, 'data_calibratge_tacograf': YYYY-MM-DD, 'tacograf_model': str} o null."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            if file_bytes.startswith(b"%PDF"):
                try:
                    import pymupdf
                    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                    if len(doc) > 0:
                        pix = doc[0].get_pixmap(dpi=150)
                        b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
                except Exception:
                    pass
            else:
                b64 = base64.b64encode(file_bytes).decode("utf-8")

        ai_res = await _cridar_ia_vision(prompt, text, b64, node_ia_url=node_ia_url)
        if ai_res:
            for k in resultat:
                if ai_res.get(k) is not None and not resultat.get(k):
                    resultat[k] = ai_res[k]
            if ai_res.get("mmr_amb_fre_kg") and not mmr_amb_fre_kg:
                try:
                    mmr_amb_fre_kg = int(ai_res["mmr_amb_fre_kg"])
                except (ValueError, TypeError):
                    pass
            if ai_res.get("servei_dgt") and not resultat.get("regim_adquisicio"):
                if str(ai_res["servei_dgt"]).upper() == "A12":
                    resultat["regim_adquisicio"] = "RENTING"
                elif str(ai_res["servei_dgt"]).upper() in ("B00", "B09"):
                    resultat["regim_adquisicio"] = "PROPIETAT"

    # =========================================================================
    # NORMALITZACIÓ POST-OCR DETERMINISTA (Python Pur, Sense confiar en el LLM)
    # =========================================================================

    # 1. Sanitització de Matrícula (Format Modern ^\d{4}-[BCDFGHJKLMNPRSTVWXYZ]{3}$ o Històric Provincial)
    if resultat.get("matricula"):
        raw_m = str(resultat["matricula"]).strip().upper()
        modern_m = re.match(r"^(\d{4})[ -]?([BCDFGHJKLMNPRSTVWXYZ]{3})$", raw_m)
        if modern_m:
            resultat["matricula"] = f"{modern_m.group(1)}-{modern_m.group(2)}"
        else:
            prov_m = re.match(r"^([A-Z]{1,2})[ -]?(\d{4})[ -]?([A-Z]{1,2})$", raw_m)
            if prov_m:
                resultat["matricula"] = f"{prov_m.group(1)}-{prov_m.group(2)}-{prov_m.group(3)}"
            else:
                prov2_m = re.match(r"^([A-Z]{1,2})[ -]?(\d{6})$", raw_m)
                if prov2_m:
                    resultat["matricula"] = f"{prov2_m.group(1)}-{prov2_m.group(2)}"

    # 2. Sanitització de VIN Bastidor (ISO 3779: 17 caràcters alfanumèrics excloent I, O, Q)
    if resultat.get("bastidor"):
        raw_vin = re.sub(r"[\s\-_]", "", str(resultat["bastidor"]).strip().upper())
        if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", raw_vin):
            resultat["bastidor"] = raw_vin
        elif len(raw_vin) == 17:
            # Correcció d'errors típics d'OCR (O -> 0, Q -> 0, I -> 1)
            fixed_vin = raw_vin.replace("O", "0").replace("Q", "0").replace("I", "1")
            if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", fixed_vin):
                resultat["bastidor"] = fixed_vin
        elif re.match(r"^[A-HJ-NPR-Z0-9]{11,18}$", raw_vin):
            resultat["bastidor"] = raw_vin

    # 3. Càlcul determinista de Càrrega Útil (kg) si no ve explícit
    if not resultat.get("carrega_util_kg") and resultat.get("mma_kg") and resultat.get("tara_kg"):
        if resultat["mma_kg"] > resultat["tara_kg"]:
            resultat["carrega_util_kg"] = resultat["mma_kg"] - resultat["tara_kg"]

    # 4. Lògica determinista de Pesants, Carnet Requerit i CAP
    # Si mma_kg > 3500 o categoria_ue in ("N2", "N3"): forçar carnet_necessari = "C" i requereix_cap = True
    # (o "C+E" si mmr_amb_fre_kg > 750 i porta enganxall)
    is_pesant = False
    if resultat.get("mma_kg") and resultat["mma_kg"] > 3500:
        is_pesant = True
    if resultat.get("categoria_ue") in ("N2", "N3", "M2", "M3"):
        is_pesant = True

    has_trailer = False
    if (mmr_amb_fre_kg and mmr_amb_fre_kg > 750) and (
        "ENGANXALL" in (resultat.get("equipament_homologat") or [])
        or "enganche" in text.lower()
        or "remolc" in text.lower()
    ):
        has_trailer = True

    if is_pesant:
        resultat["requereix_cap"] = True
        if has_trailer:
            resultat["carnet_necessari"] = "C+E"
        else:
            resultat["carnet_necessari"] = "C"
    else:
        resultat["requereix_cap"] = False
        if not resultat.get("carnet_necessari"):
            resultat["carnet_necessari"] = "B+E" if has_trailer else "B"

    # Assegurar consistència de límit km segons règim d'adquisició
    if resultat.get("regim_adquisicio") not in ("RENTING", "LEASING", "LLOGUER"):
        resultat["renting_limit_km"] = None

    trobat = bool(
        resultat.get("matricula")
        or resultat.get("bastidor")
        or (resultat.get("companyia_asseguradora") and resultat.get("polissa_asseguranca"))
        or (resultat.get("marca") and resultat.get("model"))
        or resultat.get("data_proxima_itv")
    )
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat


async def processar_ocr_proveidor(file_bytes: bytes, node_ia_url: Optional[str] = None) -> Dict[str, Any]:
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

    if (not resultat["nif"] or not resultat["rao_social"]) and node_ia_url:
        prompt = (
            "Extreu dades fiscals d'empresa o proveïdor en JSON: "
            "nif, rao_social, adreca, telefon, email."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64, node_ia_url=node_ia_url)
        if ai_res:
            for k in ("nif", "rao_social", "adreca", "telefon", "email"):
                if ai_res.get(k) and not resultat.get(k):
                    resultat[k] = ai_res[k]

    trobat = bool(resultat.get("nif") or resultat.get("rao_social"))
    resultat["status"] = ESTAT_EXTRET_AUTOMATIC if trobat else ESTAT_REVISIO_MANUAL
    resultat["confidence"] = 0.95 if trobat else 0.0
    return resultat


async def processar_tiquet_ocr(file_bytes: bytes, node_ia_url: Optional[str] = None) -> Dict[str, Any]:
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
    if resultat["import_euros"] is None and node_ia_url:
        prompt = (
            "Ets un extractor OCR de tiquets de benzina i despeses. "
            "Retorna únicament un JSON amb: import_euros (float), litres (float o null), data_tiquet (YYYY-MM-DD), nif_emissor (str)."
        )
        b64 = None
        if not text and len(file_bytes) > 0:
            b64 = base64.b64encode(file_bytes).decode("utf-8")
        ai_res = await _cridar_ia_vision(prompt, text, b64, node_ia_url=node_ia_url)
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
