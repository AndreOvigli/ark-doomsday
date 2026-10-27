"""Fase 5: avalia a resposta do Qwen nos casos D01–D24.

Etapas, cada uma com cache em eval/resultados/fase5/ (para ler os traços e para alternar
modelos na GPU de 8 GB: primeiro a busca, depois o Qwen):
  1. evidência: "oraculo" (passagens do gabarito, testa só a escrita) ou "busca" (pipeline real)
  2. resposta do Qwen (resposta/responder.py), com fallback opcional por item sem evidência
  3. juiz: o Qwen confere cada erro proibido do caso (provisório: mesmo modelo, calibrar com humano)
  4. verificação por frase (--verificar, resposta/verificar.py): o Qwen confere cada orientação
     contra os trechos citados; sai a que contradiz (e a que o trecho não diz, com --estrito)
  5. checagem por código (resposta/checagem.py): remove orientação com número que não está no
     trecho citado. Roda no relatório, então vale também para as respostas em cache.

Métricas por código: JSON válido, modo certo (pergunta x resposta), citações válidas,
cobertura das necessidades por citação, lacunas declaradas, tokens e tempo.

Uso: python v2/eval/answer_eval.py --evidencia oraculo|busca [--turno ultimo|primeiro] [--k 8] [--fallback]
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2 / "resposta"), str(V2 / "corpus"), str(V2 / "conversa")]
from responder import responder, QWEN_URL, QWEN, NUM_CTX  # noqa: E402
from checagem import corrigir  # noqa: E402
from verificar import verificar, aplicar  # noqa: E402
from search import load  # noqa: E402

OUT = V2 / "eval" / "resultados" / "fase5"


def ler(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gravar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def descarregar_embedding(modelo):
    """Tira o bge-m3 da GPU antes do Qwen (os dois não cabem juntos em 8 GB com o reranker)."""
    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/embed"
    body = json.dumps({"model": modelo, "input": [], "keep_alive": 0}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=60)
    except Exception as e:  # noqa: BLE001
        print("aviso: não consegui descarregar o embedding:", e)


JUIZ = """Você confere respostas de um assistente de sobrevivência. Para cada erro listado, diga se a RESPOSTA \
comete esse erro (afirma, recomenda ou permite o que o erro descreve). Seja literal: se a resposta não trata \
do assunto, ela não comete o erro. Devolva só JSON: {"erros": [{"erro": "...", "comete": true ou false}]}"""


def julgar(resposta_texto, erros):
    if not erros:
        return []
    user = "RESPOSTA\n" + resposta_texto + "\n\nERROS\n" + "\n".join(f"- {e}" for e in erros)
    body = {"model": QWEN, "messages": [{"role": "system", "content": JUIZ}, {"role": "user", "content": user}],
            "format": "json", "think": False, "stream": False, "options": {"temperature": 0, "num_ctx": NUM_CTX}}  # mesmo contexto da resposta: o Ollama não recarrega o modelo
    req = urllib.request.Request(QWEN_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(json.loads(r.read())["message"]["content"])
    marcados = {e.get("erro", "").strip(): bool(e.get("comete")) for e in out.get("erros", [])}
    return [e for e in erros if marcados.get(e.strip())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidencia", choices=["oraculo", "busca"], required=True)
    ap.add_argument("--turno", choices=["ultimo", "primeiro"], default="ultimo")
    ap.add_argument("--k", type=int, default=8, help="passagens entregues ao Qwen (busca)")
    ap.add_argument("--fallback", action="store_true",
                    help="se a resposta listar itens sem evidência, busca cada item e responde de novo (até 10 passagens)")
    ap.add_argument("--casos", default="", help="só estes casos, ex.: D05,D22")
    ap.add_argument("--prompt", choices=["v1", "v2", "v3"], default="v1", help="prompt da resposta (resposta/responder.py)")
    ap.add_argument("--verificar", action="store_true", help="verificação por frase (cache em _verificacao)")
    ap.add_argument("--verificador", choices=["v1", "v2"], default="v1", help="prompt da verificação por frase")
    ap.add_argument("--pensar", action="store_true", help="liga o modo de raciocínio do Qwen3 na resposta")
    ap.add_argument("--estrito", action="store_true", help="com --verificar, remove também as frases 'nao_diz'")
    ap.add_argument("--sem-checagem", action="store_true", help="relatório sem a checagem de números")
    ap.add_argument("--ancorar", action="store_true",
                    help="resposta ancorada: antes de responder, o Qwen copia proibições e passos dos trechos (resposta/ancorar.py)")
    ap.add_argument("--decomp", choices=["v3", "v4"], default="v3", help="prompt de decomposição da busca")
    ap.add_argument("--contra", action="store_true", help="busca com a consulta fixa de contraindicação (busca.CONTRA)")
    ap.add_argument("--conjunto", choices=["dev", "val"], default="dev",
                    help="dev: D01–D24; val: V01–V20, rodado uma vez com o sistema congelado")
    args = ap.parse_args()

    out = OUT if args.conjunto == "dev" else V2 / "eval" / "resultados" / "validacao"
    cases = json.loads((V2 / "eval" / f"{args.conjunto}-cases.json").read_text(encoding="utf-8"))["casos"]
    if args.casos:
        cases = [c for c in cases if c["id"] in args.casos.split(",")]
    por_id = {r["id"]: r for r in load()}
    decomp_path = (V2 / "eval" / "resultados" / f"decomposicoes-{args.decomp}-{args.turno}.json" if args.conjunto == "dev"
                   else out / f"decomposicoes-{args.decomp}-{args.turno}.json")
    decomp = ler(decomp_path)
    variante = ("" if args.decomp == "v3" else f"-d{args.decomp}") + ("-contra" if args.contra else "")
    tag = f"{args.evidencia}-{args.turno}" + (f"-k{args.k}{variante}" if args.evidencia == "busca" else "") + ("-fallback" if args.fallback else "")
    tag += ("" if args.prompt == "v1" else f"-{args.prompt}") + ("-pensar2" if args.pensar else "") + ("-ancorada" if args.ancorar else "")  # pensar2: amostragem do modo de raciocínio
    chave_ver = "_verificacao" if args.verificador == "v1" else f"_verificacao_{args.verificador}"

    def msgs(c):
        return c["mensagens"] if args.turno == "ultimo" else c["mensagens"][:1]

    # 1. Evidência
    rec_path = out / (f"evidencia-{args.evidencia}-{args.turno}"
                      + (f"-k{args.k}{variante}" if args.evidencia == "busca" else "") + ".json")
    evid = ler(rec_path)
    busca = None
    falta = [c for c in cases if c["id"] not in evid]
    if (falta and args.evidencia == "busca") or args.fallback:
        from busca import Busca
        busca = Busca()
    for c in falta:
        if args.evidencia == "oraculo":
            ids = list(dict.fromkeys(n["aceita"][0] for n in c["necessidades"]))
        else:
            if c["id"] not in decomp:
                from decompor import decompor
                decomp[c["id"]] = dict(decompor(msgs(c), args.decomp, num_ctx=NUM_CTX), mensagens=msgs(c))
                if args.conjunto != "dev":
                    gravar(decomp_path, decomp)
            ids = busca.recuperar(msgs(c), decomp[c["id"]]["consultas"], args.k, contra=args.contra)
        evid[c["id"]] = ids
    if falta:
        gravar(rec_path, evid)
    if busca and not args.fallback:
        descarregar_embedding(busca.dense.modelo)
        busca = None
        try:  # libera o reranker da GPU antes do Qwen
            import gc
            import torch
            gc.collect()
            torch.cuda.empty_cache()
        except ImportError:
            pass

    # 2. Resposta (+ fallback) e 3. juiz
    res_path = out / f"respostas-{tag}.json"
    res = ler(res_path)
    for c in cases:
        if c["id"] in res:
            continue
        d = decomp.get(c["id"], {})
        ids = list(evid[c["id"]])
        t0 = time.time()
        ancoras = None
        try:
            if args.ancorar:
                from ancorar import extrair, formatar
                ancoras = extrair(msgs(c), [por_id[i] for i in ids])
            r = responder(msgs(c), [por_id[i] for i in ids], d.get("situacao", ""), d.get("risco", ""), prompt=args.prompt,
                          pensar=args.pensar, ancoras=formatar(ancoras) if ancoras else "")
        except Exception as e:  # noqa: BLE001
            r = {"erro_execucao": str(e)}
        if ancoras is not None:
            r["_ancoras"] = ancoras
        extra = []
        if args.fallback and busca and r.get("modo") == "resposta" and r.get("sem_evidencia"):
            for item in r["sem_evidencia"][:2]:
                novos = [i for i in busca.ordenar(" ".join(msgs(c)) + "\n" + item) if i not in ids][:2]
                extra += novos
                ids += novos
            ids = ids[:10]
            if extra:
                r = responder(msgs(c), [por_id[i] for i in ids], d.get("situacao", ""), d.get("risco", ""), prompt=args.prompt, pensar=args.pensar)
        r["_segundos"] = round(time.time() - t0, 1)
        r["_ids"] = ids
        r["_fallback"] = extra
        r["_erros_proibidos"] = julgar(r.get("texto", ""), c["erros_proibidos"]) if "texto" in r else None
        res[c["id"]] = r
        gravar(res_path, res)
        print(f"[{len(res)}/{len(cases)}]", c["id"], r.get("modo"), f"{r['_segundos']}s", "erros:", r["_erros_proibidos"], flush=True)

    # 4. Verificação por frase (fica no cache das respostas, então dá para ligar depois)
    if args.verificar:
        for c in cases:
            r = res[c["id"]]
            if chave_ver in r or r.get("modo") != "resposta":
                continue
            t0 = time.time()
            r[chave_ver] = verificar(msgs(c), r, [por_id[i] for i in r["_ids"]], args.verificador)
            r["_segundos" + chave_ver] = round(time.time() - t0, 1)
            gravar(res_path, res)
            print(f"[verificação {sum(chave_ver in res[x['id']] for x in cases)}/{len(cases)}]", c["id"], "verificação:", [v["veredito"] for v in r[chave_ver]], f"{r['_segundos' + chave_ver]}s")

    # Relatório
    print(f"\nfase 5: evidência {args.evidencia}, turno {args.turno}" + (f", k {args.k}" if args.evidencia == "busca" else "")
          + (", fallback" if args.fallback else "") + f", prompt {args.prompt}"
          + (f", verificação {args.verificador}" + (" estrita" if args.estrito else "") if args.verificar else "")
          + (", pensar" if args.pensar else "") + f", modelo {QWEN}\n")
    print(f"{'caso':<5} {'tipo':<14} {'modo':<9} {'cobre':<6} {'cit.ok':<7} {'lacuna':<7} erros proibidos")
    tot = {"json": 0, "modo": 0, "cob": 0, "nec": 0, "cit": 0, "citn": 0, "crit": 0, "seg": 0.0, "tok": 0,
           "num": 0, "numc": 0, "ver": 0, "verc": [], "nd": 0, "frases": 0, "segv": 0.0}
    for c in cases:
        r = res[c["id"]]
        if args.verificar and r.get(chave_ver):
            vs = r[chave_ver]
            tot["frases"] += len(vs)
            tot["nd"] += sum(v["veredito"] == "nao_diz" for v in vs)
            tot["segv"] += r.get("_segundos" + chave_ver, 0)
            r = aplicar(r, vs, args.estrito)
            tot["ver"] += len(r.get("_verificacao_removidas", []))
            if r.get("_verificacao_removidas"):
                tot["verc"].append(c["id"])
        if not args.sem_checagem:
            r = corrigir(r, [por_id[i] for i in r.get("_ids", [])])
            tot["num"] += len(r.get("_checagem", []))
            tot["numc"] += bool(r.get("_checagem"))
        ok = "modo" in r and "texto" in r
        tot["json"] += ok
        esperado = "pergunta" if c["tipo"] == "esclarecimento" and args.turno == "primeiro" else "resposta"
        tot["modo"] += r.get("modo") == esperado
        ids = r.get("_ids", [])
        citados = set()
        for o in r.get("orientacoes", []) or []:
            for f in o.get("fontes", []) or []:
                tot["citn"] += 1
                if isinstance(f, int) and 1 <= f <= len(ids):
                    tot["cit"] += 1
                    citados.add(ids[f - 1])
        cob = sum(any(p in citados for p in n["aceita"]) for n in c["necessidades"]) if r.get("modo") == "resposta" else 0
        if esperado == "resposta":
            tot["cob"] += cob
            tot["nec"] += len(c["necessidades"])
        erros = r.get("_erros_proibidos") or []
        tot["crit"] += bool(erros)
        tot["seg"] += r.get("_segundos", 0)
        tot["tok"] += r.get("_tokens_entrada") or 0
        lac = "sim" if r.get("sem_evidencia") else "-"
        print(f"{c['id']:<5} {c['tipo']:<14} {str(r.get('modo')):<9} {cob}/{len(c['necessidades']):<4} "
              f"{'ok' if ok else 'FALHA':<7} {lac:<7} {'; '.join(erros)}")
    n = len(cases)
    print(f"\nJSON válido: {tot['json']}/{n}")
    print(f"Modo certo (pergunta x resposta): {tot['modo']}/{n}")
    print(f"Cobertura das necessidades por citação (casos de resposta): {tot['cob']}/{tot['nec']}"
          + (f" = {tot['cob']/tot['nec']:.0%}" if tot["nec"] else ""))
    print(f"Citações válidas: {tot['cit']}/{tot['citn']}")
    print(f"Casos com erro proibido (juiz provisório): {tot['crit']}/{n}")
    if args.verificar:
        print(f"Verificação por frase: {tot['ver']} frases removidas ({', '.join(tot['verc'])}); "
              f"'nao_diz' em {tot['nd']}/{tot['frases']}; +{tot['segv']/n:.1f} s por caso")
    if not args.sem_checagem:
        print(f"Checagem de números: {tot['num']} frases removidas em {tot['numc']} casos")
    cobertos = [c for c in cases if c["cobertura"] == "sustentado"]
    print(f"Casos totalmente sustentados que declararam 'sem evidência' (sem contar a checagem): "
          f"{sum(any(not str(x).startswith('número sem fonte') for x in (res[c['id']].get('sem_evidencia') or [])) for c in cobertos)}/{len(cobertos)}")
    def declarou(c):
        return any(not str(x).startswith("número sem fonte") for x in (res[c["id"]].get("sem_evidencia") or []))
    for nivel in ("lacuna", "parcial"):
        grupo = [c for c in cases if c["cobertura"] == nivel]
        if grupo:
            print(f"Casos '{nivel}' que declararam o que a biblioteca não cobre: {sum(map(declarou, grupo))}/{len(grupo)}")
    if args.evidencia == "busca":
        achou = sum(any(p in evid[c["id"]] for p in n["aceita"]) for c in cases for n in c["necessidades"])
        print(f"Busca: necessidades com passagem aceita entre as {args.k} entregues: {achou}/{sum(len(c['necessidades']) for c in cases)}")
    print(f"Tempo médio por resposta: {tot['seg']/n:.1f} s; tokens de entrada médios: {tot['tok']/n:.0f}")


if __name__ == "__main__":
    main()
