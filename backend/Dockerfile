FROM python:3.11-slim

LABEL maintainer="local-agent"
LABEL description="Asistan AI Backend — FastAPI + Ollama"

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kaynak kodu
COPY . .

# Sandbox ve log dizinlerini oluştur
RUN mkdir -p /app/sandbox /app/logs

# Ortam değişkenleri (docker-compose veya .env ile override edilir)
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ⚠️  FAZ 1 KISITI: --workers 1 zorunludur
# In-memory onay ve hafıza state'i birden fazla worker'da çalışmaz
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
