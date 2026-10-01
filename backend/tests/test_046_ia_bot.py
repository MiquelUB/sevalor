import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_ia_rag_endpoint(async_client: AsyncClient, headers: dict):
    """Comprova que l'endpoint /rag_chat de l'IA retorna correctament i respecta l'autorització."""
    payload = {"prompt": "Com s'instal·la la bomba model X?"}
    
    response = await async_client.post(
        "/gestio/copilot/rag",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "resposta" in data
    assert "PENDENT_IMPLEMENTACIO" in data["resposta"]

def test_telegram_bot_compiles():
    """Només verifica que el fitxer del bot es pot importar sense errors de sintaxi."""
    try:
        from app.bot.main import bot_router
        assert bot_router is not None
        assert bot_router.name == "sevalor_bot_router"
    except ImportError as e:
        pytest.fail(f"No s'ha pogut importar el bot: {e}")

def test_worker_sincronitzar_documents():
    """Comprova que la task s'ha registrat i es pot cridar localment."""
    from app.workers.tasks import sincronitzar_documents_vectorials
    
    resultat = sincronitzar_documents_vectorials("empresa_test", ["doc1"])
    assert resultat["status"] == "COMPLETED"
    assert resultat["empresa_id"] == "empresa_test"
    assert resultat["processats"] == 1
