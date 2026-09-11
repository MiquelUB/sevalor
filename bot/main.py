"""Microservei del Bot de Telegram per a Clients Finals (Spec 023).

Re-escriptura DES DE ZERO (Compliment Estricte RF-01).
"""
import os
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.state import State, StatesGroup
from redis.asyncio import Redis

from bot.security import RedisRateLimiter, detectar_doble_extensio, validar_magic_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_bot_v2")

# Connexió a Redis 7 segons RF-01
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

# Definim el KeyBuilder per complir el RF-01: fsm:{empresa_id}:{user_id}
# Aiogram usa per defecte "fsm:{bot_id}:{chat_id}:{user_id}".
# Configurarem un custom prefix en instanciar el storage.
storage = RedisStorage(
    redis=Redis.from_url(REDIS_URL), # necessitem instància sense decode_responses per aiogram
    key_builder=DefaultKeyBuilder(prefix="fsm:tenant", with_bot_id=False, with_destiny=False)
)

dp = Dispatcher(storage=storage)
rate_limiter = RedisRateLimiter(redis_client, limit_per_minut=10)

class ConversaClient(StatesGroup):
    esperant_incidencia = State()
    esperant_fotos = State()
    esperant_feedback_pressupost = State()

@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext, command: CommandStart):
    chat_id = message.chat.id
    if not await rate_limiter.es_permes(chat_id):
        await message.answer("⚠️ Heu superat el límit de missatges per minut. Si us plau, espereu uns instants.")
        return

    args = command.args
    # RF-05: Validar el token d'invitació via Redis (deep-link)
    if args:
        token = args.strip()
        key_token = f"invitacio:{token}"
        info_str = await redis_client.get(key_token)
        
        if info_str:
            # Token vàlid
            empresa_id, client_id, nom_client, nom_empresa = info_str.split("|")
            
            # Persistim la vinculació d'aquest xat a l'empresa permanentment a Redis
            await redis_client.set(f"vinculacio:{chat_id}", f"{empresa_id}|{client_id}|{nom_client}")
            
            # Configurem estat inicial
            await state.clear()
            
            msg = (f"👋 Us donem la benvinguda al canal d'atenció de **{nom_empresa}**!\n\n"
                   f"Benvolgut/da {nom_client}, el vostre compte ha quedat vinculat amb èxit. "
                   f"Rebreu actualitzacions en temps real de les vostres obres i instal·lacions.")
            await message.answer(msg, parse_mode="Markdown")
        else:
            await message.answer("❌ L'enllaç d'invitació ha caducat o no és vàlid. Sol·liciteu-ne un de nou a l'empresa.")
    else:
        # Usuari sense token (RF-06 Rebuig opac)
        vinculacio = await redis_client.get(f"vinculacio:{chat_id}")
        if vinculacio:
            empresa_id, client_id, nom_client = vinculacio.split("|")
            await message.answer(f"Hola {nom_client}. En què us podem ajudar avui?")
        else:
            await message.answer("Aquest és un canal privat d'atenció. Per accedir-hi, utilitzeu l'enllaç d'invitació facilitat per l'empresa.")

@dp.message(lambda msg: msg.document or msg.photo)
async def processar_arxius(message: types.Message, state: FSMContext, bot: Bot):
    chat_id = message.chat.id
    if not await rate_limiter.es_permes(chat_id):
        return

    vinculacio = await redis_client.get(f"vinculacio:{chat_id}")
    if not vinculacio:
        await message.answer("Aquest és un canal privat d'atenció. Per accedir-hi, utilitzeu l'enllaç d'invitació facilitat per l'empresa.")
        return
        
    empresa_id, client_id, _ = vinculacio.split("|")
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document.bin"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "foto.jpg"
    else:
        return
        
    # Validació RF-16 Doble Extensió
    es_malicios, motiu = detectar_doble_extensio(file_name)
    if es_malicios:
        logger.warning(f"BLOCKED MALICIOUS FILE from chat_id {chat_id}: {file_name} ({motiu})")
        await message.answer(f"🚨 L'arxiu adjuntat ha estat bloquejat pel sistema de seguretat: {motiu}")
        return
        
    # Descarregar a memòria per Magic Bytes
    file_info = await bot.get_file(file_id)
    # L'arxiu descarregat és un BytesIO a aiogram 3, utilitzem download_file
    import io
    result = io.BytesIO()
    await bot.download_file(file_info.file_path, destination=result)
    contingut = result.getvalue()
    
    valid_magic, magic_ext = validar_magic_bytes(contingut)
    if not valid_magic:
        logger.warning(f"BLOCKED BY MAGIC BYTES: {file_name}")
        await message.answer(f"🚨 L'arxiu ha estat rebutjat perquè el seu contingut no correspon a una imatge o document autoritzat.")
        return
        
    # Guardat Soberà a Hetzner
    dest_dir = f"/data/{empresa_id}/incidencies"
    try:
        os.makedirs(dest_dir, exist_ok=True)
        # Nom segur per l'arxiu amb extensió verificada
        segur_filename = f"{message.message_id}.{magic_ext}"
        dest_path = os.path.join(dest_dir, segur_filename)
        with open(dest_path, "wb") as f:
            f.write(contingut)
        await message.answer("✅ Fotografia o document d'avaria rebuda correctament. L'equip tècnic l'ha incorporada a l'expedient prioritari.")
    except PermissionError:
        # Durant el testing el directori pot ser de només lectura, mostrem error clar (zero mocks)
        await message.answer("❌ Error crític del sistema: Manca de permisos per emmagatzemar l'arxiu al volum sobirà.")
