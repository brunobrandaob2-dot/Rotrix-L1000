# -*- coding: utf-8 -*-
"""O roteamento nao pode ficar mais lento, e nao pode mudar de resposta.

    python testar_perf_roteador.py                  confere o teto de tempo
    python testar_perf_roteador.py <roteador_velho>  compara resposta com outra versao

Por que existe
--------------
Em 25/09 ele perguntou se o Haiku conseguiria buscar no banco "na mesma velocidade que
a gente faria por gatilhos". Fui medir e a premissa nao se sustentava: o caminho local
levava ~1.050 ms num ditado de quatro achados — 85% disso em difflib.get_close_matches,
chamado 92 MIL vezes por ditado, porque a mesma palavra de gatilho era comparada de novo
a cada um dos 25 mil itens do banco. Com cache por palavra (_casador) caiu para ~230 ms.

Este teste tranca as duas coisas que importam nisso:
  1. TETO DE TEMPO: ditado dificil (exame + varios achados) tem de rotear abaixo do teto.
  2. RESPOSTA IDENTICA: otimizacao em roteador clinico que muda uma decisao de
     roteamento e defeito, nao melhoria. Com o caminho de uma versao anterior na linha
     de comando, compara ditado por ditado.
"""

import importlib.util
import io
import os
import random
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador

# Teto generoso de proposito: a maquina do CI e mais lenta que a dele, e o objetivo e
# pegar REGRESSAO (voltar para a casa de 1 segundo), nao cravar o numero do dia.
TETO_MS = 600.0
REPETICOES = 3

DUROS = [
    # o ditado que ele usou como exemplo em 25/09
    "tomografia de torax sem contraste, opacidades fibroteleatasicas esparsas, "
    "ateromas calcificados na horta e ramos, aumento da area cardiaca e "
    "alteracoes degenerativas na coluna",
    "tomografia de abdome total com esteatose hepatica, calculo na vesicula, "
    "cisto renal simples a direita e alteracoes degenerativas na coluna lombar",
    "tomografia de cranio com avc isquemico no territorio da acm esquerda, "
    "atrofia cortical e microangiopatia",
    "tomografia de torax com enfisema centrolobular, nodulo no lobo superior "
    "direito de 6 mm e linfonodomegalia mediastinal",
    "tomografia de coluna lombar com espondilose, anterolistese degenerativa de "
    "l4 sobre l5 e reducao do canal vertebral",
]

falhas = []


def confere(nome, cond, extra=""):
    print(("ok      " if cond else "FALHOU  ") + nome + (("  " + extra) if extra else ""))
    if not cond:
        falhas.append(nome)


def medir():
    for d in DUROS:                                   # aquece (o app aquece no start)
        roteador.rotear(d)
    t0 = time.perf_counter()
    for _ in range(REPETICOES):
        for d in DUROS:
            roteador.rotear(d)
    return (time.perf_counter() - t0) / (REPETICOES * len(DUROS)) * 1000


def comparar(caminho_velho):
    spec = importlib.util.spec_from_file_location("rot_velho", caminho_velho)
    velho = importlib.util.module_from_spec(spec)
    sys.modules["rot_velho"] = velho
    spec.loader.exec_module(velho)
    # comparacao so vale com o MESMO banco dos dois lados
    if len(velho.BANCO.itens) != len(roteador.BANCO.itens):
        confere("comparacao com %s" % os.path.basename(caminho_velho), False,
                "bancos diferentes (%d x %d): use LAUDO_BASE apontando para o mesmo .sqlite"
                % (len(velho.BANCO.itens), len(roteador.BANCO.itens)))
        return
    random.seed(7)
    casos = random.sample([g for _t, g, *_r in roteador.BANCO.itens], 800) + DUROS + [""]
    dif = [c for c in casos if velho.rotear(c) != roteador.rotear(c)]
    confere("resposta identica a %s em %d ditados" % (os.path.basename(caminho_velho),
                                                      len(casos)),
            not dif, "mudaram: " + "; ".join(c[:40] for c in dif[:5]))


def main():
    print("=== tempo de roteamento (ditado com exame + varios achados) ===")
    ms = medir()
    confere("media abaixo do teto de %.0f ms" % TETO_MS, ms < TETO_MS, "deu %.1f ms" % ms)
    print("        media medida: %.1f ms por ditado" % ms)
    print()
    if len(sys.argv) > 1:
        print("=== resposta identica a versao anterior ===")
        comparar(sys.argv[1])
        print()
    if falhas:
        print("%d FALHA(S): %s" % (len(falhas), "; ".join(falhas)))
        return 1
    print("desempenho do roteador: tudo certo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
