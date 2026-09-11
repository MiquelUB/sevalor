FROM python:3.12-slim

# Evitar prompts interactius i generar bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Paquets del sistema necessaris per a asyncpg, geopandas/postgis i reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instal·lació de dependències de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el codi de l'aplicació
COPY . .

# Crear usuari no root per a seguretat Zero-Trust
RUN useradd -u 1000 -ms /bin/bash sevalor && \
    chown -R sevalor:sevalor /app

USER sevalor

EXPOSE 8000

# Script d'entrada: aplica Alembic migrations i després arrenca uvicorn
COPY --chown=sevalor:sevalor entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
