"""Models ORM de SQLAlchemy 2.0 per a Sevalor Suite."""

import uuid
from datetime import date, datetime, time, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    BIGINT,
    DDL,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Empresa(Base):
    __tablename__ = "empreses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    subdomini: Mapped[Optional[str]] = mapped_column(String(63), unique=True)
    domini_custom: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    estat_domini: Mapped[str] = mapped_column(
        String(30), default="NO_CONFIGURAT", server_default="NO_CONFIGURAT"
    )
    primari_hsl: Mapped[str] = mapped_column(
        String(30), default="210 100% 15%", server_default="210 100% 15%"
    )
    secundari_hsl: Mapped[str] = mapped_column(
        String(30), default="38 92% 50%", server_default="38 92% 50%"
    )
    accent_hsl: Mapped[str] = mapped_column(
        String(30), default="190 90% 50%", server_default="190 90% 50%"
    )
    logotip_path: Mapped[Optional[str]] = mapped_column(String(500))
    favicon_path: Mapped[Optional[str]] = mapped_column(String(500))
    pla_subscripcio: Mapped[str] = mapped_column(
        String(20), default="STARTER", server_default="STARTER"
    )
    estat_pagament: Mapped[str] = mapped_column(String(30), default="ACTIU", server_default="ACTIU")
    quota_operaris: Mapped[int] = mapped_column(
        Integer, default=5, server_default=text("5")
    )
    quota_buffer_mb: Mapped[int] = mapped_column(
        Integer, default=500, server_default=text("500")
    )
    tarifa_llicencia_base: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    tarifa_per_operari: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    tarifa_config_ia: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    equips_ia_venuts: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    notes_crm: Mapped[Optional[str]] = mapped_column(Text)
    quota_disc_bytes_autoritzada: Mapped[int] = mapped_column(
        BIGINT, default=10737418240, server_default=text("10737418240")
    )
    quota_disc_bytes_utilitzada: Mapped[int] = mapped_column(
        BIGINT, default=0, server_default=text("0")
    )
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_webhook_secret: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_bot_actiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    telegram_estat_connexio: Mapped[str] = mapped_column(
        String(30), default="NO_CONFIGURAT", server_default="NO_CONFIGURAT"
    )
    adn_marca_path: Mapped[Optional[str]] = mapped_column(String(500))
    adn_paleta_proposta: Mapped[Optional[dict]] = mapped_column(JSONB)
    codis_recuperacio_2fa: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    monograma: Mapped[Optional[str]] = mapped_column(String(10))
    vertical: Mapped[str] = mapped_column(String(100), default="SEVALOR", server_default="SEVALOR")
    magatzem_families_default: Mapped[Optional[str]] = mapped_column(Text)
    agent_prompt_system: Mapped[Optional[str]] = mapped_column(Text)
    node_ia_actiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    node_ia_url: Mapped[Optional[str]] = mapped_column(String(255))
    disc_dur_url: Mapped[Optional[str]] = mapped_column(String(255))
    vault_token: Mapped[Optional[str]] = mapped_column(String(255))
    feature_copilot_ia: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    feature_flota: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    feature_planols: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    feature_telegram: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    data_onboarding: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SlotJornada(Base):
    __tablename__ = "slots_jornada"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    modalitat: Mapped[str] = mapped_column(
        String(30), default="JORNADA_CONTINUADA", server_default="JORNADA_CONTINUADA"
    )
    hora_entrada_teorica: Mapped[time] = mapped_column(
        Time, default=time(8, 0), server_default=text("'08:00'")
    )
    hora_sortida_teorica: Mapped[time] = mapped_column(
        Time, default=time(17, 0), server_default=text("'17:00'")
    )
    hora_inici_dinar: Mapped[Optional[time]] = mapped_column(Time, default=time(13, 0))
    hora_fi_dinar: Mapped[Optional[time]] = mapped_column(Time, default=time(14, 0))
    hores_convenio_setmanals: Mapped[float] = mapped_column(
        Numeric(4, 2), default=40.00, server_default=text("40")
    )
    es_intensiva_estiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    data_inici_estiu: Mapped[Optional[date]] = mapped_column(Date)
    data_fi_estiu: Mapped[Optional[date]] = mapped_column(Date)
    hora_entrada_estiu: Mapped[Optional[time]] = mapped_column(Time)
    hora_sortida_estiu: Mapped[Optional[time]] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Usuari(Base):
    __tablename__ = "usuaris"
    __table_args__ = (UniqueConstraint("empresa_id", "nif", name="uq_usuaris_empresa_nif"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE")
    )
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    cognoms: Mapped[str] = mapped_column(String(100), default="", server_default="")
    email: Mapped[Optional[str]] = mapped_column(String(200))
    telefon: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    pin_hash: Mapped[Optional[str]] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(30), default="OPERARI", server_default="OPERARI")
    estat: Mapped[str] = mapped_column(String(20), default="ACTIU", server_default="ACTIU")
    secret_2fa: Mapped[Optional[str]] = mapped_column(String(64))
    totp_activat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    slot_jornada_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slots_jornada.id", ondelete="SET NULL")
    )
    ip_allowlist: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    vehicle_assignat_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    especialitat: Mapped[Optional[str]] = mapped_column(String(50), default="SISTEMES_REG")
    estat_operatiu: Mapped[str] = mapped_column(
        String(30), default="DISPONIBLE", server_default="DISPONIBLE"
    )
    cap_de_grup_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    cost_hora_eur: Mapped[float] = mapped_column(
        Numeric(8, 2), default=22.50, server_default=text("22.50")
    )
    es_alta_direccio: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    cost_hora_referencia: Mapped[float] = mapped_column(
        Numeric(8, 2), default=22.50, server_default=text("22.50")
    )
    salari_mensual_brut: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    cost_ss_mensual: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    carnet_conduir: Mapped[str] = mapped_column(String(20), default="B", server_default="B")
    carnet_caducitat: Mapped[Optional[date]] = mapped_column(Date)
    prl_certificat_vigencia: Mapped[Optional[date]] = mapped_column(Date)

    @property
    def te_cap(self) -> bool:
        """Indica si l'operari té acreditació de Certificat d'Aptitud Professional (CAP)."""
        return getattr(self, "_te_cap", False)

    @te_cap.setter
    def te_cap(self, val: bool) -> None:
        self._te_cap = bool(val)
    intents_pin_fallits: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    pin_bloquejat: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BIGINT, nullable=True)
    dispositiu_referencia: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requereix_rexifrat_idb: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    data_ultim_acces: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class RegistreJornadaLaboral(Base):
    __tablename__ = "registres_jornada_laboral"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    usuari_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False
    )
    data_jornada: Mapped[date] = mapped_column(
        Date, default=date.today, server_default=text("CURRENT_DATE")
    )
    hora_inici: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    hora_fi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    geolocalitzacio_inici: Mapped[Optional[str]] = mapped_column(String(100))
    geolocalitzacio_fi: Mapped[Optional[str]] = mapped_column(String(100))
    estat: Mapped[str] = mapped_column(String(20), default="EN_CURS", server_default="EN_CURS")
    tancament_automatic: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    motiu_incidencia: Mapped[Optional[str]] = mapped_column(Text)
    hores_ordinaries: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, server_default=text("0")
    )
    hores_extraordinaries: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, server_default=text("0")
    )
    hores_imputades_ot: Mapped[float] = mapped_column(
        Numeric(6, 2), default=0.00, server_default=text("0")
    )
    auditat_per_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    auditoria_data: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    auditoria_motiu: Mapped[Optional[str]] = mapped_column(Text)
    version_id: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class AuditoriaRegistreJornada(Base):
    __tablename__ = "auditoria_registres_jornada"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("registres_jornada_laboral.id", ondelete="CASCADE"),
        nullable=False,
    )
    modificat_per_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False
    )
    valors_anteriors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    nous_valors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    motiu_justificatiu: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("empresa_id", "codi", name="uq_clients_empresa_codi"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    rao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    telefon: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    adreca_fiscal: Mapped[Optional[str]] = mapped_column(Text)
    estat_canal_telegram: Mapped[str] = mapped_column(
        String(20), default="DESVINCULAT", server_default="DESVINCULAT"
    )
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    iban_xifrat_simetric: Mapped[Optional[str]] = mapped_column(Text)
    mandat_sepa_path: Mapped[Optional[str]] = mapped_column(String(500))
    limit_risc_credit: Mapped[float] = mapped_column(
        Numeric(12, 2), default=15000.00, server_default=text("15000.00")
    )
    estat_risc_operatiu: Mapped[str] = mapped_column(
        String(30), default="APTE", server_default="APTE"
    )
    motiu_override_risc: Mapped[Optional[str]] = mapped_column(Text)
    override_boss_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    data_override_risc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "referencia_inventari", name="uq_articles_empresa_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    referencia_inventari: Mapped[str] = mapped_column(String(50), nullable=False)
    codi_barres: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    nom: Mapped[str] = mapped_column(String(500), nullable=False)
    unitat_mesura: Mapped[str] = mapped_column(
        String(30), default="UNITAT", server_default="UNITAT"
    )
    es_material_continu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    familia: Mapped[str] = mapped_column(String(50), default="GENERAL", server_default="GENERAL")
    estoc_optim: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    estoc_minim: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    es_lot_caducable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    parent_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    proveidor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="SET NULL")
    )
    preu_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text("0"))
    preu_cost_ultim: Mapped[float] = mapped_column(
        Numeric(12, 4), default=0.0, server_default=text("0")
    )
    preu_cost_mitja: Mapped[float] = mapped_column(
        Numeric(12, 4), default=0.0, server_default=text("0")
    )
    descompte_proveidor: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.0, server_default=text("0")
    )
    marge_guanys: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.0, server_default=text("0")
    )
    preu_venda: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text("0"))
    llindar_marge_minim_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), default=25.00, server_default=text("25.00")
    )
    es_diposit_proveidor: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    es_custodia_rma_client: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    pmp_actual: Mapped[float] = mapped_column(
        Numeric(12, 4), default=0.0, server_default=text("0.0000")
    )
    ultim_preu_compra: Mapped[float] = mapped_column(
        Numeric(12, 4), default=0.0, server_default=text("0.0000")
    )
    estoc_total_actual: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0.000")
    )
    estoc_slot_residus: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0.000")
    )
    darrer_moviment_sortida: Mapped[Optional[date]] = mapped_column(Date)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Magatzem(Base):
    __tablename__ = "magatzems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    tipus: Mapped[str] = mapped_column(
        String(30), default="NAU_CENTRAL", server_default="NAU_CENTRAL"
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class EstocMagatzem(Base):
    __tablename__ = "estocs_magatzem"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "article_id", "magatzem_id", name="uq_estocs_article_magatzem"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    magatzem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="CASCADE"), nullable=False
    )
    quantitat_fisica: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    quantitat_virtual_reservada: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    quantitat_cuarentena: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    ubicacio_passadis: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "matricula", name="uq_vehicles_empresa_matricula"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    matricula: Mapped[str] = mapped_column(String(20), nullable=False)
    marca: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    tipus: Mapped[str] = mapped_column(String(30), default="THERMIC", server_default="THERMIC")
    horometre_acumulat: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.0, server_default=text("0")
    )
    odometre_acumulat: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    km_inicials_mes: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    despeses_taller_mes: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    distintiu_ambiental: Mapped[Optional[str]] = mapped_column(String(10))
    estat: Mapped[str] = mapped_column(String(30), default="OPERATIU", server_default="OPERATIU")
    conductor_habitual_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    magatzem_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="SET NULL")
    )
    data_proxima_itv: Mapped[Optional[date]] = mapped_column(Date)
    estat_itv: Mapped[str] = mapped_column(
        String(50), default="FAVORABLE", server_default="FAVORABLE"
    )
    data_caducitat_asseguranca: Mapped[Optional[date]] = mapped_column(Date)
    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))
    polissa_asseguranca: Mapped[Optional[str]] = mapped_column(String(100))
    carnet_necessari: Mapped[str] = mapped_column(String(10), default="B", server_default="B")
    historial_reparacions: Mapped[Optional[str]] = mapped_column(Text)

    # Spec 006: Rènting, Lísing, Lloguer i controls operatius
    regim_adquisicio: Mapped[str] = mapped_column(
        String(30), default="PROPIETAT", server_default="PROPIETAT"
    )
    renting_limit_km: Mapped[Optional[int]] = mapped_column(Integer)
    odometre_inici_contracte: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    data_inici_contracte: Mapped[Optional[date]] = mapped_column(Date)
    data_fi_contracte: Mapped[Optional[date]] = mapped_column(Date)
    quota_mensual_eur: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    tarifa_diaria_eur: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    preu_km_exces_eur: Mapped[float] = mapped_column(
        Numeric(6, 4), default=0.0000, server_default=text("0.0000")
    )
    # Renting, leasing i dades financeres
    empresa_renting: Mapped[Optional[str]] = mapped_column(String(120))
    num_contracte_renting: Mapped[Optional[str]] = mapped_column(String(80))
    data_venciment_renting: Mapped[Optional[date]] = mapped_column(Date)
    valor_residual_eur: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    fianca_eur: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Titularitat i arrendament (conciliació CIF tenant)
    titular_nif: Mapped[Optional[str]] = mapped_column(String(20))
    arrendatari_nif: Mapped[Optional[str]] = mapped_column(String(20))
    codi_servei_dgt: Mapped[Optional[str]] = mapped_column(String(10))

    # Classificació tècnica UE, Pesos i Càrrega (Pesants i Lleugers)
    categoria_ue: Mapped[Optional[str]] = mapped_column(String(10))
    mma_kg: Mapped[Optional[int]] = mapped_column(Integer)
    tara_kg: Mapped[Optional[int]] = mapped_column(Integer)
    carrega_util_kg: Mapped[Optional[int]] = mapped_column(Integer)
    mmr_amb_fre_kg: Mapped[Optional[int]] = mapped_column(Integer)

    requereix_cap: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    equipament_homologat: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    certificats_prl_requerits: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    dades_pesants: Mapped[Optional[dict]] = mapped_column(JSONB)
    regulacio_pesants: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    estat_semafor: Mapped[str] = mapped_column(
        String(40), default="OPERATIU_OK", server_default=text("'OPERATIU_OK'")
    )
    _apte_assignacio_pwa: Mapped[bool] = mapped_column(
        "apte_assignacio_pwa", Boolean, default=True, server_default=text("true")
    )

    # Manteniment, garantia, anomalies i alertes legals (FR-011 / US4 / Spec 006)
    data_fi_garantia_oficial: Mapped[Optional[date]] = mapped_column(Date)
    interval_canvi_oli_km: Mapped[Optional[int]] = mapped_column(
        Integer, default=15000, server_default=text("15000")
    )
    ultim_canvi_oli_km: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    anomalia_consum_descartada: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    data_itv_negativa: Mapped[Optional[date]] = mapped_column(Date)
    data_ultima_descarrega_tacograf: Mapped[Optional[date]] = mapped_column(Date)
    tacograf_necessari: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    data_propera_descarrega_tacograf: Mapped[Optional[date]] = mapped_column(Date)

    # Vehicles EV / PHEV
    capacitat_bateria_kwh: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    soh_bateria: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Capacitats físiques
    places: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    pes_maxim_autoritzat: Mapped[int] = mapped_column(
        Integer, default=3500, server_default=text("3500")
    )

    # Desnormalització de Consums (Batch Celery)
    consum_l_100km: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    consum_mitjana_historica: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    consum_adblue_litres: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.0, server_default=text("0")
    )
    targeta_combustible_bloquejada: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    @hybrid_property
    def apte_assignacio_pwa(self) -> bool:
        """Determina si el vehicle és apte per ser assignat a un operari a la PWA."""
        if getattr(self, "estat", None) in ("BLOQUEJAT", "TALLER", "BAIXA"):
            return False
        if getattr(self, "estat_itv", None) in ("DESFAVORABLE", "NEGATIVA", "CADUCADA"):
            return False
        avui = date.today()
        if self.data_proxima_itv and self.data_proxima_itv < avui:
            return False
        if self.data_caducitat_asseguranca and self.data_caducitat_asseguranca < avui:
            return False
        if self.data_venciment_renting and self.data_venciment_renting < avui:
            return False
        pesants_info = self.dades_pesants or self.regulacio_pesants
        if pesants_info and isinstance(pesants_info, dict):
            visat = pesants_info.get("data_visat_transport")
            if visat:
                try:
                    d_visat = date.fromisoformat(str(visat)) if isinstance(visat, str) else visat
                    if d_visat < avui:
                        return False
                except Exception:
                    pass
            tacograf = pesants_info.get("data_calibratge_tacograf")
            if tacograf:
                try:
                    d_taco = date.fromisoformat(str(tacograf)) if isinstance(tacograf, str) else tacograf
                    if d_taco < avui:
                        return False
                except Exception:
                    pass
        raw_val = getattr(self, "_apte_assignacio_pwa", True)
        return bool(raw_val if raw_val is not None else True)

    @apte_assignacio_pwa.setter  # type: ignore[no-redef]
    def apte_assignacio_pwa(self, val: bool) -> None:  # type: ignore[no-redef]
        self._apte_assignacio_pwa = bool(val)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class RegistreEsdevenimentsSIF(Base):
    __tablename__ = "registre_esdeveniments_sif"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="RESTRICT"), nullable=False
    )
    codi_esdeveniment: Mapped[str] = mapped_column(String(10), nullable=False)
    usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    descripcio: Mapped[str] = mapped_column(Text, nullable=False)
    hash_anterior: Mapped[Optional[str]] = mapped_column(String(64))
    hash_sello: Mapped[str] = mapped_column(String(64), nullable=False)
    dades_event: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    data_creacio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


SIF_IMMUTABLE_FN_DDL = DDL(
    """
    CREATE OR REPLACE FUNCTION fn_prevent_sif_mutation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'SIF_IMMUTABLE_VIOLATION: El Registre d Esdeveniments SIF és Append-Only i no permet UPDATE ni DELETE.';
    END;
    $$ LANGUAGE plpgsql
    """
)
SIF_IMMUTABLE_DROP_DDL = DDL("DROP TRIGGER IF EXISTS trg_sif_immutable ON registre_esdeveniments_sif")
SIF_IMMUTABLE_TRG_DDL = DDL(
    """
    CREATE TRIGGER trg_sif_immutable
    BEFORE UPDATE OR DELETE ON registre_esdeveniments_sif
    FOR EACH ROW EXECUTE FUNCTION fn_prevent_sif_mutation()
    """
)

event.listen(RegistreEsdevenimentsSIF.__table__, "after_create", SIF_IMMUTABLE_FN_DDL)
event.listen(RegistreEsdevenimentsSIF.__table__, "after_create", SIF_IMMUTABLE_DROP_DDL)
event.listen(RegistreEsdevenimentsSIF.__table__, "after_create", SIF_IMMUTABLE_TRG_DDL)


class Finca(Base):
    __tablename__ = "finques"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    latitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    ref_cadastral: Mapped[Optional[str]] = mapped_column(String(50))
    poligon_sigpac: Mapped[Optional[str]] = mapped_column(String(50))
    parcel_sigpac: Mapped[Optional[str]] = mapped_column(String(50))
    codi_candat_en_memoria: Mapped[Optional[str]] = mapped_column(String(50))
    dades_sigpac: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    superficie_ha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class EinaCustodia(Base):
    __tablename__ = "eines_custodia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    referencia_fabricant: Mapped[Optional[str]] = mapped_column(String(100))
    nom: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    numero_serie: Mapped[str] = mapped_column(String(100), nullable=False)
    estat: Mapped[str] = mapped_column(
        String(30), default="DISPONIBLE", server_default="DISPONIBLE"
    )
    custodiat_per_operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    magatzem_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="SET NULL")
    )
    data_ultima_calibracio: Mapped[Optional[date]] = mapped_column(Date)
    data_propera_calibracio: Mapped[Optional[date]] = mapped_column(Date)
    data_fi_garantia: Mapped[Optional[date]] = mapped_column(Date)
    observacions: Mapped[Optional[str]] = mapped_column(Text)
    incidencies: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class TiquetCarburant(Base):
    __tablename__ = "tiquets_carburant"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    operari_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False
    )
    tiquet_foto_path: Mapped[str] = mapped_column(String(500), nullable=False)
    odometre_foto_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    litres: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    import_: Mapped[Optional[float]] = mapped_column("import", Numeric(10, 2), nullable=True)
    data_repostatge: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    odometre_valor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estat_ocr: Mapped[str] = mapped_column(
        String(30), default="PENDENT_AUDITORIA", server_default="PENDENT_AUDITORIA"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Proveidor(Base):
    __tablename__ = "proveidors"
    __table_args__ = (UniqueConstraint("empresa_id", "codi", name="uq_proveidors_empresa_codi"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    rao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    telefon: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    especialitat: Mapped[str] = mapped_column(
        String(50), default="MATERIALS", server_default="MATERIALS"
    )
    es_recc: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    aplica_isp_defecte: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    iban_xifrat_simetric: Mapped[Optional[str]] = mapped_column(Text)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class DocumentCAERC(Base):
    __tablename__ = "documents_cae_rc"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    proveidor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="CASCADE"), nullable=False
    )
    tipus_document: Mapped[str] = mapped_column(String(30), nullable=False)
    data_caducitat: Mapped[date] = mapped_column(Date, nullable=False)
    fitxer_path: Mapped[str] = mapped_column(String(500), nullable=False)
    estat: Mapped[str] = mapped_column(String(20), default="VALIDAT", server_default="VALIDAT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FacturaProveidor(Base):
    __tablename__ = "factures_proveidor"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "proveidor_id", "numero_factura", name="uq_factures_prov_empresa_num"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    proveidor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="CASCADE"), nullable=False
    )
    numero_factura: Mapped[str] = mapped_column(String(100), nullable=False)
    data_factura: Mapped[date] = mapped_column(Date, nullable=False)
    base_imposable: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0"))
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0"))
    albara_numero: Mapped[Optional[str]] = mapped_column(String(100))
    estat: Mapped[str] = mapped_column(
        String(50), default="PENDENT_REVISIO", server_default="PENDENT_REVISIO"
    )
    comanda_numero: Mapped[Optional[str]] = mapped_column(String(100))
    estat_conciliacio: Mapped[str] = mapped_column(
        String(30), default="PENDENT", server_default="PENDENT"
    )
    desviacio_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, server_default=text("0")
    )
    fitxer_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    data_venciment: Mapped[Optional[date]] = mapped_column(Date)
    data_pagament_real: Mapped[Optional[date]] = mapped_column(Date)
    import_retencio_garantia_4008: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    import_pagat: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    es_recc_passiu_4729: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    pagada: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    estat_pagament: Mapped[str] = mapped_column(
        String(40), default="PENDENT", server_default="PENDENT"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class OrdreTreball(Base):
    __tablename__ = "ordres_treball"
    __table_args__ = (UniqueConstraint("empresa_id", "codi", name="uq_ordres_empresa_codi"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    finca_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("finques.id", ondelete="SET NULL")
    )
    titol: Mapped[str] = mapped_column(String(200), nullable=False)
    adreca: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    estat: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default="PENDENT")
    data_planificacio: Mapped[date] = mapped_column(
        Date, default=date.today, server_default=text("CURRENT_DATE")
    )
    hora_inici_prevista: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hora_fi_prevista: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hora_inici_real: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hora_fi_real: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    versio: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    latitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    gps_inici_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    gps_inici_lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    gps_fi_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    gps_fi_lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    cap_de_colla_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    planol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planols_base.id", ondelete="SET NULL")
    )
    contracte_mrr_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    vertical: Mapped[str] = mapped_column(
        String(50), default="INSTAL_LACIONS", server_default="INSTAL_LACIONS"
    )
    data_finalitzacio_camp: Mapped[Optional[date]] = mapped_column(Date)
    factura_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    import_pressupostat: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    hores_imputades_facturables: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0.00, server_default=text("0")
    )
    preu_venda_hora_aplicat: Mapped[float] = mapped_column(
        Numeric(8, 2), default=45.00, server_default=text("45.00")
    )
    cost_materials_pmp: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    pvp_materials_aplicat: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    cost_materials_picking_pmp: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    cost_ma_obra_real: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    cost_flota_real: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    import_pressupostat_net: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    km_imputats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    __mapper_args__ = {"version_id_col": versio}


class OrdreTreballOperari(Base):
    __tablename__ = "ordres_treball_operaris"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "ordre_treball_id", "operari_id", name="uq_ordres_treball_operaris"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operari_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False, index=True
    )
    es_cap_de_colla: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FullaPicking(Base):
    __tablename__ = "fulles_picking"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    estat_picking: Mapped[str] = mapped_column(
        String(30), default="PENDENT", server_default="PENDENT"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class LiniaPicking(Base):
    __tablename__ = "linies_picking"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    picking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulles_picking.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    quantitat_prevista: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    quantitat_carregada_pick_in: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    quantitat_retornada_pick_out: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    quantitat_mermada: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0.0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class Incidencia(Base):
    __tablename__ = "incidencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    ambit: Mapped[str] = mapped_column(String(30), default="TASCA", server_default="TASCA")
    tipus: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    gravetat: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    estat: Mapped[str] = mapped_column(String(20), default="VERMELL", server_default="VERMELL")
    audio_path: Mapped[Optional[str]] = mapped_column(String(500))
    foto_path: Mapped[Optional[str]] = mapped_column(String(500))
    text_observacions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class CapaAnotacio(Base):
    __tablename__ = "capes_anotacions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False
    )
    nom_capa: Mapped[str] = mapped_column(String(100), nullable=False)
    fitxer_vectorial_path: Mapped[str] = mapped_column(String(500), nullable=False)
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    estat_capa: Mapped[str] = mapped_column(String(30), default="ACTIVA", server_default="ACTIVA")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FacturaCapcalera(Base):
    __tablename__ = "factures_capcalera"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "serie", "numero_factura", name="uq_factures_empresa_serie_num"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    numero_factura: Mapped[int] = mapped_column(Integer, nullable=False)
    serie: Mapped[str] = mapped_column(String(20), default="2026", server_default="2026")
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    data_emissio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    base_imposable: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0"))
    import_retencio: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    import_suplits: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    liquid_exigible: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    estat_cobrament: Mapped[str] = mapped_column(
        String(20), default="PENDENT", server_default="PENDENT"
    )
    estat_enviament: Mapped[str] = mapped_column(
        String(20), default="PENDENT", server_default="PENDENT"
    )
    hash_anterior: Mapped[Optional[str]] = mapped_column(String(64))
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qr_code_path: Mapped[Optional[str]] = mapped_column(String(500))
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    estat_document: Mapped[str] = mapped_column(
        String(30), default="EMESA", server_default="EMESA"
    )
    data_venciment: Mapped[Optional[date]] = mapped_column(Date)
    data_cobrament_real: Mapped[Optional[date]] = mapped_column(Date)
    metode_pagament: Mapped[str] = mapped_column(
        String(30), default="TRANSFERENCIA", server_default="TRANSFERENCIA"
    )
    es_inversio_subjecte_passiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    justificant_suplerts_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    import_retencio_garantia_4308: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    import_cobrat: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0")
    )
    factura_rectificada_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="RESTRICT")
    )
    motiu_rectificacio: Mapped[Optional[str]] = mapped_column(Text)
    estat_art80: Mapped[str] = mapped_column(
        String(40), default="NO_APLICA", server_default="NO_APLICA"
    )
    justificant_reclamacio_art80_path: Mapped[Optional[str]] = mapped_column(String(500))
    qr_verifactu_payload: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FacturaLinia(Base):
    __tablename__ = "factures_linies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    factura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="CASCADE"), nullable=False
    )
    centre_de_cost_id: Mapped[Optional[str]] = mapped_column(String(50))
    obra_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    concepte: Mapped[str] = mapped_column(String(200), nullable=False)
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), default=1.0, server_default=text("1"))
    preu_venda_unitari: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0")
    )
    tipus_iva: Mapped[float] = mapped_column(
        Numeric(4, 2), default=21.00, server_default=text("21")
    )
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0"))
    compte_pgc: Mapped[str] = mapped_column(String(10), default="700000", server_default="700000")
    quantitat_merma: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0")
    )
    descompte_aplicat_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.00, server_default=text("0")
    )
    cost_unitari_historic: Mapped[float] = mapped_column(
        Numeric(12, 4), default=0.0000, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class OutboxEnviamentAEAT(Base):
    __tablename__ = "outbox_enviaments_aeat"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    factura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="CASCADE"), nullable=False
    )
    payload_xml_path: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    intents_enviament: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    estat_enviament: Mapped[str] = mapped_column(
        String(20), default="PENDENT", server_default="PENDENT"
    )
    darrera_resposta_soap: Mapped[Optional[str]] = mapped_column(Text)
    data_creacio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    data_actualitzacio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class CarpetaPlanol(Base):
    __tablename__ = "carpetes_planols"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    finca_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("finques.id", ondelete="CASCADE")
    )
    municipi: Mapped[Optional[str]] = mapped_column(String(100))
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carpetes_planols.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class PlanolBase(Base):
    __tablename__ = "planols_base"
    __table_args__ = (UniqueConstraint("empresa_id", "codi_referencia", name="uq_planols_codi"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    carpeta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carpetes_planols.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    finca_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("finques.id", ondelete="CASCADE")
    )
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    codi_referencia: Mapped[str] = mapped_column(String(50), nullable=False)
    tipus_fitxer: Mapped[str] = mapped_column(String(20), nullable=False)
    es_georeferenciat: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    fitxer_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mida_bytes: Mapped[int] = mapped_column(BIGINT, nullable=False)
    bounds_wgs84: Mapped[Optional[dict]] = mapped_column(JSONB)
    projeccio_origen: Mapped[str] = mapped_column(
        String(30), default="WGS84", server_default="WGS84"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class CapaVectorial(Base):
    __tablename__ = "capes_vectorials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    planol_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planols_base.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    disciplina: Mapped[str] = mapped_column(String(30), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    es_immutable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    color_hex: Mapped[str] = mapped_column(String(10), default="#2563eb", server_default="#2563eb")
    gruix_linia: Mapped[int] = mapped_column(Integer, default=2, server_default=text("2"))
    opacitat_percent: Mapped[int] = mapped_column(Integer, default=100, server_default=text("100"))
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    geometries_geojson: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    version_id: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    creat_per_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class PinIncidenciaPlanol(Base):
    __tablename__ = "pins_incidencia_planol"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    capa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capes_vectorials.id", ondelete="CASCADE"), nullable=False
    )
    latitud: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitud: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    simbol: Mapped[str] = mapped_column(
        String(50), default="AVARIA_REG", server_default="AVARIA_REG"
    )
    estat: Mapped[str] = mapped_column(
        String(20), default="PENDENT_REVISIO", server_default="PENDENT_REVISIO"
    )
    audio_nota_path: Mapped[Optional[str]] = mapped_column(String(500))
    foto_evidencia_path: Mapped[Optional[str]] = mapped_column(String(500))
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class ExportacioPdfPlanol(Base):
    __tablename__ = "exportacions_pdf_planol"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    planol_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planols_base.id", ondelete="CASCADE"), nullable=False
    )
    titol_report: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    finca_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("finques.id", ondelete="CASCADE")
    )
    capes_incloses_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    escala_grafica: Mapped[str] = mapped_column(String(30), default="1:500", server_default="1:500")
    pdf_generat_path: Mapped[Optional[str]] = mapped_column(String(500))
    estat: Mapped[str] = mapped_column(String(20), default="GENERAT", server_default="GENERAT")
    caixeti_dades: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class TokenInvitacioTelegram(Base):
    __tablename__ = "tokens_invitacio_telegram"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    expira_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utilitzat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    utilitzat_a: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class ConversaNotificacio(Base):
    __tablename__ = "converses_notificacio"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    estat: Mapped[str] = mapped_column(
        String(30), default="BLAU_OBERT", server_default="BLAU_OBERT"
    )
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    ultim_missatge_text: Mapped[Optional[str]] = mapped_column(Text)
    ultim_missatge_data: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    num_missatges_sense_llegir: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    es_arxivada: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MissatgeNotificacio(Base):
    __tablename__ = "missatges_notificacio"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    conversa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("converses_notificacio.id", ondelete="CASCADE"),
        nullable=False,
    )
    remitent_tipus: Mapped[str] = mapped_column(String(30), nullable=False)
    remitent_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    canal: Mapped[str] = mapped_column(String(20), default="TELEGRAM", server_default="TELEGRAM")
    contingut_text: Mapped[str] = mapped_column(Text, nullable=False)
    tipus_esdeveniment: Mapped[str] = mapped_column(
        String(50), default="MISSATGE_TEXT", server_default="MISSATGE_TEXT"
    )
    adjunt_url: Mapped[Optional[str]] = mapped_column(String(500))
    adjunt_tipus: Mapped[Optional[str]] = mapped_column(String(50))
    adjunt_mida_bytes: Mapped[Optional[int]] = mapped_column(BIGINT)
    token_aprobacio: Mapped[Optional[str]] = mapped_column(String(100))
    estat_aprobacio: Mapped[str] = mapped_column(
        String(30), default="PENDENT", server_default="PENDENT"
    )
    token_descarrega_factura: Mapped[Optional[str]] = mapped_column(String(100))
    token_descarrega_expira_a: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FaqCorporativaRag(Base):
    __tablename__ = "faqs_corporatives_rag"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    pregunta: Mapped[str] = mapped_column(String(255), nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), default="GENERAL", server_default="GENERAL")
    paraules_clau: Mapped[Optional[str]] = mapped_column(String(255))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MemorandumTecnicCopilot(Base):
    __tablename__ = "memorandums_tecnics_copilot"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    incidencia_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidencies.id", ondelete="SET NULL")
    )
    transcripcio_audio: Mapped[Optional[str]] = mapped_column(Text)
    confianca_acustica: Mapped[float] = mapped_column(
        Numeric(4, 2), default=1.00, server_default=text("1")
    )
    avis_soroll_sever: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    analisi_visual: Mapped[Optional[str]] = mapped_column(Text)
    dictamen_pericial: Mapped[str] = mapped_column(
        String(30), default="EXTRA_FACTURABLE", server_default="EXTRA_FACTURABLE"
    )
    motiu_dictamen: Mapped[str] = mapped_column(Text, nullable=False)
    estimacio_temps_extra_minuts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    estimacio_materials_extra: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    cost_estimat_total: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0")
    )
    validat_per_enginyer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    enginyer_validador_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    data_validacio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observacions_enginyer: Mapped[Optional[str]] = mapped_column(Text)
    estat: Mapped[str] = mapped_column(String(20), default="PROPOSTA", server_default="PROPOSTA")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class AuditoriaPostObra(Base):
    __tablename__ = "auditories_post_obra"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ordres_treball.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    desviacio_hores: Mapped[float] = mapped_column(
        Numeric(6, 2), default=0.00, server_default=text("0")
    )
    desviacio_materials: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    desviacio_km: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0.00, server_default=text("0")
    )
    despeses_camp: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0")
    )
    marge_previst_percentatge: Mapped[float] = mapped_column(
        Numeric(5, 2), default=30.00, server_default=text("30")
    )
    marge_real_liquidat_percentatge: Mapped[float] = mapped_column(
        Numeric(5, 2), default=30.00, server_default=text("30")
    )
    alerta_merma_operativa: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    detall_merma: Mapped[Optional[str]] = mapped_column(Text)
    bloqueig_consum_excessiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    bloqueig_sync_pendent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    pressupost_corregit_proposta: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    estat: Mapped[str] = mapped_column(
        String(30), default="PENDENT_CONFIRMACIO", server_default="PENDENT_CONFIRMACIO"
    )
    enginyer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    data_aprovacio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class AlertaGarantiaRecompra(Base):
    __tablename__ = "alertes_garantia_recompra"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    tipus_alerta: Mapped[str] = mapped_column(String(30), nullable=False)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    numero_serie: Mapped[Optional[str]] = mapped_column(String(100))
    proveidor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="SET NULL")
    )
    missatge: Mapped[str] = mapped_column(Text, nullable=False)
    data_fi_garantia: Mapped[Optional[date]] = mapped_column(Date)
    estat: Mapped[str] = mapped_column(String(20), default="ACTIVA", server_default="ACTIVA")
    dades_comanda_proposta: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class ConsultaXatCopilot(Base):
    __tablename__ = "consultes_xat_copilot"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    usuari_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False
    )
    pregunta: Mapped[str] = mapped_column(Text, nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    vertical: Mapped[str] = mapped_column(String(100), default="SEVALOR", server_default="SEVALOR")
    node_ia_actiu: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    node_ia_url: Mapped[Optional[str]] = mapped_column(String(255))
    feature_copilot_ia: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    feature_flota: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    feature_planols: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    feature_telegram: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    data_onboarding: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    temps_inferencia_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    enllacos_relacionats: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    es_error_timeout: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    denegat_per_rol: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_args: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tool_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MovimentEstoc(Base):
    __tablename__ = "moviments_estoc"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    magatzem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    tipus_moviment: Mapped[str] = mapped_column(String(20), nullable=False)
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    referencia_document: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(String(200))
    usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class AlbaraProveidor(Base):
    __tablename__ = "albarans_proveidor"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "proveidor_id", "numero_albara", name="uq_albarans_prov_empresa_num"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    proveidor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="CASCADE"), nullable=False
    )
    numero_albara: Mapped[str] = mapped_column(String(100), nullable=False)
    data_albara: Mapped[date] = mapped_column(Date, nullable=False)
    estat: Mapped[str] = mapped_column(
        String(30), default="PENDENT_AUDITORIA", server_default="PENDENT_AUDITORIA"
    )
    fitxer_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class FacturaProveidorLinia(Base):
    __tablename__ = "factures_proveidor_linies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    factura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_proveidor.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), nullable=True, default=1.0)
    preu_unitari: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)


class Pressupost(Base):
    """Model per emmagatzemar pressupostos abans de la factura (Phase 4)."""

    __tablename__ = "pressupostos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "numero", name="uq_pressupost_empresa_numero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    numero: Mapped[str] = mapped_column(String(30), nullable=False)

    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0"))
    estat: Mapped[str] = mapped_column(
        String(20), default="PENDENT", server_default="PENDENT"
    )  # PENDENT, APROVAT, REBUTJAT
    token_signatura: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # Token de Telegram al aprovar

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class HistorialAssignacioVehicle(Base):
    __tablename__ = "historial_assignacions_vehicles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "vehicle_id", "data_inici", name="uq_assignacio_inici"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    conductor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False
    )
    data_inici: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_fi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    odometre_inici: Mapped[Optional[int]] = mapped_column(Integer)
    odometre_fi: Mapped[Optional[int]] = mapped_column(Integer)
    motiu: Mapped[Optional[str]] = mapped_column(String(255))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MantenimentVehicle(Base):
    __tablename__ = "manteniments_vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    data_manteniment: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tipus: Mapped[str] = mapped_column(String(50), nullable=False)  # PREVENTIU, CORRECTIU
    descripcio: Mapped[str] = mapped_column(Text, nullable=False)
    taller: Mapped[Optional[str]] = mapped_column(String(255))
    cost_euros: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TiquetCombustible(Base):
    __tablename__ = "tiquets_combustible"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    conductor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    data_tiquet: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    import_euros: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    litres: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    kwh_recarrega: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    litres_adblue: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    odometre_registrat: Mapped[int] = mapped_column(Integer, nullable=False)
    ruta_arxiu_pwa: Mapped[Optional[str]] = mapped_column(String(500))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class DocumentFlota(Base):
    __tablename__ = "documents_flota"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    tipus_document: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # FITXA_TECNICA, INFORME_ITV, ITV, ASSEGURANCA, REPARACIO, CONTRACTE, CONTRACTE_RENTING, TARGETA_TRANSPORT, GENERAL, MANTENIMENT
    nom_arxiu: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_arxiu: Mapped[str] = mapped_column(String(500), nullable=False)
    contingut_extret: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Text extret via OCR per al Copilot
    bastidor_detectat: Mapped[Optional[str]] = mapped_column(String(30))
    nif_detectat: Mapped[Optional[str]] = mapped_column(String(20))
    metadata_ocr: Mapped[Optional[dict]] = mapped_column(JSONB)
    data_document: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )


class SaasFacturaB2B(Base):
    """Facturació B2B SaaS (Superadmin -> Empresa Client) amb Human-in-the-Loop i Veri*factu."""

    __tablename__ = "saas_factures_b2b"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True
    )
    client_nom_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    client_nif_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    serie: Mapped[str] = mapped_column(String(20), default="SAAS", server_default="SAAS")
    numero_factura: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estat: Mapped[str] = mapped_column(
        String(30), default="ESBORRANY_PREFACTURA", server_default="ESBORRANY_PREFACTURA"
    )  # ESBORRANY_PREFACTURA, EMESA_VERIFACTU, COBRADA, IMPAGADA
    periode: Mapped[str] = mapped_column(String(30), nullable=False)
    concepte_onboarding_desc: Mapped[Optional[str]] = mapped_column(String(255))
    import_onboarding: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    concepte_config_ia_desc: Mapped[Optional[str]] = mapped_column(String(255))
    import_config_ia: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    equips_ia_detall: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    import_equips_ia: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    num_operaris_facturats: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    preu_unitari_operari: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    import_operaris: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    base_imposable: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    tipus_iva_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), default=21.00, server_default=text("21.00")
    )
    quota_iva: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    import_total: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    verificada_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    data_verificacio_humana: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    hash_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    hash_anterior: Mapped[Optional[str]] = mapped_column(String(64))
    qr_verifactu: Mapped[Optional[str]] = mapped_column(Text)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    data_emissio: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasTiquetSuport(Base):
    """Tiquets d'incidència tècnica CRM conservats permanentment i amb diagnòstic de PC local."""

    __tablename__ = "saas_tiquets_suport"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True
    )
    empresa_nom_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    assumpte: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcio: Mapped[str] = mapped_column(Text, nullable=False)
    severitat: Mapped[str] = mapped_column(
        String(20), default="NORMAL", server_default="NORMAL"
    )  # BAIXA, NORMAL, ALTA, CRITICA
    estat: Mapped[str] = mapped_column(
        String(30), default="OBERT", server_default="OBERT"
    )  # OBERT, EN_CURS, RESOLT, TANCAT
    pc_empresa_online_al_crear: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    diagnostic_automatic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolucio_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SaasHistorialLlicencia(Base):
    """Traçabilitat històrica de canvis de quota d'operaris i estat del cicle de vida."""

    __tablename__ = "saas_historial_llicencia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True
    )
    quota_operaris_anterior: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_operaris_nova: Mapped[int] = mapped_column(Integer, nullable=False)
    estat_anterior: Mapped[Optional[str]] = mapped_column(String(30))
    estat_nou: Mapped[Optional[str]] = mapped_column(String(30))
    motiu: Mapped[Optional[str]] = mapped_column(String(255))
    autor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasProspeccioTasca(Base):
    """Lot atòmic d'execució de prospecció per Codi Postal i Vertical Lliure."""

    __tablename__ = "saas_prospeccio_tasques"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    codi_postal: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    vertical: Mapped[str] = mapped_column(String(150), nullable=False)
    operaris_minims: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    estat: Mapped[str] = mapped_column(
        String(30), default="PENDENT", server_default="PENDENT", index=True
    )  # PENDENT, EXECUTANT, COMPLETAT, PAUSAT, ERROR
    total_trobats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_seleccionats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_descartats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_duplicats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    resum_execucio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embut_descoberta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    autor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SaasLead(Base):
    """Prospecte o lead comercial B2B per a la prospecció de Sevalor Suite."""

    __tablename__ = "saas_leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nom_empresa: Mapped[str] = mapped_column(String(150), nullable=False)
    nom_contacte: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    telefon: Mapped[Optional[str]] = mapped_column(String(30))
    vertical: Mapped[str] = mapped_column(String(150), default="CampoPro", server_default="CampoPro")
    origen: Mapped[str] = mapped_column(String(50), default="WEB", server_default="WEB")
    estat_qualificacio: Mapped[str] = mapped_column(
        String(50), default="NOU", server_default="NOU", index=True
    )  # NOU, CONTACTAT, QUALIFICAT, DEMO_DEMANADA, DEMO_ACTIVA, PROPOSTA_ENVIADA, GUANYAT, DESCARTAT
    operaris_estimats: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    empresa_demo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True
    )
    data_inici_demo: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    data_fi_demo: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dies_demo_durada: Mapped[int] = mapped_column(Integer, default=7, server_default=text("7"))

    # Camps d'intel·ligència de prospecció, multi-validació i outreach
    cif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    web_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domini_normalitzat: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    adreca_fisica: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adreca_normalitzada: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    codi_postal: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    carrec_contacte: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fonts_investigades: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fita_recent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    punt_dolor_detectat: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    angle_atac: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    score_qualificacio: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    justificacio_ia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mx_validat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    cp_geocode_retornat: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    cp_geocode_coincideix: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gatekeeper_font_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gatekeeper_cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gatekeeper_confianca: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    esborrany_email_assumpte: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    esborrany_email_cos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rao_tancament_exit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    es_tancament_replicable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    tasca_prospeccio_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_prospeccio_tasques.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasOportunitat(Base):
    """Oportunitat de negoci al Pipeline comercial (estil Twenty CRM Kanban)."""

    __tablename__ = "saas_oportunitats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False
    )
    titol: Mapped[str] = mapped_column(String(200), nullable=False)
    etapa: Mapped[str] = mapped_column(
        String(50), default="PROSPECCIO", server_default="PROSPECCIO", index=True
    )  # PROSPECCIO, QUALIFICACIO, DEMO_7_DIES, PROPOSTA, NEGOCIACIO, GUANYAT, PERDUT
    valor_mensual_estimat: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    valor_ia_setup: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, server_default=text("0.00")
    )
    probabilitat_percent: Mapped[int] = mapped_column(Integer, default=20, server_default=text("20"))
    data_tancament_prevista: Mapped[Optional[date]] = mapped_column(Date)
    motiu_perdua: Mapped[Optional[str]] = mapped_column(String(255))
    rao_tancament_exit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requisits_replicables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    es_replicable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasActivitatLead(Base):
    """Timeline d'interaccions i notes comercials associades a un Lead."""

    __tablename__ = "saas_activitats_lead"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipus: Mapped[str] = mapped_column(
        String(30), default="NOTA", server_default="NOTA"
    )  # NOTA, TRUCADA, REUNIO, EMAIL, DEMO_LLANCADA, ESTAT_CANVIAT
    titol: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    autor_nom: Mapped[str] = mapped_column(String(100), default="Superadmin", server_default="Superadmin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasProspeccioCandidat(Base):
    """Registre transparent de candidats analitzats al Codi Postal (Seleccionats, Descartats, Duplicats)."""

    __tablename__ = "saas_prospeccio_candidats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tasca_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_prospeccio_tasques.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom_empresa: Mapped[str] = mapped_column(String(150), nullable=False)
    cif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    web_url: Mapped[str] = mapped_column(String(255), nullable=False)
    domini_normalitzat: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    adreca_fisica: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adreca_normalitzada: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    codi_postal: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    vertical: Mapped[str] = mapped_column(String(150), nullable=False)
    fonts_investigades: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_detectat: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    telefon_detectat: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    mx_validat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    operaris_estimats: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    decisor_nom: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decisor_carrec: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fita_recent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    punt_dolor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    angle_atac: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    estat_decisio: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # SELECCIONAT, SELECCIONAT_SENSE_GATEKEEPER, DESCARTAT, DUPLICAT, ERROR_EXTRACCIO
    cp_geocode_retornat: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    cp_geocode_coincideix: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gatekeeper_font_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gatekeeper_cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gatekeeper_confianca: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    vector_duplicitat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    motiu_detallat_ia: Mapped[str] = mapped_column(Text, nullable=False)
    corregit_huma: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    decisio_humana: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    motiu_correccio_humana: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_leads.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasCriteriFeedback(Base):
    """Memòria del Doble Bucle d'Aprenentatge (Descarts justificats + Tancaments d'èxit replicables)."""

    __tablename__ = "saas_criteris_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tipus_aprenentatge: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )  # CORRECCIO_DESCART, CORRECCIO_SELECCIO, TANCAMENT_EXIT_REPLICABLE
    candidat_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_prospeccio_candidats.id", ondelete="SET NULL"), nullable=True
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_leads.id", ondelete="SET NULL"), nullable=True
    )
    vertical: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    nom_empresa: Mapped[str] = mapped_column(String(150), nullable=False)
    web_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resum_evidencies_o_requisits: Mapped[str] = mapped_column(Text, nullable=False)
    decisio_ia_original: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    decisio_humana_correcta: Mapped[str] = mapped_column(String(30), nullable=False)
    explicacio_humana_o_rao_exit: Mapped[str] = mapped_column(Text, nullable=False)
    es_replicable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasCorreuMissatge(Base):
    """Fils de correu (IMAP/SMTP), campanyes de 3 emails amb tempo i esdeveniments de calendari."""

    __tablename__ = "saas_correu_missatges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipus_item_calendari: Mapped[str] = mapped_column(
        String(30), default="EMAIL_CAMPANYA", server_default="EMAIL_CAMPANYA"
    )  # EMAIL_CAMPANYA, RESPOSTA_INBOUND, SEGUIMENT_CALENDARI, REUNIO_DEMO
    pas_sequencia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1, 2, 3
    tempo_dies_offset: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))  # 0, 4, 8
    data_programada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    direccio: Mapped[str] = mapped_column(
        String(20), default="OUTBOUND", server_default="OUTBOUND"
    )  # OUTBOUND, INBOUND, INTERN_CALENDARI
    estat_enviament: Mapped[str] = mapped_column(
        String(30), default="ESBORRANY_PROGRAMAT", server_default="ESBORRANY_PROGRAMAT", index=True
    )  # ESBORRANY_PROGRAMAT, APROVAT_ENVIAT, PAUSAT_PER_RESPOSTA, CANCEL_LAT, REBUT, COMPLETAT
    remitent: Mapped[str] = mapped_column(String(150), nullable=False)
    destinatari: Mapped[str] = mapped_column(String(150), nullable=False)
    assumpte: Mapped[str] = mapped_column(String(255), nullable=False)
    cos_text: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    references_header: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intencio_ia: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resum_ia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aprovat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SaasExclusioRgpd(Base):
    """Llista negra universal d'exclusió RGPD / LSSI i rebots permanents (Do-Not-Contact)."""

    __tablename__ = "saas_exclusio_rgpd"
    __table_args__ = (
        UniqueConstraint("email", "domini", name="uq_exclusio_email_domini"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    domini: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    cif: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    motiu: Mapped[str] = mapped_column(
        String(50), default="OPTOUT_EXPLICIT", server_default="OPTOUT_EXPLICIT"
    )  # OPTOUT_EXPLICIT, REBOT_HARD, MANUAL_SUPERADMIN
    origen_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


# --- SPEC 007 (v5.0): SUITE ECONÒMICA, RETENCIONS, TIQUETS, MRR I NORMA 43 ---


class ContracteMantenimentMRR(Base):
    """Contractes de manteniment recurrent per a càlcul de MRR i sinistralitat."""

    __tablename__ = "contractes_manteniment_mrr"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    codi_contracte: Mapped[str] = mapped_column(String(50), nullable=False)
    quota_mensual_mrr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    data_inici: Mapped[date] = mapped_column(Date, nullable=False)
    data_fi: Mapped[Optional[date]] = mapped_column(Date)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class SerieFiscalVerifactu(Base):
    """Control d'encadenament SHA-256 amb bloqueig SELECT FOR UPDATE per sèrie/exercici."""

    __tablename__ = "series_fiscals_verifactu"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codi_serie", "exercici", name="uq_serie_empresa_exercici"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    codi_serie: Mapped[str] = mapped_column(String(20), nullable=False)
    exercici: Mapped[int] = mapped_column(Integer, nullable=False)
    ultim_numero: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    ultim_hash_sha256: Mapped[str] = mapped_column(
        String(64), default="0" * 64, server_default=text("repeat('0', 64)")
    )


class RetencioGarantia(Base):
    """Control de retencions per garantia d'obra (comptes 4308 / 4008, 365 dies)."""

    __tablename__ = "retencions_garantia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipus: Mapped[str] = mapped_column(String(30), nullable=False)  # CLIENT_4308 / PROVEIDOR_4008
    factura_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="SET NULL")
    )
    factura_proveidor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_proveidor.id", ondelete="SET NULL")
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    obra_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    import_retingut: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    percentatge_aplicat: Mapped[float] = mapped_column(
        Numeric(5, 2), default=5.00, server_default=text("5.00")
    )
    data_retencio: Mapped[date] = mapped_column(Date, nullable=False)
    data_venciment_garantia: Mapped[date] = mapped_column(Date, nullable=False)
    estat: Mapped[str] = mapped_column(
        String(30), default="RETINGUDA", server_default="RETINGUDA"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class TiquetDespesa(Base):
    """Tiquets i despeses de camp amb control fiscal d'IVA i llindar >100 EUR."""

    __tablename__ = "tiquets_despesa"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    usuari_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    data_tiquet: Mapped[date] = mapped_column(
        Date, default=date.today, server_default=text("CURRENT_DATE"), nullable=False
    )
    nif_emissor: Mapped[Optional[str]] = mapped_column(String(20))
    nif_comprador: Mapped[Optional[str]] = mapped_column(String(20))
    rao_social: Mapped[Optional[str]] = mapped_column(String(255))
    base_imposable: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    iva_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=21.00, server_default=text("21.00"))
    quota_iva: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, server_default=text("0.00"))
    import_total: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    subcompte_pgc: Mapped[str] = mapped_column(String(40), default="629000", server_default="629000")
    estat_aprovacio: Mapped[str] = mapped_column(
        String(50), default="PENDENT_AUDITORIA", server_default="PENDENT_AUDITORIA"
    )
    estat_fiscal: Mapped[str] = mapped_column(
        String(30), default="DEDUIBLE", server_default="DEDUIBLE"
    )
    requereix_aprovacio_boss: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    custodia_paper_confirmada: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    nom_fitxer_visible: Mapped[Optional[str]] = mapped_column(String(255))
    foto_tiquet_path: Mapped[Optional[str]] = mapped_column(String(500))
    foto_odometre_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class DespesaFixaRecurrent(Base):
    """Despeses fixes d'estructura per a EBITDA, Break-Even i Burn Rate."""

    __tablename__ = "despeses_fixes_recurrents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concepte: Mapped[str] = mapped_column(String(255), nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    import_base: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text("0.00"))
    periodicitat: Mapped[str] = mapped_column(
        String(20), default="MENSUAL", server_default="MENSUAL"
    )
    dia_carrec: Mapped[int] = mapped_column(Integer, default=5, server_default=text("5"))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class ApuntBancariNorma43(Base):
    """Moviments bancaris CSB 43 amb empremta SHA-256 idempotent."""

    __tablename__ = "apunts_bancaris_norma43"
    __table_args__ = (
        UniqueConstraint("empresa_id", "huella_sha256", name="uq_norma43_huella"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_operacio: Mapped[date] = mapped_column(Date, nullable=False)
    concepte: Mapped[str] = mapped_column(String(500), nullable=False)
    import_moviment: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    divisa: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    saldo_resultant: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    huella_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    conciliat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    factura_conciliada_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MermaInventari(Base):
    """Registre transaccional de mermes d'inventari i transferència a residus/obra."""

    __tablename__ = "mermes_inventari"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    magatzem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="CASCADE"), nullable=False
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL")
    )
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    pmp_aplicat: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    cost_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    motiu: Mapped[str] = mapped_column(String(50), nullable=False)
    subcompte_comptable: Mapped[str] = mapped_column(String(40), nullable=False)
    transferit_slot_residus: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class DespesaComptable(Base):
    """Assentament analític de despeses imputades des de Magatzem o OCR Tiquets."""

    __tablename__ = "despeses_comptables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL")
    )
    tiquet_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tiquets_despesa.id", ondelete="SET NULL")
    )
    merma_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mermes_inventari.id", ondelete="SET NULL")
    )
    concepte: Mapped[str] = mapped_column(String(500), nullable=False)
    subcompte: Mapped[str] = mapped_column(String(40), nullable=False)
    base_imposable: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    quota_iva: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    import_total: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0.00, server_default=text("0.00")
    )
    estat: Mapped[str] = mapped_column(
        String(40), default="PENDENT_VALIDACIO", server_default="PENDENT_VALIDACIO"
    )
    origen: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class TelemetriaSistema(Base):
    """Mètriques del sistema emmagatzemades a l'esquema aïllat superadmin_telemetry (Spec 022 RF-03)."""

    __tablename__ = "telemetria_sistema"
    __table_args__ = {"schema": "superadmin_telemetry"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    cluster: Mapped[str] = mapped_column(
        String(100), nullable=False, default="hetzner-cpx21", server_default="hetzner-cpx21"
    )
    node: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cpu_utilization_percent: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=0.00, server_default=text("0.00")
    )
    ram_utilization_mb: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.00, server_default=text("0.00")
    )
    ram_total_mb: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.00, server_default=text("0.00")
    )
    db_pool_occupancy_percent: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    p95_latency_ms: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    queue_depths: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class AlertaSeguretat(Base):
    """Alertes tècniques i de saturació CPU a l'esquema aïllat superadmin_telemetry (Spec 022 RF-03/RF-10)."""

    __tablename__ = "alertes_seguretat"
    __table_args__ = {"schema": "superadmin_telemetry"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tipus: Mapped[str] = mapped_column(String(100), nullable=False)
    gravetat: Mapped[str] = mapped_column(
        String(20), nullable=False, default="GROGA", server_default="GROGA"
    )
    origen: Mapped[str] = mapped_column(
        String(80), nullable=False, default="whisper_service", server_default="whisper_service"
    )
    detall: Mapped[str] = mapped_column(Text, nullable=False)
    resolta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    creat_a: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    resolta_a: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RegistreBaixaCertificat(Base):
    """Registre RGPD Art. 17 de certificats de destrucció a superadmin_telemetry (Spec 022 RF-06)."""

    __tablename__ = "registre_baixes_certificats"
    __table_args__ = {"schema": "superadmin_telemetry"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    nif_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    certificat_path: Mapped[str] = mapped_column(String(500), nullable=False)
    estat: Mapped[str] = mapped_column(
        String(40), nullable=False, default="ELIMINAT", server_default="ELIMINAT"
    )
    custodia_anys: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default=text("5")
    )
    periode_gracia_dies: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default=text("30")
    )
    creat_a: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class TraceError(Base):
    """Traces tècniques d'error SRE segregades a superadmin_telemetry (Spec 022 RF-03)."""

    __tablename__ = "traces_error"
    __table_args__ = {"schema": "superadmin_telemetry"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    metode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="GET", server_default="GET"
    )
    status_code: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500, server_default=text("500")
    )
    stack_trace: Mapped[str] = mapped_column(Text, nullable=False)
    detall: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creat_a: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
