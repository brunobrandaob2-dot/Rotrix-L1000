# -*- coding: utf-8 -*-
"""Testes da TC com as palavras do médico (python testar_tc_literal.py).

Regras do Bruno (22/09/2026):
- achado que o banco não tem entra no rótulo da estrutura, com as palavras
  ditas, e a frase normal daquela estrutura sai;
- as estruturas alteradas abrem a análise; as normais vêm abaixo;
- ditado livre sai com maiúscula no início e ponto final."""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador as r  # noqa: E402

# (ditado, rótulo que abre a análise, trechos que têm de estar, trechos que não podem estar)
CASOS = [
    ("Tomografia de abdome total, nódulo hipodenso no segmento VII do fígado medindo 1,2 cm.",
     "Fígado:", ["Fígado:  nódulo hipodenso no segmento VII do fígado medindo 1,2 cm."],
     ["de dimensões normais, contornos regulares e densidade normal", "não encontrado"]),
    ("Tomografia de abdome total, pâncreas com atrofia difusa e calcificações.",
     "Pâncreas:", ["Pâncreas:  pâncreas com atrofia difusa e calcificações."],
     ["Rins:  atrofia", "Vasos:  calcificações"]),
    ("Tomografia de crânio, hematoma subdural à direita com espessura de 8 mm.",
     "Espaços extra-axiais:", ["hematoma subdural à direita com espessura de 8 mm."], ["Sem coleções."]),
    ("tc de torax, derrame pleural a direita, nodulo no lobo superior direito de 8 mm",
     "Parênquima pulmonar:", ["Nódulo no lobo superior direito de 8 mm."],
     ["Demais segmentos sem alterações significativas", "não encontrado"]),
    ("Tomografia de abdome total, esteatose hepática, cálculo na vesícula biliar.",
     "Fígado:", ["compatível com esteatose"], []),
    ("Tomografia de crânio, calcificação da foice.",
     "Calcificações intracranianas:", ["calcificação da foice."], ["sem calcificações de aspecto patológico"]),
]


def primeira_da_analise(t):
    corpo = t.split("**ANÁLISE:**", 1)[-1].strip().split("\n")
    return corpo[0] if corpo else ""


def main():
    falhas = 0
    for dit, abre, tem, nao in CASOS:
        t, o = r.rotear(dit)
        erros = [f"falta: {x}" for x in tem if x not in t] + [f"sobrou: {x}" for x in nao if x in t]
        if not primeira_da_analise(t).startswith(abre):
            erros.append("a análise não abre com %r: %r" % (abre, primeira_da_analise(t)[:60]))
        if erros:
            falhas += 1
            print("FALHOU", dit, "->", o)
            for e in erros:
                print("       ", e)
        else:
            print("ok     ", dit[:70])
    # TC normal: nada muda de lugar
    t, o = r.rotear("tomografia de cranio normal")
    if not primeira_da_analise(t).startswith("Parênquima encefálico:"):
        falhas += 1
        print("FALHOU tc normal mudou a ordem")
    # modalidade: ressonância nunca vira radiografia
    t, o = r.rotear("ressonancia de joelho normal")
    if "RADIOGRAFIA" in t:
        falhas += 1
        print("FALHOU ressonância virou radiografia")
    # ditado livre: maiúscula e ponto final
    t, o = r.rotear("paciente com dor no joelho")
    if not re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ].*\.$", t.strip()):
        falhas += 1
        print("FALHOU texto livre sem maiúscula/ponto:", t)
    print()
    print("tc literal: tudo certo" if not falhas else f"tc literal: {falhas} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
