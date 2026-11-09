# -*- coding: utf-8 -*-
"""Botões Revisar e Analisar RX da aba Laudo (python testar_revisar_rx.py).

09/11, depois do expoweb aprovado: "preciso entender se ele analisa a imagem colada e emite
inferências". Analisar RX é o ÚNICO pedido em que a IA lê a radiografia para laudar (bloco
RADIOGRAFIA: a matriz ditado × imagem da skill); com imagem fora dele, vale o bloco IMAGEM
(só medidas). Revisar manda o bloco REVISAO e confere aqui o que mudou de sentido.
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
APRENDEU = []
roteador._aprender = lambda *a, **k: APRENDEU.append(a)
LAUDO = ("**TOMOGRAFIA COMPUTADORIZADA DO ABDOME**\n\n**TÉCNICA:**  cortes axiais sem contraste.\n\n"
         "**ANÁLISE:**\n**Fígado:**  não há lesões focais.\n**Rins:**  cálculo de 0,6 cm.\n\n"
         "**CONCLUSÃO:**\nNefrolitíase.")

# 1. Revisar: bloco REVISAO no pedido, sem diferença, conferência local, sem aprender
VISTO.clear()
RESPOSTA["texto"] = LAUDO.replace("não há lesões focais", "sem lesões focais").replace(
    "cálculo de 0,6 cm", "cálculo de 0,6 cm no rim esquerdo").replace("Nefrolitíase.", "Nefrolitíase à esquerda. Medindo 0,8 cm.")
r = roteador.ia_no_texto(LAUDO, instrucao=roteador.INSTRUCAO_REVISAR)
_s, pedido = mensagens()
confere("revisar: o pedido leva o bloco REVISÃO", "REVISÃO DO LAUDO (botão Revisar" in pedido, pedido[:300])
confere("revisar: laudo inteiro, sem numerar linhas (sem diferença)", "#1" not in pedido, pedido[-300:])
confere("revisar: volta ok com botao=revisar", r.get("ok") is True and r.get("botao") == "revisar", repr(r)[:200])
t = r.get("texto") or ""
confere("revisar: [conferir — revisão] no topo com lado novo e medida nova",
        t.startswith("[conferir — revisão:") and "lado esquerdo apareceu" in t.split("\n")[0]
        and "0,8cm" in t.split("\n")[0], t.split("\n")[0])
confere("revisar: não ensina par de palavras ao revisor local", not APRENDEU)

# 2. Analisar RX sem imagem: recusa sem chamar a IA
VISTO.clear()
r = roteador.ia_no_texto("**RADIOGRAFIA DO JOELHO DIREITO**", instrucao=roteador.INSTRUCAO_ANALISAR_RX)
confere("analisar RX sem imagem: recusa e não chama a IA", r.get("motivo") == "rx_sem_imagem" and not VISTO, repr(r))

# 3. Analisar RX com imagem: bloco RADIOGRAFIA (lê a imagem), não o IMAGEM (só medidas)
VISTO.clear()
RESPOSTA["texto"] = "**RADIOGRAFIA DO JOELHO DIREITO**\n\n**ANÁLISE:**\nDerrame articular.\n[conferir] possível corpo livre, conferir"
r = roteador.ia_no_texto("**RADIOGRAFIA DO JOELHO DIREITO**\n\n**ANÁLISE:**\nDerrame articular.",
                         instrucao=roteador.INSTRUCAO_ANALISAR_RX, imagens=[URL])
_s, pedido = mensagens()
confere("analisar RX: bloco RADIOGRAFIA com a matriz (confirma/troca/ressalva, nunca tira achado)",
        "ANALISAR RADIOGRAFIA" in pedido and "Nunca tire achado dele" in pedido and "confiança média ou baixa" in pedido,
        pedido[:300])
confere("analisar RX: sem o bloco IMAGEM (que proíbe laudar pela imagem)", "IMAGENS ANEXADAS" not in pedido)
confere("analisar RX: a imagem foi", "image" in json.dumps(VISTO.get("corpo", {}))[:100000])
confere("analisar RX: ressalva [conferir] chega ao app", "[conferir] possível corpo livre" in (r.get("texto") or ""), repr(r)[:300])

# 4. Reprocessar com imagem (sem botão): continua o bloco IMAGEM
VISTO.clear()
RESPOSTA["texto"] = "**RADIOGRAFIA DO JOELHO DIREITO**"
roteador.ia_no_texto("**RADIOGRAFIA DO JOELHO DIREITO**", imagens=[URL])
_s, pedido = mensagens()
confere("reprocessar com imagem: bloco IMAGEM, não RADIOGRAFIA", "IMAGENS ANEXADAS" in pedido and "ANALISAR RADIOGRAFIA" not in pedido)

# 5. conferência local da revisão
c = roteador._conferir_revisao("Rim direito com cálculo de 6 mm. Não há hidronefrose.",
                               "Rim esquerdo com cálculo de 8 mm. Hidronefrose.")
confere("conferência: medida nova, medida sumida, lado trocado, negação a menos",
        any("8mm" in x for x in c) and any("6mm" in x for x in c) and "lado esquerdo apareceu" in c
        and "lado direito sumiu" in c and any("negação" in x for x in c), repr(c))
confere("conferência: só redação não acusa nada",
        roteador._conferir_revisao("Fígado sem lesões, 12 cm.", "Fígado de dimensões normais, sem lesões, 12 cm.") == [])

print()
print("revisar e analisar RX: tudo certo" if not falhas else "revisar e analisar RX: %d falha(s)" % len(falhas))
sys.exit(1 if falhas else 0)
