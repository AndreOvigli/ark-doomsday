"""Fase 4: transforma a conversa em resumo da situação + consultas de busca, uma por necessidade.

Usa o Qwen3 do Ollama (QWEN_URL, padrão http://127.0.0.1:11434) só para leitura do modelo:
nada é gravado no Ollama. O resultado de cada conversa fica em cache em JSON para inspeção.
"""
import json
import os
import urllib.request

QWEN_URL = os.environ.get("QWEN_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
QWEN = os.environ.get("QWEN_MODEL", "qwen3:8b")

SISTEMA_V1 = """Você prepara buscas numa biblioteca de orientações práticas de sobrevivência no dia a dia \
(água, alimentos, higiene), escrita em português por órgãos de saúde.

Leia a conversa e devolva só um JSON neste formato:
{"situacao": "...", "consultas": ["...", "..."]}

- "situacao": 1 ou 2 frases com o que a pessoa quer, o que ela tem e o que falta (recursos, restrições, mudanças ao longo da conversa). Se a pessoa corrigiu algo, vale a versão mais recente.
- "consultas": de 1 a 4 buscas curtas. Cada uma cobre UMA necessidade distinta, inclusive as de segurança que a pessoa não pediu mas precisa saber para agir (por exemplo, como guardar, por quanto tempo, quando descartar).
- Escreva as consultas com as palavras que um manual usaria, não com as da pessoa.
- Não responda à pergunta e não invente fatos."""


# v2 (25/10/2026), corrigindo as categorias vistas nas decomposições da v1:
# preenchia sempre 4 vagas com moldes copiados do exemplo; perdia o risco central;
# escrevia o plano inseguro da pessoa como consulta ("cozinhar com água de poço").
SISTEMA_V2 = """Você prepara buscas numa biblioteca de orientações práticas de sobrevivência no dia a dia \
(água, alimentos, higiene), escrita em português por órgãos de saúde.

Leia a conversa e devolva só um JSON neste formato:
{"situacao": "...", "risco": "...", "consultas": ["..."]}

- "situacao": 1 ou 2 frases com o que a pessoa quer, o que ela tem e o que falta. Se a pessoa corrigiu algo, vale a versão mais recente.
- "risco": o que pode dar errado ou ser perigoso no que a pessoa pretende fazer, em uma frase.
- "consultas": uma busca por necessidade distinta, entre 1 e 4. Use só quantas a conversa pede; não complete vagas.
  - A primeira consulta é sobre o risco.
  - Se a pessoa vai usar um produto ou método, inclua uma consulta sobre como aplicá-lo corretamente.
  - Descreva o assunto, não o plano da pessoa: se o plano pode estar errado, a consulta não deve pressupor que ele está certo.
  - Use as palavras que um manual de saúde usaria, não as da pessoa.
- Não responda à pergunta e não invente fatos."""

# v3: a v2 passou do ponto. Fundia itens distintos numa consulta só ("arroz, feijão e farinha"
# virou "grãos"), gerava quase sempre 1 consulta na primeira mensagem e ainda pressupunha o
# plano inseguro na redação.
SISTEMA_V3 = """Você prepara buscas numa biblioteca de orientações práticas de sobrevivência no dia a dia \
(água, alimentos, higiene), escrita em português por órgãos de saúde.

Leia a conversa e devolva só um JSON neste formato:
{"situacao": "...", "risco": "...", "consultas": ["..."]}

- "situacao": 1 ou 2 frases com o que a pessoa quer, o que ela tem e o que falta. Se a pessoa corrigiu algo, vale a versão mais recente.
- "risco": o que pode dar errado ou ser perigoso no que a pessoa pretende fazer, em uma frase.
- "consultas": entre 2 e 4 buscas.
  - A primeira consulta é sobre o risco.
  - Depois, uma consulta para cada item, alimento, recurso ou tarefa distinto que a pessoa citou. Não junte itens diferentes numa consulta só.
  - Se a pessoa vai usar um produto ou método, inclua uma consulta sobre como aplicá-lo corretamente.
  - Escreva cada consulta como um tema neutro de manual ("água para preparar alimentos", "uso de carvão e ventilação"), nunca como o plano da pessoa ("como fazer X do jeito que ela quer"), porque o plano pode estar errado.
  - Se houver mais de 4 temas, junte os de menor risco.
- Não responda à pergunta e não invente fatos."""

# v4: na validação, a consulta de risco da v3 saía genérica ("água contaminada e riscos à saúde")
# e não trazia o trecho que diz "essa água não se trata" (piscina, cheiro de químico). A v4 pede
# que a primeira consulta seja sobre quando NÃO usar a coisa concreta que a pessoa citou.
SISTEMA_V4 = SISTEMA_V3.replace(
    "  - A primeira consulta é sobre o risco.\n",
    "  - A primeira consulta é sobre quando NÃO usar: em que casos a água, o alimento, o produto ou o método "
    "que a pessoa citou não serve, deve ser descartado ou o tratamento caseiro não resolve. Nomeie a coisa "
    "concreta e o motivo provável (\"água com produtos químicos: quando ferver ou clorar não resolve\").\n")
assert SISTEMA_V4 != SISTEMA_V3

PROMPTS = {"v1": SISTEMA_V1, "v2": SISTEMA_V2, "v3": SISTEMA_V3, "v4": SISTEMA_V4}


def decompor(mensagens, prompt="v2", timeout=180, num_ctx=None):
    conversa = "\n".join(f"Usuário: {m}" for m in mensagens)
    body = {
        "model": QWEN,
        "messages": [{"role": "system", "content": PROMPTS[prompt]}, {"role": "user", "content": conversa}],
        "format": "json",
        "think": False,
        "stream": False,
        # num_ctx igual ao da resposta evita o Ollama recarregar o Qwen entre as duas chamadas (app)
        "options": {"temperature": 0, **({"num_ctx": num_ctx} if num_ctx else {})},
    }
    req = urllib.request.Request(QWEN_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = json.loads(r.read())["message"]["content"]
    out = json.loads(content)
    consultas = [c for c in out.get("consultas", []) if isinstance(c, str) and c.strip()][:4]
    return {"situacao": out.get("situacao", ""), "risco": out.get("risco", ""), "consultas": consultas}
