from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from app.core.db import async_session_maker  # type: ignore
from app.models.models import Client


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            if event.message:
                chat_id = event.message.chat.id

        if not chat_id:
            return None

        async with async_session_maker() as session:
            stmt = select(Client).where(
                Client.telegram_chat_id == chat_id, Client.estat_canal_telegram == "ACTIU"
            )
            client_db = (await session.execute(stmt)).scalars().first()
            if not client_db:
                if isinstance(event, Message):
                    await event.answer("Aquest és un canal privat.")
                return None

        return await handler(event, data)
