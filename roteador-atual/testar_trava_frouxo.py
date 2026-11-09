# -*- coding: utf-8 -*-
"""Trava do gatilho sem nome de exame (python testar_trava_frouxo.py).

Auditoria de 06/11: os atalhos curtos das máscaras dele ("joelho direito", "lombar 3")
eram alcançados pela cobertura e pelo difuso — "dor no joelho direito" abria a
RADIOGRAFIA DO JOELHO e "dor lombar há três meses" a coluna lombar GRAU 3. Opção A
(08/11): ele mantém os atalhos; o roteador só os abre por igualdade ou pelo início do
ditado. O banco do CI não tem as máscaras dele: o teste injeta dois atalhos falsos."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador as r  # noqa: E402

TXT = "**RADIOGRAFIA DO JOELHO {LADO|DIREITO/ESQUERDO}**\n\n**ANÁLISE:**\nTeste."
FALSOS = [
    ("mascara", "joelho direito", "usuario/rx/joelho/teste_atalho", TXT, "", ""),
    ("mascara", "lombar tres", "usuario/rx/coluna_lombar/teste_grau_3", TXT, "", ""),
    ("mascara", "mao direita dois", "usuario/rx/mao/teste_grau_2", TXT, "", ""),
]
FALSOS_TIT = {f[2] for f in FALSOS}


def main():
    falhas = []
    antes = list(r.BANCO.itens)
    r.BANCO.itens = FALSOS + antes
    try:
        def tit(ditado):
            return r.BANCO.buscar2(r.normalizar(ditado))[0]

        # o atalho continua funcionando quando é ELE o ditado (ou o começo dele)
        for dit, alvo in [("joelho direito", "usuario/rx/joelho/teste_atalho"),
                          ("lombar três", "usuario/rx/coluna_lombar/teste_grau_3"),
                          ("mão direita dois", "usuario/rx/mao/teste_grau_2"),
                          ("joelho direito com derrame", "usuario/rx/joelho/teste_atalho")]:
            if tit(dit) != alvo:
                falhas.append("atalho parou: %r -> %r (esperado %s)" % (dit, tit(dit), alvo))
        # frase que só CONTÉM a anatomia não abre o atalho
        for dit in ["dor no joelho direito", "paciente com dor no joelho direito",
                    "dor lombar há três meses", "trauma na mão direita dois dias atrás",
                    "edema no joelho direito e no tornozelo"]:
            if tit(dit) in FALSOS_TIT:
                falhas.append("texto livre abriu atalho: %r -> %s" % (dit, tit(dit)))
        # a regra só vale para gatilho SEM palavra de exame
        for g, esperado in [("lombar 2", True), ("joelho direito", True),
                            ("raio x de joelho direito 2", False), ("tc de joelho", False)]:
            if r._gatilho_frouxo(g) is not esperado:
                falhas.append("_gatilho_frouxo(%r) devia ser %s" % (g, esperado))
        # RX literal: "raio x de tornozelo direito 2" — lado + grau não é achado; a máscara do
        # grau fica (a normal DELE do tornozelo, mesma categoria, roubava o ditado)
        for resto, esperado in [("direito 2", True), ("esquerda quatro", True), ("3", True),
                                ("com fratura", False), ("2 com derrame", False), ("direito", False)]:
            if bool(r._SO_LADO_E_GRAU.fullmatch(resto)) is not esperado:
                falhas.append("_SO_LADO_E_GRAU(%r) devia ser %s" % (resto, esperado))
        # o que ele aprovou por escrito continua livre (nome de exame dito sem modalidade)
        ap = sorted(r._aprovados_flex())
        if ap and r._gatilho_frouxo(ap[0]):
            falhas.append("gatilho aprovado ficou travado: %r" % ap[0])
    finally:
        r.BANCO.itens = antes

    for f in falhas:
        print("FALHOU", f)
    print()
    print("trava do gatilho frouxo: tudo certo" if not falhas else "trava: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
