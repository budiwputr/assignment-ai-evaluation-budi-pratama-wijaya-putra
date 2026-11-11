"""Membangun evaluation_results.csv (baseline), evaluation_results_after.csv dan
before_after_improvement_template.csv dari evaluation/raw/*.json. Jalankan: python evaluation/build_reports.py"""
import csv, statistics
from pathlib import Path
from build_data import baseline_scenarios, after_scenarios, tot

EV = Path(__file__).resolve().parent
SCEN = {r["scenario_id"]: r for r in csv.DictReader(open(EV / "evaluation_test_scenarios.csv", encoding="utf-8"))}

BASE_OBS = {
 "EVAL-01": ("Sesuai", "Menjawab 12 hari + syarat masa kerja 3 bulan sesuai FAQ #1. Kalimat tambahan soal portal HR berasal dari FAQ #6 (grounded di KB), bukan karangan. Latency 5.3-7.9 s: 93% dihabiskan satu panggilan LLM (660 thinking token vs 50 output)."),
 "EVAL-02": ("Sesuai", "Bahasa informal tetap menemukan FAQ #8 (skor 0.80). Jawaban akurat: reset mandiri via portal self-service, hubungi IT Support jika terkunci."),
 "EVAL-03": ("Sesuai", "Sinonim 'kata sandi' -> FAQ #12 (skor 0.795), semantic search bekerja. Jawaban akurat (tiket ke IT Support + verifikasi identitas)."),
 "EVAL-04": ("Sesuai (rapuh)", "Mengakui tidak punya informasi, tidak mengarang. Namun retrieval tetap mengirim 3 FAQ tak relevan (skor 0.654 > MIN_SCORE 0.45); pertahanan hanya mengandalkan LLM mengikuti prompt, satu panggilan LLM penuh (~5 s, 845 token) dipakai untuk menolak."),
 "EVAL-05": ("Sesuai (rapuh)", "Tidak mengarang nama CEO: 'Saya tidak memiliki informasi mengenai nama CEO perusahaan ini.' Sama seperti EVAL-04: 3 FAQ tak relevan terkirim (skor 0.649) dan 868 token terpakai. Hanya 1 run valid (run lain kena kuota API)."),
 "EVAL-06": ("Sesuai", "Tool call tepat: TICKET-0005, status Diproses, update 2026-08-27. Tanpa LLM, ~13 ms."),
 "EVAL-07": ("Sesuai", "Pesan informatif 'Tiket TICKET-9999 tidak ditemukan', HTTP 200, tidak crash."),
 "EVAL-08": ("Sesuai", "Meminta ID tiket, tidak menebak."),
 "EVAL-09": ("Temuan", "Router memilih ticket_status (regex 'cek tiket'); hasilnya hanya 'Mohon sebutkan nomor tiket'. Setengah pertanyaan ('kenapa laptop saya lambat') tidak terjawab padahal FAQ #15 relevan (skor 0.75). Intent tunggal tidak cukup untuk query campuran."),
 "EVAL-10": ("Sesuai", "Konsisten dengan EVAL-01: fakta sama (12 hari, masa kerja 3 bulan) di 3 run; hanya redaksi yang berbeda."),
 "EVAL-11": ("Bermasalah", "Dua run valid (run ke-3 kena kuota). Jawaban hanya membahas password & onboarding lalu menyatakan 'Saya tidak memiliki informasi mengenai kebijakan cuti' padahal KB punya 7 FAQ cuti: top-3 retrieval (FAQ #12, #31, #18) tidak memuat cuti. Klaim palsu 'tidak ada informasi' + jawaban tidak lengkap. Latency 7.2-9.0 s, 1336 token (980 thinking)."),
 "EVAL-12": ("Bermasalah", "Sapaan 'halo' dijawab: 'Silakan ajukan pertanyaan Anda terkait informasi sisa cuti, waktu perbaikan perangkat, atau prosedur izin sakit...' (topik acak dari 3 FAQ tak relevan). Token 1313 (293 prompt + 37 output + 983 thinking) hampir sama dengan EVAL-11 (1336): biaya token didominasi overhead tetap, bukan panjang query. Latency tersimpan 11.1 s mencakup 2 percobaan 429 + retry (3 panggilan); run awal tanpa retry tercatat ~6.7 s (hanya di log sesi, tidak tersimpan sebagai berkas)."),
}
AFTER_OBS = {
 "EVAL-01": ("Sesuai", "12 hari + 3 bulan, akurat. Latency 2.0-3.0 s, 451 token, thinking 0."),
 "EVAL-02": ("Sesuai", "Akurat dan relevan. 2.6 s, 360 token."),
 "EVAL-03": ("Sesuai", "Akurat. Prompt lebih panjang (572 token) karena aturan keamanan + lebih banyak konteks lolos ambang; total tetap turun (935 -> 611)."),
 "EVAL-04": ("Sesuai", "Jawaban tetap (deterministik), 0 panggilan LLM, 0 token, ~0.48 s."),
 "EVAL-05": ("Sesuai", "Jawaban tetap, 0 panggilan LLM, 0 token, ~0.46 s."),
 "EVAL-06": ("Sesuai", "Tidak berubah (jalur tool). Selisih latency 13 -> 109 ms adalah noise run pertama (197 ms, cold), bukan regresi."),
 "EVAL-07": ("Sesuai", "Tidak berubah."),
 "EVAL-08": ("Sesuai", "Tidak berubah."),
 "EVAL-09": ("Temuan (belum diperbaiki)", "Perilaku sama seperti baseline: ticket_status + minta ID; bagian 'laptop lambat' masih tidak dijawab. Dicatat sebagai rekomendasi (intent campuran)."),
 "EVAL-10": ("Sesuai", "Konsisten dengan EVAL-01 (12 hari, 3 bulan). 1.9 s, 459 token."),
 "EVAL-11": ("Sesuai (dengan catatan)", "Empat topik terjawab (cuti, reset password, perangkat, onboarding) tanpa klaim 'tidak ada informasi'. Catatan: bagian cuti membahas cuti melahirkan/pengajuan cuti, belum menyebut jatah 12 hari (FAQ #1 tidak terambil). 2.3-3.4 s, 750 token (181 output karena jawaban lebih lengkap)."),
 "EVAL-12": ("Sesuai", "Sapaan statis (intent smalltalk), 0 token, ~4 ms."),
}

def rows(data, obs):
    out = []
    for sid in sorted(SCEN):
        r, s = data[sid], data[sid]["stage"]
        verdict, note = obs[sid]
        out.append({
            "scenario_id": sid, "category": SCEN[sid]["category"], "query": SCEN[sid]["query"],
            "actual_response": (r["response"] or "").replace("\n", " \n "),
            "http_status": r["http"], "intent_detected": r["intent"],
            "latency_ms_median": r["latency_valid_median"], "latency_ms_runs_valid": "; ".join(str(round(x)) for x in r["valid_runs"]),
            "embedding_ms": round(s["embed_ms"]), "llm_ms": round(s["llm_ms"]), "llm_calls_counted": s["llm_calls"],
            "prompt_tokens": s["prompt_tokens"], "output_tokens": s["output_tokens"], "thinking_tokens": s["thinking_tokens"], "total_tokens": tot(r),
            "observation": note, "verdict": verdict,
        })
    return out

def write(path, rs):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)

if __name__ == "__main__":
    b, a = baseline_scenarios(), after_scenarios()
    write(EV / "evaluation_results.csv", rows(b, BASE_OBS))
    write(EV / "evaluation_results_after.csv", rows(a, AFTER_OBS))
    print("ditulis: evaluation_results.csv, evaluation_results_after.csv")
