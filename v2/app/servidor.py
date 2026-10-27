"""ARK v2 local: tela do terminal verde + pipeline fechado na fase 5, sem internet.

conversa -> Qwen decompõe (prompt v3) -> bge-m3 top-20 + reranker fp16 por consulta -> 8 trechos
-> Qwen responde (prompt v2 + raciocínio) -> checagem de números por código.

Só biblioteca padrão do Python além do que a avaliação já usa. Serve em 127.0.0.1 (porta 8090,
ou ARK_PORTA), separado da v1 (Open WebUI em 8080). Modelos:
  QWEN_URL   Ollama com o qwen3:8b (só leitura)
  OLLAMA_URL Ollama com o bge-m3
O reranker vem do cache local do Hugging Face; o modo offline é ligado aqui, antes de importar.

Uso: python v2/app/servidor.py
"""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

APP = Path(__file__).resolve().parent
V2 = APP.parent
RAIZ = V2.parent
sys.path[:0] = [str(V2 / "resposta"), str(V2 / "corpus"), str(V2 / "conversa")]
from busca import Busca  # noqa: E402
from checagem import corrigir  # noqa: E402
from decompor import decompor  # noqa: E402
from responder import NUM_CTX, QWEN, QWEN_URL, responder  # noqa: E402
from texto import limpar  # noqa: E402

PORTA = int(os.environ.get("ARK_PORTA", "8090"))
K = 8
TRAVA = threading.Lock()  # uma conversa por vez: os modelos dividem 8 GB de GPU
LOG = APP / "conversas.jsonl"  # registro local do test drive (fora do Git)


def fonte_css():
    """VT323 (SIL OFL 1.1, The VT323 Project Authors) só com caracteres latinos: 16 KB em vez de 192 KB."""
    return "@font-face{font-family:ArkVT;src:url('/ark-vt.woff2') format('woff2');font-display:swap}"


def descarregar(url, modelo):
    """Tira o bge-m3 da GPU depois da busca, para o Qwen caber inteiro (como na avaliação)."""
    body = json.dumps({"model": modelo, "input": [], "keep_alive": 0}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, body, {"Content-Type": "application/json"}), timeout=60)
    except Exception:  # noqa: BLE001
        pass


def aquecer_qwen():
    """Carrega o Qwen com o mesmo num_ctx da resposta, para a primeira pergunta não pagar a carga."""
    body = {"model": QWEN, "messages": [{"role": "user", "content": "ok"}], "stream": False, "think": False,
            "options": {"num_ctx": NUM_CTX, "num_predict": 1}}
    urllib.request.urlopen(urllib.request.Request(QWEN_URL, json.dumps(body).encode(),
                                                  {"Content-Type": "application/json"}), timeout=300).read()


class ARK:
    def __init__(self):
        t0 = time.time()
        self.busca = Busca()
        self.busca.reranker  # carrega já, para a primeira pergunta não esperar
        self.por_id = self.busca.por_id
        self.embed_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/embed"
        self.docs = {}
        for r in self.busca.rows:
            d = self.docs.setdefault(r["doc"], {"doc": r["doc"], "titulo": r["title"], "trechos": 0})
            d["trechos"] += 1
        print(f"busca pronta em {time.time() - t0:.0f} s ({len(self.busca.rows)} trechos)", flush=True)
        try:
            aquecer_qwen()
            print("Qwen carregado", flush=True)
        except Exception as e:  # noqa: BLE001
            print("aviso: não consegui carregar o Qwen agora:", e, flush=True)

    def conversar(self, mensagens):
        with TRAVA:
            t = {}
            t0 = time.time()
            d = decompor(mensagens, "v3", num_ctx=NUM_CTX)
            t["decompor"] = round(time.time() - t0, 1)
            t0 = time.time()
            ids = self.busca.recuperar(mensagens, d["consultas"], K)
            descarregar(self.embed_url, self.busca.dense.modelo)
            t["busca"] = round(time.time() - t0, 1)
            t0 = time.time()
            passagens = [self.por_id[i] for i in ids]
            r = responder(mensagens, passagens, d.get("situacao", ""), d.get("risco", ""))
            r = corrigir(r, passagens)
            t["resposta"] = round(time.time() - t0, 1)
        fontes = [{"n": n, "id": p["id"], "titulo": p["title"], "pagina": p.get("page")}
                  for n, p in enumerate(passagens, 1)]
        out = {"modo": r.get("modo"), "texto": r.get("texto", ""), "orientacoes": r.get("orientacoes") or [],
               "sem_evidencia": [s for s in r.get("sem_evidencia") or [] if not str(s).startswith("número sem fonte")],
               "removidas": [c["frase"] for c in r.get("_checagem", [])], "fontes": fontes,
               "tempos": t, "pensou": "_pensar_falhou" not in r, "consultas": d["consultas"]}
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"quando": time.strftime("%Y-%m-%d %H:%M:%S"), "mensagens": mensagens,
                                    **out, "_tokens_saida": r.get("_tokens_saida")}, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return out

    def trecho(self, pid):
        p = self.por_id.get(pid)
        if not p:
            return None
        return {"id": pid, "titulo": p["title"], "pagina": p.get("page"), "texto": limpar(p["text"])}


ark = None


class Handler(BaseHTTPRequestHandler):
    def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8"):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._enviar(200, (APP / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif u.path == "/fonte.css":
            self._enviar(200, FONTE.encode(), "text/css; charset=utf-8")
        elif u.path == "/ark-vt.woff2":
            self._enviar(200, (APP / "ark-vt.woff2").read_bytes(), "font/woff2")
        elif u.path == "/api/biblioteca":
            self._enviar(200, sorted(ark.docs.values(), key=lambda d: d["doc"]))
        elif u.path == "/api/trecho":
            t = ark.trecho(parse_qs(u.query).get("id", [""])[0])
            self._enviar(200 if t else 404, t or {"erro": "trecho não encontrado"})
        elif u.path == "/api/estado":
            self._enviar(200, {"modelo": QWEN, "trechos": len(ark.busca.rows), "k": K, "ocupado": TRAVA.locked()})
        else:
            self._enviar(404, {"erro": "não encontrado"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/conversa":
            return self._enviar(404, {"erro": "não encontrado"})
        try:
            corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            mensagens = [m.strip() for m in corpo.get("mensagens", []) if isinstance(m, str) and m.strip()]
            if not mensagens:
                return self._enviar(400, {"erro": "mensagem vazia"})
            self._enviar(200, ark.conversar(mensagens[-6:]))
        except Exception as e:  # noqa: BLE001
            self._enviar(500, {"erro": f"{type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        if "/api/conversa" in (args[0] if args else ""):
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))


FONTE = fonte_css()

if __name__ == "__main__":
    ark = ARK()
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"ARK v2 pronta em http://127.0.0.1:{PORTA}", flush=True)
    srv.serve_forever()
