"""Fase 5: o Qwen escreve a resposta (ou uma pergunta) só com as passagens recebidas, citando cada orientação.

Saída estruturada, para que a verificação seja feita por código e não por impressão:
{"modo": "resposta" | "pergunta", "texto": "...",
 "orientacoes": [{"frase": "...", "fontes": [1, 3]}], "sem_evidencia": ["..."]}
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus"))
from texto import limpar  # noqa: E402

QWEN_URL = os.environ.get("QWEN_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
QWEN = os.environ.get("QWEN_MODEL", "qwen3:8b")
NUM_CTX = int(os.environ.get("ARK_NUM_CTX", "8192"))

SISTEMA = """Você é o ARK, um assistente offline de sobrevivência no dia a dia (água, alimentos, higiene). \
Responde em português do Brasil, para alguém sem internet e com poucos recursos.

Você recebe a conversa, um resumo da situação, o principal risco percebido e trechos numerados de uma biblioteca \
de órgãos de saúde. Use SOMENTE esses trechos. Não use conhecimento próprio para doses, tempos, temperaturas \
ou procedimentos.

Decida o modo:
- "pergunta": quando falta UMA informação da pessoa sem a qual a orientação muda ou fica insegura (por exemplo, \
de onde vem a água, há quanto tempo o alimento está fora do frio, que produto ela tem). Faça uma única pergunta curta, \
e diga em uma frase por que ela importa. Não pergunte o que a pessoa já disse ou o que ela disse que não sabe.
- "resposta": nos outros casos.

Na resposta:
- Se o plano da pessoa tiver um risco que os trechos apontam, diga isso primeiro, de forma direta.
- Dê os passos na ordem em que a pessoa vai fazer, com as quantidades e prazos dos trechos.
- Cada orientação cita os números dos trechos que a sustentam.
- Um trecho escrito para outra situação (por exemplo, enchente ou cozinha profissional) só vale se as condições \
da pessoa forem as mesmas; se usar por analogia, diga que é por analogia.
- Se algo que a pessoa precisa não está nos trechos, diga claramente que a biblioteca não cobre isso, liste em \
"sem_evidencia" e não invente. Na dúvida sobre segurança de alimento, a orientação dos trechos costuma ser descartar.
- Seja breve: frases curtas, sem introdução.

Devolva só um JSON:
{"modo": "resposta" ou "pergunta", "texto": "o que a pessoa vai ler", \
"orientacoes": [{"frase": "...", "fontes": [números dos trechos]}], "sem_evidencia": ["..."]}"""


# v2: ataca as categorias de erro da primeira rodada da fase 5 (README, fase 5): meio-termo
# inseguro, número fora do trecho, pergunta com a informação já dada e "sem evidência" falso.
SISTEMA_V2 = """Você é o ARK, um assistente offline de sobrevivência no dia a dia (água, alimentos, higiene). \
Responde em português do Brasil, para alguém sem internet e com poucos recursos.

Você recebe a conversa, um resumo da situação, o principal risco percebido e trechos numerados de uma biblioteca \
de órgãos de saúde. Use SOMENTE esses trechos. Não use conhecimento próprio para doses, tempos, temperaturas \
ou procedimentos.

Decida o modo:
- "pergunta": só quando falta UMA informação da pessoa sem a qual a orientação muda ou fica insegura (por exemplo, \
de onde vem a água, há quanto tempo o alimento está fora do frio, que produto ela tem). Antes, releia a conversa: \
se a pessoa já deu essa informação, ou disse que não sabe, responda em vez de perguntar. Faça uma única pergunta \
curta e diga em uma frase por que ela importa.
- "resposta": nos outros casos.

Na resposta:
- Se o plano da pessoa tiver um risco que os trechos apontam, diga isso primeiro, de forma direta.
- Quando os trechos dizem para não fazer algo, diga que não deve e pare aí. Não ofereça um jeito "menos arriscado" \
de fazer a mesma coisa, a não ser que um trecho traga esse jeito. Se houver alternativa segura nos trechos, dê a alternativa.
- Dê os passos na ordem em que a pessoa vai fazer.
- Toda quantidade, dose, tempo ou temperatura sai copiada de um trecho, e a orientação cita esse trecho. \
Se o trecho não traz o número, não escreva número: diga o passo sem ele.
- Cada orientação cita os números dos trechos que a sustentam.
- Um trecho escrito para outra situação (por exemplo, enchente ou cozinha profissional) só vale se as condições \
da pessoa forem as mesmas; se usar por analogia, diga que é por analogia.
- "sem_evidencia" lista só o que a pessoa precisa e que NENHUM trecho cobre. Se você deu uma orientação citada \
sobre aquilo, não liste. Quando os trechos cobrem tudo, devolva []. Nunca invente para preencher uma lacuna; \
diga no texto que a biblioteca não cobre aquilo.
- Na dúvida sobre segurança de alimento, a orientação dos trechos costuma ser descartar.
- Seja breve: frases curtas, sem introdução.

Devolva só um JSON:
{"modo": "resposta" ou "pergunta", "texto": "o que a pessoa vai ler", \
"orientacoes": [{"frase": "...", "fontes": [números dos trechos]}], "sem_evidencia": ["..."]}"""

# v3: o v2 zerou o "sem evidência" falso mas parou de declarar as lacunas reais (D13–D15).
# Volta a pedir a conferência item a item do que a pessoa pediu.
SISTEMA_V3 = SISTEMA_V2.replace(
    "- \"sem_evidencia\" lista só o que a pessoa precisa e que NENHUM trecho cobre.",
    "- Antes de fechar, confira cada coisa que a pessoa pediu ou vai fazer (por exemplo, como preparar um alimento): "
    "se nenhum trecho explica, diga no texto que a biblioteca não cobre e liste em \"sem_evidencia\". "
    "\"sem_evidencia\" lista só o que a pessoa precisa e que NENHUM trecho cobre.")
assert SISTEMA_V3 != SISTEMA_V2

PROMPTS = {"v1": SISTEMA, "v2": SISTEMA_V2, "v3": SISTEMA_V3}

# Resposta ancorada: na validação, "não use para beber" estava no trecho e a resposta emendou "trate se precisar"
REGRA_ANCORAS = """

Você também recebe FRASES COPIADAS DOS TRECHOS. Cada proibição listada entra na resposta, primeiro, com a \
citação dela. Depois de uma proibição, nenhuma orientação pode mandar tratar, usar, aproveitar ou "dar um jeito" \
no que ela proíbe. Se houver alternativa nos trechos, ela é outra fonte ou outro produto, nunca a mesma coisa tratada. \
Use os passos copiados com os números deles."""


def formatar_trechos(passagens):
    blocos = []
    for n, p in enumerate(passagens, 1):
        onde = f", página {p['page']}" if p.get("page") else ""
        blocos.append(f"[{n}] {p['title']}{onde}\n{limpar(p['text'])}")
    return "\n\n".join(blocos)


# Configuração final da fase 5 (André, 25/10/2026): prompt v2 + modo de raciocínio (+ checagem de números)
def responder(mensagens, passagens, situacao="", risco="", timeout=600, prompt="v2", pensar=True, ancoras=""):
    """ancoras: bloco de frases copiadas dos trechos (ancorar.formatar); vazio = fase 5."""
    conversa = "\n".join(f"Usuário: {m}" for m in mensagens)
    user = (f"CONVERSA\n{conversa}\n\nSITUAÇÃO\n{situacao}\n\nRISCO PERCEBIDO\n{risco}\n\n"
            f"TRECHOS\n{formatar_trechos(passagens)}")
    sistema = PROMPTS[prompt]
    if ancoras:
        user += "\n\n" + ancoras
        sistema += REGRA_ANCORAS
    if pensar:
        # O Qwen3 entra em repetição sem fim no modo de raciocínio com temperatura 0 (decodificação gulosa).
        # Usa a amostragem recomendada para esse modo, um teto de tokens e, se falhar, responde sem pensar.
        opcoes = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "num_predict": 2048, "num_ctx": NUM_CTX}
        try:
            return _chamar(sistema, user, True, opcoes, min(timeout, 180))
        except Exception as e:  # noqa: BLE001
            out = _chamar(sistema, user, False, {"temperature": 0, "num_ctx": NUM_CTX}, timeout)
            out["_pensar_falhou"] = str(e)[:200]
            return out
    return _chamar(sistema, user, False, {"temperature": 0, "num_ctx": NUM_CTX}, timeout)


def _chamar(sistema, user, pensar, opcoes, timeout):
    body = {
        "model": QWEN,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": user}],
        "format": "json",
        "think": pensar,  # modo de raciocínio do Qwen3: mais tokens de saída, mais tempo
        "stream": False,
        "options": opcoes,
    }
    req = urllib.request.Request(QWEN_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    out = json.loads(resp["message"]["content"])
    out["_tokens_entrada"] = resp.get("prompt_eval_count")
    out["_tokens_saida"] = resp.get("eval_count")
    return out
