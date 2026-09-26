# -*- coding: utf-8 -*-
"""A IA "às vezes não responde": tempo de espera e laudo cortado no teto.

    python testar_tempo_nuvem.py

26/09: 12 de 170 chamadas do Sonnet 5 estouraram o tempo — todas as longas. O
timeout era 40 s fixo e a rota do laudo pede até 4.000 tokens; sem streaming,
nada chega antes de a resposta inteira ficar pronta, e o que a API gerou é
cobrado mesmo assim. E 6 laudos saíram com 3.900–4.000 tokens: a API parou no
teto e o texto vinha como se estivesse inteiro. Este teste exige:
  1. espera proporcional ao teto (4.000 -> 85 s, o máximo antes de o app desistir),
     nunca menos que o timeout_s do config
  2. o teto de verdade chega na chamada HTTP
  3. resposta cortada no teto vem MARCADA e o log diz "ok_cortado fim=max_tokens"
  4. tempo esgotado fica no log com quanto esperou e o teto
  5. o log continua sem conteúdo do laudo
Sem internet e sem chave de verdade (respostas simuladas).
"""
import io
import json
import os
import socket
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import nuvem  # noqa: E402

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp
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


VISTO = {}
RESP = {}


def _falso(req, timeout=None, context=None):
    VISTO["timeout"] = timeout
    VISTO["corpo"] = json.loads(req.data.decode("utf-8"))
    return RESP["f"]()


urllib.request.urlopen = _falso
C = {"ativa": True, "provedor": "anthropic", "modelo": "claude-sonnet-5",
     "timeout_s": 40, "max_tokens": 1500, "limite_mes_usd": 0, "marcar_saida": False}
PEDIDO = "LAUDO NA TELA:\nTOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênquima sem alterações.\nformar laudo"

# 1. espera proporcional
confere("4.000 tokens de teto -> 85 s (o app desiste em 90 s)", nuvem.tempo_de_espera(4000, C) == 85)
confere("1.500 -> 67 s", nuvem.tempo_de_espera(1500, C) == 67)
confere("com timeout_max_s maior, 4.000 -> 130 s", nuvem.tempo_de_espera(4000, {"timeout_max_s": 200}) == 130)
confere("nunca menos que o timeout_s do config", nuvem.tempo_de_espera(300, {"timeout_s": 90}) == 90)

# 2 e 3. resposta cortada no teto
RESP["f"] = lambda: _R(json.dumps({
    "content": [{"type": "text", "text": "TOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênquima sem"}],
    "stop_reason": "max_tokens",
    "usage": {"input_tokens": 700, "output_tokens": 4000}}).encode())
texto, origem = nuvem.chamar(PEDIDO, dict(C), modo="laudo", marcar=False, max_tokens=4000)
confere("o timeout HTTP é o proporcional (85 s), não os 40 s", VISTO.get("timeout") == 85,
        repr(VISTO.get("timeout")))
confere("o teto pedido chega na API", VISTO["corpo"].get("max_tokens") == 4000)
confere("laudo cortado vem marcado para conferir o fim",
        origem == "nuvem" and (texto or "").startswith("[a IA parou no limite de tamanho"), repr(texto)[:120])
ult = io.open(nuvem.LOG, encoding="utf-8").read().strip().splitlines()[-1]
confere("log: ok_cortado, fim=max_tokens, teto e tempo", "\tok_cortado\t" in ult and "fim=max_tokens" in ult
        and "teto=4000" in ult and "\tms=" in ult, ult)

# resposta inteira: sem marca
RESP["f"] = lambda: _R(json.dumps({
    "content": [{"type": "text", "text": "TOMOGRAFIA DO TÓRAX\nCONCLUSÃO:\nSem alterações."}],
    "stop_reason": "end_turn", "usage": {"input_tokens": 700, "output_tokens": 900}}).encode())
texto, origem = nuvem.chamar(PEDIDO, dict(C), modo="laudo", marcar=False, max_tokens=4000)
confere("resposta inteira não leva marca", not (texto or "").startswith("[a IA parou"))
ult = io.open(nuvem.LOG, encoding="utf-8").read().strip().splitlines()[-1]
confere("log: ok, fim=end_turn", "\tok\t" in ult and "fim=end_turn" in ult, ult)


# 4. tempo esgotado
def _estoura():
    raise socket.timeout("timed out")


RESP["f"] = _estoura
texto, origem = nuvem.chamar(PEDIDO, dict(C), modo="laudo", marcar=False, max_tokens=4000)
ult = io.open(nuvem.LOG, encoding="utf-8").read().strip().splitlines()[-1]
confere("tempo esgotado devolve erro, não texto", texto is None and origem.startswith("nuvem_erro_"), origem)
confere("log do tempo esgotado tem quanto esperou e o teto", "\tms=" in ult and "teto=4000" in ult, ult)

# 5. nada do laudo no log
tudo = io.open(nuvem.LOG, encoding="utf-8").read()
confere("o log não tem texto do laudo", "Parênquima" not in tudo and "TÓRAX" not in tudo)
# e quem lê o log pela 1a coluna (cálculo do cache) continua lendo
confere("o cálculo do cache ainda lê as horas do log", len(nuvem._horas_de_chamada()) == 3)

print()
print("tempo e corte da nuvem: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
