with open("backend/app/models/models.py", "r") as f:
    content = f.read()

import_str = "    import_suplits: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, server_default=text('0'))\n"
new_hash_str = "    hash_cadena: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)\n"

if "hash_cadena: Mapped[str]" not in content:
    content = content.replace(import_str, import_str + new_hash_str)

with open("backend/app/models/models.py", "w") as f:
    f.write(content)
