"""Checagem por código: todo número de uma orientação precisa estar escrito num trecho citado.

Pega a categoria "número inventado com citação válida" (ex.: proporção do arroz citando a
página do hipoclorito). Números por extenso viram dígitos dos dois lados, então "cinco
minutos" na resposta casa com "5 minutos" no trecho.
"""
import re
import unicodedata

EXTENSO = {
    "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5",
    "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10", "doze": "12", "quinze": "15",
    "vinte": "20", "trinta": "30", "quarenta": "40", "cinquenta": "50", "cem": "100",
    "duzentos": "200", "quinhentos": "500", "mil": "1000", "meia": "0.5",
}
NUM = re.compile(r"\d+(?:[.,]\d+)?(?:/\d+)?")
# unidade logo depois do número: "15 minutos" só é sustentado por "15 minutos", não por um "15" qualquer
UNIDADE = {"minuto": "min", "minutos": "min", "min": "min", "hora": "h", "horas": "h", "h": "h",
           "dia": "dia", "dias": "dia", "litro": "l", "litros": "l", "l": "l", "ml": "ml", "g": "g",
           "gramas": "g", "kg": "kg", "gota": "gota", "gotas": "gota", "colher": "colher",
           "colheres": "colher", "%": "%", "ppm": "ppm", "graus": "grau", "c": "grau"}
TOKEN = re.compile(r"\d+(?:[.,]\d+)?(?:/\d+)?|[a-z]+|%")


def _norm(texto):
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def numeros(texto):
    """Conjunto de números do texto, com a unidade quando houver ("15 minutos" -> "15 min").

    Normaliza "2,5" -> "2.5", "2,0" -> "2" e "duas" -> "2". "um"/"uma" por extenso é quase
    sempre artigo, e "meio" quase sempre adjetivo ("meio aberto"), então não contam.
    """
    toks = TOKEN.findall(_norm(texto))
    achados = set()
    for i, tk in enumerate(toks):
        if tk[0].isdigit():
            n = tk.replace(",", ".")
            n = n[:-2] if n.endswith(".0") else n
        elif tk in EXTENSO and tk not in ("um", "uma"):
            n = EXTENSO[tk]
        else:
            continue
        prox = toks[i + 1] if i + 1 < len(toks) else ""
        achados.add(f"{n} {UNIDADE[prox]}" if prox in UNIDADE else n)
    return achados


def sem_suporte(orientacoes, passagens):
    """Lista (frase, números) das orientações com número ausente de todos os trechos citados.

    orientacoes: [{frase, fontes}] como o Qwen devolve; passagens: os dicts entregues, na ordem
    das fontes (fonte 1 = passagens[0]).
    """
    problemas = []
    for o in orientacoes or []:
        nums = numeros(o.get("frase", ""))
        if not nums:
            continue
        citados = [passagens[f - 1] for f in o.get("fontes", []) or []
                   if isinstance(f, int) and 1 <= f <= len(passagens)]
        base = set().union(*(numeros(p.get("title", "") + "\n" + p.get("text", "")) for p in citados)) if citados else set()
        faltam = sorted(nums - base)
        if faltam:
            problemas.append((o.get("frase", ""), faltam))
    return problemas


def corrigir(resposta, passagens):
    """Remove as orientações com número sem suporte e as declara em sem_evidencia.

    No ARK, dose ou tempo sem fonte é pior que lacuna declarada. Não tenta re-citar outro
    trecho: número pequeno ("2", "15") aparece por coincidência em muito trecho.
    Devolve a resposta corrigida, com as frases removidas em _checagem.
    """
    if resposta.get("modo") != "resposta":
        return resposta
    ruins = sem_suporte(resposta.get("orientacoes"), passagens)
    if not ruins:
        return dict(resposta, _checagem=[])
    frases = {f for f, _ in ruins}
    return dict(resposta,
                orientacoes=[o for o in resposta.get("orientacoes") or [] if o.get("frase", "") not in frases],
                sem_evidencia=list(resposta.get("sem_evidencia") or []) + [f"número sem fonte: {f}" for f in frases],
                _checagem=[{"frase": f, "numeros": n} for f, n in ruins])
