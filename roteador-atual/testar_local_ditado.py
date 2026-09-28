# -*- coding: utf-8 -*-
"""O local que ele dita entra na frase do banco.

    python testar_local_ditado.py

27/09: ele quer ditar só "descreva <achado> <local>" e receber a frase padrão
na ANÁLISE e a linha da CONCLUSÃO, as duas com o local dito. O bloco de
atelectasia oferece {localizacao|nas bases pulmonares/no lobo médio e na
língula/nos lobos inferiores}: "no lobo superior direito" não é opção e sumia
calado. No "descrever X" da radiografia a aproximação trocava o lobo ditado por
"no lobo médio e na língula". Este teste exige:
  1. local ditado fora das opções entra, com as palavras dele (ANÁLISE e CONCLUSÃO)
  2. local que É opção continua saindo igual
  3. lacuna de local que não é de lugar com preposição (hérnia: central/foraminal) não muda
  4. a aproximação da radiografia não troca mais o lobo
Precisa do banco (construir_base.py). Sem rede.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


P = roteador.preencher
ATEL = "{localizacao|nas bases pulmonares/no lobo médio e na língula/nos lobos inferiores}"
BRONQ = "{localizacao|nos lobos inferiores/nos lobos superiores/no lobo médio e na língula/difusamente}"

confere("lobo ditado fora das opções entra",
        P(ATEL, "atelectasia laminar no lobo superior direito") == "no lobo superior direito",
        P(ATEL, "atelectasia laminar no lobo superior direito"))
confere("'em ambos os campos pulmonares' entra",
        P(ATEL, "atelectasia laminar em ambos os campos pulmonares") == "em ambos os campos pulmonares",
        P(ATEL, "atelectasia laminar em ambos os campos pulmonares"))
confere("segmento do lobo inteiro",
        P(ATEL, "atelectasia no segmento apical do lobo inferior esquerdo") == "no segmento apical do lobo inferior esquerdo",
        P(ATEL, "atelectasia no segmento apical do lobo inferior esquerdo"))
confere("o local para antes de 'sem'",
        P(ATEL, "atelectasia laminar no lobo médio sem distorção") == "no lobo médio",
        P(ATEL, "atelectasia laminar no lobo médio sem distorção"))
confere("opção dita continua igual",
        P(ATEL, "atelectasia laminar nas bases pulmonares") == "nas bases pulmonares")
confere("'em mosaico' não é local",
        P(ATEL, "pavimentação em mosaico") == "[nas bases pulmonares/no lobo médio e na língula/nos lobos inferiores]",
        P(ATEL, "pavimentação em mosaico"))
confere("hérnia (central/foraminal): não mexe",
        P("{localizacao|central/paracentral/foraminal}", "hérnia no lobo superior") ==
        "[central/paracentral/foraminal]")
confere("radiografia (aproximar): não troca o lobo ditado",
        P(BRONQ, "bronquiectasias no lobo superior direito", aproximar=True) == "no lobo superior direito",
        P(BRONQ, "bronquiectasias no lobo superior direito", aproximar=True))

# ponta a ponta: o que ele dita no botão leve (roteador local, sem IA)
if roteador.BANCO.itens:
    for ditado, analise, conclusao in [
        ("tomografia de tórax. descreva atelectasia laminar no lobo superior direito",
         "estrias fibroatelectásicas no lobo superior direito",
         "Atelectasias laminares/estrias fibroatelectásicas no lobo superior direito."),
        ("tomografia de tórax. descreva atelectasia laminar em ambos os campos pulmonares",
         "estrias fibroatelectásicas em ambos os campos pulmonares",
         "Atelectasias laminares/estrias fibroatelectásicas em ambos os campos pulmonares."),
        ("tomografia de tórax. descreva atelectasia laminar nas bases pulmonares",
         "estrias fibroatelectásicas nas bases pulmonares",
         "Atelectasias laminares/estrias fibroatelectásicas nas bases pulmonares."),
    ]:
        out = roteador.rotear(ditado)
        t = out[0] if isinstance(out, tuple) else out
        confere("TC ponta a ponta: " + ditado.split(". ", 1)[1], analise in t and conclusao in t, t[-600:])
    # 27/09 (2): "pavimentação em mosaico" (vidro fosco com septos interlobulares
    # espessados de permeio) NÃO é "atenuação em mosaico" (hipoventilação/hipoperfusão).
    # "pavimentacao" não está no banco e o ouvido a trocava por "movimentacao"; o
    # "em mosaico" que sobrava caía no bloco de atenuação pelo gatilho solto "mosaico".
    confere("o ouvido não troca 'pavimentação' por 'movimentação'",
            "pavimentação" in roteador.ouvido_bruto("descreva pavimentação em mosaico"),
            roteador.ouvido_bruto("descreva pavimentação em mosaico"))
    out = roteador.rotear("tomografia de tórax. descreva pavimentação em mosaico no lobo superior direito")
    t = out[0] if isinstance(out, tuple) else out
    confere("pavimentação em mosaico não vira atenuação/hipoperfusão",
            "hipoperfus" not in t and "atenuação em mosaico" not in t, t[-500:])
    confere("sem bloco próprio: as palavras dele, no parênquima e na conclusão, sem o 'descreva'",
            "Parênquima pulmonar:  pavimentação em mosaico no lobo superior direito." in t
            and "\nPavimentação em mosaico no lobo superior direito." in t and "escreva" not in t, t[-500:])
    out = roteador.rotear("tomografia de tórax. atenuação em mosaico")
    t = out[0] if isinstance(out, tuple) else out
    confere("atenuação em mosaico continua no bloco dela", "hipoperfusão com padrão de atenuação em mosaico" in t)
    # contradição: o achado novo traz "Não há consolidações" e a linha já tem consolidação
    out = roteador.rotear("tomografia de tórax. descreva consolidação no lobo inferior esquerdo. "
                          "descreva atelectasia laminar em ambos os campos pulmonares")
    t = out[0] if isinstance(out, tuple) else out
    par = [l for l in t.split("\n") if l.startswith("Parênquima pulmonar:")]
    confere("consolidação + atelectasia: sem 'Não há consolidações' na mesma linha",
            len(par) == 1 and "consolidação com broncogramas" in par[0] and "Não há consolidações" not in par[0]
            and "Atelectasias laminares e estrias fibroatelectásicas em ambos os campos pulmonares" in par[0],
            par[0] if par else t)
else:
    confere("banco carregado (rode construir_base.py)", False)

print()
print("local ditado: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
