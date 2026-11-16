# -*- coding: utf-8 -*-
"""Sonnet 5 / Opus 5: raciocínio sob controle (python testar_claude_raciocinio.py).

16/11, ele: "a API da Anthropic está gastando, fazendo uns laudos tudo quebrado ... o Sonnet 5
demora 20, 30 segundos para um laudo". Auditoria do nuvem.log: em novembro, 73 chamadas do
Sonnet 5 — 40 VAZIAS e 15 CORTADAS, US$ 3,72 pagos por nada, mediana de 40 s. O Sonnet 5 e o
Opus 5 pensam sozinhos (esforço "high") quando o pedido não fala de raciocínio, e o pensamento
entra no max_tokens: os 4.000 tokens acabavam antes de o laudo ser escrito.

Este teste (sem internet, respostas simuladas) exige:
  1. laudo/formatar no Sonnet 5: "thinking": {"type": "disabled"}
  2. botão (Revisar, reescrever, 2ª IA) e imagem: adaptativo com esforço "low" e teto de
     8.000 (cabe pensar e escrever); ditado cru: sem raciocínio
  3. Haiku 4.5 (não pensa sozinho): nenhum campo novo no pedido
  4. a linha da tabela ("raciocinio") e o config "claude_raciocinio" mandam
  5. resposta vazia ou cortada depois de pensar: refaz UMA vez sem raciocínio, devolve o laudo,
     e o log guarda as duas (a 1ª como "vazia_pensando", com o custo)
  6. API que recusa o campo (400): refaz sem ele
  7. o log diz o raciocínio usado (rac=none / rac=low) e continua sem conteúdo do laudo"""
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import nuvem  # noqa: E402

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp
nuvem.CONFIG = os.path.join(tmp, "config.json")
nuvem.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
os.environ["ANTHROPIC_API_KEY"] = "teste-anthropic"

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


PEDIDOS = []
FILA = []


def _falso(req, timeout=None, context=None):
    corpo = json.loads(req.data.decode("utf-8"))
    PEDIDOS.append(corpo)
    r = FILA.pop(0)
    if isinstance(r, Exception):
        raise r
    return _R(json.dumps(r).encode("utf-8"))


def _resp(texto, fim="end_turn", out=300, pensou=False):
    content = ([{"type": "thinking", "thinking": "", "signature": "x"}] if pensou else []) + \
              ([{"type": "text", "text": texto}] if texto else [])
    return {"content": content, "stop_reason": fim,
            "usage": {"input_tokens": 1000, "output_tokens": out}}


urllib.request.urlopen = _falso
BASE = {"ativa": True, "provedor": "anthropic", "modelo": "claude-sonnet-5", "timeout_s": 40,
        "max_tokens": 1500, "limite_mes_usd": 0, "marcar_saida": False}
PEDIDO = ("LAUDO NA TELA:\nTOMOGRAFIA DO TÓRAX\nTÉCNICA: aquisição volumétrica.\nANÁLISE:\n"
          "Parênquima pulmonar sem opacidades.\nPleura livre.\nMediastino sem linfonodomegalias.")
LAUDO_OK = "TOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênquima pulmonar sem opacidades."


def chamar(c, **kw):
    del PEDIDOS[:]
    return nuvem.chamar(PEDIDO, dict(BASE, **c), modo="laudo", marcar=False, max_tokens=4000, **kw)


# 1. laudo sem raciocínio
FILA[:] = [_resp(LAUDO_OK)]
t, o = chamar({})
pd = PEDIDOS[0]
confere("laudo no Sonnet 5: thinking desligado", pd.get("thinking") == {"type": "disabled"}
        and "output_config" not in pd, json.dumps({k: pd.get(k) for k in ("thinking", "output_config")}))
confere("laudo no Sonnet 5: teto continua 4.000", pd.get("max_tokens") == 4000, str(pd.get("max_tokens")))
confere("laudo volta", o == "nuvem" and t == LAUDO_OK, o)

# 2. botão: raciocínio baixo com folga
FILA[:] = [_resp(LAUDO_OK, pensou=True, out=1500)]
t, o = chamar({}, botao="revisar", analise=True)
pd = PEDIDOS[0]
confere("botão Revisar: adaptativo com esforço low", pd.get("thinking") == {"type": "adaptive"}
        and pd.get("output_config") == {"effort": "low"}, json.dumps(pd.get("output_config")))
confere("botão Revisar: teto 8.000 (pensar + escrever)", pd.get("max_tokens") == 8000, str(pd.get("max_tokens")))
FILA[:] = [_resp(LAUDO_OK)]
chamar({"modelo": "claude-opus-5"}, analise=True)
confere("ditado cru (botão de raciocínio) no Opus 5: sem raciocínio",
        PEDIDOS[0].get("thinking") == {"type": "disabled"})
FILA[:] = [_resp(LAUDO_OK, pensou=True)]
chamar({"modelo": "claude-opus-5"}, botao="revisar_2", analise=True)
confere("2ª IA da revisão no Opus 5: esforço low", PEDIDOS[0].get("output_config") == {"effort": "low"})

# 3. Haiku 4.5: nada novo
FILA[:] = [_resp(LAUDO_OK)]
chamar({"modelo": "claude-haiku-4-5-20251001"})
confere("Haiku 4.5: sem thinking nem output_config",
        "thinking" not in PEDIDOS[0] and "output_config" not in PEDIDOS[0])
FILA[:] = [_resp(LAUDO_OK)]
chamar({"modelo": "claude-sonnet-5-5"})
confere("Sonnet 5.5 também entra na regra", PEDIDOS[0].get("thinking") == {"type": "disabled"})

# 4. quem manda por cima
FILA[:] = [_resp(LAUDO_OK, pensou=True)]
chamar({"ia_por_exame": {"tc": {"provedor": "anthropic", "modelo": "claude-sonnet-5", "raciocinio": "medium"}}})
confere("linha da tabela com raciocinio=medium manda",
        PEDIDOS[0].get("output_config") == {"effort": "medium"}, json.dumps(PEDIDOS[0].get("output_config")))
FILA[:] = [_resp(LAUDO_OK, pensou=True)]
chamar({"claude_raciocinio": {"laudo": "low"}})
confere("config claude_raciocinio.laudo=low manda", PEDIDOS[0].get("output_config") == {"effort": "low"})

# 5. pensou e não escreveu: refaz sem pensar
open(nuvem.LOG, "w").close()
FILA[:] = [_resp("", fim="max_tokens", out=8000, pensou=True), _resp(LAUDO_OK)]
t, o = chamar({}, botao="revisar", analise=True)
confere("vazia depois de pensar: refaz e devolve o laudo", o == "nuvem" and t == LAUDO_OK, o)
confere("a 2ª vai sem raciocínio", len(PEDIDOS) == 2 and PEDIDOS[1].get("thinking") == {"type": "disabled"})
log = open(nuvem.LOG, encoding="utf-8").read()
confere("log: 1ª como vazia_pensando com custo, 2ª ok com rac=none",
        "\tvazia_pensando\t" in log and "rac=low" in log and "\tok\t" in log and "rac=none" in log, log[:300])
u = nuvem.ultima_desta_chamada() or {}
confere("recibo soma as duas chamadas", float(u.get("usd") or 0) > 0.05, str(u.get("usd")))
FILA[:] = [_resp("TOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênq", fim="max_tokens", out=8000, pensou=True),
           _resp(LAUDO_OK)]
t, o = chamar({}, botao="revisar", analise=True)
confere("cortada depois de pensar: refaz e devolve inteiro", t == LAUDO_OK, (t or "")[:60])
FILA[:] = [_resp("", fim="max_tokens", out=4000)]
t, o = chamar({})
confere("sem raciocínio e vazia: não refaz (nada a ganhar)", len(PEDIDOS) == 1 and o == "nuvem_vazia", o)


# 6. API recusa o campo
class _Http(urllib.error.HTTPError):
    def __init__(self, msg):
        super().__init__("u", 400, "bad", {}, io.BytesIO(msg.encode()))


FILA[:] = [_Http('{"error":{"message":"thinking.type: disabled is not supported for this model"}}'),
           _resp(LAUDO_OK)]
t, o = chamar({})
confere("400 pelo thinking: refaz sem o campo", o == "nuvem" and len(PEDIDOS) == 2
        and "thinking" not in PEDIDOS[1], o)

# 7. log sem conteúdo
log = open(nuvem.LOG, encoding="utf-8").read()
confere("log sem conteúdo do laudo", "Parênquima" not in log and "TOMOGRAFIA" not in log)

print()
print("raciocínio do Claude: tudo certo" if not falhas else "raciocínio do Claude: %d falha(s)" % len(falhas))
sys.exit(1 if falhas else 0)
