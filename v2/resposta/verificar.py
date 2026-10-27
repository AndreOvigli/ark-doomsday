"""Verificação por frase: o Qwen confere cada orientação contra os trechos que ela cita.

O juiz geral (eval/answer_eval.py) lê a resposta inteira e erra muito. Aqui a tarefa é menor:
uma frase, o plano da pessoa e só os trechos citados. Pega a categoria "proíbe e depois libera"
(D24: "não use na garagem" seguido de "mantenha o portão aberto", citando o CDC, que proíbe
garagem mesmo com a porta aberta) e a frase pendurada numa fonte que não diz aquilo.

Vereditos: "sustenta", "contradiz" (o trecho diz o contrário, ou proíbe o que a frase permite
nas condições da pessoa) ou "nao_diz" (o trecho não trata disso).
"""
import json
import urllib.request

from responder import QWEN, QWEN_URL, NUM_CTX
from texto import limpar

SISTEMA = """Você confere uma orientação de um assistente de sobrevivência contra os trechos que ela cita. \
Leia a conversa para saber as condições da pessoa. Responda:
- "contradiz": algum trecho diz o contrário da orientação, ou proíbe o que a orientação permite ou sugere \
nas condições da pessoa (inclusive um jeito "menos arriscado" de fazer algo que o trecho proíbe);
- "sustenta": os trechos dizem o que a orientação diz, nas condições da pessoa;
- "nao_diz": os trechos não tratam do que a orientação diz.
Devolva só JSON: {"veredito": "sustenta" | "contradiz" | "nao_diz", "motivo": "uma frase"}"""


# v2: a v1 confundia polaridade (marcava "contradiz" quando frase e trecho proibiam a mesma coisa)
# e quase nunca dizia "nao_diz". Troca a escolha entre três rótulos por duas perguntas de sim ou não.
SISTEMA_V2 = """Você confere uma orientação de um assistente de sobrevivência contra os trechos que ela cita. \
Leia a conversa para saber as condições da pessoa. Responda duas perguntas, cada uma com true ou false:

1. "permite_proibido": a orientação manda, permite ou sugere fazer algo que um trecho manda NÃO fazer, \
nas condições da pessoa? Isso inclui oferecer um jeito "menos arriscado" de fazer o que o trecho proíbe. \
Se a orientação e o trecho proíbem a mesma coisa, a resposta é false.
Exemplo: trecho "não beba água sem tratar". Orientação "não beba a água do rio sem tratar": false. \
Orientação "pode beber a água do rio se ela parecer limpa": true.

2. "fora_do_trecho": a orientação traz uma quantidade, tempo, temperatura ou passo que NÃO está escrito \
em nenhum dos trechos citados? Dizer com outras palavras o que o trecho diz não conta.
Exemplo: trecho "ferva por 5 minutos". Orientação "deixe ferver por 5 minutos": false. \
Orientação "cozinhe por 20 minutos": true.

Devolva só JSON: {"permite_proibido": true ou false, "fora_do_trecho": true ou false, "motivo": "uma frase"}"""


def verificar_frase(mensagens, frase, citados, timeout=300, versao="v1"):
    conversa = "\n".join(f"Usuário: {m}" for m in mensagens)
    trechos = "\n\n".join(f"[{i}] {p['title']}\n{limpar(p['text'])}" for i, p in citados)
    user = f"CONVERSA\n{conversa}\n\nORIENTAÇÃO\n{frase}\n\nTRECHOS CITADOS\n{trechos or '(nenhum)'}"
    body = {"model": QWEN, "messages": [{"role": "system", "content": SISTEMA if versao == "v1" else SISTEMA_V2},
                                        {"role": "user", "content": user}],
            "format": "json", "think": False, "stream": False,
            "options": {"temperature": 0, "num_ctx": NUM_CTX}}  # mesmo contexto da resposta: o Ollama não recarrega
    req = urllib.request.Request(QWEN_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(json.loads(r.read())["message"]["content"])
    if versao != "v1":
        v = ("contradiz" if out.get("permite_proibido") is True else
             "nao_diz" if out.get("fora_do_trecho") is True else "sustenta")
        return {"veredito": v, "motivo": out.get("motivo", "")}
    v = out.get("veredito")
    return {"veredito": v if v in ("sustenta", "contradiz", "nao_diz") else "nao_diz", "motivo": out.get("motivo", "")}


def verificar(mensagens, resposta, passagens, versao="v1"):
    """Lista de vereditos, um por orientação, na mesma ordem."""
    vereditos = []
    for o in resposta.get("orientacoes") or []:
        citados = [(f, passagens[f - 1]) for f in o.get("fontes", []) or []
                   if isinstance(f, int) and 1 <= f <= len(passagens)]
        vereditos.append(dict(verificar_frase(mensagens, o.get("frase", ""), citados, versao=versao), frase=o.get("frase", "")))
    return vereditos


def aplicar(resposta, vereditos, estrito=False):
    """Remove as orientações que contradizem a fonte (e as "nao_diz", se estrito)."""
    if resposta.get("modo") != "resposta" or not vereditos:
        return resposta
    cortar = {"contradiz", "nao_diz"} if estrito else {"contradiz"}
    fora = {v["frase"] for v in vereditos if v["veredito"] in cortar}
    if not fora:
        return resposta
    return dict(resposta, orientacoes=[o for o in resposta.get("orientacoes") or [] if o.get("frase", "") not in fora],
                _verificacao_removidas=sorted(fora))
