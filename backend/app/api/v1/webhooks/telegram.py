from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.telegram_service import telegram_service

router = APIRouter(prefix="/webhooks/telegram", tags=["Telegram Webhooks"])

@router.post("")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Rep els missatges/updates de Telegram."""
    data = await request.json()
    
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
