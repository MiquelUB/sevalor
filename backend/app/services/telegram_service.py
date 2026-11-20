import logging
import uuid
from typing import Any, Dict

import httpx
from sqlalchemy import select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Client, Empresa, TokenInvitacioTelegram
from app.services.vault_tunnel import VaultTunnelError, empresa_target_key, vault_tunnel_broker

logger = logging.getLogger("telegram_service")


class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        bot_token: str | None = None,
    ) -> bool:
        effective_token = (bot_token or self.bot_token or "").strip()
        if not effective_token or effective_token == "DUMMY_TOKEN":
            logger.info(f"[TELEGRAM DISPATCH] Missatge a {chat_id}: {text} (markup={reply_markup})")
            return True

        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        api_url = f"https://api.telegram.org/bot{effective_token}"
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(f"{api_url}/sendMessage", json=payload)
                return res.status_code == 200
            except Exception as e:
                logger.error(f"Error enviant missatge Telegram: {e}")
                return False

    async def edit_message_reply_markup(
        self, chat_id: int, message_id: int, reply_markup: dict = None  # type: ignore
    ) -> bool:
        if not self.bot_token or self.bot_token == "DUMMY_TOKEN":
            logger.info(f"[TELEGRAM DISPATCH] Eliminat teclat a {chat_id}, missatge {message_id}")
            return True

        payload = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup:
            payload["reply_markup"] = reply_markup  # type: ignore

        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(f"{self.api_url}/editMessageReplyMarkup", json=payload)
                return res.status_code == 200
            except Exception as e:
                logger.error(f"Error editant missatge Telegram: {e}")
                return False

    async def processar_comanda_start(
        self, db: AsyncSession, chat_id: int, payload_text: str
    ) -> str:
        await db.execute(sa_text("RESET ROLE;"))
        parts = payload_text.split(" ")

        if len(parts) < 2:
            return "Benvingut al Bot de Sevalor. Necessites un enllaç d'invitació vàlid per enllaçar el teu compte."

        token_str = parts[1]

        # Buscar el token a la BD
        stmt = select(TokenInvitacioTelegram).where(
            TokenInvitacioTelegram.token_hash == token_str,
            TokenInvitacioTelegram.utilitzat.is_(False),
        )
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

        await db.execute(sa_text("RESET ROLE;"))
        # Obtenir client per chat_id
        stmt = select(Client).where(
            Client.telegram_chat_id == chat_id, Client.estat_canal_telegram == "ACTIU"
        )

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
            q_faq = (
                select(FaqCorporativaRag)
                .where(
                    FaqCorporativaRag.empresa_id == empresa_id, FaqCorporativaRag.actiu.is_(True)
                )
                .where(or_(*filtres_rag))
            )
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

        # La IA només opera si l'empresa té ordinador dedicat actiu i connectat via Túnel WSS. Zero egress a Hetzner.
        stmt_emp = select(Empresa).where(Empresa.id == empresa_id)
        emp_obj = (await db.execute(stmt_emp)).scalar_one_or_none()
        if not (
            emp_obj
            and emp_obj.node_ia_actiu
            and getattr(emp_obj, "feature_copilot_ia", True)
        ):
            if context_rag:
                return f"Informació d'atenció al client:\n\n{context_rag}"
            return "Gràcies pel vostre missatge. Hem registrat la vostra consulta i el nostre equip tècnic us respondrà aviat."

        target_key = empresa_target_key(empresa_id)
        if not await vault_tunnel_broker.is_online(target_key):
            if context_rag:
                return f"Informació d'atenció al client:\n\n{context_rag}"
            return "Gràcies pel vostre missatge. Hem registrat la vostra consulta i el nostre equip tècnic us respondrà aviat."

        model_name = getattr(settings, "LM_STUDIO_MODEL", "qwen2.5-vl-7b-instruct")
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt_telegram},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,  # Molt baixa per evitar al·lucinacions
            "max_tokens": 400,
        }

        try:
            resultat = await vault_tunnel_broker.call_llm_chat(target_key, payload, timeout=35.0)
            choices = resultat.get("choices", [])
            if choices and "message" in choices[0]:
                return str(choices[0]["message"].get("content", "")).strip()
        except (VaultTunnelError, Exception) as e:
            logger.warning("Error connectant a LM Studio via WSS des de Telegram: %s", e)

        if context_rag:
            return f"He trobat aquesta informació que et podria ser útil:\n\n{context_rag}"
        return "Ho sento, hi ha hagut un problema tècnic. Torna-ho a provar més tard."

    async def processar_callback_query(
        self, db: AsyncSession, chat_id: int, callback_data: str
    ) -> str:
        """Processa les accions de botons en línia (aprovacions de pressupostos, etc.)"""
        from sqlalchemy import select

        from app.models.models import Client, Pressupost

        await db.execute(sa_text("RESET ROLE;"))
        # Verificar que el client està enllaçat
        stmt = select(Client).where(
            Client.telegram_chat_id == chat_id, Client.estat_canal_telegram == "ACTIU"
        )

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
                Pressupost.estat == "PENDENT",
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
                Pressupost.estat == "PENDENT",
            )
            pressupost = (await db.execute(q_press)).scalars().first()
            if not pressupost:
                return "❌ Error: Pressupost no vàlid."

            pressupost.estat = "REBUTJAT"
            await db.commit()
            return f"❌ Has rebutjat el pressupost {pressupost.numero}."

        return "Acció no reconeguda."

    async def enviar_pressupost_telegram(
        self,
        db: AsyncSession,
        pressupost_id: uuid.UUID,
        titol: str | None = None,
        acceptacio_url: str | None = None,
    ) -> dict:
        """Envia un pressupost al client amb botons d'Inline Keyboard per aprovar o rebutjar."""
        from app.models.models import Client, Empresa, Pressupost

        q_p = select(Pressupost).where(Pressupost.id == pressupost_id)
        pressupost = (await db.execute(q_p)).scalars().first()
        if not pressupost:
            return {"ok": False, "detail": "Pressupost no trobat"}

        q_c = select(Client).where(Client.id == pressupost.client_id)
        client = (await db.execute(q_c)).scalars().first()
        if not client or not client.telegram_chat_id or client.estat_canal_telegram != "ACTIU":
            return {"ok": False, "detail": "El client no té el canal de Telegram vinculat o actiu"}

        empresa = (
            await db.execute(select(Empresa).where(Empresa.id == pressupost.empresa_id))
        ).scalars().first()
        emp_token = (
            empresa.telegram_bot_token.strip()
            if empresa and empresa.telegram_bot_actiu and empresa.telegram_bot_token
            else None
        )

        titol_line = f"• *Concepte:* {titol}\n" if titol else ""
        link_line = f"\n🔗 *Detall complet:* {acceptacio_url}\n" if acceptacio_url else ""
        text = (
            f"📄 *Nou Pressupost Pendent d'Aprovació*\n\n"
            f"• *Número:* {pressupost.numero}\n"
            f"{titol_line}"
            f"• *Import Total:* {float(pressupost.total):.2f} €\n"
            f"• *Estat:* {pressupost.estat}\n"
            f"{link_line}\n"
            f"Si us plau, revisa els termes i confirma o rebutja la proposta directament aquí sota:"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Acceptar Pressupost",
                        "callback_data": f"aprovar_pressupost:{pressupost.id}",
                    },
                    {
                        "text": "❌ Demanar Canvis",
                        "callback_data": f"rebutjar_pressupost:{pressupost.id}",
                    },
                ]
            ]
        }
        sent = await self.send_message(
            client.telegram_chat_id,
            text,
            reply_markup=reply_markup,
            bot_token=emp_token,
        )
        return {
            "ok": sent,
            "pressupost_id": str(pressupost.id),
            "chat_id": client.telegram_chat_id,
            "numero": pressupost.numero,
        }


telegram_service = TelegramService()


async def send_telegram_direct_message(
    empresa_id: uuid.UUID,
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> bool:
    """Envia un missatge directe via Telegram Bot a un operari o usuari vinculat."""
    logger.info("Enviant missatge Telegram directe (empresa=%s, chat_id=%s)", empresa_id, chat_id)
    return await telegram_service.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


send_telegram_Direct_message = send_telegram_direct_message
