# -*- coding: utf-8 -*-
"""Print para o formulário (escanometria, panorâmicas, idade óssea) e a IA do botão leve.

    python testar_ler_print.py

03/10, pedidos dele:
  - "na escanometria ... eu queria poder simplesmente anexar uma imagem, colar um
    print com as medidas" — o botão "Colar print com as medidas" só mostrava aviso
  - "na idade óssea, eu queria jogar a imagem e a data de aniversário e a IA já
    calculava"
  - "a barra ao lado da IA mais fraca ... não estou conseguindo selecionar qual IA"
Este teste exige:
  1. a leitura usa o PRÓPRIO prompt de sistema (só JSON), não o do redator
  2. só as chaves do formulário voltam; número normalizado com vírgula; o resto cai
  3. idade óssea: só a imagem e o sexo vão — a data de nascimento NUNCA vai
  4. idade fora da faixa ou resposta torta: recusa, não preenche
  5. imagem inválida, IA desligada, alvo desconhecido: recusa sem chamar a IA
  6. modelo_leve do config manda nas chamadas do leve ("analisar …"); vazio = padrão
Sem internet e sem chave de verdade.
"""
import base64
import io
import json
import os
import struct
import sys
import tempfile
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import nuvem  # noqa: E402

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp
nuvem.CONFIG = os.path.join(tmp, "config.json")
nuvem.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
os.environ["OPENAI_API_KEY"] = "teste-openai"

import roteador  # noqa: E402

roteador._aprender = lambda *a, **k: None
falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


def png(w=8, h=8):
    def pedaco(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    cru = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + pedaco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + pedaco(b"IDAT", zlib.compress(cru)) + pedaco(b"IEND", b""))


URL = "data:image/png;base64," + base64.b64encode(png()).decode()


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


VISTO = {}
RESPOSTA = {"texto": "{}"}


def _falso(req, timeout=None, context=None):
    VISTO["corpo"] = json.loads(req.data.decode("utf-8"))
    return _R(json.dumps({"choices": [{"message": {"content": RESPOSTA["texto"]}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 60}}).encode())


urllib.request.urlopen = _falso


def cfg(**extra):
    c = {"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol", "limite_mes_usd": 0,
         "marcar_saida": False, "ia_por_exame": {}}
    c.update(extra)
    with io.open(nuvem.CONFIG, "w", encoding="utf-8") as f:
        json.dump(c, f)


def mensagens():
    msgs = VISTO.get("corpo", {}).get("messages") or []
    sistema = " ".join(m.get("content", "") for m in msgs if m.get("role") in ("system", "developer")
                       and isinstance(m.get("content"), str))
    user = [m for m in msgs if m.get("role") == "user"]
    pedido = user[-1].get("content", "") if user else ""
    if isinstance(pedido, list):
        pedido = " ".join(p.get("text", "") for p in pedido if isinstance(p, dict) and p.get("type") == "text")
    return sistema, pedido


cfg()

# 1-2. escanometria
VISTO.clear()
RESPOSTA["texto"] = ('{"valores": {"quadril_d": "12.5", "quadril_e": "12,75 cm", "joelho_d": 55, '
                     '"inventado": "99", "tornozelo_d": "ilegível"}, "nao_achei": ["tornozelo_e"], '
                     '"obs": "régua em cm"}')
r = roteador.ler_print("escanometria", URL)
sistema, pedido = mensagens()
confere("escanometria: lê", r.get("ok") is True, repr(r)[:200])
confere("prompt de sistema próprio (só JSON), não o do redator",
        "SOMENTE com um objeto JSON" in sistema and "DECISAO" not in sistema and len(sistema) < 600, sistema[:200])
confere("o pedido lista os campos do formulário", "quadril_d: Quadril direito" in pedido, pedido[:300])
confere("a imagem foi junto", "image" in json.dumps(VISTO.get("corpo", {}))[:100000])
confere("só as chaves do formulário, número com vírgula",
        r.get("valores") == {"quadril_d": "12,5", "quadril_e": "12,75", "joelho_d": "55"}, repr(r.get("valores")))
confere("o que não veio aparece em 'nao_achei'",
        set(r.get("nao_achei") or []) == {"joelho_e", "tornozelo_d", "tornozelo_e"}, repr(r.get("nao_achei")))
confere("recibo com modelo", r.get("modelo") == "openai:gpt-6-sol", repr(r.get("modelo")))

# panorâmica da coluna
RESPOSTA["texto"] = '{"valores": {"cobb": "23º", "sva": "-2,1"}}'
r = roteador.ler_print("panoramica_coluna", URL)
confere("panorâmica da coluna: grau e negativo", r.get("valores") == {"cobb": "23", "sva": "-2,1"}, repr(r))

# 3. idade óssea
VISTO.clear()
RESPOSTA["texto"] = ('{"anos": 9, "meses": 0, "entre": "8a10m e 10a0m", "achados": "epífises das falanges '
                     'da largura das metáfises", "confianca": "media"}')
r = roteador.ler_print("idade_ossea", URL, {"sexo": "feminino", "nascimento": "2016-05-12"})
sistema, pedido = mensagens()
confere("idade óssea: lê anos e meses", r.get("ok") and r.get("anos") == 9 and r.get("meses") == 0, repr(r))
confere("o sexo vai", "Sexo: feminino" in pedido, pedido[:200])
confere("a data de nascimento NUNCA vai", "2016" not in json.dumps(VISTO.get("corpo", {}))
        and "nascimento" not in pedido.lower().replace("idade cronológica não", ""), pedido[:400])

# 4. respostas tortas
for nome, resp in [("idade fora da faixa", '{"anos": 35, "meses": 0}'),
                   ("meses fora da faixa", '{"anos": 9, "meses": 14}'),
                   ("sem JSON", "a idade óssea parece 9 anos")]:
    RESPOSTA["texto"] = resp
    r = roteador.ler_print("idade_ossea", URL, {"sexo": "masculino"})
    confere("%s: recusa" % nome, r.get("ok") is False and r.get("motivo") == "resposta_fora_do_formato", repr(r))
RESPOSTA["texto"] = '{"erro": "não é mão e punho"}'
r = roteador.ler_print("idade_ossea", URL, {"sexo": "masculino"})
confere("imagem que não serve: diz o porquê", r.get("motivo") == "imagem_nao_serve"
        and "mão" in r.get("detalhe", ""), repr(r))

# 5. recusas sem chamar a IA
VISTO.clear()
confere("imagem inválida", roteador.ler_print("escanometria", "data:image/png;base64,AAAA")["motivo"]
        == "imagem_invalida" and not VISTO)
confere("sem imagem", roteador.ler_print("escanometria", "")["motivo"] == "sem_imagem" and not VISTO)
confere("alvo desconhecido", roteador.ler_print("cranio", URL)["motivo"] == "alvo_desconhecido" and not VISTO)
cfg(ativa=False)
confere("IA desligada", roteador.ler_print("escanometria", URL)["motivo"] == "nuvem_desligada" and not VISTO)
cfg(ia_imagens=False)
confere("imagem desligada no config", roteador.ler_print("escanometria", URL)["motivo"] == "imagem_desligada"
        and not VISTO)
fonte = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteador.py"), encoding="utf-8").read()
confere("rota POST /v1/ler_print existe", '"/ler_print"' in fonte and "ler_print(corpo.get(\"alvo\")" in fonte)

# 6. a IA do botão leve
RESPOSTA["texto"] = "Nódulo sólido de 8 mm."
cfg(modelo_leve="gpt-6-luna")
VISTO.clear()
t, o = roteador.rotear("analisar nódulo sólido de 8 mm no lobo superior direito")
confere("'analisar …' no leve usa a IA escolhida para o leve",
        VISTO.get("corpo", {}).get("model") == "gpt-6-luna", repr((o, VISTO.get("corpo", {}).get("model"))))
cfg(modelo_leve="")
VISTO.clear()
t, o = roteador.rotear("analisar nódulo sólido de 8 mm no lobo superior direito")
confere("sem escolha: o Modelo padrão", VISTO.get("corpo", {}).get("model") == "gpt-6-sol",
        repr(VISTO.get("corpo", {}).get("model")))
cfg(modelo_leve="gpt-6-luna")
confere("a tela lê a escolha (GET /v1/ia)", nuvem.estado().get("modelo_leve") == "gpt-6-luna")
VISTO.clear()
roteador.ia_no_texto("TC DE TÓRAX\nNódulo de 8 mm.", "", "", None)
confere("o botão forte NÃO muda com a escolha do leve", VISTO.get("corpo", {}).get("model") == "gpt-6-sol",
        repr(VISTO.get("corpo", {}).get("model")))

print()
print("ler print e IA do leve: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
