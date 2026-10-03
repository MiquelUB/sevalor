import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MemorandumTecnicCopilot


class IAOcrNotImplementedError(NotImplementedError):
    pass

async def generar_memorandum_tecnic(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    incidencia_id: Optional[uuid.UUID],
    ordre_treball_id: Optional[uuid.UUID],
    transcripcio: str,
    confianca_acustica: float,
    foto_path: Optional[str] = None
) -> MemorandumTecnicCopilot:
    """
    Genera un dictamen (Extra Facturable vs Cost No Imputable) basat en àudio i foto.
    Desa a memorandum_tecnic amb estat PENDENT_REVISIO.
    """
    analisi_visual = None
    if foto_path:
        # PENDENT_IMPLEMENTACIO: Connexió real amb model de visió per a OCR i anàlisi de danys.
        # Zero Mock Data: Aixecarem un error si intentem usar OCR fins que estigui implementat,
        # o ho marcarem com a pendent d'auditoria si el flux ho requereix.
        analisi_visual = "PENDENT_AUDITORIA"

    # Lògica bàsica de dictamen (En el futur serà generada per un LLM)
    dictamen = "EXTRA_FACTURABLE"
    motiu = "S'ha generat un memoràndum provisional. Pendent d'anàlisi de LLM per determinar la responsabilitat exacta."

    if "no imputable" in transcripcio.lower() or "garantia" in transcripcio.lower():
        dictamen = "COST_NO_IMPUTABLE"
        motiu = "Possible incidència coberta per garantia segons la transcripció."

    nou_memo = MemorandumTecnicCopilot(
        empresa_id=empresa_id,
        incidencia_id=incidencia_id,
        ordre_treball_id=ordre_treball_id,
        transcripcio_audio=transcripcio,
        confianca_acustica=confianca_acustica,
        avis_soroll_sever=(confianca_acustica < 0.6),
        analisi_visual=analisi_visual,
        dictamen_pericial=dictamen,
        motiu_dictamen=motiu,
        estat="PENDENT_REVISIO"
    )

    db.add(nou_memo)
    await db.commit()

    return nou_memo
