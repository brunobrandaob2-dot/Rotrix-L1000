# -*- coding: utf-8 -*-
"""Testes do RX literal (python testar_rx_literal.py). Sem internet, sem chave.

Cada caso: o ditado, frases que TÊM de estar na análise e frases que NÃO
podem estar (a normal trocada, conclusão que o médico não ditou, lacunas)."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador as r  # noqa: E402

CASOS = [
    ("raio x de tórax realizado no leito, com tubo orotraqueal, sonda enteral, cateter venoso central "
     "à direita, opacidades pulmonares bilaterais, dreno de tórax à direita",
     ["Tubo orotraqueal.", "Sonda enteral.", "Cateter venoso central à direita.", "Dreno de tórax à direita.",
      "Opacidades pulmonares bilaterais.", "RADIOGRAFIA DO TÓRAX NO LEITO"],
     ["Sonda ventral", "Campos pulmonares sem opacidades", "[em posição adequada", "___", "não encontrado"]),
    ("raio x de tórax com opacificação da base pulmonar direita e obliteração do seio costofrênico esquerdo",
     ["Opacificação da base pulmonar direita.", "Obliteração do seio costofrênico esquerdo."],
     ["derrame", "Seios costofrênicos livres", "Campos pulmonares sem opacidades"]),
    ("raio x da coluna lombar com osteófitos marginais incipientes",
     ["Osteófitos marginais incipientes.", "Corpos vertebrais com altura preservada"],
     ["espondilose", "Espondilose", "___"]),
    ("raio x da coluna lombar com osteófitos marginais proeminentes, redução dos espaços discais inferiores "
     "e artrose interapofisária L5 S1",
     ["Osteófitos marginais proeminentes.", "Redução dos espaços discais inferiores.",
      "Artrose interapofisária em L5-S1."],
     ["Espaços discais preservados", "Elementos posteriores preservados", "___"]),
    ("raio x do cavum com discreto aumento de partes moles na região da adenoide, diminuindo a coluna de ar",
     ["Discreto aumento de partes moles na região da adenoide, diminuindo a coluna de ar."],
     ["Tecido adenoideano de dimensões normais", "Coluna aérea da rinofaringe preservada", "["]),
    ("raio x de joelho direito com gonartrose do compartimento medial",
     ["Gonartrose do compartimento medial.", "JOELHO DIREITO"],
     ["Espaços articulares preservados", "Kellgren"]),
    ("raio x de joelho direito, descrever gonartrose do compartimento medial",
     ["Artrose femorotibial medial do joelho"], ["[femorotibial medial/"]),
    ("raio x de joelho esquerdo com artrose tricompartimental e joelho em varo",
     ["Artrose tricompartimental.", "Joelho em varo."], ["Alinhamento articular preservado"]),
    ("raio x do tornozelo direito com entesopatia calcânea posterior",
     ["Entesopatia calcânea posterior.", "Demais partes moles sem alterações."], []),
    ("raio x do tornozelo esquerdo com fratura oblíqua do maléolo lateral",
     ["Fratura oblíqua do maléolo lateral."], ["Weber", "Não há sinais de fraturas"]),
    ("raio x da bacia com coxartrose bilateral",
     ["Coxartrose bilateral."], ["Kellgren", "[superolateral", "Espaços articulares coxofemorais preservados"]),
    ("raio x de tórax com alterações crônicas",           # rótulo: mantém a máscara pronta
     ["Acentuação difusa da trama broncovascular"], []),
    ("raio x de tórax sem sinais de pneumotórax",
     ["Sem sinais de pneumotórax.", "Seios costofrênicos livres."], []),
    ("raio x de fêmur direito com fratura da diáfise",
     ["RADIOGRAFIA DO FÊMUR DIREITO", "Fratura da diáfise."], ["CRÂNIO"]),
    ("raio x de tórax com marcapasso com eletrodos em átrio e ventrículo direitos",
     ["Marcapasso com eletrodos em átrio e ventrículo direitos."], []),
]


def main():
    falhas = 0
    for dit, tem, nao in CASOS:
        t, o = r.rotear(dit)
        erros = [f"falta: {x}" for x in tem if x not in t] + [f"sobrou: {x}" for x in nao if x in t]
        if erros:
            falhas += 1
            print("FALHOU", dit, "->", o)
            for e in erros:
                print("       ", e)
            print("       " + t.replace("\n", "\n       "))
        else:
            print("ok     ", dit[:70])
    # modo antigo continua disponível: sem RX literal, nada muda fora da radiografia
    t, o = r.rotear("tomografia de abdome normal")
    if not o.startswith(("mascara", "auto")):
        falhas += 1
        print("FALHOU tomografia normal ->", o)
    print()
    print("rx literal: tudo certo" if not falhas else f"rx literal: {falhas} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
