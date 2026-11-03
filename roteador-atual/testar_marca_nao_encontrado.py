# -*- coding: utf-8 -*-
"""Achado ditado que não casou com bloco NÃO pode sumir do laudo.   python testar_marca_nao_encontrado.py

03/11: o achado sem bloco entra como "[não encontrado no banco — completar: …]", e o modo
genérico (rotear) apagava essa linha como se fosse lacuna. "angio de aorta abdominal e
ilíacas com aneurisma de 4,5 cm" saía como exame normal; "TC de crânio de idoso com cisto
coloide de 8 mm" saía sem o cisto. A marca é aviso do sistema: tem de chegar na tela.
"""
import contextlib
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with contextlib.redirect_stdout(io.StringIO()):
    import roteador  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


def rotear(f):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return roteador.rotear(f)


# 1) o modo genérico preserva a marca e continua tirando lacuna de verdade
marca = "[não encontrado no banco — completar: Cisto coloide de 8 mm.]"
txt = "**ANÁLISE:**\nRins:  sem alterações.\n" + marca + "\nBaço:  medindo ___ cm, de contornos regulares."
g = roteador.generalizar(txt)
confere("generalizar mantém a marca de achado não encontrado", marca in g, repr(g))
confere("generalizar continua tirando a lacuna ___", "___" not in g, repr(g))
confere("sem acento também ('nao encontrado')", "[nao encontrado no banco — completar: X.]" in
        roteador.generalizar("[nao encontrado no banco — completar: X.]"))

# 2) de ponta a ponta: o achado ditado chega no laudo final
for ditado, palavra in (("tomografia de abdome com cisto coloide de 8 mm", "coloide"),
                        ("angio de aorta com cisto coloide de 8 mm", "coloide")):
    t, origem = rotear(ditado)
    confere("achado sem bloco chega no laudo: " + ditado,
            palavra in t.lower() and "não encontrado" in t, origem)

# 3) a mesma frase sem o aviso no começo continua sendo lacuna (não virou exceção geral)
g3 = roteador.generalizar("Pleura:  derrame pleural, de [pequeno/moderado] volume.")
confere("colchete comum continua lacuna", "[pequeno/moderado]" not in g3 and "derrame pleural" in g3, repr(g3))

if falhas:
    print("\n%d falha(s)" % len(falhas))
    sys.exit(1)
print("\nok: %d conferências" % 6)
