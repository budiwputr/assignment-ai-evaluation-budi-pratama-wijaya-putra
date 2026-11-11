"""
Router — menentukan apakah query user butuh RAG (informasi/kebijakan)
atau tool call (aksi spesifik, misal cek status tiket).

Pola ini mengikuti workflow router yang sudah dipelajari di Sesi 12.4:
  user input -> intent detection -> jika butuh data -> retrieval (RAG)
                                  -> jika butuh aksi -> tool call

Intent detection berjenjang (hybrid) agar cepat, murah, dan deterministik
untuk kasus yang jelas, dengan LLM hanya sebagai fallback kasus ambigu:
  1. Ada ID tiket (TICKET-XXXX)            -> ticket_status  (aturan pasti)
  2. Frasa cek status tiket                -> ticket_status  (aturan pasti)
  3. Menyebut tiket/status tapi tak jelas  -> tanya LLM
  4. Tidak ada sinyal tiket sama sekali    -> faq
"""

import re

from app.guardrails import check_input
from app.llm import generate_text
from app.rag import answer_from_knowledge_base
from app.tools import get_ticket_status

# "TICKET-0042", "ticket 42", "tiket #42", "TKT-0042" -> angka ditangkap lalu dinormalisasi.
_TICKET_ID_PATTERN = re.compile(r"\b(?:ticket|tiket|tkt)[\s\-_#:]*(\d{1,6})\b", re.IGNORECASE)

# Frasa yang jelas bermakna "cek status/progres tiket".
_STATUS_PHRASES = re.compile(
    r"(status|progres|progress|perkembangan|update)\s+(?:dari\s+)?(?:ticket|tiket)"
    r"|(?:cek|lacak|track)\s+(?:ticket|tiket)"
    r"|(?:ticket|tiket)\s+\S+(?:\s+\S+)?\s+(?:sudah|belum|sampai mana|bagaimana|gimana)",
    re.IGNORECASE,
)

# Kata yang menandakan kemungkinan ada hubungannya dengan tiket; memicu LLM fallback.
_WEAK_CUES = re.compile(r"\b(ticket|tiket|tkt|status|progres|progress|laporan)\b", re.IGNORECASE)

# Sapaan / basa-basi murni: dijawab statis (0 token), tidak perlu embedding + LLM.
_SMALLTALK = re.compile(
    r"^\s*(halo+|hai+|hi+|hello|hey|pagi|siang|sore|malam|selamat\s+(?:pagi|siang|sore|malam)|"
    r"terima\s*kasih|makasih|thanks|thank you|ok(?:e|ay)?|sip)"
    r"(?:\s+(?:kak|min|bot|admin|semua|tim|team|helpdesk))?[\s!.,?]*$",
    re.IGNORECASE,
)
SMALLTALK_REPLY = (
    "Halo! Saya asisten IT Helpdesk. Saya bisa membantu pertanyaan seputar cuti, password/akses, perangkat, "
    "onboarding, serta cek status tiket (contoh: TICKET-0001). Ada yang bisa dibantu?"
)
MAX_TICKETS_PER_QUERY = 5

_INTENT_PROMPT = """Klasifikasikan pertanyaan berikut ke dalam salah satu kategori:
'faq' (pertanyaan informasi/kebijakan umum, termasuk cara membuat/mengajukan tiket) atau
'ticket_status' (permintaan mengecek status/progres tiket tertentu milik user).
Jawab hanya dengan satu kata: faq atau ticket_status.
Pertanyaan: {query}"""


async def detect_intent(query: str) -> str:
    """
    Menentukan intent dari query user. Mengembalikan salah satu:
      - "faq"           -> pertanyaan informasi/kebijakan, arahkan ke RAG
      - "ticket_status" -> permintaan cek status tiket, arahkan ke tool call
    """
    if _TICKET_ID_PATTERN.search(query) or _STATUS_PHRASES.search(query):
        return "ticket_status"

    if not _WEAK_CUES.search(query):
        return "faq"

    answer = await generate_text(_INTENT_PROMPT.format(query=query), temperature=0.0, max_output_tokens=256)
    return "ticket_status" if "ticket_status" in answer.lower() else "faq"


async def handle_query(query: str) -> dict:
    """
    Fungsi utama yang dipanggil oleh endpoint /ask.
    Menjalankan intent detection, lalu merutekan ke RAG atau tool call yang sesuai.
    """
    refusal = check_input(query)
    if refusal:
        return {"status": "refused", "intent": "guardrail_blocked", "data": refusal}

    if _SMALLTALK.match(query):
        return {"status": "success", "intent": "smalltalk", "data": SMALLTALK_REPLY}

    intent = await detect_intent(query)

    if intent == "ticket_status":
        ticket_ids = extract_ticket_ids(query)
        if not ticket_ids:
            data = get_ticket_status(None)
        else:
            # Semua ID (maks. MAX_TICKETS_PER_QUERY) diproses; sebelumnya hanya ID pertama dan sisanya diam-diam diabaikan.
            data = "\n".join(get_ticket_status(t) for t in ticket_ids[:MAX_TICKETS_PER_QUERY])
            if len(ticket_ids) > MAX_TICKETS_PER_QUERY:
                data += f"\n(Hanya {MAX_TICKETS_PER_QUERY} tiket pertama yang diproses per permintaan.)"
        return {"status": "success", "intent": "ticket_status", "data": data}

    elif intent == "faq":
        data = await answer_from_knowledge_base(query)
        return {"status": "success", "intent": "faq", "data": data}

    else:
        return {"status": "error", "intent": "unknown", "data": "Maaf, saya tidak memahami permintaan Anda."}


def extract_ticket_ids(query: str) -> list[str]:
    """Semua ID tiket pada query (urutan kemunculan, tanpa duplikat), dinormalisasi ke 'TICKET-XXXX'."""
    seen: list[str] = []
    for m in _TICKET_ID_PATTERN.finditer(query):
        tid = f"TICKET-{int(m.group(1)):04d}"
        if tid not in seen:
            seen.append(tid)
    return seen


def extract_ticket_id(query: str) -> str | None:
    """
    Mengekstrak ticket_id dari teks query dan menormalisasinya ke format
    'TICKET-XXXX' (sama dengan mock_tickets.csv). Mengembalikan None jika
    user tidak menyebutkan nomor tiket.
    """
    match = _TICKET_ID_PATTERN.search(query)
    if not match:
        return None
    return f"TICKET-{int(match.group(1)):04d}"
