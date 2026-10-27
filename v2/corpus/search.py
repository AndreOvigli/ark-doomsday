"""Busca BM25 simples sobre as passagens, para inspeção manual do acervo.

Uso: python v2/corpus/search.py "consulta" [-k 10] [--doc ARK-006]
"""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

PASSAGES = Path(__file__).parent / "build" / "passages.jsonl"


def tokens(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [Counter(tokens(d)) for d in docs]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / len(self.lens)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = tokens(query)
        out = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for t in q:
                f = d.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


def load():
    return [json.loads(l) for l in PASSAGES.read_text(encoding="utf-8").splitlines()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--doc")
    ap.add_argument("--chars", type=int, default=160)
    args = ap.parse_args()
    rows = load()
    if args.doc:
        rows = [r for r in rows if r["doc"] == args.doc]
    bm = BM25([r["text"] for r in rows])
    ranked = sorted(zip(bm.scores(args.query), rows), key=lambda x: -x[0])[: args.k]
    for s, r in ranked:
        snippet = " ".join(r["text"].split())[: args.chars]
        print(f"{s:6.2f}  {r['id']:<48} {snippet}")


if __name__ == "__main__":
    main()
