"""Monta o corpus de passagens da v2 a partir da biblioteca instalada.

Uma passagem = uma página física de PDF ou um recorte editorial (.txt).
O ID é estável: <documento>#p<página> ou <documento>#<nome-do-recorte>.
A saída fica em v2/corpus/build/ (fora do Git, por direitos das fontes).

Uso: python v2/corpus/build_passages.py --library C:\\ARK\\library
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

# Documentos paginados: texto preparado pela v1 (_rag/*.pages.jsonl) ou extraído do PDF.
PAGED = {
    "ARK-001": "_rag/ARK-001.pages.jsonl",
    "ARK-002": "_rag/ARK-002.pages.jsonl",
    "ARK-003": "_rag/ARK-003.pages.jsonl",
    "ARK-004": "_rag/ARK-004.pages.jsonl",
    "ARK-005": "_rag/ARK-005.pages.jsonl",
    "ARK-006": "_rag/ARK-006.pages.jsonl",
    "ARK-008": "agricultura-alimentos/ARK-008.pdf",
    "ARK-009": "sobrevivencia-emergencias/ARK-009.pdf",
}

# Recortes editoriais (fontes estrangeiras traduzidas ou trechos conferidos).
EXCERPT_DIRS = [
    "_rag/alpha-water-gaps",
    "_rag/alpha115-additions",
    "_rag/alpha117-additions",
    "_rag/alpha118-additions",
    "_rag/emergency-additions",
    "_rag/flood-food-additions",
    "_rag/food-planning-additions",
    "_rag/hand-hygiene-additions",
    "_rag/official-extension",
    "conservas-limites",
]


# Títulos dos PDFs que não estão no catálogo da v1 (_pilot/catalog.json).
TITLES = {
    "ARK-008": "Anvisa. Cartilha sobre Boas Práticas para Serviços de Alimentação",
    "ARK-009": "Ministério da Saúde. Evite mais riscos em situações de desastres ou emergências: cuidados com a água e os alimentos",
}


def excerpt_title(text, slug):
    """Título de um recorte = a linha FONTE (fonte e nome do documento), senão a primeira linha."""
    for l in text.splitlines():
        m = re.match(r"\s*fonte( oficial)?\s*:\s*(.+)", l, re.I)
        if m and not m.group(2).startswith("http"):
            return m.group(2).strip()
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return first or slug


def pdf_pages(path):
    # Sem -layout: o modo padrão lê cada coluna inteira. Com -layout, as cartilhas em duas
    # colunas ("O que fazer? / Por que fazer?") saem intercaladas linha a linha.
    out = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\f")]


def clean(text):
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "build" / "passages.jsonl")
    args = ap.parse_args()
    lib = args.library
    catalog = {d["id"]: d for d in json.loads((lib / "_pilot/catalog.json").read_text(encoding="utf-8"))}
    rows = []

    for doc, rel in PAGED.items():
        src = lib / rel
        if src.suffix == ".jsonl":
            pages = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
            pages = [(p["pdf_page"], p["text"]) for p in pages]
        else:
            pages = list(enumerate(pdf_pages(src), start=1))
        title = catalog.get(doc, {}).get("title") or TITLES.get(doc, "")
        for n, text in pages:
            text = clean(text)
            if len(text) < 40:
                continue
            rows.append({"id": f"{doc}#p{n:03d}", "doc": doc, "title": title, "page": n, "kind": "page", "text": text})

    for d in EXCERPT_DIRS:
        for f in sorted((lib / d).glob("*.txt")):
            doc = f.name[:7]
            slug = f.stem[8:]
            text = clean(f.read_text(encoding="utf-8"))
            rows.append({"id": f"{doc}#{slug}", "doc": doc, "title": excerpt_title(text, slug), "page": None,
                         "kind": "excerpt", "text": text})

    seen = set()
    for r in rows:
        assert r["id"] not in seen, r["id"]
        seen.add(r["id"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} passagens -> {args.out}")


if __name__ == "__main__":
    main()
