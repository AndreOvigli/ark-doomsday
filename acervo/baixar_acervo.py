"""Monta a biblioteca local do ARK a partir das fontes oficiais.

O repositório não traz os documentos (eles pertencem às instituições que os publicaram).
Este script baixa cada original listado em fontes.json, confere o SHA256 da captura,
extrai o texto por página dos PDFs e copia os recortes traduzidos que podem ser publicados.
A saída tem o layout que v2/corpus/build_passages.py espera.

É a única etapa do acervo que precisa de internet. Requer pdftotext (Poppler) no PATH.

Uso: python acervo/baixar_acervo.py --library ./biblioteca
"""
import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

AQUI = Path(__file__).parent

# Onde cada PDF fica dentro da biblioteca. Os de _rag viram <id>.pages.jsonl; 008 e 009 são lidos direto do PDF.
PAGINADOS = {
    "ARK-001": "_rag", "ARK-002": "_rag", "ARK-003": "_rag",
    "ARK-004": "_rag", "ARK-005": "_rag", "ARK-006": "_rag",
    "ARK-008": "agricultura-alimentos", "ARK-009": "sobrevivencia-emergencias",
}


def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "ARK-acervo/0.1 (+github.com/AndreOvigli/ark-doomsday)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = r.read()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    return hashlib.sha256(dados).hexdigest(), len(dados)


def paginas_pdf(pdf):
    # Mesmo modo do build_passages.py: sem -layout, para ler cada coluna inteira.
    out = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    return out.split("\f")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", required=True, type=Path)
    ap.add_argument("--fontes", type=Path, default=AQUI / "fontes.json")
    ap.add_argument("--recortes", type=Path, default=AQUI / "recortes")
    args = ap.parse_args()
    lib = args.library
    fontes = json.loads(args.fontes.read_text(encoding="utf-8"))["fontes"]
    relatorio, catalogo = [], []

    for f in fontes:
        ext = ".pdf" if f["tipo"] == "pdf" else ".html"
        pasta = PAGINADOS.get(f["id"], "originais")
        destino = lib / (pasta if pasta != "_rag" else "originais") / f"{f['id']}{ext}"
        try:
            sha, tamanho = baixar(f["url"], destino)
        except Exception as e:  # uma fonte fora do ar não derruba as outras
            relatorio.append({"id": f["id"], "estado": "falhou", "erro": str(e)})
            print(f"  {f['id']}: FALHOU ({e})")
            continue
        if f.get("sha256_captura") is None:
            estado = "sem hash de referência"
        elif sha == f["sha256_captura"]:
            estado = "igual à captura"
        else:
            # Páginas HTML mudam com frequência; um PDF diferente pede reavaliação da fonte.
            estado = "MUDOU desde a captura: reavaliar"
        relatorio.append({"id": f["id"], "estado": estado, "sha256": sha, "bytes": tamanho})
        print(f"  {f['id']}: {estado} ({tamanho / 1e6:.1f} MB)")

        if PAGINADOS.get(f["id"]) == "_rag":
            jsonl = lib / "_rag" / f"{f['id']}.pages.jsonl"
            jsonl.parent.mkdir(parents=True, exist_ok=True)
            with jsonl.open("w", encoding="utf-8") as fh:
                for n, texto in enumerate(paginas_pdf(destino), start=1):
                    fh.write(json.dumps({"pdf_page": n, "text": texto}, ensure_ascii=False) + "\n")
        catalogo.append({"id": f["id"], "title": f["titulo"], "institution": f["instituicao"], "source_url": f["url"]})

    # Recortes traduzidos publicáveis: acervo/recortes/<pasta>/*.txt -> <biblioteca>/_rag/<pasta>/
    # (conservas-limites fica na raiz da biblioteca, como o build_passages.py espera).
    n_recortes = 0
    for txt in sorted(args.recortes.glob("*/*.txt")) if args.recortes.exists() else []:
        base = lib if txt.parent.name == "conservas-limites" else lib / "_rag"
        alvo = base / txt.parent.name / txt.name
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(txt.read_text(encoding="utf-8"), encoding="utf-8")
        n_recortes += 1

    (lib / "_pilot").mkdir(parents=True, exist_ok=True)
    (lib / "_pilot" / "catalog.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    (lib / "relatorio-acervo.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    falhas = sum(r["estado"] == "falhou" for r in relatorio)
    mudou = sum(r["estado"].startswith("MUDOU") for r in relatorio)
    total = sum(r.get("bytes", 0) for r in relatorio)
    print(f"{len(relatorio) - falhas}/{len(relatorio)} fontes baixadas, {mudou} mudaram, "
          f"{n_recortes} recortes, {total / 1e6:.0f} MB em disco -> {lib}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
