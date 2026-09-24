import csv
import io
from typing import Any, Dict, List, Type, Tuple
from pydantic import BaseModel, ValidationError

class CsvImportResult(BaseModel):
    total_processats: int
    inserits: int
    errors_detectats: List[Dict[str, Any]]
    
def parse_and_validate_csv(
    file_content: bytes, 
    schema_class: Type[BaseModel]
) -> Tuple[List[BaseModel], List[Dict[str, Any]]]:
    """
    Llegeix el contingut d'un CSV (en bytes) i el valida contra un model Pydantic.
    Retorna una tupla amb:
      - llista d'instàncies validades del model.
      - llista d'errors detallats (fila, columna, valor original, motiu).
    """
    decoded_content = file_content.decode('utf-8-sig') # '-sig' elimina el BOM si l'Excel el posa
    reader = csv.DictReader(io.StringIO(decoded_content), delimiter=',')
    
    valid_records = []
    errors = []
    
    # La fila 1 és la capçalera, les dades comencen a la fila 2
    row_number = 2 
    
    for row in reader:
        # Netejem els valors en blanc per considerar-los None si cal
        clean_row = {k.strip(): (v.strip() if v.strip() != "" else None) for k, v in row.items() if k}
        
        try:
            valid_record = schema_class(**clean_row)
            valid_records.append(valid_record)
        except ValidationError as e:
            for err in e.errors():
                # L'error de Pydantic indica on ha fallat a 'loc'
                col_name = str(err["loc"][0]) if err.get("loc") else "desconeguda"
                motiu = err.get("msg", "Error de validació")
                valor_original = clean_row.get(col_name, "")
                
                errors.append({
                    "fila": row_number,
                    "columna": col_name,
                    "valor": str(valor_original) if valor_original is not None else "",
                    "motiu": motiu
                })
                
        row_number += 1
        
    return valid_records, errors

def generate_csv_content(records: List[Dict[str, Any]], fieldnames: List[str]) -> io.StringIO:
    """
    Genera un contingut CSV a partir d'una llista de diccionaris.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=',')
    writer.writeheader()
    for row in records:
        writer.writerow(row)
    return output
