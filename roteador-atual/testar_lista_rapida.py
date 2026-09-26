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
 10-13. revisão independente de 26/09: pedido simultâneo, chave trocada no meio da
     busca, "research" não é "search", economia do provedor da ROTA, regra
     "Demais exames" e botão da barra mandam, gravação simultânea do cache
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

    # 10. revisão de 26/09: pedido SIMULTÂNEO sem nada para mostrar espera a mesma busca
    roteador._esquecer_listas()
    CONFIG["modelos_vistos"] = {}
    RESPOSTA["openai"] = "ok"
    ATRASO.update(anthropic=1.0, openai=1.0)
    CHAVE.update(anthropic="k-ant-9", openai="k-oai-9")
    saida = {}
    th = threading.Thread(target=lambda: saida.update(a=roteador.ia_modelos()))
    th.start()
    time.sleep(0.2)
    rb = roteador.ia_modelos()
    th.join()
    confere("2o pedido simultâneo, sem lista guardada, não volta vazio",
            len(rb.get("modelos", [])) >= 3 and rb.get("ok"), repr(rb)[:160])

    # 11. chave trocada com busca da chave velha no ar: busca de novo, e a velha não vale
    ATRASO.update(anthropic=0.0, openai=1.2)
    CHAVE["openai"] = "k-oai-10"
    roteador._esquecer_listas()
    th = threading.Thread(target=roteador.ia_modelos)
    th.start()
    time.sleep(0.1)                       # busca com k-oai-10 no ar
    CHAVE["openai"] = "k-oai-11"
    RESPOSTA["openai"] = "401"            # a chave nova é recusada
    ATRASO["openai"] = 0.1
    antes = len(IDAS)
    r = roteador.ia_modelos()
    th.join()
    time.sleep(1.3)
    confere("chave trocada durante a busca: busca de novo com a chave nova",
            IDAS[antes:].count("openai") == 1, repr(IDAS[antes:]))
    r = roteador.ia_modelos()
    confere("...e o 401 da chave nova aparece (a lista da chave velha não o esconde)",
            "http_401" in str((r.get("falhas") or {}).get("openai", "")), repr(r.get("falhas")))
    RESPOSTA["openai"] = "ok"
finally:
    n.config, n.provedores_com_chave, n.modelos, n.gravar_config, n.chave_e_origem = orig
    roteador._esquecer_listas()

# 7b. filtro: "search" como palavra, não dentro de "research"
confere("sonar-deep-research (texto) fica; gpt-4o-search-preview sai",
        roteador._de_texto({"id": "perplexity/sonar-deep-research"})
        and not roteador._de_texto({"id": "gpt-4o-search-preview"}))

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
    # 12. revisão 26/09: a rota vai para a OpenAI -> o barato vem da lista da OpenAI
    n._gravar_cache_modelos("anthropic", ["claude-haiku-4-5-20251001", "claude-sonnet-5"])
    n._gravar_cache_modelos("openai", ["gpt-5.6-luna", "gpt-5.6-terra"])
    confere("economia: barato da OpenAI quando a rota é OpenAI (id claude na OpenAI = 404)",
            n.modelo_barato(ce, "openai") == "gpt-5.6-luna", repr(n.modelo_barato(ce, "openai")))
    ce2 = dict(ce, ia_por_exame={"padrao": "openai:gpt-5.6-terra"}, economizar=True)
    r = n.rota("corrige isso", ce2, "laudo")
    confere("regra 'Demais exames' escrita por ele não é trocada pela economia",
            r["provedor"] == "openai" and r["modelo"] == "gpt-5.6-terra", repr(r))
    r = n.rota("corrige isso", n.com_modelo(dict(ce, economizar=True), "claude-opus-5-5"), "laudo")
    confere("botão da barra manda: Opus escolhido não vira Haiku",
            r["modelo"] == "claude-opus-5-5" and r["regra"] != "economia", repr(r))
    r = n.rota("corrige isso", dict(ce, economizar=True), "laudo")
    confere("sem botão e sem regra (comando falado), a economia continua valendo",
            r["regra"] == "economia" and r["modelo"] == "claude-haiku-4-5-20251001", repr(r))

    # 13. duas threads gravando o cache de ids ao mesmo tempo não perdem provedor
    def _grava(nome, ids):
        for _ in range(40):
            n._gravar_cache_modelos(nome, ids[::-1])
            n._gravar_cache_modelos(nome, ids)
    t1 = threading.Thread(target=_grava, args=("anthropic", ["claude-haiku-4-5-20251001", "claude-x"]))
    t2 = threading.Thread(target=_grava, args=("openai", ["gpt-5.6-luna", "gpt-y"]))
    t1.start(); t2.start(); t1.join(); t2.join()
    confere("gravação simultânea do cache: os dois provedores ficam",
            n._modelos_conhecidos("anthropic") and n._modelos_conhecidos("openai"))
finally:
    n.CACHE_MODELOS = guarda

print()
print("lista rápida de modelos: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
