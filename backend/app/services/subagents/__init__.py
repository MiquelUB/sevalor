"""Paquet de Subagents Especialitzats i Orquestrador Central de Sevalor Suite."""

from app.services.subagents.base import BaseSubagent
from app.services.subagents.dispatcher import CopilotDispatcher, copilot_dispatcher
from app.services.subagents.subagent_auditoria_marge import SubagentAuditoriaMarge
from app.services.subagents.subagent_client_telegram import SubagentClientTelegram
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from app.services.subagents.subagent_ocr_vision import SubagentOcrVision
from app.services.subagents.subagent_peritatge_camp import SubagentPeritatgeCamp

__all__ = [
    "BaseSubagent",
    "CopilotDispatcher",
    "copilot_dispatcher",
    "SubagentAuditoriaMarge",
    "SubagentClientTelegram",
    "SubagentFlotaDespatx",
    "SubagentGeneralRag",
    "SubagentLogisticaEstoc",
    "SubagentOcrVision",
    "SubagentPeritatgeCamp",
]
