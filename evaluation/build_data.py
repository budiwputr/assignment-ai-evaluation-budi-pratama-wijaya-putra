"""Menggabungkan hasil mentah (evaluation/raw/*.json) menjadi struktur baseline vs after yang bersih.
Dipakai oleh build_reports.py dan analisis angka di README."""
import json, statistics
from pathlib import Path
RAW = Path(__file__).resolve().parent / "raw"
L = lambda f: json.load(open(RAW / f"{f}.json", encoding="utf-8"))
BAD = "Layanan AI sedang tidak tersedia"   # 503 akibat kuota API: bukan perilaku sistem -> run dibuang

def clean(r):
    """Buang run yang gagal karena kuota (503) dari statistik latency."""
    ok = [i for i, x in enumerate(r["all_responses"]) if BAD not in (x or "")]
    r = dict(r)
    r["valid_runs"] = [r["latency_ms_runs"][i] for i in ok]
    r["n_valid"] = len(ok)
    r["latency_valid_median"] = round(statistics.median(r["valid_runs"]), 1) if ok else None
    return r

def baseline_scenarios():
    d = {r["scenario_id"]: r for r in L("scenarios_baseline_partial_quota_exhausted")}
    d["EVAL-05"] = [r for r in L("scenarios_baseline_eval05") if r["scenario_id"] == "EVAL-05"][0]
    d["EVAL-12"] = [r for r in L("scenarios_baseline_fill") if r["scenario_id"] == "EVAL-12"][0]
    return {k: clean(v) for k, v in d.items()}

def after_scenarios():
    return {r["scenario_id"]: clean(r) for r in L("scenarios_after")}

def baseline_safety():
    d = {}
    for f in ("safety_baseline", "safety_baseline_fill", "safety_baseline_fill2"):
        for r in L(f):
            if BAD not in str(r["response"]):   # hanya hasil valid; yang kena kuota ditimpa file berikutnya
                d[r["scenario_id"]] = r
    return d

def after_safety():
    return {r["scenario_id"]: r for r in L("safety_after")}

def tot(r):
    s = r["stage"]; return s["prompt_tokens"] + s["output_tokens"] + s["thinking_tokens"]

if __name__ == "__main__":
    b, a = baseline_scenarios(), after_scenarios()
    print(f"{'id':7} {'b_med':>7} {'a_med':>7} {'b_llm%':>6} {'b_tok(p/o/t=sum)':>22} {'a_tok(p/o/t=sum)':>22}")
    for k in sorted(b):
        x, y = b[k], a[k]; s, t = x["stage"], y["stage"]
        share = round(100 * s["llm_ms"] / x["latency_ms_runs"][0]) if s["llm_ms"] and x["latency_ms_runs"] else 0
        print(f"{k:7} {x['latency_valid_median']:>7} {y['latency_valid_median']:>7} {share:>5}% "
              f"{s['prompt_tokens']:>5}/{s['output_tokens']}/{s['thinking_tokens']}={tot(x):<6} {t['prompt_tokens']:>5}/{t['output_tokens']}/{t['thinking_tokens']}={tot(y):<6} nvalid_b={x['n_valid']}")
    faq = ["EVAL-01","EVAL-02","EVAL-03","EVAL-10"]
    print("\nrata2 median latency FAQ yang tetap memakai LLM (01,02,03,10): before", round(statistics.mean(b[k]['latency_valid_median'] for k in faq)), "after", round(statistics.mean(a[k]['latency_valid_median'] for k in faq)))
    print("rata2 token/req (01,02,03,10): before", round(statistics.mean(tot(b[k]) for k in faq)), "after", round(statistics.mean(tot(a[k]) for k in faq)))
    print("thinking share before (01,02,03,10):", round(100*sum(b[k]['stage']['thinking_tokens'] for k in faq)/sum(tot(b[k]) for k in faq)), "%")
    allb = [k for k in b if b[k]["stage"]["llm_calls"] or True]
    print("total token 12 skenario before", sum(tot(b[k]) for k in b), "after", sum(tot(a[k]) for k in a))
    print("EVAL-11 vs EVAL-12 baseline lat:", b['EVAL-11']['latency_valid_median'], b['EVAL-12']['latency_valid_median'], "runs12:", b['EVAL-12']['latency_ms_runs'], b['EVAL-12']['stage'])
    bs, as_ = baseline_safety(), after_safety()
    print("\nSAFETY")
    for k in as_:
        x = bs.get(k); y = as_[k]
        print(k, "before:", (x['http'], x['intent'], round(x['latency_ms_median']), tot(x)) if x else "tidak diuji", "| after:", (y['http'], y['intent'], round(y['latency_ms_median']), tot(y)))
