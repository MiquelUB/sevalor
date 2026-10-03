import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ia_rag_sense_node_ia_retorna_503(async_client: AsyncClient, headers: dict):
    """Sense node LM Studio, /rag NO ha d'inventar text: retorna 503 (Zero Mock Data)."""
    response = await async_client.post(
        "/gestio/copilot/rag",
        json={"prompt": "Com s'instal·la la bomba model X?"},
        headers=headers,
    )

    assert response.status_code == 503, f"Expected 503, got {response.status_code}: {response.text}"
    assert "simulada" not in response.text.lower()


@pytest.mark.asyncio
async def test_ia_rag_prompt_buit_retorna_422(async_client: AsyncClient, headers: dict):
    response = await async_client.post(
        "/gestio/copilot/rag",
        json={"prompt": "\x00\x01\x02   "},
        headers=headers,
    )
    assert response.status_code == 422


def test_sanititzar_prompt_elimina_control_i_limita():
    from app.api.v1.gestio.ia import MAX_PROMPT_CHARS, sanititzar_prompt

    assert sanititzar_prompt("hola\x00\x07 món\n") == "hola món"
    assert len(sanititzar_prompt("a" * (MAX_PROMPT_CHARS + 500))) == MAX_PROMPT_CHARS


def test_magic_bytes_rebutja_portes_del_darrere(tmp_path):
    from app.api.v1.gestio.ia import verificar_magic_bytes

    fals_audio = tmp_path / "x.webm"
    fals_audio.write_bytes(b"ValidAud" + b"\x00" * 16)
    fals_foto = tmp_path / "x.jpg"
    fals_foto.write_bytes(b"ValidPho" + b"\x00" * 16)
    assert verificar_magic_bytes(str(fals_audio), "audio") is False
    assert verificar_magic_bytes(str(fals_foto), "imatge") is False

    bo_audio = tmp_path / "ok.ogg"
    bo_audio.write_bytes(b"OggS" + b"\x00" * 16)
    bo_foto = tmp_path / "ok.png"
    bo_foto.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    assert verificar_magic_bytes(str(bo_audio), "audio") is True
    assert verificar_magic_bytes(str(bo_foto), "imatge") is True

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
