path = "/media/akaun/Project_1/SEVALOR/backend/app/models/models.py"
with open(path, "r") as f:
    text = f.read()

new_table = """
class DocumentFlota(Base):
    __tablename__ = "documents_flota"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    tipus_document: Mapped[str] = mapped_column(String(50), nullable=False) # ITV, ASSEGURANCA, REPARACIO, CONTRACTE, FITXA_TECNICA
    nom_arxiu: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_arxiu: Mapped[str] = mapped_column(String(500), nullable=False)
    contingut_extret: Mapped[Optional[str]] = mapped_column(Text) # Text extret via OCR per al Copilot
    data_document: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
    creat_per_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuaris.id", ondelete="SET NULL"))
"""
text += new_table

with open(path, "w") as f:
    f.write(text)
print("Added DocumentFlota model")
