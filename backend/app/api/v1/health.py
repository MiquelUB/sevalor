"""Endpoint de diagnòstic i salut de Sevalor Suite."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=Dict[str, Any])
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Comprova la connectivitat del sistema i de la base de dades PostgreSQL."""
    try:
        result = await db.execute(text("SELECT 1;"))
        db_alive = result.scalar() == 1
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Error de connectivitat amb la base de dades: {str(exc)}",
        ) from exc

    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected" if db_alive else "unreachable",
    }
