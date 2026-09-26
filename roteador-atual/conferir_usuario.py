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

Correção de 26/09 (tarde)
-------------------------
A primeira versão procurava a disputa dentro do base.sqlite. Só que o
construir_base guarda UM dono por gatilho — o perdedor nem entra no banco —,
então a interseção era sempre vazia e o relatório dizia "nenhum gatilho seu
está na frente" justamente na máquina em que estava. Agora a disputa sai dos
ARQUIVOS (dados/mascaras e dados/mascaras_usuario), com a mesma normalização
do construir_base, e o banco só é usado para confirmar quem sai hoje.
"""

import io
import os
import re
import sys
import unicodedata

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AQUI = os.path.dirname(os.path.abspath(__file__))
RX = re.compile(r"^\*\*TÉCNICA:\*\*\s*(.*)$")


def normalizar(s):
    """Igual ao construir_base.normalizar (lá o módulo compila ao ser importado)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tecnica(texto):
    linhas = (texto or "").split("\n")
    for i, l in enumerate(linhas):
        m = RX.match(l)
        if m:
            fora = [m.group(1).strip()] if m.group(1).strip() else []
            # a TÉCNICA vai até a linha em branco ou a próxima seção — a segunda
            # linha nem sempre começa com "Exame realizado" (a dele de tórax é
            # "Incidência em anteroposterior.")
            j = i + 1
            while j < len(linhas) and linhas[j].strip() and not linhas[j].startswith("**"):
                fora.append(linhas[j].strip())
                j += 1
            return fora
    return []


def ler_mascaras(raiz, prefixo=""):
    """{titulo: (gatilhos_normalizados, corpo)} das MÁSCARAS de uma pasta.
    Bloco (# tipo: bloco), frases.txt e _legado ficam de fora, como no construir_base."""
    fora = {}
    if not os.path.isdir(raiz):
        return fora
    for r, pastas, arquivos in os.walk(raiz):
        pastas[:] = sorted(p for p in pastas if p != "_legado" and not p.startswith("."))
        for nome in sorted(arquivos):
            if not nome.lower().endswith(".txt") or nome.lower() == "frases.txt":
                continue
            caminho = os.path.join(r, nome)
            try:
                bruto = io.open(caminho, encoding="utf-8").read().splitlines()
            except Exception:
                continue
            meta, corpo = {}, []
            for l in bruto:
                m = re.match(r"^#\s*([a-z_]+)\s*:\s*(.*)$", l.strip())
                if m and not corpo:
                    meta[m.group(1)] = m.group(2)
                else:
                    corpo.append(l)
            if meta.get("tipo", "").strip() not in ("", "mascara"):
                continue
            gat = [normalizar(g) for g in (meta.get("gatilhos") or "").split("|")]
            gat = [g for g in gat if g]
            if not gat:
                continue
            tit = prefixo + os.path.relpath(caminho, raiz).replace("\\", "/")[:-4]
            fora[tit] = (gat, "\n".join(corpo).strip())
    return fora


def disputas(dados):
    """Devolve (pares, mortas).
    pares: {(titulo_seu, titulo_rotrix): [gatilhos]} — gatilho que existe nos dois.
    mortas: {titulo_seu: titulo_seu_que_ganha} — máscara sua que nunca sai, porque
            outra máscara SUA tem os mesmos gatilhos todos."""
    suas = ler_mascaras(os.path.join(dados, "mascaras_usuario"), "usuario/")
    rotrix = ler_mascaras(os.path.join(dados, "mascaras"))
    dono_rotrix = {}
    for tit, (gat, _c) in sorted(rotrix.items()):
        for g in gat:
            dono_rotrix.setdefault(g, tit)
    pares, dono_seu = {}, {}
    for tit, (gat, _c) in sorted(suas.items()):
        for g in gat:
            dono_seu.setdefault(g, tit)
            if g in dono_rotrix:
                pares.setdefault((tit, dono_rotrix[g]), [])
                if g not in pares[(tit, dono_rotrix[g])]:
                    pares[(tit, dono_rotrix[g])].append(g)
    mortas = {}
    for tit, (gat, _c) in sorted(suas.items()):
        donos = {dono_seu[g] for g in gat}
        if tit not in donos and len(donos) == 1:
            mortas[tit] = donos.pop()
    # uma sua que nunca sai não disputa nada: tira dos pares
    pares = {k: v for k, v in pares.items() if k[0] not in mortas}
    return pares, mortas, suas, rotrix


def main():
    dados = os.path.join(AQUI, "dados")
    pares, mortas, suas, rotrix = disputas(dados)
    print("máscaras suas: %d   |   do Rotrix: %d   |   pares em disputa: %d"
          % (len(suas), len(rotrix), len(pares)))
    print()

    rotear = None
    try:
        import roteador
        rotear = roteador.rotear
    except Exception as e:
        print("(banco não carregou: %s — mostro só os arquivos)" % type(e).__name__)
        print()

    if not pares:
        print("nenhum gatilho seu está na frente de máscara do Rotrix.")
    else:
        print("=" * 74)
        print("  ONDE A SUA MÁSCARA GANHA — e o que o Rotrix diria no lugar")
        print("=" * 74)
    for (tit_u, tit_r), gatilhos in sorted(pares.items()):
        print()
        print("SUA:    %s" % tit_u)
        print("Rotrix: %s" % tit_r)
        print("gatilhos: %s%s" % (", ".join(gatilhos[:6]),
                                  "  (+%d)" % (len(gatilhos) - 6) if len(gatilhos) > 6 else ""))
        if rotear:
            try:
                _t, origem = rotear(gatilhos[0])
                print("   sai hoje: %s" % origem)
            except Exception as e:
                print("   (não consegui rotear: %s)" % type(e).__name__)
        tec_u = tecnica(suas[tit_u][1])
        tec_r = tecnica(rotrix[tit_r][1])
        if tec_u == tec_r:
            print("   TÉCNICA: igual nas duas.")
            continue
        print("   TÉCNICA da sua:")
        for l in (tec_u or ["(sem TÉCNICA)"]):
            print("      %s" % l)
        print("   TÉCNICA da máscara do Rotrix:")
        for l in (tec_r or ["(sem TÉCNICA)"]):
            print("      %s" % l)

    if mortas:
        print()
        print("=" * 74)
        print("  MÁSCARAS SUAS QUE NUNCA SAEM (outra sua tem os mesmos gatilhos)")
        print("=" * 74)
        for m, dono in sorted(mortas.items()):
            print("   %s   -> quem sai é %s" % (m, dono))

    print()
    print("=" * 74)
    print("  O QUE FAZER — nada é automático, a máscara é sua")
    print("=" * 74)
    print("  1. deixar como está  -> o laudo sai com a SUA técnica, como hoje")
    print("  2. ajustar a sua     -> abrir a máscara em Máscaras > Minhas e trocar")
    print("                          só a linha da TÉCNICA")
    print("  3. usar a do Rotrix  -> tirar a sua máscara daquela região da pasta")
    print()
    print("  As máscaras suas ficam em:")
    print("     %s" % os.path.join(dados, "mascaras_usuario"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
