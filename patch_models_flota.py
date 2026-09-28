path = "/media/akaun/Project_1/SEVALOR/backend/app/models/models.py"
with open(path, "r") as f:
    text = f.read()

target_vehicle = """    estat_itv: Mapped[str] = mapped_column(String(50), default="FAVORABLE", server_default="FAVORABLE")
    data_caducitat_asseguranca: Mapped[Optional[date]] = mapped_column(Date)
    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))
    carnet_necessari: Mapped[str] = mapped_column(String(10), default="B", server_default="B")
    historial_reparacions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))"""

replacement_vehicle = """    estat_itv: Mapped[str] = mapped_column(String(50), default="FAVORABLE", server_default="FAVORABLE")
    data_caducitat_asseguranca: Mapped[Optional[date]] = mapped_column(Date)
    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))
    carnet_necessari: Mapped[str] = mapped_column(String(10), default="B", server_default="B")
    historial_reparacions: Mapped[Optional[str]] = mapped_column(Text)
    
    # Spec 006: Rènting i controls operatius
    regim_adquisicio: Mapped[str] = mapped_column(String(30), default="PROPIETAT", server_default="PROPIETAT")
    renting_limit_km: Mapped[Optional[int]] = mapped_column(Integer)
    tacograf_necessari: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    data_propera_descarrega_tacograf: Mapped[Optional[date]] = mapped_column(Date)
    
    # Vehicles EV / PHEV
    capacitat_bateria_kwh: Mapped[Optional[float]] = mapped_column(Numeric(6,2))
    soh_bateria: Mapped[Optional[float]] = mapped_column(Numeric(5,2))
    
    # Capacitats físiques
    places: Mapped[int] = mapped_column(Integer, default=5, server_default=text('5'))
    pes_maxim_autoritzat: Mapped[int] = mapped_column(Integer, default=3500, server_default=text('3500'))
    
    # Desnormalització de Consums (Batch Celery)
    consum_l_100km: Mapped[Optional[float]] = mapped_column(Numeric(5,2))
    consum_mitjana_historica: Mapped[Optional[float]] = mapped_column(Numeric(5,2))
    consum_adblue_litres: Mapped[float] = mapped_column(Numeric(10,2), default=0.0, server_default=text('0'))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))"""

if target_vehicle in text:
    text = text.replace(target_vehicle, replacement_vehicle)
    print("Vehicle patched.")
else:
    print("Vehicle target not found.")

# Append new tables
new_tables = """
class HistorialAssignacioVehicle(Base):
    __tablename__ = "historial_assignacions_vehicles"
    __table_args__ = (
        UniqueConstraint("empresa_id", "vehicle_id", "data_inici", name="uq_assignacio_inici"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    conductor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="CASCADE"), nullable=False)
    data_inici: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_fi: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    motiu: Mapped[Optional[str]] = mapped_column(String(255))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))

class TiquetCombustible(Base):
    __tablename__ = "tiquets_combustible"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    conductor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    data_tiquet: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    import_euros: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    litres: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    kwh_recarrega: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    litres_adblue: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    odometre_registrat: Mapped[int] = mapped_column(Integer, nullable=False)
    ruta_arxiu_pwa: Mapped[Optional[str]] = mapped_column(String(500))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
"""
text += new_tables

with open(path, "w") as f:
    f.write(text)
print("Done appending tables")
