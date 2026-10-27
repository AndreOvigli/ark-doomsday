"""Busca: a consulta de contraindicação traz o trecho "isso não se trata"?

Na validação (V02 piscina, V05 cheiro de químico), o trecho que dizia "essa água não serve,
ferver não resolve" não chegou ao Qwen. Este script mede, nos casos de desenvolvimento
(D01–D29; D25–D29 são da família contraindicação), quatro variantes da busca do app:
  v3          decomposição atual
  v3+contra   v3 e uma consulta fixa de contraindicação na frente (busca.CONTRA)
  v4          decomposição com a primeira consulta sobre quando NÃO usar
  v4+contra   as duas coisas

Métricas: necessidades com passagem aceita entre as k entregues, no total e só nas
necessidades de contraindicação (marcadas no gabarito, mais o D24 n1). Não usa o V-set.

Uso: python v2/eval/busca_contra.py [--k 8]
"""
import argparse
import json
import sys
import time
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2 / "resposta"), str(V2 / "corpus"), str(V2 / "conversa")]
from busca import Busca  # noqa: E402
from decompor import decompor  # noqa: E402
from responder import NUM_CTX  # noqa: E402

RES = V2 / "eval" / "resultados"


def critica(c, n):
    return n.get("contraindicacao") or (c["id"] == "D24" and n["id"] == "n1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()
    cases = json.loads((V2 / "eval" / "dev-cases.json").read_text(encoding="utf-8"))["casos"]
    busca = Busca()

    decomp = {}
    for prompt in ("v3", "v4"):
        path = RES / f"decomposicoes-{prompt}-ultimo.json"
        d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        for i, c in enumerate(cases, 1):
            if c["id"] not in d:
                t0 = time.time()
                d[c["id"]] = dict(decompor(c["mensagens"], prompt, num_ctx=NUM_CTX), mensagens=c["mensagens"])
                path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[decompor {prompt} {i}/{len(cases)}] {c['id']} {time.time() - t0:.1f}s", flush=True)
        decomp[prompt] = d

    variantes = [("v3", False), ("v3", True), ("v4", False), ("v4", True)]
    out = {}
    for prompt, contra in variantes:
        nome = prompt + ("+contra" if contra else "")
        tot = crit = n_tot = n_crit = 0
        perdas = {}
        evid = {}
        t0 = time.time()
        for c in cases:
            ids = busca.recuperar(c["mensagens"], decomp[prompt][c["id"]]["consultas"], args.k, contra=contra)
            evid[c["id"]] = ids
            for n in c["necessidades"]:
                ok = any(p in ids for p in n["aceita"])
                tot += ok
                n_tot += 1
                if critica(c, n):
                    crit += ok
                    n_crit += 1
                if not ok:
                    perdas.setdefault(c["id"], []).append(n["id"] + ("*" if critica(c, n) else ""))
        out[nome] = {"evidencia": evid, "total": [tot, n_tot], "contraindicacao": [crit, n_crit],
                     "segundos": round(time.time() - t0, 1)}
        print(f"\n{nome}: total {tot}/{n_tot} = {tot / n_tot:.0%}; contraindicação {crit}/{n_crit}; "
              f"{out[nome]['segundos'] / len(cases):.1f} s por caso")
        print("  perdidas (* = contraindicação):", "; ".join(f"{k} {','.join(v)}" for k, v in perdas.items()))
    (RES / f"busca-contra-k{args.k}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nconsultas v4 dos casos D25–D29 e D24:")
    for c in cases:
        if c["id"] in ("D24", "D25", "D26", "D27", "D28", "D29"):
            print(" ", c["id"], decomp["v4"][c["id"]]["consultas"])


if __name__ == "__main__":
    main()
