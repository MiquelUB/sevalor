with open("backend/app/models/models.py", "r") as f:
    content = f.read()

new_model = """class FacturaProveidorLinia(Base):
    __tablename__ = "factures_proveidor_linies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    factura_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures_proveidor.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), default=1.0)
    preu_unitari: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

class FacturaProveidor(Base):"""

# And I will add estat="PENDENT" to FacturaProveidor
old_fact = """    comanda_numero: Mapped[Optional[str]] = mapped_column(String(100))"""
new_fact = """    comanda_numero: Mapped[Optional[str]] = mapped_column(String(100))
    estat: Mapped[str] = mapped_column(String(30), default="PENDENT", server_default=text("'PENDENT'"))"""

content = content.replace("class FacturaProveidor(Base):", new_model)
content = content.replace(old_fact, new_fact)

with open("backend/app/models/models.py", "w") as f:
    f.write(content)
