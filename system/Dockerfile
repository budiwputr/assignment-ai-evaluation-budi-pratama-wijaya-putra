# Dockerfile untuk IT Helpdesk Assistant (FastAPI + FAISS + Gemini).
# Pola Sesi 14.2: FROM python -> WORKDIR -> COPY -> RUN pip -> CMD.

FROM python:3.11-slim

# Jangan buffer stdout/stderr (log langsung terlihat) & jangan tulis .pyc.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy requirements.txt lebih dulu, lalu install dependencies
# (agar layer cache tetap valid selama requirements tidak berubah).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source code dan data. File .env TIDAK ikut (lihat .dockerignore);
# API key dikirim saat runtime lewat --env-file / -e.
COPY app/ ./app/
COPY data/ ./data/

EXPOSE 8000

# 0.0.0.0 wajib agar endpoint bisa diakses dari luar container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
