"""Mede o recall da busca contra o gabarito de evidência (dev-cases.json).

Recall@k de um caso = necessidades com pelo menos uma passagem aceita no top-k / necessidades.
A consulta é a concatenação das mensagens do usuário até o turno avaliado.

Uso: python v2/eval/retrieval_eval.py [--k 5 20] [--turno ultimo|primeiro]
         [--metodo bm25|denso|hibrido] [--modelo bge-m3] [--rerank N]
Denso e híbrido usam o Ollama local (ver corpus/dense.py).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "corpus"))
from search import BM25, load  # noqa: E402
from dense import Dense, rrf  # noqa: E402
from texto import limpar  # noqa: E402
sys.path.insert(0, str(ROOT / "conversa"))


def check_ids(cases, ids):
    missing = [(c["id"], n["id"], p) for c in cases for n in c["necessidades"] for p in n["aceita"] if p not in ids]
    for m in missing:
        print("ID inexistente:", *m)
    return not missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[5, 20])
    ap.add_argument("--turno", choices=["ultimo", "primeiro"], default="ultimo")
    ap.add_argument("--metodo", choices=["bm25", "denso", "hibrido"], default="bm25")
    ap.add_argument("--modelo", default="bge-m3", help="modelo de embedding no Ollama")
    ap.add_argument("--rerank", type=int, default=0, metavar="N",
                    help="reordena os N primeiros itens com o reranker (corpus/rerank.py)")
    ap.add_argument("--unidade", choices=["passagem", "trecho"], default="passagem",
                    help="busca em passagens inteiras ou em trechos (build_chunks.py)")
    ap.add_argument("--contexto", action="store_true",
                    help="trechos com cabeçalho de documento e página")
    ap.add_argument("--excluir", default="", help="documentos fora da busca, ex.: ARK-002,ARK-006")
    ap.add_argument("--limpar", action="store_true",
                    help="tira a ficha de catalogação (FONTE, URL, datas) do texto de busca")
    ap.add_argument("--titulo-rerank", action="store_true",
                    help="o reranker lê 'título do documento + texto'")
    ap.add_argument("--max-len", type=int, default=1024, help="tokens que o reranker lê por par")
    ap.add_argument("--consultas", choices=["conversa", "oraculo", "qwen"], default="conversa",
                    help="conversa = uma busca com as mensagens; oraculo = uma busca por necessidade do gabarito "
                         "(teto, não é resultado); qwen = o Qwen decompõe a conversa (conversa/decompor.py)")
    ap.add_argument("--sub-conversa", action="store_true",
                    help="com --consultas qwen: cada subconsulta vai junto com a conversa")
    ap.add_argument("--prompt", choices=["v1", "v2", "v3"], default="v3", help="versão do prompt de decomposição")
    ap.add_argument("--com-conversa", action="store_true",
                    help="com --consultas qwen: a busca da conversa inteira entra como a primeira lista intercalada")
    ap.add_argument("--k-adaptativo", default="", metavar="BASE,MAX",
                    help="com --consultas qwen: k = BASE + (consultas - 1), limitado a MAX. Ex.: 5,8")
    ap.add_argument("--fp16", action="store_true", help="reranker em meia precisão (menos VRAM)")
    args = ap.parse_args()
    cases = json.loads((ROOT / "eval" / "dev-cases.json").read_text(encoding="utf-8"))["casos"]
    rows = load()
    if not check_ids(cases, {r["id"] for r in rows}):
        sys.exit(1)

    # Itens de busca: passagens, ou trechos que apontam para a passagem-mãe.
    if args.unidade == "passagem":
        items = [{"id": r["id"], "parent": r["id"], "doc": r["doc"], "title": r["title"], "text": r["text"]} for r in rows]
    else:
        path = ROOT / "corpus" / "build" / "chunks.jsonl"
        items = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
        if args.contexto:
            items = [dict(i, text=i["ctx"]) for i in items]
    if args.limpar:
        items = [dict(i, text=limpar(i["text"])) for i in items]
    fora = set(filter(None, args.excluir.split(",")))
    items = [i for i in items if i["doc"] not in fora]

    variante = args.unidade + ("-ctx" if args.contexto else "") + ("-limpo" if args.limpar else "")
    bm = BM25([i["text"] for i in items])
    dn = Dense(args.modelo, items, variante) if args.metodo != "bm25" else None

    def scores(q):
        if args.metodo == "bm25":
            return bm.scores(q)
        if args.metodo == "denso":
            return dn.scores(q)
        return rrf(bm.scores(q), dn.scores(q))

    rr = None
    if args.rerank:
        from rerank import Reranker
        rr = Reranker(fp16=args.fp16, max_length=args.max_len)

    print(f"método: {args.metodo}" + (f" ({args.modelo})" if dn else "") + f", turno: {args.turno}"
          + f", unidade: {variante}" + (f", sem {args.excluir}" if fora else "")
          + (f", rerank top-{args.rerank}" + (" fp16" if args.fp16 else "") + (" +título" if args.titulo_rerank else "")
             + (f" max {args.max_len}" if args.max_len != 1024 else "") if rr else "") + "\n")

    def buscar(q):
        """Itens ordenados para uma consulta, com o reranker julgando contra essa consulta."""
        s = scores(q)
        order = sorted(range(len(items)), key=lambda i: -s[i])
        if rr:
            cand = order[: args.rerank]
            pre = (lambda i: items[i]["title"] + "\n") if args.titulo_rerank else (lambda i: "")
            rs = rr.scores(q, [pre(i) + items[i]["text"] for i in cand])
            order = [i for _, i in sorted(zip(rs, cand), key=lambda x: -x[0])] + order[args.rerank :]
        return list(dict.fromkeys(items[i]["parent"] for i in order))

    def intercalar(listas):
        """Round-robin: 1º de cada consulta, depois 2º de cada... sem repetir passagem."""
        out, seen = [], set()
        for pos in range(max(len(l) for l in listas)):
            for l in listas:
                if pos < len(l) and l[pos] not in seen:
                    seen.add(l[pos])
                    out.append(l[pos])
        return out

    cache_path = ROOT / "eval" / "resultados" / f"decomposicoes-{args.prompt}-{args.turno}.json"
    decomp = {}
    if args.consultas == "qwen":
        from decompor import decompor, QWEN
        decomp = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        print(f"consultas: Qwen ({QWEN}), prompt {args.prompt}" + (", + conversa" if args.com_conversa else "")
              + f", cache em {cache_path.name}")
    elif args.consultas == "oraculo":
        print("consultas: oráculo (uma por necessidade do gabarito; é um teto, não um resultado)")

    total = Counter()
    util = Counter()  # passagens do top-k que estão aceitas para alguma necessidade do caso
    adapt, soma_k = 0, 0
    base_k, max_k = (int(x) for x in args.k_adaptativo.split(",")) if args.k_adaptativo else (0, 0)
    print(f"{'caso':<5} {'cobertura':<11} " + " ".join(f"R@{k:<4}" for k in args.k) + " necessidades perdidas no top-%d" % max(args.k))
    for c in cases:
        msgs = c["mensagens"] if args.turno == "ultimo" else c["mensagens"][:1]
        q = " ".join(msgs)
        # k conta passagens distintas: vários trechos da mesma página ocupam uma vaga só.
        if args.consultas == "conversa":
            ranked = buscar(q)
        else:
            if args.consultas == "oraculo":
                subs = [n["o_que"] for n in c["necessidades"]]
            else:
                if c["id"] not in decomp:
                    decomp[c["id"]] = dict(decompor(msgs, args.prompt), mensagens=msgs)
                    cache_path.parent.mkdir(exist_ok=True)
                    cache_path.write_text(json.dumps(decomp, ensure_ascii=False, indent=2), encoding="utf-8")
                subs = decomp[c["id"]]["consultas"] or [q]
            juntar = args.consultas == "qwen" and args.sub_conversa
            listas = [buscar(q + "\n" + sq if juntar else sq) for sq in subs]
            if args.com_conversa and args.consultas == "qwen":
                listas = [buscar(q)] + listas
            ranked = intercalar(listas)
            if base_k:
                ka = min(max_k, base_k + len(subs) - 1)
                soma_k += ka
                adapt += sum(any(p in set(ranked[:ka]) for p in n["aceita"]) for n in c["necessidades"])
        aceitas = {p for n in c["necessidades"] for p in n["aceita"]}
        for k in args.k:
            util[k] += sum(p in aceitas for p in ranked[:k])
        line = []
        for k in args.k:
            top = set(ranked[:k])
            hit = sum(any(p in top for p in n["aceita"]) for n in c["necessidades"])
            total[k] += hit
            line.append(f"{hit}/{len(c['necessidades'])}  ")
        top = set(ranked[: max(args.k)])
        lost = [n["id"] for n in c["necessidades"] if not any(p in top for p in n["aceita"])]
        print(f"{c['id']:<5} {c['cobertura']:<11} " + " ".join(line) + " " + ",".join(lost))
    n = sum(len(c["necessidades"]) for c in cases)
    print("\nTotal de necessidades:", n)
    for k in args.k:
        print(f"Recall@{k}: {total[k]}/{n} = {total[k]/n:.0%}   Precision@{k}: {util[k]/(k*len(cases)):.0%}")
    if base_k:
        print(f"Recall@adaptativo ({args.k_adaptativo}): {adapt}/{n} = {adapt/n:.0%}, "
              f"média de {soma_k/len(cases):.1f} passagens por caso (compare com R@k fixo de mesma média)")


if __name__ == "__main__":
    main()
