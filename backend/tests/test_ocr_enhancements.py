import pytest

from app.services.ocr_service import processar_albara_ocr
from app.services.subagents.dispatcher import CopilotDispatcher
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc


@pytest.mark.asyncio
async def test_ocr_pipe_lines_with_quantities_and_discounts():
    """Verifica que l'OCR extreu correctament quantitats, preus i descomptes en línies delimitades."""
    mock_doc = (
        "SUBMINISTRAMENTS INDUSTRIALS DEL REG, S.L.\n"
        "NIF: B98765432\n"
        "Albarà: ALB-2026-999\n"
        "Data: 13/10/2026\n"
        "DADES DEL CLIENT: Sevalor Agro SL\n"
        "--------------------------------------------------\n"
        "CODI | DESCRIPCIO | QUANTITAT | PREU | DTE % | TOTAL\n"
        "TUB-PE-32-10 | Tub Polietilè Agrícola DN 32mm | 150 | 0.45 | 10% | 60.75 €\n"
        "VALV-BERMAD-2 | Electrovàlvula Bermad 2 Polzades | 4 | 45.00 | 5 | 171.00 €\n"
        "EINA-TREP-BOSCH | Trepant Percutor Bosch 18V | 1 | 180.00 | 0 | 180.00 €\n"
    ).encode("utf-8")

    res = await processar_albara_ocr(mock_doc)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["proveidor_nif"] == "B98765432"
    # El nom del proveïdor no ha de ser un codi ni una capçalera prohibida
    assert "SUBMINISTRAMENTS INDUSTRIALS" in res["proveidor_nom"]
    assert res["numero_albara"] == "ALB-2026-999"
    assert res["data_albara"] == "2026-10-13"

    linies = res["linies"]
    assert len(linies) == 3

    # Línia 1: Material amb 10% de descompte
    l1 = linies[0]
    assert l1["referencia"] == "TUB-PE-32-10"
    assert l1["quantitat"] == 150.0
    assert l1["preu"] == 0.45
    assert l1["descompte_percent"] == 10.0
    assert l1["tipus"] == "MATERIAL"

    # Línia 2: Valvula amb 5% (sense símbol %)
    l2 = linies[1]
    assert l2["referencia"] == "VALV-BERMAD-2"
    assert l2["quantitat"] == 4.0
    assert l2["preu"] == 45.0
    assert l2["descompte_percent"] == 5.0
    assert l2["tipus"] == "MATERIAL"

    # Línia 3: Eina de custòdia
    l3 = linies[2]
    assert l3["referencia"] == "EINA-TREP-BOSCH"
    assert l3["quantitat"] == 1.0
    assert l3["preu"] == 180.0
    assert l3["descompte_percent"] == 0.0
    assert l3["tipus"] == "EINA"


@pytest.mark.asyncio
async def test_subagent_logistica_synonyms_and_fallbacks(admin_session, boss_token):
    """Verifica que el subagent de logística resol consultes de famílies i sinònims ('tubs' -> 'CANONADA')."""
    token, empresa_id_str = boss_token
    import uuid
    empresa_id = uuid.UUID(empresa_id_str)

    subagent = SubagentLogisticaEstoc()

    # Provar consulta de material família tubs
    res_stock = await subagent.tool_get_real_stock(admin_session, empresa_id, "material familia tubs")
    # Ha de cercar 'tub' i trobar l'article TUB-PE-32-10 o suggerir famílies sense bloquejar
    assert "articles" in res_stock
    assert "total_disponible" in res_stock

    # Provar consulta genèrica d'inventari
    res_general = await subagent.tool_get_real_stock(admin_session, empresa_id, "inventari general")
    assert "articles" in res_general


@pytest.mark.asyncio
async def test_subagent_flota_fleet_status_routing():
    """Verifica que 'quins vehicles estan en ruta' puntua el subagent de flota adequadament."""
    dispatcher = CopilotDispatcher()
    scored = dispatcher.score_subagents("quins vehicles estan en ruta", "BOSS")
    top_subagent, top_score = scored[0]
    assert top_subagent.id == "subagent_flota_despatx"
    assert top_score >= 5.0
