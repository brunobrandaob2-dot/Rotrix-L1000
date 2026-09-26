# -*- coding: utf-8 -*-
"""Quais máscaras SUAS estão na frente das do Rotrix — e o que muda por causa disso.

    python conferir_usuario.py

Por que existe
--------------
26/09: o testar_tecnica_rx falhou na máquina dele em tórax, tornozelo e ombro.
Não era o banco: são as máscaras DELE (dados/mascaras_usuario) ganhando o
gatilho. Isso é o desenho certo — máscara dele manda — mas tem um efeito que
ninguém via: as incidências de TÉCNICA que ele ditou em 25/09 entraram nas
máscaras do Rotrix e NÃO chegam no laudo dele, porque a dele vem na frente.

Este relatório mostra, lado a lado, a TÉCNICA que ele usa hoje e a que o Rotrix
passou a ter. Não muda nada: quem decide é ele.
"""

import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador

AQUI = os.path.dirname(os.path.abspath(__file__))
RX = re.compile(r"^\*\*TÉCNICA:\*\*\s*(.*)$")


def tecnica(texto):
    linhas = (texto or "").split("\n")
    for i, l in enumerate(linhas):
        m = RX.match(l)
        if m:
            fora = [m.group(1).strip()]
            j = i + 1
            while j < len(linhas) and linhas[j].startswith("Exame realizado"):
                fora.append(linhas[j].strip())
                j += 1
            return fora
    return []


def main():
    # gatilho -> (titulo do usuario, titulo do rotrix)
    do_usuario, do_rotrix = {}, {}
    for t, g, tit, txt, sec, con in roteador.BANCO.itens:
        if t != "mascara" or not g:
            continue
        (do_usuario if tit.startswith("usuario/") else do_rotrix).setdefault(g, tit)

    disputados = sorted(set(do_usuario) & set(do_rotrix))
    print("máscaras suas: %d gatilhos   |   do Rotrix: %d   |   disputados: %d"
          % (len(do_usuario), len(do_rotrix), len(disputados)))
    print()

    if not disputados:
        print("nenhum gatilho seu está na frente de máscara do Rotrix.")
        return 0

    # agrupa por par de máscaras, para não repetir o mesmo caso 20 vezes
    pares = {}
    for g in disputados:
        pares.setdefault((do_usuario[g], do_rotrix[g]), []).append(g)

    print("=" * 74)
    print("  ONDE A SUA MÁSCARA GANHA — e o que o Rotrix diria no lugar")
    print("=" * 74)
    for (tit_u, tit_r), gatilhos in sorted(pares.items()):
        print()
        print("SUA:    %s" % tit_u)
        print("Rotrix: %s" % tit_r)
        print("gatilhos: %s%s" % (", ".join(gatilhos[:6]),
                                  "  (+%d)" % (len(gatilhos) - 6) if len(gatilhos) > 6 else ""))
        try:
            t_u, _o = roteador.rotear(gatilhos[0])
        except Exception as e:
            print("   (não consegui rotear: %s)" % type(e).__name__)
            continue
        tec_u = tecnica(t_u)
        # a do Rotrix: pega o texto da máscara dele direto do banco
        tec_r = []
        for t, g, tit, txt, sec, con in roteador.BANCO.itens:
            if tit == tit_r:
                tec_r = tecnica(txt)
                break
        if tec_u == tec_r:
            print("   TÉCNICA: igual nas duas.")
            continue
        print("   TÉCNICA que sai hoje (a sua):")
        for l in (tec_u or ["(sem TÉCNICA)"]):
            print("      %s" % l)
        print("   TÉCNICA da máscara do Rotrix:")
        for l in (tec_r or ["(sem TÉCNICA)"]):
            print("      %s" % l)

    print()
    print("=" * 74)
    print("  O QUE FAZER — nada é automático, a máscara é sua")
    print("=" * 74)
    print("  1. deixar como está  -> o laudo sai com a SUA técnica, como hoje")
    print("  2. ajustar a sua     -> abrir a máscara em Máscaras > Minhas e trocar")
    print("                          só a linha da TÉCNICA")
    print("  3. usar a do Rotrix  -> apagar (ou renomear) a sua máscara daquela região")
    print()
    print("  As máscaras suas ficam em:")
    print("     %s" % os.path.join(AQUI, "dados", "mascaras_usuario"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
