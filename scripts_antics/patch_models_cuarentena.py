with open("backend/app/models/models.py", "r") as f:
    content = f.read()

estoc_find = "    quantitat_virtual_reservada: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))\n"
estoc_replace = estoc_find + "    quantitat_cuarentena: Mapped[float] = mapped_column(Numeric(12, 3), default=0.0, server_default=text('0'))\n"
if "quantitat_cuarentena" not in content:
    content = content.replace(estoc_find, estoc_replace)

with open("backend/app/models/models.py", "w") as f:
    f.write(content)
