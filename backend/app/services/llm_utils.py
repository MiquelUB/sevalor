"""Utilitats segures per a inferència LLM local, neteja de `<think>`, anti-injecció i guardes deterministes."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("llm_utils")

# Regex per netejar blocs de raonament <think>...</think> (tancats o truncats per max_tokens)
_THINK_CLOSED_RE = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
_THINK_UNCLOSED_RE = re.compile(r"<think>.*$", flags=re.IGNORECASE | re.DOTALL)

# Caràcters de control ASCII prohibits (conservant \n, \r, \t) — AGENTS.md §3.5
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Detecció de narració d'eines internes o noms de funcions filtrats en prosa
NARRACIO_EINA_RE = re.compile(
    r"(?:utilitz\w*|usar\w*|crid\w+|execut\w+|invoc\w+|fent\s+servir|farem\s+servir)"
    r"\s+(?:l['’]eina|la\s+eina|la\s+herramienta|la\s+funci[oó]|el\s+m[eè]tode)"
    r"|\b(?:get|propose|check|send|extract|audit|reconcile|detect|notify|receive|search|generar|replanificar)_[a-z0-9_]+\b"
    r"|\btool_calls?\b"
    r"|\bfunction_call\b",
    flags=re.IGNORECASE,
)

# Extracció de números (suporta format català 4.850,00 i anglès 327.0 / 14,5)
_NUM_TOKEN_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ0-9_])"
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
    r"(?![A-Za-zÀ-ÿ0-9_])"
)

# Prefix de llista numerada Markdown ("1. ", "2) ") al començament de línia
_MD_LIST_PREFIX_RE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s+")

# Codi d'identificador alfanumèric amb números (OT-2026-001, PE-100, 1234-XYZ, 1234XYZ) per no confondre'l amb xifres inventades
_CODE_TOKEN_RE = re.compile(
    r"\b(?:OT|PRES|CLI|CAB|TUB|SN|REF)[-_A-Z0-9]+\b"
    r"|\b[A-Z]{2,8}[-_][A-Z0-9]+(?:[-_][A-Z0-9]+)*\b"
    r"|\b\d{4}[-\s]?[A-Z]{3}\b",
    flags=re.IGNORECASE,
)

# Separador de milers català estricte: mai comença per 0. (evita confondre floats 0.125 amb 125)
_CATALAN_THOUSANDS_RE = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?")
_AMBIGUOUS_THREE_DEC_RE = re.compile(r"[1-9]\d{0,2}\.\d{3}")

# Dates i hores ISO (p.ex. 2026-05-03T09:30:00) perquè 03 i 09 adjacents a 'T' entrin a la font
_ISO_DATETIME_RE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?\b"
)

# Unitats tècniques enganxades a dades_json (p.ex. "24V", "10mm", "5kg", "10%", "25€")
_SOURCE_UNIT_NUM_RE = re.compile(
    r"(?<![A-Za-z])(\d+(?:[.,]\d+)?)\s*(?:kWh|kW|MW|mA|bar|min|cm|mm|km|kg|mg|V|W|A|m|g|l|h|%|€)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def strip_think(text: Optional[str]) -> str:
    """Elimina blocs `<think>...</think>` tancats i també blocs `<think>` truncats sense tancar."""
    if not text:
        return ""
    cleaned = _THINK_CLOSED_RE.sub("", text)
    cleaned = _THINK_UNCLOSED_RE.sub("", cleaned)
    return cleaned.strip()


def sanitize_llm_text(text: Optional[str], *, max_length: int = 2000) -> str:
    """Elimina caràcters de control i acota la longitud d'entrades abans de passar-les al LLM."""
    if not text:
        return ""
    cleaned = _CONTROL_CHARS_RE.sub("", str(text)).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def escape_data_block(raw_text: str, tag: str = "dades_empresa") -> str:
    """Escapa qualsevol etiqueta de tancament/obertura del bloc de dades (defensa anti Prompt-Injection)."""
    if not raw_text:
        return ""
    pattern = re.compile(rf"</?{re.escape(tag)}\s*>", flags=re.IGNORECASE)
    return pattern.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), raw_text)


def conte_narracio_eina(text: Optional[str]) -> bool:
    """Retorna True si el text del model narra eines internes o filtra noms de funcions."""
    if not text:
        return False
    return bool(NARRACIO_EINA_RE.search(text))


def _parse_number_token(token: str, *, allow_thousands_dot: bool = True) -> Optional[Decimal]:
    """Converteix un token numèric (format català o estàndard) a `Decimal` normalitzat."""
    raw = token.strip()
    if not raw:
        return None
    if allow_thousands_dot and _CATALAN_THOUSANDS_RE.fullmatch(raw):
        norm = raw.replace(".", "").replace(",", ".")
    else:
        norm = raw.replace(",", ".")
    try:
        return Decimal(norm).normalize()
    except InvalidOperation:
        return None


def _expand_decimal_variants(val: Decimal) -> Set[Decimal]:
    """Genera variants arrodonides legítimes (0, 1 i 2 decimals) d'un valor font."""
    variants: Set[Decimal] = {val.normalize()}
    for q in (Decimal("1"), Decimal("0.1"), Decimal("0.01")):
        try:
            variants.add(val.quantize(q).normalize())
        except InvalidOperation:
            pass
    return variants


def _extract_decimals_from_text(
    text: str, *, strip_md_lists: bool = False, allow_thousands_dot: bool = True
) -> List[Tuple[str, Decimal]]:
    """Extreu parells `(token_original, Decimal)` d'un text."""
    if not text:
        return []
    work = _MD_LIST_PREFIX_RE.sub("", text) if strip_md_lists else text
    found: List[Tuple[str, Decimal]] = []
    for m in _NUM_TOKEN_RE.finditer(work):
        tok = m.group(0)
        dec = _parse_number_token(tok, allow_thousands_dot=allow_thousands_dot)
        if dec is not None:
            found.append((tok, dec))
    return found


def _collect_source_text_extras(text: str, font_decimals: Set[Decimal]) -> None:
    """Extreu components de dates/hores ISO i números seguits d'unitats tècniques d'un text font."""
    if not text:
        return
    for iso_m in _ISO_DATETIME_RE.finditer(text):
        for grp in iso_m.groups():
            if grp is not None:
                d = _parse_number_token(grp, allow_thousands_dot=False)
                if d is not None:
                    font_decimals.add(d)
    for unit_m in _SOURCE_UNIT_NUM_RE.finditer(text):
        tok = unit_m.group(1)
        d = _parse_number_token(tok, allow_thousands_dot=True)
        if d is not None:
            font_decimals.update(_expand_decimal_variants(d))


def extract_whitelisted_numbers(text: str) -> List[float]:
    """Extreu totes les xifres vàlides d'un text de configuració (p.ex. idiosincràsia/SLA) per a `extra_whitelist`."""
    if not text:
        return []
    out: List[float] = []
    seen: Set[float] = set()
    decimals: Set[Decimal] = set()
    for _, dec in _extract_decimals_from_text(text, allow_thousands_dot=True):
        decimals.update(_expand_decimal_variants(dec))
    _collect_source_text_extras(text, decimals)
    for d in decimals:
        val = float(d)
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _collect_json_source_decimals(dades_json: Any) -> Set[Decimal]:
    """Recull tots els números reals de `dades_json` distingint floats/ints JSON de strings catalans."""
    font_decimals: Set[Decimal] = {Decimal("0").normalize()}
    parsed: Any
    if isinstance(dades_json, (dict, list)):
        parsed = dades_json
    else:
        raw_str = "" if dades_json is None else str(dades_json)
        try:
            parsed = json.loads(raw_str)
        except Exception:
            for _, dec in _extract_decimals_from_text(raw_str, allow_thousands_dot=False):
                font_decimals.update(_expand_decimal_variants(dec))
            _collect_source_text_extras(raw_str, font_decimals)
            return font_decimals

    def _walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            try:
                font_decimals.update(_expand_decimal_variants(Decimal(str(node))))
            except InvalidOperation:
                pass
            return
        if isinstance(node, str):
            for _, dec in _extract_decimals_from_text(node, allow_thousands_dot=True):
                font_decimals.update(_expand_decimal_variants(dec))
            _collect_source_text_extras(node, font_decimals)
            for code in _CODE_TOKEN_RE.findall(node):
                for digits in re.findall(r"\d+", code):
                    d = _parse_number_token(digits, allow_thousands_dot=False)
                    if d is not None:
                        font_decimals.add(d)
            return
        if isinstance(node, list):
            font_decimals.add(Decimal(len(node)).normalize())
            for item in node:
                _walk(item)
            return
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)

    _walk(parsed)
    return font_decimals


def xifres_inventades(
    resposta: str,
    dades_json: Any,
    *,
    pregunta: str = "",
    ara_str: str = "",
    extra_whitelist: Optional[Iterable[int | float | Decimal]] = None,
) -> List[str]:
    """Detecta xifres presents a `resposta` que no provenen de `dades_json`, la `pregunta` ni el context temporal."""
    if not resposta:
        return []

    font_decimals = _collect_json_source_decimals(dades_json)

    # També admetem números dins codis alfanumèrics presents al JSON en brut (p.ex. 2026, 001 de OT-2026-001, 1234 de 1234XYZ)
    raw_json_str = (
        json.dumps(dades_json, ensure_ascii=False, default=str)
        if isinstance(dades_json, (dict, list))
        else str(dades_json or "")
    )
    for code in _CODE_TOKEN_RE.findall(raw_json_str):
        for digits in re.findall(r"\d+", code):
            d = _parse_number_token(digits, allow_thousands_dot=False)
            if d is not None:
                font_decimals.add(d)

    # Whitelist de xifres provinents de la pregunta de l'usuari i de la data/hora actual
    for ctx_text in (pregunta, ara_str):
        for _, dec in _extract_decimals_from_text(ctx_text, allow_thousands_dot=True):
            font_decimals.update(_expand_decimal_variants(dec))
        for digits in re.findall(r"\d+", ctx_text or ""):
            d = _parse_number_token(digits, allow_thousands_dot=False)
            if d is not None:
                font_decimals.add(d)

    if extra_whitelist:
        for item in extra_whitelist:
            try:
                font_decimals.update(_expand_decimal_variants(Decimal(str(item))))
            except InvalidOperation:
                pass

    inventades: List[str] = []
    for tok, dec in _extract_decimals_from_text(resposta, strip_md_lists=True, allow_thousands_dot=True):
        if dec in font_decimals:
            continue
        # Si a la resposta apareix p.ex. "1.234", acceptar-lo també si correspon al float JSON 1.234
        if _AMBIGUOUS_THREE_DEC_RE.fullmatch(tok):
            dec_float = _parse_number_token(tok, allow_thousands_dot=False)
            if dec_float is not None and dec_float in font_decimals:
                continue
        inventades.append(tok)
    return inventades


def triar_resposta(
    resp_llm: Optional[str],
    resp_local: Optional[str],
    execucions: Sequence[Dict[str, Any]],
    dades_json: str,
    *,
    es_domini_operatiu: bool = True,
    pregunta: str = "",
    ara_str: str = "",
    extra_whitelist: Optional[Iterable[int | float | Decimal]] = None,
) -> Tuple[str, str]:
    """
    Guarda determinista final del Coordinador (FR-019 / FR-023):
    - Mai deixa passar blocs `<think>` ni narració d'eines internes.
    - En consultes de domini operatiu exigeix execucions reals i zero xifres inventades.
    - Si qualsevol guarda falla, retorna sempre la resposta determinista del(s) subagent(s).

    Retorna `(text_final, mode_resposta)` on `mode_resposta` ∈ `{"llm", "determinista", "buit"}`.
    """
    llm_net = strip_think(resp_llm)

    if not es_domini_operatiu:
        if llm_net and not conte_narracio_eina(llm_net):
            return llm_net, "llm"
        if llm_net:
            logger.warning("triar_resposta ha descartat resposta conversacional per narració d'eina.")
        if resp_local and resp_local.strip():
            return resp_local.strip(), "determinista"
        return "Com et puc ajudar avui?", "buit"

    if llm_net and bool(execucions):
        te_narracio = conte_narracio_eina(llm_net)
        inventades = (
            []
            if te_narracio
            else xifres_inventades(
                llm_net,
                dades_json,
                pregunta=pregunta,
                ara_str=ara_str,
                extra_whitelist=extra_whitelist,
            )
        )
        if not te_narracio and not inventades:
            return llm_net, "llm"
        logger.warning(
            "triar_resposta ha rebutjat resposta LLM (narracio=%s, xifres_inventades=%s); "
            "es fa fallback determinista.",
            te_narracio,
            inventades,
        )

    if resp_local and resp_local.strip():
        return resp_local.strip(), "determinista"

    return "No he trobat dades registrades per a aquesta consulta al disc dur de l'empresa.", "buit"


def apply_qwen3_no_think(
    model_name: Optional[str],
    messages: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Afegeix `/no_think` al darrer missatge d'usuari quan el model pertany a la família Qwen3.

    Manté `messages[0]` (system prompt) byte a byte intacte per al KV-cache i evita
    que Qwen3 consumeixi `max_tokens` i latència raonant abans d'emetre la resposta.
    """
    msg_list: List[Dict[str, Any]] = [dict(m) for m in messages]
    if "qwen3" not in (model_name or "").lower():
        return msg_list
    for idx in range(len(msg_list) - 1, -1, -1):
        msg = msg_list[idx]
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str) and "/no_think" not in content:
                msg["content"] = f"{content.rstrip()}\n/no_think"
            break
    return msg_list
