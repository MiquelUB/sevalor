with open("backend/app/models/models.py", "r") as f:
    content = f.read()

find_str = """class FacturaProveidorLinia(Base):
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

replace_str = """class FacturaProveidorLinia(Base):
    __tablename__ = "factures_proveidor_linies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("empreses.id", ondelete="CASCADE"), nullable=False)
    factura_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures_proveidor.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"))
    quantitat: Mapped[float] = mapped_column(Numeric(12, 3), nullable=True, default=1.0)
    preu_unitari: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)
"""
content = content.replace(find_str, replace_str)

with open("backend/app/models/models.py", "w") as f:
    f.write(content)
