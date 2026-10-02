import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ContracteManteniment(Base):
    __tablename__ = "contractes_manteniment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    numero_contracte: Mapped[str] = mapped_column(String(50), nullable=False)
    data_inici: Mapped[date] = mapped_column(Date, nullable=False)
    data_fi: Mapped[Optional[date]] = mapped_column(Date)
    import_anual: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, server_default=text('0'))
    periodicitat: Mapped[str] = mapped_column(String(20), default="ANUAL", server_default="ANUAL") # MENSUAL, TRIMESTRAL, SEMESTRAL, ANUAL
    estat: Mapped[str] = mapped_column(String(20), default="ACTIU", server_default="ACTIU")
    observacions: Mapped[Optional[str]] = mapped_column(Text)
    renovacio_tacita: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    increment_renovacio_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, server_default=text("0.00"))
    motiu_baixa: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero_contracte", name="uq_contractes_empresa_num"),
    )


class ContractesMantenimentFinques(Base):
    __tablename__ = "contractes_manteniment_finques"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    contracte_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contractes_manteniment.id", ondelete="CASCADE"), nullable=False)
    finca_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("finques.id", ondelete="CASCADE"), nullable=False)
    data_assignacio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    
    __table_args__ = (
        UniqueConstraint("contracte_id", "finca_id", name="uq_contracte_finca"),
    )


class RevisionsContracte(Base):
    __tablename__ = "revisions_contracte"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    contracte_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contractes_manteniment.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    data_prevista: Mapped[date] = mapped_column(Date, nullable=False)
    estat: Mapped[str] = mapped_column(String(20), default="PENDENT", server_default="PENDENT") # PENDENT, GENERADA_OT, COMPLETADA, CANCELADA, VENCUDA
    alerta_emesa_dies: Mapped[Optional[int]] = mapped_column(Numeric(2, 0)) # 15, 5, 1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
