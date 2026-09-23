import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Client, TokenInvitacioTelegram

logger = logging.getLogger("telegram_service")

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: int, text: str, reply_markup: dict = None) -> bool:
        if not self.bot_token or self.bot_token == "DUMMY_TOKEN":
            logger.info(f"[TELEGRAM DISPATCH] Missatge a {chat_id}: {text} (markup={reply_markup})")
            return True

        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload
                )
                return res.status_code == 200
            except Exception as e:
                logger.error(f"Error enviant missatge Telegram: {e}")
                return False

    async def processar_comanda_start(self, db: AsyncSession, chat_id: int, payload_text: str) -> str:
        parts = payload_text.split(" ")
        if len(parts) < 2:
            return "Benvingut al Bot de Sevalor. Necessites un enllaç d'invitació vàlid per enllaçar el teu compte."

        token_str = parts[1]

        # Buscar el token a la BD
        stmt = select(TokenInvitacioTelegram).where(TokenInvitacioTelegram.token_hash == token_str, TokenInvitacioTelegram.utilitzat.is_(False))
        token_db = (await db.execute(stmt)).scalars().first()

        if not token_db:
            return "El token d'invitació és invàlid o ja ha estat utilitzat."

        token_db.utilitzat = True

        # Enllaçar el client al chat ID
        stmt_client = select(Client).where(Client.id == token_db.client_id)
        client_db = (await db.execute(stmt_client)).scalars().first()

        if client_db:
            client_db.telegram_chat_id = chat_id
            client_db.estat_canal_telegram = "ACTIU"

        await db.commit()
        return "✅ Compte de client enllaçat correctament! A partir d'ara rebràs les alertes d'intervencions per aquí."


    async def processar_missatge_general(self, db: AsyncSession, chat_id: int, text: str) -> str:
        from sqlalchemy import func, or_, select

        from app.models.models import FaqCorporativaRag

        # Obtenir client per chat_id
        stmt = select(Client).where(Client.telegram_chat_id == chat_id, Client.estat_canal_telegram == "ACTIU")
        client_db = (await db.execute(stmt)).scalars().first()

        if not client_db:
            return "El teu compte no està enllaçat o actiu. Si us plau, utilitza l'enllaç del panell de client."

        empresa_id = client_db.empresa_id

        # Cerca estricta només al RAG de la base de coneixement
        paraules = text.lower().split()
        filtres_rag = []
        for p in paraules:
            if len(p) > 3:
                filtres_rag.append(func.lower(FaqCorporativaRag.resposta).contains(p))
                filtres_rag.append(func.lower(FaqCorporativaRag.pregunta).contains(p))
                filtres_rag.append(func.lower(FaqCorporativaRag.paraules_clau).contains(p))

        context_rag = ""
        if filtres_rag:
            q_faq = select(FaqCorporativaRag).where(FaqCorporativaRag.empresa_id == empresa_id, FaqCorporativaRag.actiu.is_(True)).where(or_(*filtres_rag))
            res_faq = (await db.execute(q_faq)).scalars().all()
            if res_faq:
                context_rag += "Informació autoritzada de la base de coneixement de l'empresa:\n"
                for faq in res_faq:
                    context_rag += f"[{faq.pregunta}]: {faq.resposta}\n"

        # Lògica estricta per a clients externs (Zero al·lucinacions, zero dades financeres)
        system_prompt_telegram = (
            "Ets un assistent virtual per a clients. El teu únic objectiu és resoldre dubtes utilitzant EXCLUSIVAMENT "
            "la informació autoritzada proporcionada en el context. Sota cap concepte pots revelar dades financeres, facturació, salaris "
            "ni dades privades de l'empresa. Si la resposta a la pregunta de l'usuari NO es troba al context adjunt, "
            "has de respondre OBLIGATÒRIAMENT: 'Ho sento, no disposo d'aquesta informació. Si us plau, contacta directament amb el departament d'atenció al client.' "
            "Context proporcionat:\n" + context_rag
        )

        # En comptes d'usar directament cridar_lm_studio amb el prompt estàndard, fem una trucada adaptada o li passem el vertical
        # Com cridar_lm_studio genera un system_prompt dins, la millor manera és injectar aquest súper-prompt al "context_addicional"
        # i fer que la instrucció tingui més pes. O refer la trucada aquí mateix de forma independent per major seguretat.

        lm_url = getattr(settings, "LMSTUDIO_URL", None) or getattr(settings, "LM_STUDIO_URL", None)
        if not lm_url:
            if context_rag:
                return f"L'assistent no està disponible en aquest moment, però he trobat això al manual:\n\n{context_rag}"
            else:
                return "Ho sento, en aquest moment no et puc atendre i no he trobat resposta als manuals. Contacta amb atenció al client."

        base_url = lm_url.rstrip("/")
        endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
        model_name = getattr(settings, "LM_STUDIO_MODEL", "default")
        api_key = getattr(settings, "LM_STUDIO_API_KEY", "lm-studio")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt_telegram},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,  # Molt baixa per evitar al·lucinacions
            "max_tokens": 400,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.post(
                    endpoint,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    resultat = resp.json()
                    choices = resultat.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "").strip()
        except Exception as e:
            logger.warning(f"Error connectant a LM Studio des de Telegram: {e}")

        if context_rag:
            return f"He trobat aquesta informació que et podria ser útil:\n\n{context_rag}"
        return "Ho sento, hi ha hagut un problema tècnic. Torna-ho a provar més tard."


    async def processar_callback_query(self, db: AsyncSession, chat_id: int, callback_data: str) -> str:
        """Processa les accions de botons en línia (aprovacions de pressupostos, etc.)"""
        from sqlalchemy import select

        from app.models.models import Client, Pressupost

        # Verificar que el client està enllaçat
        stmt = select(Client).where(Client.telegram_chat_id == chat_id, Client.estat_canal_telegram == "ACTIU")
        client_db = (await db.execute(stmt)).scalars().first()

        if not client_db:
            return "❌ Error: El teu compte no està enllaçat. Demana un nou enllaç d'invitació."

        if callback_data.startswith("aprovar_pressupost:"):
            parts = callback_data.split(":")
            if len(parts) < 2:
                return "❌ Error: Format de comanda invàlid."
            pressupost_id_str = parts[1]
            try:
                pressupost_uuid = uuid.UUID(pressupost_id_str)
            except (ValueError, TypeError):
                return "❌ Error: Aquest pressupost no existeix, no pertany a la teva empresa, o ja no està pendent d'aprovació."

            # Buscar pressupost
            q_press = select(Pressupost).where(
                Pressupost.id == pressupost_uuid,
                Pressupost.client_id == client_db.id,
                Pressupost.estat == "PENDENT"
            )
            pressupost = (await db.execute(q_press)).scalars().first()

            if not pressupost:
                return "❌ Error: Aquest pressupost no existeix, no pertany a la teva empresa, o ja no està pendent d'aprovació."

            # Canviar estat a aprovat i establir Token de signatura com el chat_id
            pressupost.estat = "APROVAT"
            pressupost.token_signatura = f"TG-APROV-{chat_id}-{pressupost.id}"

            await db.commit()
            return f"✅ Has aprovat correctament el pressupost {pressupost.numero}.\nEl nostre equip es posarà en contacte ben aviat per programar l'execució."

        elif callback_data.startswith("rebutjar_pressupost:"):
            parts = callback_data.split(":")
            if len(parts) < 2:
                return "❌ Error: Format de comanda invàlid."
            pressupost_id_str = parts[1]
            try:
                pressupost_uuid = uuid.UUID(pressupost_id_str)
            except (ValueError, TypeError):
                return "❌ Error: Pressupost no vàlid."
            q_press = select(Pressupost).where(
                Pressupost.id == pressupost_uuid,
                Pressupost.client_id == client_db.id,
                Pressupost.estat == "PENDENT"
            )
            pressupost = (await db.execute(q_press)).scalars().first()
            if not pressupost:
                return "❌ Error: Pressupost no vàlid."

            pressupost.estat = "REBUTJAT"
            await db.commit()
            return f"❌ Has rebutjat el pressupost {pressupost.numero}."

        return "Acció no reconeguda."

    async def enviar_pressupost_telegram(self, db: AsyncSession, pressupost_id: uuid.UUID) -> dict:
        """Envia un pressupost al client amb botons d'Inline Keyboard per aprovar o rebutjar."""
        from app.models.models import Client, Pressupost

        q_p = select(Pressupost).where(Pressupost.id == pressupost_id)
        pressupost = (await db.execute(q_p)).scalars().first()
        if not pressupost:
            return {"ok": False, "detail": "Pressupost no trobat"}

        q_c = select(Client).where(Client.id == pressupost.client_id)
        client = (await db.execute(q_c)).scalars().first()
        if not client or not client.telegram_chat_id or client.estat_canal_telegram != "ACTIU":
            return {"ok": False, "detail": "El client no té el canal de Telegram vinculat o actiu"}

        text = (
            f"📄 *Nou Pressupost Pendent d'Aprovació*\n\n"
            f"• *Número:* {pressupost.numero}\n"
            f"• *Import Total:* {float(pressupost.total):.2f} €\n"
            f"• *Estat:* {pressupost.estat}\n\n"
            f"Si us plau, revisa els termes i confirma o rebutja la proposta directament aquí sota:"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Aprovar Pressupost", "callback_data": f"aprovar_pressupost:{pressupost.id}"},
                    {"text": "❌ Rebutjar Pressupost", "callback_data": f"rebutjar_pressupost:{pressupost.id}"},
                ]
            ]
        }
        sent = await self.send_message(client.telegram_chat_id, text, reply_markup=reply_markup)
        return {
            "ok": sent,
            "pressupost_id": str(pressupost.id),
            "chat_id": client.telegram_chat_id,
            "numero": pressupost.numero,
        }

telegram_service = TelegramService()
