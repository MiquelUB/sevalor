"""Utilitats segures per a inferència LLM local, neteja de `<think>`, anti-injecció i guardes deterministes."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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

# Codi d'identificador alfanumèric amb números (OT-2026-001, PE-100, 1234-XYZ) per no confondre'l amb xifres inventades
_CODE_TOKEN_RE = re.compile(r"\b(?:OT|PRES|CLI|CAB|TUB|SN|REF)[-_A-Z0-9]+\b", flags=re.IGNORECASE)


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


def _parse_number_token(token: str) -> Optional[Decimal]:
    """Converteix un token numèric (format català o estàndard) a `Decimal` normalitzat."""
    raw = token.strip()
    if not raw:
        return None
    # Format de milers amb punt: 4.850 o 4.850,25
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
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


def _extract_decimals_from_text(text: str, *, strip_md_lists: bool = False) -> List[Tuple[str, Decimal]]:
    """Extreu parells `(token_original, Decimal)` d'un text."""
    if not text:
        return []
    work = _MD_LIST_PREFIX_RE.sub("", text) if strip_md_lists else text
    found: List[Tuple[str, Decimal]] = []
    for m in _NUM_TOKEN_RE.finditer(work):
        tok = m.group(0)
        dec = _parse_number_token(tok)
        if dec is not None:
            found.append((tok, dec))
    return found


def _extract_json_array_lengths(dades_json: str) -> Set[Decimal]:
    """Extreu les longituds de totes les llistes dins del JSON (per permetre recomptes reals a la síntesi)."""
    lengths: Set[Decimal] = set()
    try:
        parsed = json.loads(dades_json)
    except Exception:
        return lengths

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            lengths.add(Decimal(len(node)).normalize())
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)

    _walk(parsed)
    return lengths


def xifres_inventades(
    resposta: str,
    dades_json: str,
    *,
    pregunta: str = "",
    ara_str: str = "",
    extra_whitelist: Optional[Iterable[int | float | Decimal]] = None,
) -> List[str]:
    """Detecta xifres presents a `resposta` que no provenen de `dades_json`, la `pregunta` ni el context temporal."""
    if not resposta:
        return []

    font_decimals: Set[Decimal] = {Decimal("0").normalize()}

    for _, dec in _extract_decimals_from_text(dades_json):
        font_decimals.update(_expand_decimal_variants(dec))

    # També admetem números dins codis alfanumèrics presents a les dades (p.ex. 2026, 001 de OT-2026-001)
    for code in _CODE_TOKEN_RE.findall(dades_json):
        for digits in re.findall(r"\d+", code):
            d = _parse_number_token(digits)
            if d is not None:
                font_decimals.add(d)

    # Recomptes reals d'arrays presents a les dades JSON
    font_decimals.update(_extract_json_array_lengths(dades_json))

    # Whitelist de xifres provinents de la pregunta de l'usuari i de la data/hora actual
    for ctx_text in (pregunta, ara_str):
        for _, dec in _extract_decimals_from_text(ctx_text):
            font_decimals.update(_expand_decimal_variants(dec))
        for digits in re.findall(r"\d+", ctx_text or ""):
            d = _parse_number_token(digits)
            if d is not None:
                font_decimals.add(d)

    if extra_whitelist:
        for item in extra_whitelist:
            try:
                font_decimals.update(_expand_decimal_variants(Decimal(str(item))))
            except InvalidOperation:
                pass

    inventades: List[str] = []
    for tok, dec in _extract_decimals_from_text(resposta, strip_md_lists=True):
        if dec not in font_decimals:
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
        if resp_local and resp_local.strip():
            return resp_local.strip(), "determinista"
        return "Com et puc ajudar avui?", "buit"

    if (
        llm_net
        and bool(execucions)
        and not conte_narracio_eina(llm_net)
        and not xifres_inventades(llm_net, dades_json, pregunta=pregunta, ara_str=ara_str)
    ):
        return llm_net, "llm"

    if resp_local and resp_local.strip():
        return resp_local.strip(), "determinista"

    return "No he trobat dades registrades per a aquesta consulta al disc dur de l'empresa.", "buit"
