path = "/media/akaun/Project_1/SEVALOR/backend/app/models/models.py"
with open(path, "r") as f:
    text = f.read()

target = """    data_proxima_itv: Mapped[Optional[date]] = mapped_column(Date)"""
replacement = """    data_proxima_itv: Mapped[Optional[date]] = mapped_column(Date)
    estat_itv: Mapped[str] = mapped_column(String(50), default="FAVORABLE", server_default="FAVORABLE")
    data_caducitat_asseguranca: Mapped[Optional[date]] = mapped_column(Date)
    companyia_asseguradora: Mapped[Optional[str]] = mapped_column(String(100))
    carnet_necessari: Mapped[str] = mapped_column(String(10), default="B", server_default="B")
    historial_reparacions: Mapped[Optional[str]] = mapped_column(Text)"""

if target in text:
    text = text.replace(target, replacement)
    print("Vehicle model patched!")
else:
    print("Target not found")

with open(path, "w") as f:
    f.write(text)
