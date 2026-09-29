# -*- coding: utf-8 -*-
"""O print com as medidas vai para a IA junto com o laudo.

    python testar_imagem_ia.py

27/09: o app punha a imagem na folha (recortada e redesenhada, sem metadado),
mas o botão da IA mandava só o texto. A IA nunca via o print do TT-TG do
protocolo de Lyon e não fazia a conclusão com a medida. Este teste exige:
  1. só entra imagem de verdade: data URL png/jpeg/webp/gif, cabeçalho do arquivo
     conferido, no máximo 4, até 4,5 MB cada
  2. Anthropic: blocos "image" (base64) ANTES do texto; OpenAI/compatíveis:
     "image_url" com data URL (detail high na OpenAI)
  3. com imagem, a rota não cai em "só formatar" nem no modelo barato
  4. ia_no_texto manda as regras do bloco IMAGEM no pedido, não no sistema
     (o prompt de sistema continua o mesmo: o cache não se perde)
  5. sem imagem, nada muda (o pedido é o de sempre, texto puro)
  6. o log conta as imagens e nunca guarda o conteúdo
Sem internet e sem chave de verdade (respostas simuladas). Imagem sintética.
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
os.environ["ANTHROPIC_API_KEY"] = "teste-anthropic"
os.environ["OPENAI_API_KEY"] = "teste-openai"

import roteador  # noqa: E402

roteador._aprender = lambda *a, **k: None      # nunca grava aprendizado.json na pasta real

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


def png(w=4, h=3):
    """PNG sintético mínimo (cinza), sem biblioteca."""
    cru = b"".join(b"\x00" + b"\x80" * w for _ in range(h))

    def pedaco(tipo, dados):
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + pedaco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + pedaco(b"IDAT", zlib.compress(cru)) + pedaco(b"IEND", b""))


B64 = base64.b64encode(png()).decode()
URL_PNG = "data:image/png;base64," + B64

# 1. o que entra
imgs, erro = roteador.imagens_para_ia([URL_PNG])
confere("PNG de verdade entra", erro == "" and imgs == [("image/png", B64)], erro)
confere("sem imagem: lista vazia, sem erro", roteador.imagens_para_ia(None) == ([], ""))
confere("texto disfarçado de imagem não entra",
        roteador.imagens_para_ia(["data:image/png;base64," + base64.b64encode(b"Paciente: Fulano").decode()])[1]
        == "imagem_invalida")
confere("tipo que não é imagem não entra",
        roteador.imagens_para_ia(["data:text/plain;base64," + B64])[1] == "imagem_invalida")
confere("JPEG declarado com conteúdo PNG não entra",
        roteador.imagens_para_ia(["data:image/jpeg;base64," + B64])[1] == "imagem_invalida")
confere("mais de 4 imagens: recusa", roteador.imagens_para_ia([URL_PNG] * 5)[1] == "imagens_demais")
grande = "data:image/png;base64," + base64.b64encode(png()[:8] + b"\x00" * 4_600_000).decode()
confere("imagem acima de 4,5 MB: recusa", roteador.imagens_para_ia([grande])[1] == "imagem_grande")

# 2. formato de cada provedor
a = nuvem._conteudo_anthropic("LAUDO", [("image/png", B64)])
confere("Anthropic: imagem antes do texto, em base64",
        a[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": B64}}
        and a[-1] == {"type": "text", "text": "LAUDO"})
o = nuvem._conteudo_openai("LAUDO", [("image/png", B64)], detalhe=True)
confere("OpenAI: texto + image_url em data URL, detail high",
        o[0] == {"type": "text", "text": "LAUDO"}
        and o[1] == {"type": "image_url", "image_url": {"url": URL_PNG, "detail": "high"}})
confere("sem imagem: texto puro nos dois", nuvem._conteudo_anthropic("X", []) == "X"
        and nuvem._conteudo_openai("X", None) == "X")

# 3. rota
C_RX = {"ativa": True, "provedor": "anthropic", "modelo": "claude-opus-5-5", "economizar": True,
        "ia_por_exame": {"rx": {"provedor": "anthropic", "modelo": "claude-haiku-4-5", "modo": "formatar"}}}
P_RX = "LAUDO NA TELA:\nRADIOGRAFIA DO JOELHO DIREITO\nANÁLISE:\nsem alterações"
confere("sem imagem, a regra dele prende a RX em 'formatar'", nuvem.rota(P_RX, C_RX, "laudo")["modo"] == "formatar")
confere("com imagem, não prende em 'formatar'",
        nuvem.rota(P_RX, C_RX, "laudo", com_imagem=True)["modo"] == "laudo")

# 29/09 tarde: o config DELE (RX só formatar no gpt-6-luna, TC no gpt-6-sol). O print
# com medida foi para o Luna, que "não entende". Linha "Só formatar" cede ao padrão.
C_DELE = {"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol",
          "ia_por_exame": {"rx": {"provedor": "openai", "modelo": "gpt-6-luna", "modo": "formatar"},
                           "tc": {"provedor": "openai", "modelo": "gpt-6-sol"}}}
P_TC = "LAUDO NA TELA:\nTOMOGRAFIA COMPUTADORIZADA DO JOELHO DIREITO\nANÁLISE:\nTA-GT: ___"
r = nuvem.rota(P_RX, C_DELE, "laudo", com_imagem=True)
confere("config dele: RX com imagem vai para o Modelo padrão (gpt-6-sol), não para o Luna",
        r["modelo"] == "gpt-6-sol" and r["provedor"] == "openai" and r["regra"] == "imagem"
        and r.get("modelo_pedido") == "gpt-6-luna", repr(r))
confere("config dele: RX sem imagem continua no Luna só formatando",
        nuvem.rota(P_RX, C_DELE, "laudo")["modelo"] == "gpt-6-luna"
        and nuvem.rota(P_RX, C_DELE, "laudo")["modo"] == "formatar")
confere("config dele: TC com imagem fica na regra da TC (gpt-6-sol)",
        nuvem.rota(P_TC, C_DELE, "laudo", com_imagem=True)["regra"] == "tc")
r = nuvem.rota(P_RX, nuvem.com_modelo(C_DELE, "gpt-6-astra"), "laudo", com_imagem=True)
confere("RX com imagem e Astra escolhido na barra: vai o da barra", r["modelo"] == "gpt-6-astra", repr(r))
C_OUTRO = dict(C_DELE, provedor="anthropic", modelo="claude-opus-5-5")
r = nuvem.rota(P_RX, C_OUTRO, "laudo", com_imagem=True)
confere("padrão em outro provedor: provedor e modelo andam juntos",
        r["provedor"] == "anthropic" and r["modelo"] == "claude-opus-5-5", repr(r))


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


VISTO = {}


def _falso(req, timeout=None, context=None):
    VISTO["url"] = req.full_url
    VISTO["corpo"] = json.loads(req.data.decode("utf-8"))
    if "anthropic" in req.full_url:
        return _R(json.dumps({"content": [{"type": "text", "text": "LAUDO PRONTO"}], "stop_reason": "end_turn",
                              "usage": {"input_tokens": 900, "output_tokens": 200}}).encode())
    return _R(json.dumps({"choices": [{"message": {"content": "LAUDO PRONTO"}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 200}}).encode())


urllib.request.urlopen = _falso


def cfg(**k):
    c = {"ativa": True, "provedor": "anthropic", "modelo": "claude-sonnet-5", "economizar": True,
         "limite_mes_usd": 0, "marcar_saida": False}
    c.update(k)
    with io.open(nuvem.CONFIG, "w", encoding="utf-8") as f:
        json.dump(c, f)


LAUDO = ("TOMOGRAFIA COMPUTADORIZADA DOS JOELHOS - PROTOCOLO DE LYON\nANÁLISE:\n"
         "Distância TT-TG direita:\nDistância TT-TG esquerda:\nCONCLUSÃO:\n{conclusao_1}")

# 4. ponta a ponta, Anthropic
cfg()
r = roteador.ia_no_texto(LAUDO, "", "", [URL_PNG])
corpo = VISTO.get("corpo", {})
msg = (corpo.get("messages") or [{}])[0].get("content")
confere("Anthropic: a imagem chega na mensagem", isinstance(msg, list) and msg[0].get("type") == "image"
        and msg[0]["source"]["data"] == B64, repr(msg)[:160])
texto_pedido = msg[-1].get("text", "") if isinstance(msg, list) else ""
confere("as regras da IMAGEM vão no pedido", "IMAGENS ANEXADAS" in texto_pedido
        and "1 IMAGEM(NS) ANEXADA(S)" in texto_pedido and "LAUDO NA TELA:" in texto_pedido, texto_pedido[:200])
sistema = corpo.get("system", [{}])[0].get("text", "")
confere("e NÃO no prompt de sistema (cache intacto)", "IMAGENS ANEXADAS" not in sistema)
confere("resposta diz quantas imagens foram", r.get("ok") and r.get("imagens") == 1, repr(r)[:160])

# 5. sem imagem: igual a antes
r = roteador.ia_no_texto(LAUDO, "", "", None)
msg = VISTO["corpo"]["messages"][0]["content"]
confere("sem imagem: texto puro e sem as regras da imagem",
        isinstance(msg, str) and msg.startswith("LAUDO NA TELA:") and "IMAGENS ANEXADAS" not in msg)

# OpenAI, com imagem e a regra de economia ligada: não troca para o barato
cfg(provedor="openai", modelo="gpt-5.5")
r = roteador.ia_no_texto(LAUDO, "organize o protocolo de Lyon", "", [URL_PNG])
corpo = VISTO["corpo"]
msg = corpo["messages"][1]["content"]
confere("OpenAI: image_url com a imagem", "openai.com" in VISTO["url"] and isinstance(msg, list)
        and msg[1]["image_url"]["url"] == URL_PNG, repr(msg)[:160])
confere("com imagem, o modelo não é trocado pelo barato", corpo.get("model") == "gpt-5.5", corpo.get("model"))
confere("a instrução falada vai junto", "INSTRUÇÃO FALADA: organize o protocolo de Lyon" in msg[0]["text"])

# imagem ruim: nada sai
VISTO.clear()
r = roteador.ia_no_texto(LAUDO, "", "", ["data:image/png;base64,QUJD"])
confere("imagem inválida: não chama a IA e diz o motivo", not VISTO and r.get("motivo") == "imagem_invalida")
cfg(ia_imagens=False)
r = roteador.ia_no_texto(LAUDO, "", "", [URL_PNG])
confere("ia_imagens: false no config bloqueia imagem", not VISTO and r.get("motivo") == "imagem_desligada")

# 6. log
tudo = io.open(nuvem.LOG, encoding="utf-8").read()
confere("log conta as imagens", "\timg=1" in tudo, tudo[-200:])
confere("log não guarda imagem nem laudo", B64[:20] not in tudo and "LYON" not in tudo and "TT-TG" not in tudo)

print()
print("imagem para a IA: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
