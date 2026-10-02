# -*- coding: utf-8 -*-
"""Botão de raciocínio: o ditado vai cru para a IA, sem gatilho e sem banco.

    python testar_raciocinio.py

02/10, pedido dele: "muitas vezes eu só vou dizer: descreva isso, descreva aquilo"
e a IA tem de escrever a frase padrão do léxico radiológico. E os gatilhos estavam
atrapalhando: ditando "derrame pleural bilateral, pequeno à direita" no botão
forte, o roteador já encaixava frase do banco (no PC dele, "ateromas calcificados";
no banco do repositório, a máscara "derrame + atelectasia", com uma atelectasia que
ele não ditou, e o "pequeno à direita" virava "pequeno/moderado"). A IA só recebia
o resultado e não tinha como desfazer. Decisão dele: ignora o banco e faz a
descrição padrão. Este teste exige:
  1. folha vazia: SÓ o nome do exame escolhe a máscara, e ela é a NORMAL
  2. o ditado chega à IA como ele falou (menos o nome do exame), com o bloco
     DESCREVA no pedido e nenhuma frase do banco
  3. o bloco DESCREVA vai no pedido, não no prompt de sistema (cache intacto)
  4. folha com laudo: a tela vai como está e o ditado vai à parte
  5. raciocínio não cai em "só formatar" nem no modelo básico da linha da tabela
  6. sem ditado, nada muda; e o log não guarda o ditado
  7. (02/10, o switch "roteador") ligado: a tela vai com o que o roteador encaixou e
     a IA recebe a regra de conferir isso contra a fala crua
Sem internet e sem chave de verdade (respostas simuladas).
"""
import io
import json
import os
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
nuvem.CONFIG = os.path.join(tmp, "config.json")
nuvem.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
os.environ["OPENAI_API_KEY"] = "teste-openai"
os.environ["ANTHROPIC_API_KEY"] = "teste-anthropic"

import roteador  # noqa: E402

roteador._aprender = lambda *a, **k: None      # nunca grava aprendizado.json na pasta real

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


VISTO = {}


def _falso(req, timeout=None, context=None):
    VISTO["url"] = req.full_url
    VISTO["corpo"] = json.loads(req.data.decode("utf-8"))
    return _R(json.dumps({"choices": [{"message": {"content": "LAUDO PRONTO"}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 200}}).encode())


urllib.request.urlopen = _falso

# o config dele (29/09): RX só formatar no gpt-6-luna, TC no gpt-6-sol, padrão gpt-6-sol
C_DELE = {"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol", "limite_mes_usd": 0,
          "marcar_saida": False,
          "ia_por_exame": {"rx": {"provedor": "openai", "modelo": "gpt-6-luna", "modo": "formatar"},
                           "tc": {"provedor": "openai", "modelo": "gpt-6-sol"}}}


def cfg(c):
    with io.open(nuvem.CONFIG, "w", encoding="utf-8") as f:
        json.dump(c, f)


def pedido_e_sistema():
    msgs = VISTO.get("corpo", {}).get("messages") or []
    sistema = " ".join(m.get("content", "") for m in msgs if m.get("role") in ("system", "developer")
                       and isinstance(m.get("content"), str))
    user = [m for m in msgs if m.get("role") == "user"]
    pedido = user[-1].get("content", "") if user else ""
    if isinstance(pedido, list):
        pedido = " ".join(p.get("text", "") for p in pedido if isinstance(p, dict))
    return pedido, sistema


def tela(pedido):
    return pedido.split("LAUDO NA TELA:", 1)[1] if "LAUDO NA TELA:" in pedido else ""


cfg(C_DELE)

# 1-3. folha vazia, o exemplo dele
VISTO.clear()
r = roteador.ia_no_texto("", "", "", None, "tomografia de tórax. derrame pleural bilateral, pequeno à direita")
pedido, sistema = pedido_e_sistema()
confere("folha vazia + ditado: chama a IA", r.get("ok") and r.get("ditado") is True, repr(r)[:200])
confere("a máscara é a NORMAL da TC de tórax, escolhida só pelo nome do exame",
        "TOMOGRAFIA COMPUTADORIZADA DO TÓRAX" in tela(pedido).upper(), tela(pedido)[:200])
confere("nenhuma atelectasia (que ele não ditou) na tela que vai para a IA",
        "atelectasia" not in tela(pedido).lower(), tela(pedido)[:400])
confere("o ditado vai como ele falou, sem o nome do exame",
        "DITADO DO RADIOLOGISTA:\nderrame pleural bilateral, pequeno à direita\n" in pedido, pedido[-600:])
confere("nenhuma frase do banco ('pequeno/moderado volume')", "pequeno/moderado" not in pedido)
confere("as regras do DESCREVA vão no pedido", "DITADO DE RACIOCÍNIO" in pedido and "COMO DESCREVER" in pedido)
confere("e não no prompt de sistema (cache intacto)", "DITADO DE RACIOCÍNIO" not in sistema and len(sistema) > 1000,
        str(len(sistema)))
confere("TC com raciocínio: gpt-6-sol", VISTO.get("corpo", {}).get("model") == "gpt-6-sol",
        VISTO.get("corpo", {}).get("model"))

# 4. folha já com laudo: a tela vai como está
LAUDO = ("TOMOGRAFIA COMPUTADORIZADA DE ABDOME SUPERIOR E PELVE\n\nANÁLISE:\n"
         "Fígado:  de dimensões normais, contornos regulares e densidade normal.\n\nCONCLUSÃO:\n"
         "Estudo dentro dos limites da normalidade.")
VISTO.clear()
r = roteador.ia_no_texto(LAUDO, "", "", None, "descreva esteatose hepática")
pedido, _s = pedido_e_sistema()
confere("folha com laudo: a tela é o laudo dela, sem trocar de máscara",
        tela(pedido).strip().startswith("TOMOGRAFIA COMPUTADORIZADA DE ABDOME SUPERIOR E PELVE")
        and "densidade normal" in tela(pedido), tela(pedido)[:200])
confere("e o 'descreva' vai para a IA, que é quem descreve",
        "DITADO DO RADIOLOGISTA:\ndescreva esteatose hepática" in pedido, pedido[-400:])

confere("switch desligado: o pedido diz que nada foi encaixado", "ROTEADOR DESLIGADO" in pedido
        and "ROTEADOR LIGADO." not in pedido)

# switch "roteador" ligado: a tela tem o que o roteador encaixou; a IA confere contra a fala
ROTEADA = LAUDO.replace("densidade normal.", "densidade normal.\nVasos:  ateromas calcificados na aorta abdominal.")
VISTO.clear()
r = roteador.ia_no_texto(ROTEADA, "", "", None, "derrame pleural bilateral, pequeno à direita", True)
pedido, _s = pedido_e_sistema()
confere("switch ligado: vai a regra de conferir o que o roteador encaixou",
        "ROTEADOR LIGADO" in pedido and "Confira o que ele encaixou contra o DITADO" in pedido
        and "ROTEADOR DESLIGADO" not in pedido, pedido[:300])
confere("switch ligado: a tela vai com o que o roteador pôs, e a fala crua vai junto",
        "ateromas calcificados" in tela(pedido)
        and "DITADO DO RADIOLOGISTA:\nderrame pleural bilateral, pequeno à direita" in pedido)
confere("POST /v1/ia passa o switch", 'bool(corpo.get("roteado"))' in io.open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteador.py"), encoding="utf-8").read())

# 5. RX: a linha "Só formatar" (Luna) cede ao padrão no raciocínio
VISTO.clear()
RX = "RADIOGRAFIA DO TÓRAX\n\nTÉCNICA:  incidências em PA e perfil.\n\nANÁLISE:\nCampos pulmonares sem opacidades."
r = roteador.ia_no_texto(RX, "", "", None, "descreva consolidação no lobo inferior direito")
confere("RX com raciocínio: não vai para o Luna da linha 'Só formatar'",
        VISTO.get("corpo", {}).get("model") == "gpt-6-sol", VISTO.get("corpo", {}).get("model"))
ro = nuvem.rota("LAUDO NA TELA:\n" + RX, nuvem.config(), "laudo", analise=True)
confere("e não cai em 'só formatar'", ro["modo"] == "laudo" and ro["regra"] == "raciocinio", repr(ro))
ro = nuvem.rota("LAUDO NA TELA:\n" + RX, nuvem.config(), "laudo")
confere("sem raciocínio, o RX continua no Luna só formatando", ro["modelo"] == "gpt-6-luna" and ro["modo"] == "formatar",
        repr(ro))

# tela vazia sem nome de exame: o tipo vem do ditado (e não das regras do DESCREVA)
p = ("REGRAS ... na TC, atenuação; na radiografia, opacidade\n\nDITADO DO RADIOLOGISTA:\n"
     "raio x mostrando fratura do arco costal\n\nLAUDO NA TELA:\n(vazia, sem máscara)")
confere("tela vazia: o tipo do exame vem do ditado", nuvem.tipo_exame(p) == "rx", nuvem.tipo_exame(p))
p2 = p.replace("raio x mostrando fratura do arco costal", "fratura do arco costal")
confere("e as palavras das regras não contam", nuvem.tipo_exame(p2) == "", nuvem.tipo_exame(p2))

VISTO.clear()
r = roteador.ia_no_texto("", "", "", None, "derrame pleural bilateral pequeno à direita")
pedido, _s = pedido_e_sistema()
confere("sem nome de exame: nenhuma máscara aberta, a tela vai vazia",
        "(vazia, sem máscara)" in tela(pedido) and "TOMOGRAFIA" not in tela(pedido).upper(), tela(pedido)[:200])

# 6. sem ditado nada muda
VISTO.clear()
r = roteador.ia_no_texto(LAUDO, "", "", None)
pedido, _s = pedido_e_sistema()
confere("sem ditado: o pedido é o de sempre", pedido.startswith("LAUDO NA TELA:\n") and "DESCREVA" not in pedido
        and "DITADO DO RADIOLOGISTA" not in pedido, pedido[:120])
confere("folha vazia e sem ditado: recusa", roteador.ia_no_texto("", "", "", None, "")["motivo"] == "texto_vazio")
tudo = io.open(nuvem.LOG, encoding="utf-8").read()
confere("o log não guarda o ditado", "derrame" not in tudo and "esteatose" not in tudo and "consolida" not in tudo,
        tudo[-300:])

# a rota do roteador leva o "ditado" do app
fonte = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteador.py"), encoding="utf-8").read()
confere("POST /v1/ia passa o 'ditado' adiante", 'corpo.get("ditado") or ""' in fonte)

print()
print("raciocínio: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
