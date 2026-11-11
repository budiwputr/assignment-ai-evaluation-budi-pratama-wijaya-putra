"""
Menjalankan skenario uji ke endpoint /ask dan mencetak tabel hasil.

Pemakaian (server harus sudah berjalan, lokal maupun di Docker):
    python tests/run_scenarios.py
    python tests/run_scenarios.py --url http://localhost:8000 --out tests/results.md

Hanya memakai library standar Python, jadi tidak perlu install tambahan.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

# (nama skenario, query, intent yang diharapkan)
SCENARIOS = [
    ("1. FAQ - kebijakan cuti", "Berapa jatah cuti tahunan saya?", "faq"),
    ("2. FAQ - reset password VPN", "Gimana cara reset password VPN kalau akun saya terkunci?", "faq"),
    ("3. Tiket - ID ada", "Apa status tiket TICKET-0005 saya?", "ticket_status"),
    ("4. Tiket - ID tidak ada", "Tolong cek status TICKET-0999", "ticket_status"),
    ("5. Ambigu / di luar cakupan", "Bagaimana prakiraan cuaca di Jakarta besok?", "faq"),
    ("6. Tambahan - cara membuat tiket (harus FAQ)", "Bagaimana cara mengajukan tiket untuk laptop baru?", "faq"),
    ("7. Tambahan - format ID longgar", "cek tiket 7 dong, sudah sampai mana?", "ticket_status"),
    ("8. Tambahan - tiket tanpa nomor", "Status tiket saya bagaimana?", "ticket_status"),
]


def ask(base_url: str, query: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{base_url}/ask",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--out", help="Simpan hasil sebagai file Markdown")
    args = parser.parse_args()

    rows, routed_ok = [], 0
    for name, query, expected in SCENARIOS:
        http_status, body = ask(args.url, query)
        intent = body.get("intent", "-")
        ok = intent == expected
        routed_ok += ok
        rows.append((name, query, expected, intent, http_status, body.get("data", ""), ok))
        print(f"\n{name}\n  query    : {query}\n  HTTP     : {http_status}\n  intent   : {intent} (harapan: {expected}) {'OK' if ok else 'SALAH'}\n  jawaban  : {body.get('data')}")

    print(f"\nRouting benar: {routed_ok}/{len(SCENARIOS)}")

    if args.out:
        lines = ["| Skenario | Query | Intent diharapkan | Intent aktual | HTTP | Respons | Routing |", "|---|---|---|---|---|---|---|"]
        for name, query, expected, intent, http_status, data, ok in rows:
            data = data.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {name} | {query} | `{expected}` | `{intent}` | {http_status} | {data} | {'✅' if ok else '❌'} |")
        lines.append(f"\nRouting benar: **{routed_ok}/{len(SCENARIOS)}**")
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Hasil disimpan ke {args.out}")

    return 0 if routed_ok == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(main())
