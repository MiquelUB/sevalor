from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.services.telegram_service import telegram_service

router = APIRouter(prefix="/webhooks/telegram", tags=["Telegram Webhooks"])


@router.post("")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Rep els missatges/updates de Telegram."""
    secret_token = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if secret_token:
        header_token = request.headers.get("x-telegram-bot-api-secret-token")
        if header_token != secret_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    data = await request.json()

    # Rate Limiting
    from app.bot.security import RedisRateLimiter

    chat_id = None
    if "message" in data:
        chat_id = data.get("message", {}).get("chat", {}).get("id")
    elif "callback_query" in data:
        chat_id = data.get("callback_query", {}).get("message", {}).get("chat", {}).get("id")

    if chat_id:
        limiter = RedisRateLimiter(limit_per_minut=60)  # 1 msg/s = 60/min
        if not await limiter.check_rate_limit(chat_id):
            raise HTTPException(status_code=429, detail="Massa peticions")

    if "callback_query" in data:
        callback = data["callback_query"]
        message_data = callback.get("message", {})
        chat_id = message_data.get("chat", {}).get("id")
        message_id = message_data.get("message_id")
        callback_data = callback.get("data", "")

        if chat_id and callback_data:
            resposta = await telegram_service.processar_callback_query(db, chat_id, callback_data)
            if message_id:
                # T022: Eliminar la botonera interactiva editant el missatge (buit a reply_markup)
                await telegram_service.edit_message_reply_markup(chat_id, message_id)
            await telegram_service.send_message(chat_id, resposta)
            return {"status": "ok", "action": "callback_processed"}

    if "message" in data:
        message = data["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if chat_id:
            if text.startswith("/start"):
                resposta = await telegram_service.processar_comanda_start(db, chat_id, text)
                accio = "linked"
            else:
                resposta = await telegram_service.processar_missatge_general(db, chat_id, text)
                accio = "processed"

            await telegram_service.send_message(chat_id, resposta)
            return {"status": "ok", "action": accio}

    return {"status": "ok"}
