"""
Entry point aplikasi FastAPI — IT Helpdesk Assistant.

Alur endpoint utama:
  1. Menerima pertanyaan/permintaan dari user
  2. Meneruskan ke router (router.py) untuk menentukan intent
  3. Router memanggil RAG (rag.py) atau tool (tools.py) sesuai intent
  4. Mengembalikan response terstruktur ke client
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.guardrails import sanitize
from app.llm import LLMError
from app.rag import build_index
from app.router import handle_query

logger = logging.getLogger("helpdesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bangun index FAISS sekali saat startup. Jika gagal (mis. API key belum
    # diisi), aplikasi tetap hidup dan index dicoba lagi pada request FAQ pertama.
    try:
        build_index()
        logger.info("Index FAISS siap.")
    except Exception as exc:
        logger.warning("Index FAISS belum siap saat startup: %s", exc)
    yield


app = FastAPI(title="IT Helpdesk Assistant API", lifespan=lifespan)


MAX_QUERY_LENGTH = 1000


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Body tidak valid (field hilang, kosong, terlalu panjang, bukan string) dijawab dengan bentuk
    {status, intent, data} yang sama dengan endpoint lain, bukan JSON detail mentah FastAPI.
    """
    kinds = {err.get("type", "") for err in exc.errors()}
    if "string_too_short" in kinds:
        return _error(400, "invalid_request", "Pertanyaan tidak boleh kosong.")
    if "string_too_long" in kinds:
        return _error(422, "invalid_request", f"Pertanyaan terlalu panjang (maksimal {MAX_QUERY_LENGTH} karakter).")
    return _error(422, "invalid_request", 'Permintaan tidak valid. Kirim JSON dengan format {"query": "teks pertanyaan"}.')


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)


class AskResponse(BaseModel):
    status: str
    intent: str
    data: str


@app.get("/health")
async def health():
    """Endpoint sederhana untuk memastikan service berjalan."""
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Endpoint utama. Menerima pertanyaan bebas dari user (bisa berupa
    pertanyaan informasi/kebijakan ATAU permintaan cek status tiket),
    lalu meneruskannya ke router untuk diproses.

    Error ditangani agar bentuk response selalu {status, intent, data}:
      - 400: query kosong/hanya spasi
      - 503: LLM/embedding gagal merespons
      - 422: intent tidak dikenali
      - 500: error tak terduga
    """
    query = sanitize(request.query)
    if not query:
        return _error(400, "invalid_request", "Pertanyaan tidak boleh kosong.")

    try:
        result = await handle_query(query)
    except LLMError as exc:
        logger.error("LLM gagal merespons: %s", exc)
        return _error(503, "llm_error", "Layanan AI sedang tidak tersedia. Silakan coba lagi nanti.")
    except Exception:
        logger.exception("Error tak terduga saat memproses query")
        return _error(500, "internal_error", "Terjadi kesalahan pada server.")

    if result.get("intent") == "unknown":
        return _error(422, "unknown", result["data"])
    return AskResponse(**result)


def _error(status_code: int, intent: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "intent": intent, "data": message},
    )
