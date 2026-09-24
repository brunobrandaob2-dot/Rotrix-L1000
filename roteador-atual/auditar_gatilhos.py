# -*- coding: utf-8 -*-
"""Audita os gatilhos de MÁSCARA: quais dão para alcançar sem dizer o exame.

Existe porque um ditado de ACHADO puxava máscara inteira de outro exame:
"aorta torácica com calcificações ateromatosas" abria a ANGIOTOMOGRAFIA DA
AORTA. A regra nova do roteador (`_modalidade_compativel`) fecha o caso de quem
NOMEIA a modalidade no gatilho. Sobra a classe que este auditor mede: gatilho de
máscara que não nomeia modalidade nenhuma — esse continua alcançável por uma
frase que só descreve achado.

Uso:
    python3 auditar_gatilhos.py                  # resumo por região
    python3 auditar_gatilhos.py <regiao>         # os gatilhos daquela região
    python3 auditar_gatilhos.py --todos          # tudo, para revisar de uma vez

Saída 1 = tem gatilho frouxo (é o que derruba o CI).
"""
import collections
import io
import os
import sys

import roteador as R

# Nomes de exame que ele fala SEM dizer a modalidade — "escanometria",
# "panorâmica de membros inferiores", "urotc", "escore de cálcio". São exames de
# verdade, não achados: ficam liberados por escrito, um por linha. O que não
# estiver aqui derruba o CI — é isso que impede a brecha de voltar na próxima
# máscara que alguém escrever.
APROVADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "dados", "gatilhos_aprovados.txt")


def aprovados():
    try:
        with io.open(APROVADOS, encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        return set()


def frouxos(ignorar_aprovados=True):
    """[(regiao, titulo, gatilho)] — gatilho de máscara sem palavra de exame."""
    ok = aprovados() if ignorar_aprovados else set()
    fora = []
    for tipo, g, tit, _txt, _sec, _con in R.BANCO.itens:
        if tipo != "mascara" or not g:
            continue
        if R._familias_do_gatilho(g):
            continue                      # nomeia o exame: a regra nova protege
        if g in ok:
            continue                      # nome de exame liberado por ele
        meta = R.BANCO.meta.get(tit, ("", "", "", ""))
        regiao = "%s/%s/%s" % (meta[0] or "?", meta[1] or "?", meta[2] or "?")
        fora.append((regiao, tit, g))
    return fora


def main(argv):
    if "--semear" in argv:
        # grava a lista atual como aprovada. Só na primeira vez, e só depois de
        # ele ler: aprovar sozinho o que eu mesmo escrevi não vale como revisão.
        itens = frouxos(ignorar_aprovados=False)
        linhas = ["# Gatilhos de máscara que NÃO dizem a modalidade e mesmo assim",
                  "# estão liberados: são nomes de exame que o Bruno fala assim.",
                  "# Um por linha. O que não estiver aqui derruba o CI.", ""]
        for regiao in sorted({r for r, _t, _g in itens}):
            linhas.append("# " + regiao)
            for _r, _t, g in sorted((x for x in itens if x[0] == regiao), key=lambda x: x[2]):
                linhas.append(g)
            linhas.append("")
        os.makedirs(os.path.dirname(APROVADOS), exist_ok=True)
        io.open(APROVADOS, "w", encoding="utf-8", newline="\n").write("\n".join(linhas))
        print("gravados %d gatilhos aprovados em %s" % (len(itens), APROVADOS))
        return 0

    itens = frouxos()
    por_regiao = collections.defaultdict(list)
    for regiao, tit, g in itens:
        por_regiao[regiao].append((tit, g))

    alvo = [a for a in argv[1:] if not a.startswith("--")]
    todos = "--todos" in argv

    if alvo or todos:
        chaves = sorted(por_regiao) if todos else \
            [k for k in sorted(por_regiao) if any(a in k for a in alvo)]
        for k in chaves:
            print("\n=== %s  (%d)" % (k, len(por_regiao[k])))
            for tit, g in sorted(por_regiao[k], key=lambda x: x[1]):
                print("  %-58s  %s" % (g[:58], tit.rsplit("/", 1)[-1]))
    else:
        print("gatilhos de máscara: %d" % sum(
            1 for t, g, *_ in R.BANCO.itens if t == "mascara" and g))
        print("frouxos (não dizem o exame): %d, em %d regiões\n"
              % (len(itens), len(por_regiao)))
        for k in sorted(por_regiao, key=lambda x: -len(por_regiao[x])):
            print("  %-46s %4d" % (k, len(por_regiao[k])))
        print("\npara ver uma região:  python3 auditar_gatilhos.py <parte do nome>")

    return 1 if itens else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
