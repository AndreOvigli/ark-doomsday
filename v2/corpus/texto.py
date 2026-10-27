"""Texto de busca: o que o modelo lê para achar e ordenar, sem a ficha de catalogação.

Os recortes editoriais começam com metadados (FONTE, URL, datas de captura...).
Eles servem para citar, mas na busca competem com o conteúdo: o reranker lê
"FONTE: Ministério da Saúde..." como se fosse resposta. Aqui saem só os campos
de catalogação; conteúdo, tradução, original e limites ficam.
"""
import re

_META = re.compile(
    r"^\s*(fonte( oficial)?|url( oficial)?|p[áa]gina f[íi]sica|data[^:]{0,30}|edi[çc][ãa]o|captura|consulta|origem)\s*:",
    re.I,
)
_SO_URL = re.compile(r"^\s*https?://\S+\s*$")
_DATA_SOLTA = re.compile(r"^\s*data de (edi[çc][ãa]o|cria[çc][ãa]o|publica[çc][ãa]o)\b", re.I)
# Rótulos editoriais de recorte: o rótulo sai, o conteúdo depois dele fica.
_ROTULO = re.compile(
    r"^\s*(contexto editorial|escopo|se[çc][ãa]o|limita[çc][õo]es( editoriais)?|limites( editoriais)?"
    r"|orienta[çc][ãa]o em portugu[êe]s e limites)\s*:\s*",
    re.I,
)
# Linhas que só anunciam o bloco seguinte ("ORIGINAL EM INGLÊS:", "TRECHO CONFERIDO VISUALMENTE; ...").
_ANUNCIO = re.compile(
    r"^\s*(trecho(s)? (original|originais|conferido)|texto original|original em ingl[êe]s|tradu[çc][ãa]o"
    r"|evid[êe]ncia original|recorte de limites)\b[^\n]*$",
    re.I,
)


def limpar(texto):
    linhas = []
    for l in texto.splitlines():
        if _META.match(l) or _SO_URL.match(l) or _DATA_SOLTA.match(l) or _ANUNCIO.match(l):
            continue
        linhas.append(_ROTULO.sub("", l))
    return "\n".join(linhas).strip() or texto
