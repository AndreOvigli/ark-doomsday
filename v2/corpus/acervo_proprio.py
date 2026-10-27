"""Monta o corpus de passagens a partir de qualquer pasta de documentos.

Para quem monta o próprio acervo (veja GUIA-DE-FONTES.md). Lê a pasta inteira, recursivamente:
- cada .pdf vira uma passagem por página física (<arquivo>#p<página>);
- cada .txt vira uma passagem só (<arquivo>#txt), com título da linha "FONTE:" se houver.
Gera o mesmo passages.jsonl que build_passages.py, então a busca e o app funcionam igual.
Requer pdftotext (Poppler) no PATH.

Uso: python v2/corpus/acervo_proprio.py --library ./minha-biblioteca
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from build_passages import clean, excerpt_title, pdf_pages


def doc_id(path, raiz):
    # ID estável a partir do caminho relativo, sem espaços nem acentos problemáticos.
    rel = path.relative_to(raiz).with_suffix("").as_posix()
    return re.sub(r"[^\w./-]+", "-", rel)


def pdf_title(path):
    try:
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
    except FileNotFoundError:
        info = ""
    m = re.search(r"^Title:\s*(.+)$", info, re.M)
    return m.group(1).strip() if m and m.group(1).strip() else path.stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "build" / "passages.jsonl")
    args = ap.parse_args()
    lib = args.library
    rows = []

    for f in sorted(lib.rglob("*")):
        if f.suffix.lower() == ".pdf":
            doc, title = doc_id(f, lib), pdf_title(f)
            for n, text in enumerate(pdf_pages(f), start=1):
                text = clean(text)
                if len(text) < 40:
                    continue
                rows.append({"id": f"{doc}#p{n:03d}", "doc": doc, "title": title, "page": n, "kind": "page", "text": text})
        elif f.suffix.lower() == ".txt":
            doc = doc_id(f, lib)
            text = clean(f.read_text(encoding="utf-8"))
            if len(text) < 40:
                continue
            rows.append({"id": f"{doc}#txt", "doc": doc, "title": excerpt_title(text, f.stem), "page": None,
                         "kind": "excerpt", "text": text})

    if not rows:
        raise SystemExit(f"nenhum .pdf ou .txt com texto em {lib}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} passagens de {len({r['doc'] for r in rows})} documentos -> {args.out}")


if __name__ == "__main__":
    main()
