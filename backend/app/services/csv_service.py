import csv
import io
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


class CsvImportResult(BaseModel):
    total_processats: int
    inserits: int
    errors_detectats: List[Dict[str, Any]]


def _decode_csv_bytes(file_content: bytes) -> str:
    """Descodifica bytes CSV suportant UTF-8 (amb o sense BOM), Windows-1252 i Latin-1."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_content.decode("utf-8", errors="replace")


def _detect_csv_delimiter(decoded_content: str) -> str:
    """Detecta el delimitador de la capçalera (',' vs ';' vs '\\t')."""
    for line in decoded_content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        best_delim = ","
        best_cols = 1
        for delim in (",", ";", "\t"):
            try:
                cols = next(csv.reader([stripped], delimiter=delim))
                if len(cols) > best_cols:
                    best_cols = len(cols)
                    best_delim = delim
            except csv.Error:
                continue
        return best_delim
    return ","


def _normalize_header(raw_header: str, column_aliases: Optional[Dict[str, str]] = None) -> str:
    """Normalitza el nom d'una columna CSV i aplica àlies opcionals."""
    cleaned = raw_header.strip().lstrip("\ufeff")
    ascii_str = "".join(
        ch for ch in unicodedata.normalize("NFKD", cleaned) if not unicodedata.combining(ch)
    )
    norm = re.sub(r"[\s\-/]+", "_", ascii_str.lower()).strip("_")
    if column_aliases and norm in column_aliases:
        return column_aliases[norm]
    return norm if norm else cleaned


def parse_and_validate_csv_with_rows(
    file_content: bytes,
    schema_class: Type[TModel],
    column_aliases: Optional[Dict[str, str]] = None,
) -> Tuple[List[Tuple[int, TModel]], List[Dict[str, Any]]]:
    """
    Llegeix el contingut d'un CSV (en bytes) i el valida contra un model Pydantic.
    Retorna una tupla amb:
      - llista de tuples (número de fila, instància validada del model).
      - llista d'errors detallats (fila, columna, valor original, motiu).
    """
    decoded_content = _decode_csv_bytes(file_content)
    if not decoded_content.strip():
        return [], [
            {
                "fila": 1,
                "columna": "fitxer",
                "valor": "",
                "motiu": "El fitxer CSV està buit o no té capçalera",
            }
        ]

    delimiter = _detect_csv_delimiter(decoded_content)
    reader = csv.DictReader(io.StringIO(decoded_content), delimiter=delimiter)
    if not reader.fieldnames:
        return [], [
            {
                "fila": 1,
                "columna": "fitxer",
                "valor": "",
                "motiu": "El fitxer CSV no té capçalera vàlida",
            }
        ]

    valid_records: List[Tuple[int, TModel]] = []
    errors: List[Dict[str, Any]] = []

    for row in reader:
        row_number = reader.line_num
        clean_row: Dict[str, Any] = {}
        for k, v in row.items():
            if not k:
                continue
            norm_key = _normalize_header(k, column_aliases)
            if isinstance(v, str):
                stripped = v.strip()
                clean_row[norm_key] = stripped if stripped != "" else None
            else:
                clean_row[norm_key] = None

        if not any(val is not None for val in clean_row.values()):
            continue

        try:
            valid_record = schema_class(**clean_row)
            valid_records.append((row_number, valid_record))
        except ValidationError as e:
            for err in e.errors():
                col_name = str(err["loc"][0]) if err.get("loc") else "desconeguda"
                motiu = err.get("msg", "Error de validació")
                valor_original = clean_row.get(col_name, "")

                errors.append(
                    {
                        "fila": row_number,
                        "columna": col_name,
                        "valor": str(valor_original) if valor_original is not None else "",
                        "motiu": motiu,
                    }
                )

    return valid_records, errors


def parse_and_validate_csv(
    file_content: bytes,
    schema_class: Type[TModel],
    column_aliases: Optional[Dict[str, str]] = None,
) -> Tuple[List[TModel], List[Dict[str, Any]]]:
    """
    Llegeix el contingut d'un CSV (en bytes) i el valida contra un model Pydantic.
    Retorna una tupla amb:
      - llista d'instàncies validades del model.
      - llista d'errors detallats (fila, columna, valor original, motiu).
    """
    rows, errors = parse_and_validate_csv_with_rows(
        file_content, schema_class, column_aliases=column_aliases
    )
    return [record for _, record in rows], errors


def generate_csv_content(records: List[Dict[str, Any]], fieldnames: List[str]) -> io.StringIO:
    """
    Genera un contingut CSV a partir d'una llista de diccionaris.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=",")
    writer.writeheader()
    for row in records:
        writer.writerow(row)
    return output
