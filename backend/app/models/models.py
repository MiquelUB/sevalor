"""Models ORM de SQLAlchemy 2.0 per a Sevalor Suite."""

import uuid
from datetime import date, datetime, time, timezone
from typing import Any, List, Optional
from sqlalchemy import (
    BIGINT,
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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Empresa(Base):
    __tablename__ = "empreses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    subdomini: Mapped[Optional[str]] = mapped_column(String(63), unique=True)
    primari_hsl: Mapped[str] = mapped_column(String(30), default="210 100% 15%", server_default="210 100% 15%")
    secundari_hsl: Mapped[str] = mapped_column(String(30), default="38 92% 50%", server_default="38 92% 50%")
    accent_hsl: Mapped[str] = mapped_column(String(30), default="190 90% 50%", server_default="190 90% 50%")
    logotip_path: Mapped[Optional[str]] = mapped_column(String(500))
    favicon_path: Mapped[Optional[str]] = mapped_column(String(500))
    pla_subscripcio: Mapped[str] = mapped_column(String(20), default="STARTER", server_default="STARTER")
    estat_pagament: Mapped[str] = mapped_column(String(20), default="ACTIU", server_default="ACTIU")
    quota_disc_bytes_autoritzada: Mapped[int] = mapped_column(BIGINT, default=10737418240, server_default=text('10737418240'))
    quota_disc_bytes_utilitzada: Mapped[int] = mapped_column(BIGINT, default=0, server_default=text('0'))
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_webhook_secret: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_bot_actiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    telegram_estat_connexio: Mapped[str] = mapped_column(String(30), default="NO_CONFIGURAT", server_default="NO_CONFIGURAT")
    adn_marca_path: Mapped[Optional[str]] = mapped_column(String(500))
    adn_paleta_proposta: Mapped[Optional[dict]] = mapped_column(JSONB)
    codis_recuperacio_2fa: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    monograma: Mapped[Optional[str]] = mapped_column(String(10))
    vertical: Mapped[str] = mapped_column(String(50), default="SEVALOR", server_default="SEVALOR")
    node_ia_actiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    node_ia_url: Mapped[Optional[str]] = mapped_column(String(255))
    feature_copilot_ia: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    feature_flota: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    feature_planols: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    feature_telegram: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    data_onboarding: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class SlotJornada(Base):
    __tablename__ = "slots_jornada"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    modalitat: Mapped[str] = mapped_column(String(30), default="JORNADA_CONTINUADA", server_default="JORNADA_CONTINUADA")
    hora_entrada_teorica: Mapped[time] = mapped_column(Time, default=time(8, 0), server_default=text("'08:00'"))
    hora_sortida_teorica: Mapped[time] = mapped_column(Time, default=time(17, 0), server_default=text("'17:00'"))
    hora_inici_dinar: Mapped[Optional[time]] = mapped_column(Time, default=time(13, 0))
    hora_fi_dinar: Mapped[Optional[time]] = mapped_column(Time, default=time(14, 0))
    hores_convenio_setmanals: Mapped[float] = mapped_column(Numeric(4, 2), default=40.00, server_default=text('40'))
    es_intensiva_estiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    data_inici_estiu: Mapped[Optional[date]] = mapped_column(Date)
    data_fi_estiu: Mapped[Optional[date]] = mapped_column(Date)
    hora_entrada_estiu: Mapped[Optional[time]] = mapped_column(Time)
    hora_sortida_estiu: Mapped[Optional[time]] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Usuari(Base):
    __tablename__ = "usuaris"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nif", name="uq_usuaris_empresa_nif"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"))
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
    totp_activat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    slot_jornada_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("slots_jornada.id", ondelete="SET NULL"))
    ip_allowlist: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    vehicle_assignat_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    especialitat: Mapped[Optional[str]] = mapped_column(String(50), default="SISTEMES_REG")
    estat_operatiu: Mapped[str] = mapped_column(String(30), default="DISPONIBLE", server_default="DISPONIBLE")
    cap_de_grup_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    cost_hora_eur: Mapped[float] = mapped_column(Numeric(8, 2), default=22.50, server_default=text('22.50'))
    carnet_conduir: Mapped[str] = mapped_column(String(20), default="B", server_default="B")
    carnet_caducitat: Mapped[Optional[date]] = mapped_column(Date)
    prl_certificat_vigencia: Mapped[Optional[date]] = mapped_column(Date)
    intents_pin_fallits: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    pin_bloquejat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    data_ultim_acces: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class RegistreJornadaLaboral(Base):
    __tablename__ = "registres_jornada_laboral"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    usuari_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False)
    data_jornada: Mapped[date] = mapped_column(Date, default=date.today, server_default=text('CURRENT_DATE'))
    hora_inici: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    hora_fi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    geolocalitzacio_inici: Mapped[Optional[str]] = mapped_column(String(100))
    geolocalitzacio_fi: Mapped[Optional[str]] = mapped_column(String(100))
    estat: Mapped[str] = mapped_column(String(20), default="EN_CURS", server_default="EN_CURS")
    tancament_automatic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    motiu_incidencia: Mapped[Optional[str]] = mapped_column(Text)
    hores_ordinaries: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, server_default=text('0'))
    hores_extraordinaries: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, server_default=text('0'))
    auditat_per_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    auditoria_data: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    auditoria_motiu: Mapped[Optional[str]] = mapped_column(Text)
    version_id: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class AuditoriaRegistreJornada(Base):
    __tablename__ = "auditoria_registres_jornada"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("registres_jornada_laboral.id", ondelete="CASCADE"), nullable=False)
    modificat_per_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False)
    valors_anteriors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    nous_valors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    motiu_justificatiu: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))



class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codi", name="uq_clients_empresa_codi"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    rao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    telefon: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    adreca_fiscal: Mapped[Optional[str]] = mapped_column(Text)
    estat_canal_telegram: Mapped[str] = mapped_column(String(20), default="DESVINCULAT", server_default="DESVINCULAT")
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    iban_xifrat_simetric: Mapped[Optional[str]] = mapped_column(Text)
    mandat_sepa_path: Mapped[Optional[str]] = mapped_column(String(500))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "referencia_inventari", name="uq_articles_empresa_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    referencia_inventari: Mapped[str] = mapped_column(String(50), nullable=False)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    unitat_mesura: Mapped[str] = mapped_column(String(30), default="UNITAT", server_default="UNITAT")
    familia: Mapped[str] = mapped_column(String(50), default="GENERAL", server_default="GENERAL")
    estoc_optim: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    estoc_minim: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    es_lot_caducable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    parent_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    preu_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text('0'))
    preu_venda: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text('0'))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Magatzem(Base):
    __tablename__ = "magatzems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    tipus: Mapped[str] = mapped_column(String(30), default="NAU_CENTRAL", server_default="NAU_CENTRAL")
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class EstocMagatzem(Base):
    __tablename__ = "estocs_magatzem"
    __table_args__ = (
        UniqueConstraint("empresa_id", "article_id", "magatzem_id", name="uq_estocs_article_magatzem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    magatzem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="CASCADE"), nullable=False)
    quantitat_fisica: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    quantitat_virtual_reservada: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    ubicacio_passadis: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "matricula", name="uq_vehicles_empresa_matricula"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    matricula: Mapped[str] = mapped_column(String(20), nullable=False)
    marca: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    tipus: Mapped[str] = mapped_column(String(30), default="THERMIC", server_default="THERMIC")
    horometre_acumulat: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text('0'))
    odometre_acumulat: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    distintiu_ambiental: Mapped[Optional[str]] = mapped_column(String(10))
    estat: Mapped[str] = mapped_column(String(30), default="OPERATIU", server_default="OPERATIU")
    conductor_habitual_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    magatzem_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="SET NULL"))
    data_proxima_itv: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class RegistreEsdevenimentsSIF(Base):
    __tablename__ = "registre_esdeveniments_sif"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="RESTRICT"), nullable=False)
    codi_esdeveniment: Mapped[str] = mapped_column(String(10), nullable=False)
    usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    descripcio: Mapped[str] = mapped_column(Text, nullable=False)
    hash_anterior: Mapped[Optional[str]] = mapped_column(String(64))
    hash_sello: Mapped[str] = mapped_column(String(64), nullable=False)
    dades_event: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    data_creacio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Finca(Base):
    __tablename__ = "finques"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    adreca: Mapped[Optional[str]] = mapped_column(Text)
    codi_candat_en_memoria: Mapped[Optional[str]] = mapped_column(String(50))
    dades_sigpac: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    superficie_ha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class EinaCustodia(Base):
    __tablename__ = "eines_custodia"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    referencia_fabricant: Mapped[Optional[str]] = mapped_column(String(100))
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    numero_serie: Mapped[str] = mapped_column(String(100), nullable=False)
    estat: Mapped[str] = mapped_column(String(30), default="DISPONIBLE", server_default="DISPONIBLE")
    custodiat_per_operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    magatzem_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("magatzems.id", ondelete="SET NULL"))
    data_ultima_calibracio: Mapped[Optional[date]] = mapped_column(Date)
    data_propera_calibracio: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class TiquetCarburant(Base):
    __tablename__ = "tiquets_carburant"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    operari_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False)
    tiquet_foto_path: Mapped[str] = mapped_column(String(500), nullable=False)
    odometre_foto_path: Mapped[str] = mapped_column(String(500), nullable=False)
    litres: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    import_: Mapped[float] = mapped_column("import", Numeric(10, 2), nullable=False)
    data_repostatge: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    odometre_valor: Mapped[int] = mapped_column(Integer, nullable=False)
    estat_ocr: Mapped[str] = mapped_column(String(30), default="PENDENT_AUDITORIA", server_default="PENDENT_AUDITORIA")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Proveidor(Base):
    __tablename__ = "proveidors"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codi", name="uq_proveidors_empresa_codi"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    rao_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    telefon: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    especialitat: Mapped[str] = mapped_column(String(50), default="MATERIALS", server_default="MATERIALS")
    es_recc: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    aplica_isp_defecte: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    iban_xifrat_simetric: Mapped[Optional[str]] = mapped_column(Text)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class DocumentCAERC(Base):
    __tablename__ = "documents_cae_rc"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    proveidor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="CASCADE"), nullable=False)
    tipus_document: Mapped[str] = mapped_column(String(30), nullable=False)
    data_caducitat: Mapped[date] = mapped_column(Date, nullable=False)
    fitxer_path: Mapped[str] = mapped_column(String(500), nullable=False)
    estat: Mapped[str] = mapped_column(String(20), default="VALIDAT", server_default="VALIDAT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class FacturaProveidor(Base):
    __tablename__ = "factures_proveidor"
    __table_args__ = (
        UniqueConstraint("empresa_id", "proveidor_id", "numero_factura", name="uq_factures_prov_empresa_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    proveidor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="CASCADE"), nullable=False)
    numero_factura: Mapped[str] = mapped_column(String(100), nullable=False)
    data_factura: Mapped[date] = mapped_column(Date, nullable=False)
    base_imposable: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    albara_numero: Mapped[Optional[str]] = mapped_column(String(100))
    comanda_numero: Mapped[Optional[str]] = mapped_column(String(100))
    estat_conciliacio: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default="PENDENT")
    desviacio_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, server_default=text('0'))
    fitxer_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class OrdreTreball(Base):
    __tablename__ = "ordres_treball"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codi", name="uq_ordres_empresa_codi"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    finca_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("finques.id", ondelete="SET NULL"))
    titol: Mapped[str] = mapped_column(String(200), nullable=False)
    adreca: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    estat: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default="PENDENT")
    data_planificacio: Mapped[date] = mapped_column(Date, default=date.today, server_default=text('CURRENT_DATE'))
    cap_de_colla_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class FullaPicking(Base):
    __tablename__ = "fulles_picking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"))
    estat_picking: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default="PENDENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class LiniaPicking(Base):
    __tablename__ = "linies_picking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    picking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fulles_picking.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    quantitat_prevista: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    quantitat_carregada_pick_in: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    quantitat_retornada_pick_out: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    quantitat_mermada: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class Incidencia(Base):
    __tablename__ = "incidencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"))
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    ambit: Mapped[str] = mapped_column(String(30), default="TASCA", server_default="TASCA")
    estat: Mapped[str] = mapped_column(String(20), default="VERMELL", server_default="VERMELL")
    audio_path: Mapped[Optional[str]] = mapped_column(String(500))
    foto_path: Mapped[Optional[str]] = mapped_column(String(500))
    text_observacions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class CapaAnotacio(Base):
    __tablename__ = "capes_anotacions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False)
    nom_capa: Mapped[str] = mapped_column(String(100), nullable=False)
    fitxer_vectorial_path: Mapped[str] = mapped_column(String(500), nullable=False)
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    estat_capa: Mapped[str] = mapped_column(String(30), default="ACTIVA", server_default="ACTIVA")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class FacturaCapcalera(Base):
    __tablename__ = "factures_capcalera"
    __table_args__ = (
        UniqueConstraint("empresa_id", "serie", "numero_factura", name="uq_factures_empresa_serie_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    numero_factura: Mapped[int] = mapped_column(Integer, nullable=False)
    serie: Mapped[str] = mapped_column(String(20), default="2026", server_default="2026")
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    data_emissio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    base_imposable: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    import_retencio: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    import_suplits: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    liquid_exigible: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    estat_cobrament: Mapped[str] = mapped_column(String(20), default="PENDENT", server_default="PENDENT")
    estat_enviament: Mapped[str] = mapped_column(String(20), default="PENDENT", server_default="PENDENT")
    hash_anterior: Mapped[Optional[str]] = mapped_column(String(64))
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qr_code_path: Mapped[Optional[str]] = mapped_column(String(500))
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class FacturaLinia(Base):
    __tablename__ = "factures_linies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    factura_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="CASCADE"), nullable=False)
    centre_de_cost_id: Mapped[Optional[str]] = mapped_column(String(50))
    obra_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    concepte: Mapped[str] = mapped_column(String(200), nullable=False)
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), default=1.0, server_default=text('1'))
    preu_venda_unitari: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, server_default=text('0'))
    tipus_iva: Mapped[float] = mapped_column(Numeric(4, 2), default=21.00, server_default=text('21'))
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class OutboxEnviamentAEAT(Base):
    __tablename__ = "outbox_enviaments_aeat"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    factura_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures_capcalera.id", ondelete="CASCADE"), nullable=False)
    payload_xml_path: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    intents_enviament: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    estat_enviament: Mapped[str] = mapped_column(String(20), default="PENDENT", server_default="PENDENT")
    darrera_resposta_soap: Mapped[Optional[str]] = mapped_column(Text)
    data_creacio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    data_actualitzacio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class CarpetaPlanol(Base):
    __tablename__ = "carpetes_planols"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    municipi: Mapped[Optional[str]] = mapped_column(String(100))
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("carpetes_planols.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class PlanolBase(Base):
    __tablename__ = "planols_base"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codi_referencia", name="uq_planols_codi"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    carpeta_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carpetes_planols.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    codi_referencia: Mapped[str] = mapped_column(String(50), nullable=False)
    tipus_fitxer: Mapped[str] = mapped_column(String(20), nullable=False)
    es_georeferenciat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    fitxer_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mida_bytes: Mapped[int] = mapped_column(BIGINT, nullable=False)
    bounds_wgs84: Mapped[Optional[dict]] = mapped_column(JSONB)
    projeccio_origen: Mapped[str] = mapped_column(String(30), default="WGS84", server_default="WGS84")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class CapaVectorial(Base):
    __tablename__ = "capes_vectorials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    planol_base_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("planols_base.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    disciplina: Mapped[str] = mapped_column(String(30), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    es_immutable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    color_hex: Mapped[str] = mapped_column(String(10), default="#2563eb", server_default="#2563eb")
    gruix_linia: Mapped[int] = mapped_column(Integer, default=2, server_default=text('2'))
    opacitat_percent: Mapped[int] = mapped_column(Integer, default=100, server_default=text('100'))
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    geometries_geojson: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    version_id: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    creat_per_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class PinIncidenciaPlanol(Base):
    __tablename__ = "pins_incidencia_planol"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    capa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("capes_vectorials.id", ondelete="CASCADE"), nullable=False)
    latitud: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitud: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcio: Mapped[Optional[str]] = mapped_column(Text)
    simbol: Mapped[str] = mapped_column(String(50), default="AVARIA_REG", server_default="AVARIA_REG")
    estat: Mapped[str] = mapped_column(String(20), default="PENDENT_REVISIO", server_default="PENDENT_REVISIO")
    audio_nota_path: Mapped[Optional[str]] = mapped_column(String(500))
    foto_evidencia_path: Mapped[Optional[str]] = mapped_column(String(500))
    operari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class ExportacioPdfPlanol(Base):
    __tablename__ = "exportacions_pdf_planol"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    planol_base_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("planols_base.id", ondelete="CASCADE"), nullable=False)
    titol_report: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    capes_incloses_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    escala_grafica: Mapped[str] = mapped_column(String(30), default="1:500", server_default="1:500")
    pdf_generat_path: Mapped[Optional[str]] = mapped_column(String(500))
    estat: Mapped[str] = mapped_column(String(20), default="GENERAT", server_default="GENERAT")
    caixeti_dades: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class TokenInvitacioTelegram(Base):
    __tablename__ = "tokens_invitacio_telegram"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    expira_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utilitzat: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    utilitzat_a: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class ConversaNotificacio(Base):
    __tablename__ = "converses_notificacio"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    estat: Mapped[str] = mapped_column(String(30), default="BLAU_OBERT", server_default="BLAU_OBERT")
    titol: Mapped[str] = mapped_column(String(150), nullable=False)
    ultim_missatge_text: Mapped[Optional[str]] = mapped_column(Text)
    ultim_missatge_data: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    num_missatges_sense_llegir: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    es_arxivada: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class MissatgeNotificacio(Base):
    __tablename__ = "missatges_notificacio"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    conversa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("converses_notificacio.id", ondelete="CASCADE"), nullable=False)
    remitent_tipus: Mapped[str] = mapped_column(String(30), nullable=False)
    remitent_usuari_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    canal: Mapped[str] = mapped_column(String(20), default="TELEGRAM", server_default="TELEGRAM")
    contingut_text: Mapped[str] = mapped_column(Text, nullable=False)
    tipus_esdeveniment: Mapped[str] = mapped_column(String(50), default="MISSATGE_TEXT", server_default="MISSATGE_TEXT")
    adjunt_url: Mapped[Optional[str]] = mapped_column(String(500))
    adjunt_tipus: Mapped[Optional[str]] = mapped_column(String(50))
    adjunt_mida_bytes: Mapped[Optional[int]] = mapped_column(BIGINT)
    token_aprobacio: Mapped[Optional[str]] = mapped_column(String(100))
    estat_aprobacio: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default="PENDENT")
    token_descarrega_factura: Mapped[Optional[str]] = mapped_column(String(100))
    token_descarrega_expira_a: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class FaqCorporativaRag(Base):
    __tablename__ = "faqs_corporatives_rag"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    pregunta: Mapped[str] = mapped_column(String(255), nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), default="GENERAL", server_default="GENERAL")
    paraules_clau: Mapped[Optional[str]] = mapped_column(String(255))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class MemorandumTecnicCopilot(Base):
    __tablename__ = "memorandums_tecnics_copilot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    incidencia_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("incidencies.id", ondelete="SET NULL"))
    transcripcio_audio: Mapped[Optional[str]] = mapped_column(Text)
    confianca_acustica: Mapped[float] = mapped_column(Numeric(4, 2), default=1.00, server_default=text('1'))
    avis_soroll_sever: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    analisi_visual: Mapped[Optional[str]] = mapped_column(Text)
    dictamen_pericial: Mapped[str] = mapped_column(String(30), default="EXTRA_FACTURABLE", server_default="EXTRA_FACTURABLE")
    motiu_dictamen: Mapped[str] = mapped_column(Text, nullable=False)
    estimacio_temps_extra_minuts: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    estimacio_materials_extra: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    cost_estimat_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, server_default=text('0'))
    validat_per_enginyer: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    enginyer_validador_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    data_validacio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observacions_enginyer: Mapped[Optional[str]] = mapped_column(Text)
    estat: Mapped[str] = mapped_column(String(20), default="PROPOSTA", server_default="PROPOSTA")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class AuditoriaPostObra(Base):
    __tablename__ = "auditories_post_obra"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="CASCADE"), nullable=False, unique=True)
    desviacio_hores: Mapped[float] = mapped_column(Numeric(6, 2), default=0.00, server_default=text('0'))
    desviacio_materials: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    desviacio_km: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, server_default=text('0'))
    despeses_camp: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, server_default=text('0'))
    marge_previst_percentatge: Mapped[float] = mapped_column(Numeric(5, 2), default=30.00, server_default=text('30'))
    marge_real_liquidat_percentatge: Mapped[float] = mapped_column(Numeric(5, 2), default=30.00, server_default=text('30'))
    alerta_merma_operativa: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    detall_merma: Mapped[Optional[str]] = mapped_column(Text)
    bloqueig_consum_excessiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    bloqueig_sync_pendent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    pressupost_corregit_proposta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    estat: Mapped[str] = mapped_column(String(30), default="PENDENT_CONFIRMACIO", server_default="PENDENT_CONFIRMACIO")
    enginyer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    data_aprovacio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class AlertaGarantiaRecompra(Base):
    __tablename__ = "alertes_garantia_recompra"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    ordre_treball_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ordres_treball.id", ondelete="SET NULL"))
    tipus_alerta: Mapped[str] = mapped_column(String(30), nullable=False)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    numero_serie: Mapped[Optional[str]] = mapped_column(String(100))
    proveidor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("proveidors.id", ondelete="SET NULL"))
    missatge: Mapped[str] = mapped_column(Text, nullable=False)
    data_fi_garantia: Mapped[Optional[date]] = mapped_column(Date)
    estat: Mapped[str] = mapped_column(String(20), default="ACTIVA", server_default="ACTIVA")
    dades_comanda_proposta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))


class ConsultaXatCopilot(Base):
    __tablename__ = "consultes_xat_copilot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    usuari_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False)
    pregunta: Mapped[str] = mapped_column(Text, nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    vertical: Mapped[str] = mapped_column(String(50), default="SEVALOR", server_default="SEVALOR")
    node_ia_actiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    node_ia_url: Mapped[Optional[str]] = mapped_column(String(255))
    feature_copilot_ia: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    feature_flota: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    feature_planols: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    feature_telegram: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    data_onboarding: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    temps_inferencia_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    enllacos_relacionats: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    es_error_timeout: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    denegat_per_rol: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))





