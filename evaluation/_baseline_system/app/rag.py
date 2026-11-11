"""
Modul RAG — mengubah knowledge base menjadi embedding, menyimpannya ke FAISS,
melakukan semantic search, lalu menghasilkan jawaban menggunakan LLM.

Alur ini serupa dengan yang sudah dibangun di Assignment 3 (Semantic Search &
LLM Application) dan Sesi 11 (Building a Simple RAG System) — di assignment ini,
alur tersebut dibungkus menjadi fungsi yang dipanggil oleh router.py.
"""

from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from google.genai import types

from app.llm import EMBEDDING_DIM, EMBEDDING_MODEL, LLMError, generate_text, get_client

KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "data" / "it_helpdesk_knowledge_base.csv"

# Skor cosine similarity di bawah ini dianggap tidak relevan (di luar cakupan KB).
# Diset longgar karena keputusan akhir "tahu / tidak tahu" tetap di tangan LLM
# lewat instruksi prompt; ambang ini hanya mencegah context sampah.
MIN_SCORE = 0.45

_index: faiss.Index | None = None
_df: pd.DataFrame | None = None


def _embed(texts: list[str], task_type: str) -> np.ndarray:
    """Embedding batch -> matriks float32 ter-normalisasi (L2) untuk cosine similarity."""
    try:
        result = get_client().models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIM,
            ),
        )
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"Gagal membuat embedding: {exc}") from exc

    vectors = np.array([e.values for e in result.embeddings], dtype="float32")
    # Dimensi yang dipangkas tidak ter-normalisasi otomatis, jadi normalisasi manual.
    faiss.normalize_L2(vectors)
    return vectors


def build_index() -> None:
    """
    Memuat knowledge base dan membangun index FAISS. Dipanggil sekali saat
    startup (lihat lifespan di main.py), bukan pada setiap request.

    Unit retrievable = pasangan pertanyaan + jawaban, sehingga query user yang
    mirip pertanyaan FAQ maupun isi jawabannya sama-sama bisa cocok.
    """
    global _index, _df

    df = pd.read_csv(KNOWLEDGE_BASE_PATH).fillna("")
    documents = (df["question"] + "\n" + df["answer"]).tolist()

    vectors = _embed(documents, task_type="RETRIEVAL_DOCUMENT")
    index = faiss.IndexFlatIP(vectors.shape[1])  # inner product == cosine (vektor ter-normalisasi)
    index.add(vectors)

    _df, _index = df, index


def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """Mengembalikan top_k entri KB paling relevan beserta skor similarity."""
    if _index is None or _df is None:
        build_index()

    query_vector = _embed([query], task_type="RETRIEVAL_QUERY")
    scores, ids = _index.search(query_vector, min(top_k, _index.ntotal))

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        row = _df.iloc[int(idx)]
        results.append(
            {
                "faq_id": int(row["faq_id"]),
                "category": row["category"],
                "question": row["question"],
                "answer": row["answer"],
                "score": float(score),
            }
        )
    return results


def _build_prompt(query: str, contexts: list[dict]) -> str:
    """Prompt terstruktur Persona / Task / Context / Format."""
    context_text = "\n\n".join(
        f"[{c['category']}] Q: {c['question']}\nA: {c['answer']}" for c in contexts
    ) or "(tidak ada informasi relevan yang ditemukan)"

    return f"""# Persona
Kamu adalah asisten IT Helpdesk internal perusahaan yang ramah, ringkas, dan profesional.

# Task
Jawab pertanyaan karyawan HANYA berdasarkan informasi pada bagian Context.
Jangan menambahkan fakta, angka, atau kebijakan yang tidak ada di Context.
Jika Context tidak memuat jawabannya atau pertanyaan di luar topik IT/HR perusahaan,
katakan dengan jujur bahwa kamu tidak memiliki informasinya dan sarankan
menghubungi tim IT Support atau HR melalui tiket.

# Context
{context_text}

# Format
- Jawab dalam Bahasa Indonesia, maksimal 3 kalimat.
- Langsung ke inti jawaban, tanpa pembukaan basa-basi dan tanpa menyebut kata "Context".

# Pertanyaan
{query}"""


async def answer_from_knowledge_base(query: str) -> str:
    """
    Fungsi yang dipanggil router.py ketika intent = 'faq'.
    semantic_search -> susun prompt dengan context -> panggil LLM.
    """
    contexts = [c for c in semantic_search(query) if c["score"] >= MIN_SCORE]
    prompt = _build_prompt(query, contexts)
    # Temperature rendah: jawaban harus setia pada knowledge base, bukan kreatif.
    return await generate_text(prompt, temperature=0.2)
