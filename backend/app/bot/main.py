import os
import sys

# Per si cal executar-ho autònomament
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.core.config import settings

bot_router = Router(name="sevalor_bot_router")

@bot_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Gestor per a la comanda /start"""
    await message.answer(
        "👋 Benvingut al bot de Sevalor Suite (Operaris).\n"
        "Per comprovar l'estat d'una OT, utilitza /estat_ot <ID>"
    )

@bot_router.message(Command("estat_ot"))
async def cmd_estat_ot(message: Message) -> None:
    """Gestor per a la comanda /estat_ot"""
    text_parts = message.text.split() if message.text else []

    if len(text_parts) < 2:
        await message.answer("Si us plau, indica l'ID de l'OT. Exemple: /estat_ot OT-1234")
        return

    ot_id = text_parts[1]

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    from app.core.db import get_engine

    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Utilitzem text i assumeix que el ot_id pot ser un ID parcial
            stmt = text("SELECT estat FROM ordres_treball WHERE id::text ILIKE :ot_id OR numero = :num LIMIT 1")
            res = await session.execute(stmt, {"ot_id": f"%{ot_id}%", "num": ot_id})
            estat = res.scalar()

            if estat:
                await message.answer(f"L'estat de l'Ordre de Treball {ot_id} és: <b>{estat}</b>")
            else:
                await message.answer(f"No s'ha trobat cap Ordre de Treball amb l'ID/Número: {ot_id}")
    except Exception as e:
        import logging
        logging.error(f"Error bot: {e}")
        await message.answer("S'ha produït un error consultant la base de dades.")

async def main() -> None:
    """Funció principal per arrencar el bot en mode long-polling (si escau)"""
    token = settings.TELEGRAM_BOT_TOKEN or "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    from app.bot.middleware import AuthMiddleware
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_router(bot_router)

    # Només arranquem el bot si s'executa com a script
    # await dp.start_polling(bot)
    pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
