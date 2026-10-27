"""Busca densa via Ollama (OLLAMA_URL, padrão http://127.0.0.1:11434), sem dependências além da stdlib.

Os vetores das passagens ficam em cache em build/emb-<modelo>.json.
"""
import hashlib
import json
import math
import os
import urllib.request
from pathlib import Path

BUILD = Path(__file__).parent / "build"
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/embed"

# Alguns modelos foram treinados com prefixo de tarefa; usar sem ele piora a busca.
PREFIXOS = {"nomic-embed-text": ("search_query: ", "search_document: ")}


def _prefixos(modelo):
    return PREFIXOS.get(modelo.split(":")[0], ("", ""))


def embed(modelo, textos, lote=16):
    out = []
    for i in range(0, len(textos), lote):
        body = json.dumps({"model": modelo, "input": textos[i : i + lote], "truncate": True}).encode()
        req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            out += json.loads(r.read())["embeddings"]
    return [_norm(v) for v in out]


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Dense:
    def __init__(self, modelo, rows, variante="passagem"):
        self.modelo = modelo
        nome = modelo.replace(":", "_").replace("/", "_")
        # O cache antigo (só passagens) continua valendo sem renomear.
        cache = BUILD / (f"emb-{nome}.json" if variante == "passagem" else f"emb-{nome}-{variante}.json")
        # Chave = ID + hash do texto: se a preparação mudar o texto, o vetor é refeito.
        keys = [r["id"] + "|" + hashlib.sha1(r["text"].encode()).hexdigest()[:12] for r in rows]
        data = json.loads(cache.read_text()) if cache.exists() else {}
        falta = [(k, r) for k, r in zip(keys, rows) if k not in data]
        if falta:
            doc = _prefixos(modelo)[1]
            vecs = embed(modelo, [doc + r["text"] for _, r in falta])
            data.update({k: v for (k, _), v in zip(falta, vecs)})
            cache.write_text(json.dumps({k: data[k] for k in keys}))
        self.vecs = [data[k] for k in keys]

    def scores(self, query):
        q = embed(self.modelo, [_prefixos(self.modelo)[0] + query])[0]
        return [sum(a * b for a, b in zip(q, v)) for v in self.vecs]


def rrf(*listas_scores, k=60):
    """Reciprocal Rank Fusion: soma 1/(k + posição) de cada ranking."""
    n = len(listas_scores[0])
    out = [0.0] * n
    for s in listas_scores:
        for pos, i in enumerate(sorted(range(n), key=lambda i: -s[i])):
            out[i] += 1 / (k + pos + 1)
    return out
