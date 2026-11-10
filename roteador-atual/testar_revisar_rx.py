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
confere("revisar (conferir incoerências): REVISAO + SO_CONFERIR, sem a liberdade do reescrever",
        "CONFERÊNCIA DE INCOERÊNCIAS" in pedido and "SÓ A CONFERÊNCIA" in pedido
        and "REESCREVER O LAUDO" not in pedido and "NÃO corrija: aponte" in pedido, pedido[:300])
confere("revisar: laudo inteiro, sem numerar linhas (sem diferença)", "#1" not in pedido, pedido[-300:])
confere("revisar: volta ok com botao=revisar", r.get("ok") is True and r.get("botao") == "revisar", repr(r)[:200])
t = r.get("texto") or ""
confere("revisar: [conferir — revisão] no topo com lado novo e medida nova",
        t.startswith("[conferir — revisão:") and "lado esquerdo apareceu" in t.split("\n")[0]
        and "0,8cm" in t.split("\n")[0], t.split("\n")[0])
confere("revisar: não ensina par de palavras ao revisor local", not APRENDEU)

# 1b. (10/11) Revisar › melhorar a redação: REVISAO + MELHORAR, mesma conferência local
VISTO.clear()
RESPOSTA["texto"] = LAUDO
r = roteador.ia_no_texto(LAUDO, instrucao=roteador.INSTRUCAO_MELHORAR + "\nOPÇÕES: defensivo; técnico"
                                     "\nORIENTAÇÃO: alterações pulmonares mais defensivas\nconclusão curta")
_s, pedido = mensagens()
confere("reescrever: REVISAO + MELHORAR (liberdade de revisor), sem o SO_CONFERIR",
        "CONFERÊNCIA DE INCOERÊNCIAS" in pedido and "REESCREVER O LAUDO" in pedido and "LIBERDADE" in pedido
        and "SÓ A CONFERÊNCIA" not in pedido, pedido[:300])
confere("reescrever: limites que ficam (achado alterado não sai; medida, lado e nível não mudam)",
        "Achado alterado nunca sai do laudo" in pedido and "Nenhuma medida, número, lado, nível" in pedido)
confere("reescrever: opções marcadas e orientação dele vão no pedido",
        "REDAÇÃO DEFENSIVA" in pedido and "MAIS TÉCNICO" in pedido and "INFERÊNCIAS:" not in pedido
        and "ORIENTAÇÃO DO RADIOLOGISTA" in pedido and "alterações pulmonares mais defensivas\nconclusão curta" in pedido,
        pedido[pedido.find("PEDIDO:"):pedido.find("PEDIDO:") + 400])
confere("melhorar: volta ok com botao=melhorar e sem [conferir] quando nada mudou de sentido",
        r.get("ok") is True and r.get("botao") == "melhorar" and not (r.get("texto") or "").startswith("[conferir"),
        repr(r)[:200])
confere("melhorar usa a linha do Botão Revisar", nuvem.CHAVE_DO_BOTAO.get("melhorar") == "revisar")
confere("reescrever no Luna: raciocínio 'low' (o básico formatando recebe 'none')",
        nuvem.rota("TC DO TÓRAX", {"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol",
                                   "ia_por_exame": {"revisar": {"provedor": "openai", "modelo": "gpt-6-luna"}}},
                   "laudo", analise=True, botao="melhorar")["raciocinio"] == "low")
src_n = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nuvem.py"), encoding="utf-8").read()
confere("chamar dá 'low' ao básico no reescrever em qualquer rota",
        'if not rac and botao == "melhorar" and _modelo_basico(r["modelo"]):' in src_n)

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

# 6. (10/11) a linha do botão na tabela escolhe a IA — e vence a barra
cb = {"ativa": True, "provedor": "anthropic", "modelo": "claude-sonnet-5",
      "ia_por_exame": {"rx": {"provedor": "openai", "modelo": "gpt-6-luna", "modo": "formatar"},
                       "revisar": {"provedor": "openai", "modelo": "gpt-6-sol"}}}
rr = nuvem.rota("RADIOGRAFIA DO JOELHO", nuvem.com_modelo(cb, "anthropic:claude-opus-5"), "laudo",
                analise=True, botao="revisar")
confere("linha 'Botão Revisar' escolhe a IA da revisão (vence a barra e a linha do RX)",
        (rr["provedor"], rr["modelo"], rr["regra"], rr["modo"]) == ("openai", "gpt-6-sol", "botao:revisar", "laudo"),
        repr(rr))
rr = nuvem.rota("RADIOGRAFIA DO JOELHO", cb, "laudo", analise=True, botao="rx")
confere("sem linha do Analisar RX: caminho de sempre (o 'Só formatar' do RX cede ao padrão)",
        rr["regra"] != "botao:analisar_rx" and rr["modo"] == "laudo" and rr["modelo"] == "claude-sonnet-5", repr(rr))

# 7. (10/11) "mais de uma IA": 2ª IA da revisão roda junto; diferença vira [conferir]
DUAS = {"gpt-6-sol": LAUDO.replace("Nefrolitíase.", "Nefrolitíase."),
        "gpt-6-luna": LAUDO.replace("Nefrolitíase.", "Nefrolitíase.\nEsteatose hepática.")}
MODELOS_VISTOS = []


def _falso2(req, timeout=None, context=None):
    corpo = json.loads(req.data.decode("utf-8"))
    MODELOS_VISTOS.append(corpo.get("model"))
    txt = DUAS.get(corpo.get("model"), "SEM MUDANÇAS")
    return _R(json.dumps({"choices": [{"message": {"content": txt}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 60}}).encode())


urllib.request.urlopen = _falso2
cfg(ia_por_exame={"revisar": {"provedor": "openai", "modelo": "gpt-6-sol"},
                  "revisar_2": {"provedor": "openai", "modelo": "gpt-6-luna"}})
r = roteador.ia_no_texto(LAUDO, instrucao=roteador.INSTRUCAO_REVISAR)
confere("2ª IA: as duas foram chamadas (Sol e Luna)", sorted(MODELOS_VISTOS) == ["gpt-6-luna", "gpt-6-sol"],
        repr(MODELOS_VISTOS))
confere("2ª IA: a 1ª vai para a folha", r.get("ok") and "Esteatose" not in (r.get("texto") or "").split("]\n")[-1],
        repr(r)[:300])
confere("2ª IA: a revisão dela volta para o botão de trocar",
        "Esteatose hepática." in ((r.get("segunda") or {}).get("texto") or ""), repr(r.get("segunda"))[:200])
confere("2ª IA: conclusão que só ela tem vai no [conferir — 2ª IA]",
        "[conferir — 2ª IA (gpt-6-luna): conclusão dela: \"Esteatose hepática.\"" in (r.get("texto") or ""),
        (r.get("texto") or "")[:200])
MODELOS_VISTOS.clear()
cfg(ia_por_exame={"revisar": {"provedor": "openai", "modelo": "gpt-6-sol"}})
r = roteador.ia_no_texto(LAUDO, instrucao=roteador.INSTRUCAO_REVISAR)
confere("sem a 2ª IA: uma chamada só", MODELOS_VISTOS == ["gpt-6-sol"] and r.get("segunda") is None, repr(MODELOS_VISTOS))
urllib.request.urlopen = _falso

print()
print("revisar e analisar RX: tudo certo" if not falhas else "revisar e analisar RX: %d falha(s)" % len(falhas))
sys.exit(1 if falhas else 0)
