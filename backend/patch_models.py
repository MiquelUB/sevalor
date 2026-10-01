import re

with open('/media/akaun/Project_1/SEVALOR/backend/app/models/models.py', 'r') as f:
    content = f.read()

# Replace version_id with versio in OrdreTreball
content = re.sub(
    r"version_id: Mapped\[int\] = mapped_column\(Integer, default=1, server_default=\"1\", nullable=False\)",
    r"versio: Mapped[int] = mapped_column(Integer, default=1, server_default=\"1\", nullable=False)\n    latitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))\n    longitud: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))",
    content
)

content = re.sub(
    r"\"version_id_col\": version_id",
    r"\"version_id_col\": versio",
    content
)

with open('/media/akaun/Project_1/SEVALOR/backend/app/models/models.py', 'w') as f:
    f.write(content)
