"""Reranker (cross-encoder): relê os candidatos da primeira busca e reordena.

Requer sentence-transformers e torch (ver README da v2). Roda na GPU se houver.
"""
from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, modelo="BAAI/bge-reranker-v2-m3", max_length=1024, fp16=False):
        kw = {}
        if fp16:
            import torch
            kw["model_kwargs"] = {"torch_dtype": torch.float16}
        self.model = CrossEncoder(modelo, max_length=max_length, **kw)

    def scores(self, query, textos):
        return [float(s) for s in self.model.predict([(query, t) for t in textos], batch_size=8)]
