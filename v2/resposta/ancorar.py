"""Resposta ancorada, etapa 1: copiar dos trechos o que proíbe e o que manda fazer.

Na validação, o Qwen tinha "não use para beber ou cozinhar" no trecho (V10) e mesmo assim
escreveu "trate se precisar". Aqui ele só copia: as frases que proíbem, mandam descartar ou
dizem que algo não resolve, e as frases com os passos e quantidades. O código confere que cada
frase está mesmo escrita no trecho (cópia, não paráfrase) e descarta o resto. As frases
conferidas entram na resposta como obrigatórias (responder.py, ancoras=...).
"""
import json
import re
import unicodedata
import urllib.request

from responder import NUM_CTX, QWEN, QWEN_URL, formatar_trechos

SISTEMA = """Você copia frases de trechos de uma biblioteca de saúde. Não responda à pessoa.

Leia a conversa e os trechos numerados. Copie, palavra por palavra, sem mudar nada:
- "proibicoes": as frases que dizem para NÃO usar, NÃO fazer, descartar, ou que dizem que algo não serve \
ou não resolve, e que valem para a água, o alimento, o produto ou o método que a pessoa tem ou pretende usar;
- "passos": as frases com os passos, quantidades e tempos que respondem ao que a pessoa perguntou.
Cada frase vem com o número do trecho. No máximo 4 proibições e 6 passos. Se não houver, devolva lista vazia.

Devolva só JSON: {"proibicoes": [{"trecho": n, "frase": "..."}], "passos": [{"trecho": n, "frase": "..."}]}"""


def _norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9%,.]+", " ", t).strip(" .")


def literal(frase, texto):
    """A frase está escrita no trecho? Compara sem acento, caixa, pontuação e espaços."""
    f = _norm(frase)
    return len(f) >= 15 and f in _norm(texto)


def extrair(mensagens, passagens, timeout=180):
    conversa = "\n".join(f"Usuário: {m}" for m in mensagens)
    user = f"CONVERSA\n{conversa}\n\nTRECHOS\n{formatar_trechos(passagens)}"
    body = {"model": QWEN, "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": user}],
            "format": "json", "think": False, "stream": False,
            "options": {"temperature": 0, "num_ctx": NUM_CTX}}
    req = urllib.request.Request(QWEN_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(json.loads(r.read())["message"]["content"])
    from texto import limpar
    res = {"proibicoes": [], "passos": [], "_descartadas": 0}
    for tipo in ("proibicoes", "passos"):
        for item in out.get(tipo) or []:
            n, frase = item.get("trecho"), str(item.get("frase", "")).strip()
            if isinstance(n, int) and 1 <= n <= len(passagens) and literal(frase, limpar(passagens[n - 1]["text"])):
                res[tipo].append({"trecho": n, "frase": frase})
            else:
                res["_descartadas"] += 1
    return res


def formatar(ancoras):
    """Bloco que vai para o prompt da resposta."""
    if not ancoras or not (ancoras["proibicoes"] or ancoras["passos"]):
        return ""
    linhas = ["FRASES COPIADAS DOS TRECHOS"]
    if ancoras["proibicoes"]:
        linhas.append("Proibições que valem para a pessoa (obrigatórias):")
        linhas += [f"- [{a['trecho']}] {a['frase']}" for a in ancoras["proibicoes"]]
    if ancoras["passos"]:
        linhas.append("Passos e quantidades:")
        linhas += [f"- [{a['trecho']}] {a['frase']}" for a in ancoras["passos"]]
    return "\n".join(linhas)
