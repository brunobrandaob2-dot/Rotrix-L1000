# -*- coding: utf-8 -*-
"""A lista de modelos da barra do Laudo responde antes de o app desistir.

    python testar_lista_rapida.py

26/09 (fim da tarde): "não consigo trocar as IAs lá na página de laudo". O app
espera 2,5 s por /v1/ia/modelos; o roteador perguntava Anthropic (1,6 s) e
OpenAI (2,1 s) um depois do outro, na hora, a cada pedido: ~4 s. A lista
chegava vazia e a barra ficava presa no modelo do config. Este teste exige:
  1. com os dois provedores lentos, a 1a resposta sai em menos de 2,2 s
  2. provedor só LENTO não vira "falha" (não acende alarme falso na tela)
  3. a busca termina por trás: a 2a resposta traz os dois, na hora
  4. dentro da validade, nenhuma nova ida à API
  5. modelos_vistos só é regravado quando a lista muda
  6. chave trocada descarta a lista da memória
  7. 401 aparece em "falhas" e não é repetido a cada pedido
  8. modelo que não escreve texto (embedding, áudio, imagem) não entra na barra
  9. o modelo barato da economia não some quando outro provedor lista depois
Sem rede e sem tocar no config.json de verdade.
"""
import io
import os
import sys
import tempfile
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador  # noqa: E402

n = roteador.nuvem
falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


CONFIG = {"provedor": "anthropic", "modelo": "claude-sonnet-5", "modelos_vistos": {}}
GRAVOU = []
IDAS = []
ATRASO = {"anthropic": 1.6, "openai": 2.1}
RESPOSTA = {"openai": "ok"}
CHAVE = {"anthropic": "k-ant-1", "openai": "k-oai-1"}
_trava = threading.Lock()

ANT = [{"id": "claude-haiku-4-5", "nome": "Haiku 4.5"}, {"id": "claude-opus-5-5", "nome": "Opus 5.5"},
       {"id": "claude-sonnet-5", "nome": "Sonnet 5"}]
OAI = [{"id": x, "nome": x} for x in ("gpt-5.6-luna", "gpt-5.6-terra", "o3", "text-embedding-3-large",
                                        "whisper-1", "gpt-image-1", "tts-1", "davinci-002",
                                        "omni-moderation-latest", "gpt-realtime")]


def falso_modelos(c=None, nome=None, timeout=12):
    with _trava:
        IDAS.append(nome)
    time.sleep(ATRASO.get(nome, 0))
    if nome == "openai" and RESPOSTA["openai"] == "401":
        return {"ok": False, "motivo": "http_401", "provedor": nome, "modelos": []}
    return {"ok": True, "provedor": nome, "modelos": list(ANT if nome == "anthropic" else OAI)}


def falso_gravar(d):
    with _trava:
        GRAVOU.append(sorted(d))
        CONFIG.update(d)
    return True


orig = (n.config, n.provedores_com_chave, n.modelos, n.gravar_config, n.chave_e_origem)
n.config = lambda: dict(CONFIG)
n.provedores_com_chave = lambda c=None: ["anthropic", "openai"]
n.modelos = falso_modelos
n.gravar_config = falso_gravar
n.chave_e_origem = lambda c, nome: (CHAVE.get(nome, ""), "arquivo:chave_%s.txt" % nome)
roteador._esquecer_listas()
try:
    # 1 e 2
    t0 = time.time()
    r = roteador.ia_modelos()
    dt = time.time() - t0
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("1a resposta com os dois lentos sai antes de 2,2 s (o app desiste em 2,5)", dt < 2.2, "%.2f s" % dt)
    confere("a Anthropic (1,6 s) já vem", "claude-sonnet-5" in ids, repr(ids))
    confere("OpenAI só lenta NÃO vira falha", "openai" not in (r.get("falhas") or {}), repr(r.get("falhas")))
    confere("...e a resposta diz que ela ainda está chegando", "openai" in (r.get("atualizando") or []),
            repr(r.get("atualizando")))

    # 3
    time.sleep(0.6)
    t0 = time.time()
    r = roteador.ia_modelos()
    dt = time.time() - t0
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("2a resposta sai na hora (< 0,2 s)", dt < 0.2, "%.2f s" % dt)
    confere("2a resposta já tem a OpenAI, prefixada", "openai:gpt-5.6-terra" in ids, repr(ids)[:200])
    confere("2a resposta sem falha nenhuma", not r.get("falhas"), repr(r.get("falhas")))

    # 8
    confere("embedding/áudio/imagem/legado fora da barra",
            not any(x in i for i in ids for x in ("embedding", "whisper", "image", "tts", "davinci",
                                                   "moderation", "realtime")), repr(ids))
    confere("modelos de texto da OpenAI ficam", "openai:o3" in ids and "openai:gpt-5.6-luna" in ids)

    # 4 e 5
    antes = len(IDAS)
    for _ in range(5):
        roteador.ia_modelos()
    confere("dentro da validade, nenhuma ida nova à API", len(IDAS) == antes, "%d idas" % (len(IDAS) - antes))
    confere("modelos_vistos gravado uma vez por provedor, não a cada pedido", len(GRAVOU) == 2,
            "%d gravações" % len(GRAVOU))

    # 6
    CHAVE["openai"] = "k-oai-2"
    ATRASO["openai"] = 0.1
    antes = len(IDAS)
    r = roteador.ia_modelos()
    confere("chave da OpenAI trocada: a lista é buscada de novo", IDAS[antes:].count("openai") == 1,
            repr(IDAS[antes:]))

    # 6b. OpenAI lenta de novo (chave nova, API demorando): quem pergunta durante a
    # busca não espera outra vez — sem internet, cada volta à tela custaria 1,8 s
    CHAVE["openai"] = "k-oai-lenta"
    ATRASO["openai"] = 2.5
    t0 = time.time()
    roteador.ia_modelos()
    d1 = time.time() - t0
    t0 = time.time()
    r = roteador.ia_modelos()
    d2 = time.time() - t0
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("busca lenta: 1o pedido espera só o prazo", d1 < 2.2, "%.2f s" % d1)
    confere("busca lenta: quem pergunta durante ela não espera de novo", d2 < 0.2, "%.2f s" % d2)
    confere("busca lenta: a lista guardada da OpenAI continua na barra, sem alarme",
            "openai:gpt-5.6-terra" in ids and "openai" not in (r.get("falhas") or {}), repr(r.get("falhas")))
    time.sleep(2.6)
    ATRASO["openai"] = 0.1

    # 7
    CHAVE["openai"] = "k-oai-3"
    RESPOSTA["openai"] = "401"
    r = roteador.ia_modelos()
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("401 aparece em falhas, com a lista antiga marcada",
            "http_401" in str((r.get("falhas") or {}).get("openai", "")) and
            "lista antiga" in str((r.get("falhas") or {}).get("openai", "")), repr(r.get("falhas")))
    confere("com 401, a Anthropic continua na barra", "claude-sonnet-5" in ids)
    antes = len(IDAS)
    for _ in range(3):
        roteador.ia_modelos()
    confere("401 não é repetido a cada pedido (espera 20 s)", "openai" not in IDAS[antes:], repr(IDAS[antes:]))

    # pedido de um provedor só continua funcionando
    r1 = roteador.ia_modelos("anthropic")
    confere("ia_modelos('anthropic') devolve a lista dele", r1.get("ok") and len(r1.get("modelos", [])) == 3)
finally:
    n.config, n.provedores_com_chave, n.modelos, n.gravar_config, n.chave_e_origem = orig
    roteador._esquecer_listas()

# 9. economia: cada provedor com a sua lista de ids reais
tmp = tempfile.mkdtemp()
guarda = n.CACHE_MODELOS
n.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
try:
    n._gravar_cache_modelos("anthropic", ["claude-haiku-4-5-20251001", "claude-opus-5-5", "claude-sonnet-5"])
    n._gravar_cache_modelos("openai", ["gpt-5.6-luna", "gpt-5.6-terra"])
    ce = {"provedor": "anthropic", "modelo": "claude-sonnet-5"}
    confere("economia: a lista da OpenAI gravada depois não apaga o barato da Anthropic",
            n.modelo_barato(ce) == "claude-haiku-4-5-20251001", repr(n.modelo_barato(ce)))
    io.open(n.CACHE_MODELOS, "w", encoding="utf-8").write(
        '{"provedor": "anthropic", "modelos": ["claude-haiku-4-5-20251001"]}')
    confere("economia: arquivo no formato antigo ainda é lido",
            n.modelo_barato(ce) == "claude-haiku-4-5-20251001", repr(n.modelo_barato(ce)))
    n._gravar_cache_modelos("openai", ["gpt-5.6-luna"])
    confere("economia: formato antigo convertido sem perder a Anthropic",
            n.modelo_barato(ce) == "claude-haiku-4-5-20251001", repr(n.modelo_barato(ce)))
finally:
    n.CACHE_MODELOS = guarda

print()
print("lista rápida de modelos: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
