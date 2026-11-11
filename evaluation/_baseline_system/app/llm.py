"""
Klien Gemini bersama untuk rag.py dan router.py.

API key dan nama model dibaca dari environment variable (file .env saat
lokal, --env-file saat Docker), tidak pernah di-hardcode.
"""

import asyncio
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

load_dotenv()

GENERATION_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
MAX_ATTEMPTS = 3
RETRYABLE_CODES = {429, 500, 503}
EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
# Dimensi embedding dipangkas (default model 3072) agar index FAISS lebih kecil.
EMBEDDING_DIM = int(os.environ.get("GEMINI_EMBEDDING_DIM", "768"))

_client: genai.Client | None = None


class LLMError(Exception):
    """Gemini API gagal merespons (key tidak ada/salah, kuota, jaringan, dsb)."""


def get_client() -> genai.Client:
    """Client dibuat lazy agar aplikasi tetap bisa start tanpa API key."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise LLMError("GEMINI_API_KEY belum diatur pada environment variable.")
        _client = genai.Client(api_key=api_key)
    return _client


async def generate_text(prompt: str, temperature: float, max_output_tokens: int = 1024) -> str:
    """
    Memanggil Gemini dan mengembalikan teks jawaban; error dibungkus LLMError.
    Error sementara (429/503: kuota atau model sedang padat) dicoba ulang
    beberapa kali dengan jeda singkat sebelum menyerah.
    """
    client = get_client()
    config = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_output_tokens)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=GENERATION_MODEL, contents=prompt, config=config
            )
            break
        except genai_errors.APIError as exc:
            if exc.code in RETRYABLE_CODES and attempt < MAX_ATTEMPTS:
                await asyncio.sleep(attempt)  # 1 dtk, 2 dtk
                continue
            raise LLMError(f"Gagal memanggil Gemini: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Gagal memanggil Gemini: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise LLMError("Gemini mengembalikan respons kosong.")
    return text
