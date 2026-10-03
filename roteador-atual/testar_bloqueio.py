# -*- coding: utf-8 -*-
"""Recusa da triagem: a tela diz O QUE barrou e ONDE; o log registra sem conteúdo.

    python testar_bloqueio.py

03/10, pergunta dele: "pq a nuvem está dizendo que a IA está bloqueada?". Config
certo (ativa, chave, US$ 1,92 de 25), mas a tela mostrava só "a IA não respondeu
(nuvem_bloqueada)" e o nuvem.log não guardava a recusa. Este teste exige:
  1. data completa na folha: recusa, nada vai para a internet, e o motivo diz
     'data completa “12/08/2025” na folha'
  2. no ditado do botão de raciocínio: '... no ditado'
  3. linha "Paciente: FULANO": o motivo mostra só o rótulo, nunca o nome
  4. o motivo continua começando por "nuvem_bloqueada" (o app instalado mostra o
     motivo cru; o AdendoPage e os testes antigos comparam por esse começo)
  5. nuvem.log ganha a linha da recusa só com o NOME do motivo — sem data, sem nome
  6. as regras que o próprio Rotrix põe no pedido (DESCREVA, ROTEADO, IMAGEM) não
     disparam a triagem
Sem internet e sem chave de verdade.
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
import prompts  # noqa: E402

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


SAIU = []


def _falso(req, timeout=None, context=None):
    SAIU.append(req.full_url)
    raise AssertionError("não devia sair nada para a internet")


urllib.request.urlopen = _falso

with io.open(nuvem.CONFIG, "w", encoding="utf-8") as f:
    json.dump({"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol", "limite_mes_usd": 25,
               "ia_por_exame": {"tc": {"provedor": "openai", "modelo": "gpt-6-sol"}}}, f)

LAUDO = ("TOMOGRAFIA COMPUTADORIZADA DO TÓRAX\n\nANÁLISE:\n"
         "Nódulo sólido no lobo superior direito medindo 8 mm, estável em relação ao exame de 12/08/2025.\n\n"
         "CONCLUSÃO:\nNódulo pulmonar estável.")

# 1. data completa na folha
r = roteador.ia_no_texto(LAUDO, "", "", None)
m = r.get("motivo", "")
confere("data na folha: recusa", r.get("ok") is False and m.startswith("nuvem_bloqueada"), repr(r)[:200])
confere("e diz o que e onde", "data completa “12/08/2025” na folha" in m, m)
confere("nada saiu para a internet", not SAIU, repr(SAIU))
confere("o laudo volta intacto", r.get("texto") == LAUDO)
confere("o app recebe a lista", r.get("bloqueio") == [{"onde": "na folha", "motivo": "data completa",
                                                       "trecho": "12/08/2025"}], repr(r.get("bloqueio")))

# 2. no ditado do raciocínio
r = roteador.ia_no_texto(LAUDO.replace(" de 12/08/2025", " anterior"), "", "", None,
                         "descreva comparando com o exame de 03/09/2026")
m = r.get("motivo", "")
confere("data no ditado: '... no ditado'", "data completa “03/09/2026” no ditado" in m and "na folha" not in m, m)

# 3. linha de paciente: só o rótulo
r = roteador.ia_no_texto("Paciente: FULANO BELTRANO DA SILVA\n" + LAUDO.replace(" de 12/08/2025", ""), "", "", None)
m = r.get("motivo", "")
confere("linha de paciente: mostra o rótulo", "linha de identificação do paciente “Paciente:” na folha" in m, m)
confere("e nunca o nome", "FULANO" not in m and "BELTRANO" not in json.dumps(r.get("bloqueio"), ensure_ascii=False))

# CPF: só o rótulo
tr = nuvem.triagem_trechos("cpf 123.456.789-00")
confere("CPF: sem os números", tr and tr[0] == ("CPF", "") and "123" not in nuvem.descrever_bloqueio(tr), repr(tr))

# 4. compatível com quem compara o começo
confere("motivo começa por 'nuvem_bloqueada' (app instalado)", m.startswith("nuvem_bloqueada"))
confere("chamar() continua devolvendo 'nuvem_bloqueada' cru",
        nuvem.chamar("cpf 123.456.789-00", nuvem.config(), modo="laudo")[1] == "nuvem_bloqueada")

# 5. log sem conteúdo
log = io.open(nuvem.LOG, encoding="utf-8").read()
confere("nuvem.log registra a recusa", log.count("bloqueada(") >= 4, log)
confere("com o nome do motivo", "bloqueada(data completa)" in log, log)
confere("sem a data, sem o nome, sem o CPF", "12/08/2025" not in log and "03/09/2026" not in log
        and "FULANO" not in log and "123.456" not in log, log)
confere("a recusa não conta como chamada nas estatísticas do cache",
        nuvem._horas_de_chamada(nuvem.LOG) == [], repr(nuvem._horas_de_chamada(nuvem.LOG)))

# 6. as regras do Rotrix não disparam a triagem
for b in ("DESCREVA", "ROTEADO", "IMAGEM"):
    t = prompts.bloco(b) or ""
    confere("bloco %s não dispara a triagem" % b, t and not nuvem.triagem(t), repr(nuvem.triagem_trechos(t)))

# o caminho completo do raciocínio, sem identificador, não é barrado
VISTO = {}


def _ok(req, timeout=None, context=None):
    VISTO["corpo"] = json.loads(req.data.decode("utf-8"))

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass
    return _R(json.dumps({"choices": [{"message": {"content": "LAUDO PRONTO"}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 200}}).encode())


urllib.request.urlopen = _ok
for roteado in (False, True):
    r = roteador.ia_no_texto("", "", "", None, "tomografia de tórax. derrame pleural bilateral, pequeno à direita",
                             roteado)
    confere("raciocínio limpo passa (roteador %s)" % ("ligado" if roteado else "desligado"),
            r.get("ok") is True, repr(r)[:200])

print()
print("bloqueio: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
