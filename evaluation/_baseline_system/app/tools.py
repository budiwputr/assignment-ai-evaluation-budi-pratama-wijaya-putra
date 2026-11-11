"""
Modul Tools — fungsi-fungsi "aksi" yang dipanggil router ketika intent
BUKAN pertanyaan informasi/kebijakan, melainkan permintaan spesifik
yang butuh pengecekan data langsung (bukan retrieval semantik).

Pola ini mengikuti konsep Tool Integration di Sesi 12.3.
"""

from pathlib import Path

import pandas as pd

MOCK_TICKETS_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_tickets.csv"


def _load_tickets() -> pd.DataFrame:
    # Dibaca per pemanggilan: datanya kecil, dan perubahan CSV langsung terbaca.
    return pd.read_csv(MOCK_TICKETS_PATH, dtype=str).fillna("")


def get_ticket_status(ticket_id: str | None) -> str:
    """
    Mencari status tiket berdasarkan ticket_id pada data mock_tickets.csv.
    Tidak pernah melempar error ke pemanggil: tiket tidak ditemukan, ID kosong,
    atau file data bermasalah dikembalikan sebagai pesan yang informatif.
    """
    if not ticket_id:
        return (
            "Mohon sebutkan nomor tiket yang ingin dicek, "
            "contoh: TICKET-0001."
        )

    ticket_id = ticket_id.strip().upper()

    try:
        tickets = _load_tickets()
    except (OSError, pd.errors.ParserError):
        return "Maaf, data tiket sedang tidak dapat diakses. Silakan coba lagi nanti."

    match = tickets[tickets["ticket_id"].str.upper() == ticket_id]
    if match.empty:
        return (
            f"Tiket {ticket_id} tidak ditemukan. "
            "Periksa kembali nomor tiket Anda (format: TICKET-XXXX)."
        )

    row = match.iloc[0]
    return (
        f"Tiket {row['ticket_id']} — {row['subject']} "
        f"(kategori: {row['category']}). "
        f"Status: {row['status']}. Update terakhir: {row['last_update']}."
    )
