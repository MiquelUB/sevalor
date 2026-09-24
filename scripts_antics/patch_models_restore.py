with open("backend/app/models/models.py", "r") as f:
    content = f.read()

# 1. Restore quantitat_cuarentena
estoc_find = "    quantitat_virtual_reservada: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))\n"
estoc_replace = estoc_find + "    quantitat_cuarentena: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))\n"
content = content.replace(estoc_find, estoc_replace)

# 2. Restore estat to FacturaProveidor and add FacturaProveidorLinia
factura_prov_find = """    base_imposable: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    total_factura: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))"""

factura_prov_replace = """    base_imposable: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    quota_iva: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    total_factura: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, server_default=text('0'))
    estat: Mapped[str] = mapped_column(String(50), default="PENDENT_REVISIO", server_default="PENDENT_REVISIO")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))

class FacturaProveidorLinia(Base):
    __tablename__ = "factures_proveidor_linies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    factura_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures_proveidor.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    descripcio: Mapped[str] = mapped_column(String(200), nullable=False)
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    preu_unitari: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=text('now()'))
"""
content = content.replace(factura_prov_find, factura_prov_replace)

with open("backend/app/models/models.py", "w") as f:
    f.write(content)
