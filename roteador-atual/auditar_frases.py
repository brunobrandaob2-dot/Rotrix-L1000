# -*- coding: utf-8 -*-
"""Frase quebrada no laudo: procura em TODAS as mascaras, sem chave e sem nuvem.

    python auditar_frases.py            relatorio + falha se piorar
    python auditar_frases.py --lista    so a lista, sem travar

Por que existe
--------------
Em 26/09, escrevendo o bloco de hidrocefalia, vi isto sair de uma mascara do banco:

    "Colo proximal com cm de extensao a partir da arteria renal mais baixa. ."
    "...indice de Evans de,30), sugerindo hidrocefalia de padrao comunicante."
    "Derrame pleural direito de volume."

O caminho: o banco escreve {tamanho}; o preencher() troca por ___ quando ele nao ditou a
medida; o generalizar() tira o ___ — e a UNIDADE, o parenteses de referencia e o
substantivo de medida ficavam para tras. Isso sai em laudo assinado, em achado que nao e
pequeno: aneurisma de aorta, obstrucao intestinal, apendicite, sobrecarga de VD no TEP.

Dois consertos gerais entraram no roteador em 26/09:
  - a lacuna de valor leva com ela a unidade e o "(referencia: ate X cm)";
  - a virgula DENTRO de parenteses nao separa mais pedaco (era ela que cortava
    "(referencia: acima de 4,5 cm)" no meio e deixava ",5 cm)" no laudo).
De 22 linhas quebradas caiu para 15.

As 15 que sobram sao de outra natureza — lacuna DENTRO de lista de opcoes, duas lacunas
na mesma frase, "em {n} parte(s)". Nao tem regex que resolva sem risco de apagar
conteudo: o texto da mascara precisa ser reescrito para um mundo sem lacuna. Este
auditor existe para que esse numero nao volte a subir enquanto isso.
"""

import collections
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador

# Quanto ja se sabe que esta quebrado (26/09). O auditor falha se PASSAR disto.
TETO = 0

PADROES = [
    (re.compile(r"\b(?:com|de|em|ate|até|medindo)\s+(?:de|da|do|a partir|ao|em|no|na)\b",
                re.I), "preposicao sem objeto"),
    (re.compile(r"\b(?:de|com)\s+(?:volume|extens[ãa]o|calibre|di[âa]metro|espessura)\s*[.;,]",
                re.I), "substantivo de medida sem numero"),
    (re.compile(r"\.\s+\."), "frase que ficou vazia"),
    # (?<!\d): "3,0 cm" e texto certo; o defeito e a virgula que abre pedaco, ",5 cm)"
    (re.compile(r"(?<!\d),\d"), "decimal solto"),
    (re.compile(r"\(\s*\)|\(\s*[.;,]"), "parenteses vazio"),
    (re.compile(r"___"), "lacuna sobrando"),
    (re.compile(r"\bparte\(s\)|\bcaso\(s\)|\blado\(s\)"), "plural de lacuna sem numero"),
]


def varrer():
    vistos, achados = set(), []
    for t, g, tit, txt, sec, con in roteador.BANCO.itens:
        if t != "mascara" or tit in vistos:
            continue
        # prescricao e FORMULARIO, nao laudo: o "( )" dela e caixa de marcar, nao
        # parenteses vazio, e ela nunca passa por IA nem por generalizar()
        if tit.startswith("prescricao/"):
            continue
        vistos.add(tit)
        try:
            texto, _o = roteador.rotear(g)
        except Exception as e:
            achados.append(("erro ao rotear (%s)" % type(e).__name__, tit, g[:70]))
            continue
        for ln in (texto or "").split("\n"):
            if ln.startswith("**") or not ln.strip():
                continue
            for rx, nome in PADROES:
                if rx.search(ln):
                    achados.append((nome, tit, ln.strip()[:110]))
                    break
    return vistos, achados


def main():
    vistos, achados = varrer()
    print("mascaras percorridas: %d" % len(vistos))
    print("linhas quebradas: %d  (teto conhecido: %d)" % (len(achados), TETO))
    print()
    for nome, n in collections.Counter(a[0] for a in achados).most_common():
        print("   %-34s %d" % (nome, n))
    print()
    for nome, tit, ln in achados:
        print("  [%s]" % nome)
        print("     %s" % tit)
        print("     %s" % ln)
    print()
    if "--lista" in sys.argv:
        return 0
    if len(achados) > TETO:
        print("PIOROU: %d linhas quebradas, o teto e %d." % (len(achados), TETO))
        print("Ou conserte a mascara, ou baixe o TETO se voce acabou de consertar algo.")
        return 1
    if len(achados) < TETO:
        print("MELHOROU: %d linhas, teto %d. Baixe o TETO no auditar_frases.py para trancar."
              % (len(achados), TETO))
    print("frases do banco: dentro do teto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
