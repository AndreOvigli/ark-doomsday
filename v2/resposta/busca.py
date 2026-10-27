"""Busca da v2 na configuração escolhida nas fases 2 a 4.

conversa -> Qwen decompõe (prompt v3) -> para cada consulta: bge-m3 top-20 -> reranker fp16
(título + texto) -> listas intercaladas -> k passagens distintas.
"""
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2 / "corpus"), str(V2 / "conversa")]
from dense import Dense  # noqa: E402
from search import load  # noqa: E402


# Consulta fixa: na validação, a busca procurava "como tratar" e não "quando não usar"
CONTRA = "quando não usar: não serve para consumo, deve ser descartado, ferver ou clorar não resolve"


def intercalar(listas):
    """Round-robin: 1º de cada consulta, depois 2º de cada... sem repetir passagem."""
    out, seen = [], set()
    for pos in range(max((len(l) for l in listas), default=0)):
        for l in listas:
            if pos < len(l) and l[pos] not in seen:
                seen.add(l[pos])
                out.append(l[pos])
    return out


class Busca:
    def __init__(self, modelo="bge-m3", pool=20):
        self.rows = load()
        self.por_id = {r["id"]: r for r in self.rows}
        self.dense = Dense(modelo, self.rows)
        self.pool = pool
        self._rr = None

    @property
    def reranker(self):
        if self._rr is None:
            from rerank import Reranker
            self._rr = Reranker(fp16=True)
        return self._rr

    def ordenar(self, consulta):
        """IDs de passagem em ordem, com o reranker julgando contra esta consulta."""
        s = self.dense.scores(consulta)
        cand = sorted(range(len(self.rows)), key=lambda i: -s[i])[: self.pool]
        rs = self.reranker.scores(consulta, [self.rows[i]["title"] + "\n" + self.rows[i]["text"] for i in cand])
        return [self.rows[i]["id"] for _, i in sorted(zip(rs, cand), key=lambda x: -x[0])]

    def recuperar(self, mensagens, consultas, k=8, contra=False):
        """contra: soma, na frente, uma consulta fixa de contraindicação (quando não usar)."""
        conversa = " ".join(mensagens)
        consultas = ([CONTRA] if contra else []) + list(consultas)
        listas = [self.ordenar(conversa + "\n" + c) for c in consultas] or [self.ordenar(conversa)]
        return intercalar(listas)[:k]
