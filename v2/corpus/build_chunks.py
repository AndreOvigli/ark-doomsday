"""Corta as passagens (páginas e recortes) em trechos menores para a busca.

Cada trecho guarda o ID da passagem-mãe: a busca roda nos trechos, mas o
resultado é contado e entregue por passagem (small-to-big).

Uso: python v2/corpus/build_chunks.py [--palavras 120] [--sobra 2]
"""
import argparse
import json
from pathlib import Path

BUILD = Path(__file__).parent / "build"


def cortar(texto, palavras, sobra):
    """Junta linhas até ~`palavras` palavras; o próximo trecho repete as últimas `sobra` linhas."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    trechos, atual = [], []
    for l in linhas:
        atual.append(l)
        if sum(len(x.split()) for x in atual) >= palavras:
            trechos.append(atual)
            atual = atual[-sobra:] if sobra else []
    if atual and (not trechos or atual != trechos[-1][-len(atual):]):
        trechos.append(atual)
    return ["\n".join(t) for t in trechos] or [texto]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palavras", type=int, default=120)
    ap.add_argument("--sobra", type=int, default=2)
    args = ap.parse_args()
    rows = [json.loads(l) for l in (BUILD / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
    out = []
    for r in rows:
        for n, t in enumerate(cortar(r["text"], args.palavras, args.sobra), 1):
            onde = f"página {r['page']}" if r.get("page") else "recorte"
            out.append({
                "id": f"{r['id']}~c{n:02d}",
                "parent": r["id"],
                "doc": r["doc"],
                "title": r["title"],
                "text": t,
                # Cabeçalho de contexto: o trecho sozinho não diz de que documento veio.
                "ctx": f"{r['title']} ({r['doc']}, {onde})\n{t}",
            })
    dest = BUILD / "chunks.jsonl"
    dest.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in out), encoding="utf-8")
    print(f"{len(rows)} passagens -> {len(out)} trechos em {dest}")


if __name__ == "__main__":
    main()
