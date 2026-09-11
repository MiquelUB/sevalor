FROM python:3.12-slim

# Evitar prompts interactius i generar bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Paquets del sistema necessaris
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instal·lació de dependències de Python del bot
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el codi del bot
COPY . .

# Crear usuari no root per a seguretat Zero-Trust
RUN useradd -u 1000 -ms /bin/bash sevalor && \
    chown -R sevalor:sevalor /app

USER sevalor

EXPOSE 8080

# El bot Telegram s'inicia amb el run principal
CMD ["python", "-m", "main"]