import pytest
import io
import csv
from sqlalchemy import select, text
from app.models.models import Client

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_csv_import_success_and_errors(async_client, db_session):
    # 1. Preparem un CSV mixt (registres vàlids i invàlids/amb dades faltants)
    # CLI_OK1: Vàlid
    # CLI_OK2: Vàlid, sense telefon ni email (que són opcionals)
    # CLI_ERR1: Sense NIF (obligatori)
    # CLI_ERR2: Codi massa llarg (>20 chars) o NIF massa llarg
    csv_content = """codi,rao_social,nif,telefon,email,adreca_fiscal,iban
CLI_OK1,Client Valid 1,B11111111,600111111,test1@mail.com,Carrer Fals 123,
CLI_OK2,Client Valid 2,B22222222,,,,
CLI_ERR1,Client Error 1,,600333333,test3@mail.com,,
CLI_ERR2,Client Error 2,B33333333333333333333333333333,600444444,test4@mail.com,,
"""
    file_bytes = csv_content.encode('utf-8')
    files = {"file": ("test_clients.csv", io.BytesIO(file_bytes), "text/csv")}

    # 2. Executem l'endpoint d'importació
    response = await async_client.post("/gestio/clients/import", files=files)
    
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    
    # 3. Comprovem la resposta estructurada
    assert "total_processats" in data
    assert "inserits" in data
    assert "errors_detectats" in data
    
    # Dels 4 registres: 2 haurien de ser inserits, i 2 haurien de donar error.
    assert data["inserits"] == 2
    
    errors = data["errors_detectats"]
    assert len(errors) == 2
    
    # Busquem els detalls dels errors
    error_nif_buit = next((e for e in errors if e["fila"] == 4), None) # Fila 4 = CLI_ERR1 (Fila 1 capçalera)
    assert error_nif_buit is not None
    assert error_nif_buit["columna"] == "nif"
    assert "String should have at least 1 character" in error_nif_buit["motiu"] or "field required" in error_nif_buit["motiu"] or "value is not a valid" in error_nif_buit["motiu"] or "string_too_short" in error_nif_buit["motiu"]

    error_nif_llarg = next((e for e in errors if e["fila"] == 5), None) # Fila 5 = CLI_ERR2
    assert error_nif_llarg is not None
    assert error_nif_llarg["columna"] == "nif"

    # 4. Comprovem l'escriptura real a la Base de Dades per garantir que no hi ha errors de tipus (Type errors)
    # L'usuari del test pertany a una empresa, ho busquem globalment perquè és BD de tests
    result = await db_session.execute(select(Client).where(Client.codi.in_(["CLI_OK1", "CLI_OK2"])))
    clients_db = result.scalars().all()
    
    assert len(clients_db) == 2
    c1 = next(c for c in clients_db if c.codi == "CLI_OK1")
    assert c1.rao_social == "Client Valid 1"
    assert c1.nif == "B11111111"

async def test_csv_export_endpoint(async_client, db_session):
    # Assegurem que l'exportació retorna CSV i inclou les dades prèvies inserides
    response = await async_client.get("/gestio/clients/export")
    
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=clients_export.csv" in response.headers["content-disposition"]
    
    csv_text = response.text
    # Verifiquem que els clients prèviament inserits estan en el CSV exportat
    assert "codi,rao_social,nif,telefon,email,adreca_fiscal,actiu" in csv_text
    assert "CLI_OK1,Client Valid 1,B11111111" in csv_text
    assert "CLI_OK2,Client Valid 2,B22222222" in csv_text
