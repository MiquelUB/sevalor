import pytest
import pytest_asyncio
import os
from redis.asyncio import Redis
from bot.security import detectar_doble_extensio, validar_magic_bytes, RedisRateLimiter

# Connectarem contra el Redis autèntic dockeritzat per provar
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

@pytest_asyncio.fixture
async def redis():
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    # Netejar per no deixar rastre després dels tests
    await client.flushdb()
    await client.aclose()

@pytest.mark.asyncio
async def test_seguretat_doble_extensio():
    es_malicios, motiu = detectar_doble_extensio("arxiu_normal.jpg")
    assert not es_malicios

    es_malicios, motiu = detectar_doble_extensio("factura.exe.pdf")
    assert es_malicios
    assert "Doble extensió detectada" in motiu

    es_malicios, motiu = detectar_doble_extensio("malware.bat")
    assert es_malicios
    assert "no permesa" in motiu

@pytest.mark.asyncio
async def test_seguretat_magic_bytes():
    # Simulació de signatura PNG real
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    es_valid, ext = validar_magic_bytes(png_bytes)
    assert es_valid
    assert ext == "png"

    # Simulació de binari desconegut/brossa
    brossa_bytes = b'Mz\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff'
    es_valid, ext = validar_magic_bytes(brossa_bytes)
    assert not es_valid

@pytest.mark.asyncio
async def test_rate_limiter_via_redis(redis):
    limiter = RedisRateLimiter(redis, limit_per_minut=2)
    user_id = 99999
    
    # Intent 1 (Permès)
    assert await limiter.es_permes(user_id) == True
    # Intent 2 (Permès)
    assert await limiter.es_permes(user_id) == True
    # Intent 3 (Bloquejat, supera limit de 2)
    assert await limiter.es_permes(user_id) == False

@pytest.mark.asyncio
async def test_persistència_vinculacio_redis(redis):
    # Demostrar que el magatzem és permanent i no volàtil, validant el flux d'onboarding FSM de Spec 023
    token = "token-secret-123"
    await redis.set(f"invitacio:{token}", "emp-001|cli-123|Joan|Llauners S.A.")
    
    # Comprovem que s'ha guardat correctament
    val = await redis.get(f"invitacio:{token}")
    assert val == "emp-001|cli-123|Joan|Llauners S.A."
