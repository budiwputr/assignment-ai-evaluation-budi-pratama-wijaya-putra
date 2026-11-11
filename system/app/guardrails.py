"""
Guardrail input berbasis pola perilaku (ringan, deterministik, tanpa panggilan LLM).

Dipasang SEBELUM router/RAG. Dua kelas permintaan ditolak di sini:
  1. Instruction override  : meminta sistem melupakan/mengabaikan instruksi atau mengganti perannya.
  2. Information boundary  : meminta isi system prompt, API key, konfigurasi, atau struktur data internal.

Ini lapisan pertama (murah, 0 token). Lapisan kedua ada di prompt RAG (instruksi anti-override) dan
lapisan ketiga di retrieval threshold (query di luar topik tidak sampai ke LLM). Pola regex tidak akan
menangkap semua parafrase; lihat 'Rekomendasi' di README untuk guardrail berbasis klasifikasi.
"""

import re
import unicodedata

_FLAGS = re.IGNORECASE

# --- Instruction override ---------------------------------------------------
_OVERRIDE = re.compile(
    r"(abaikan|lupakan|acuhkan|kesampingkan|batalkan|hiraukan)\s+(?:\w+\s+){0,3}?(instruksi|perintah|aturan|batasan|peran|prompt|arahan)"
    r"|(ignore|disregard|forget|override)\s+(?:\w+\s+){0,3}?(instruction|rule|prompt|role|restriction|guideline)s?"
    r"|(kamu|anda)\s+(?:sekarang|kini|mulai sekarang)\s+(?:adalah|jadi|menjadi)"
    r"|(?:mulai sekarang|sekarang)\s+(?:kamu|anda)\s+(?:adalah|bukan|tidak)"
    r"|\byou\s+are\s+now\b|\bact\s+as\b|\bpretend\s+(?:to\s+be|you)\b|\bjailbreak\b|\bDAN\s+mode\b"
    r"|tidak\s+(?:lagi\s+)?(?:dibatasi|terikat)|tanpa\s+(?:batasan|aturan|filter)"
    r"|ubah\s+peranmu|ganti\s+peranmu",
    _FLAGS,
)

# --- Information boundary ---------------------------------------------------
_EXTRACTION = re.compile(
    r"system\s*prompt|prompt\s+(?:sistem|awal|mu|kamu)|instruksi\s+(?:awal|sistem|internal|yang\s+(?:diberikan|kamu\s+terima))"
    r"|(?:isi|tampilkan|bocorkan|tunjukkan|sebutkan|ungkap\w*|reveal|show|print|display|leak)\s+(?:\w+\s+){0,4}?(?:api[\s_-]*key|kunci\s+api|token|password\s+admin|secret|credential|kredensial|\.env|environment)"
    r"|api[\s_-]*key|gemini_api_key|\.env\b|variabel\s+lingkungan"
    r"|(?:struktur|skema|isi)\s+(?:file|berkas|data|database|knowledge\s*base|basis\s+pengetahuan)"
    r"|(?:seluruh|semua)\s+isi\s+knowledge\s*base|nama\s+model\s+(?:yang\s+)?(?:kamu|dipakai|digunakan)",
    _FLAGS,
)

OVERRIDE_REFUSAL = (
    "Maaf, saya tidak dapat mengubah peran atau mengabaikan aturan layanan. "
    "Saya adalah asisten IT Helpdesk internal yang membantu pertanyaan seputar HR/IT "
    "(cuti, password, perangkat, onboarding) dan cek status tiket."
)
EXTRACTION_REFUSAL = (
    "Maaf, saya tidak dapat membagikan detail konfigurasi internal sistem. "
    "Secara umum saya adalah asisten IT Helpdesk yang menjawab pertanyaan HR/IT dari knowledge base "
    "dan mengecek status tiket. Silakan ajukan pertanyaan seputar layanan tersebut."
)

# Control char (kecuali \n, \t), zero-width, dan bidi override (U+202E dst.) dibuang sebelum diproses.
_STRIP_CATEGORIES = {"Cc", "Cf"}


def sanitize(text: str) -> str:
    """Buang karakter kontrol/tak terlihat, rapikan spasi berulang."""
    cleaned = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in _STRIP_CATEGORIES
    )
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def check_input(query: str) -> str | None:
    """Mengembalikan pesan penolakan jika query melanggar guardrail, selain itu None."""
    if _OVERRIDE.search(query):
        return OVERRIDE_REFUSAL
    if _EXTRACTION.search(query):
        return EXTRACTION_REFUSAL
    return None
