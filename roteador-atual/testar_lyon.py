# -*- coding: utf-8 -*-
"""Protocolo de Lyon estruturado: os números viram o laudo, sempre igual.

    python testar_lyon.py

27/09: ele pediu o Lyon na aba Estruturados, com o passo a passo de cada medida.
Este teste exige:
  1. o caso dele de hoje (joelho direito, tróclea rasa, discreta lateralização,
     TT-TG 16 mm) sai com a redação que ele corrigiu
  2. cada corte do infográfico: sulco 145°, Caton-Deschamps 0,6/1,2, inclinação
     20°, TT-TG 15/20 mm, TT-PCL 24 mm
  3. campo vazio não vira lacuna; linha sem número sai
  4. os dois lados, na ordem da máscara (estrutura por estrutura, direita antes)
  5. sem nada alterado, a frase normal na conclusão
  6. avisos: sulco acima de 145° com tróclea "habitual"/"rasa", TT-TG em cm
  7. pelo roteador (a rota que a aba chama), com o mesmo texto
Sem rede.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lyon  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


def laudo(lado="direito", ossos=None, **valores):
    return lyon.montar({"lado": lado, "valores": valores, "ossos": ossos})


# 1. o caso de hoje
r = laudo(troclea_d="rasa", posicao_d="discreta lateralização", tttg_d="16")
t = r["texto"]
confere("título e técnica do joelho direito",
        t.startswith("**TOMOGRAFIA COMPUTADORIZADA DO JOELHO DIREITO - PROTOCOLO DE LYON**")
        and "aquisições tomográficas do joelho direito conforme protocolo de Lyon" in t, t[:200])
confere("tróclea rasa, sem displasia", "Tróclea femoral direita:  rasa, sem outras alterações morfológicas." in t)
confere("lateralização discreta", "Articulação femoropatelar direita:  discreta lateralização da patela, sem subluxação franca." in t)
confere("TT-TG 16 limítrofe", "Distância TT-TG direita:  16 mm, limítrofe (normal até 15 mm; patológica a partir de 20 mm)." in t)
confere("conclusão como ele escreveu", r["conclusao"] ==
        "Tróclea femoral direita rasa, com discreta lateralização da patela.\nDistância TT-TG direita limítrofe (16 mm).",
        r["conclusao"])
confere("sem TT-PCL medido, a linha não aparece", "TT-PCL" not in t)
confere("nada de lacuna", "___" not in t and "[" not in t and "{" not in t)
confere("estruturas ósseas: a primeira opção da máscara",
        "Estruturas ósseas:  sem fraturas ou lesões ósseas focais evidentes." in t)

# 2. cortes
def conc(**v):
    return laudo(**v)["conclusao"]

confere("TT-TG 15 = normal (não entra na conclusão)", conc(tttg_d="15") == lyon.FRASE_NORMAL)
confere("TT-TG 19,5 = limítrofe", "limítrofe (19,5 mm)" in conc(tttg_d="19,5"))
confere("TT-TG 20 = aumentada", "Distância TT-TG direita aumentada (20 mm)." in conc(tttg_d="20"))
confere("TT-PCL 24 = normal", conc(ttpcl_d="24") == lyon.FRASE_NORMAL)
confere("TT-PCL 25 = aumentada", "Distância TT-PCL direita aumentada (25 mm)." in conc(ttpcl_d="25"))
confere("Caton-Deschamps 1,2 = normal", conc(cd_d="1,2") == lyon.FRASE_NORMAL
        and "(altura normal)" in laudo(cd_d="1,2")["texto"])
confere("Caton-Deschamps 1,3 = patela alta",
        "Patela alta à direita (índice de Caton-Deschamps de 1,3)." in conc(cd_d="1,3"))
confere("Caton-Deschamps 0,5 = patela baixa", "Patela baixa à direita" in conc(cd_d="0.5"))
confere("inclinação 20 = normal", conc(tilt_rel_d="20") == lyon.FRASE_NORMAL)
confere("inclinação 22 = aumentada, com o contraído na análise",
        "Inclinação patelar aumentada à direita (22°)." in conc(tilt_rel_d="22", tilt_con_d="14")
        and "inclinação patelar de 22° com o quadríceps relaxado e de 14° contraído (aumentada"
        in laudo(tilt_rel_d="22", tilt_con_d="14")["texto"])
confere("displasia B", "Displasia troclear tipo B de Dejour à direita." in conc(troclea_d="displasia B")
        and "displasia troclear tipo B de Dejour (ângulo do sulco de 152°)." in
        laudo(troclea_d="displasia B", sulco_d="152")["texto"])
confere("subluxação sem displasia", "Subluxação lateral da patela direita." in conc(posicao_d="subluxação lateral"))

# 3 e 5. normal
r = laudo()
confere("tudo vazio: laudo normal e a frase normal", r["conclusao"] == lyon.FRASE_NORMAL
        and "Tróclea femoral direita:  de morfologia habitual." in r["texto"]
        and "Patela direita:  de morfologia habitual." in r["texto"]
        and "Articulação femoropatelar direita:  patela centrada, sem subluxação." in r["texto"])

# 4. os dois lados
r = laudo("ambos", troclea_d="rasa", tttg_d="16", tttg_e="12", ttpcl_e="26")
linhas = [l for l in r["texto"].split("\n") if ":  " in l and not l.startswith("**")]
ordem = [l.split(":")[0] for l in linhas]
confere("ambos: título e técnica no plural", "DOS JOELHOS - PROTOCOLO DE LYON" in r["texto"]
        and "aquisições tomográficas dos joelhos" in r["texto"])
confere("ordem da máscara: estrutura por estrutura, direita antes",
        ordem == ["Tróclea femoral direita", "Tróclea femoral esquerda", "Patela direita", "Patela esquerda",
                  "Articulação femoropatelar direita", "Articulação femoropatelar esquerda",
                  "Distância TT-TG direita", "Distância TT-TG esquerda", "Distância TT-PCL esquerda",
                  "Estruturas ósseas"], repr(ordem))
confere("conclusão dos dois lados", r["conclusao"].split("\n") == [
    "Tróclea femoral direita rasa.", "Distância TT-TG direita limítrofe (16 mm).",
    "Distância TT-PCL esquerda aumentada (26 mm)."], r["conclusao"])
r = laudo("esquerdo", tttg_d="30", tttg_e="12")
confere("só o esquerdo: o direito digitado não entra", "direit" not in r["texto"].replace("DIREITO", "")
        and "DO JOELHO ESQUERDO" in r["texto"], r["texto"][:300])

# 6. avisos
confere("sulco 150° com tróclea habitual: avisa, não troca",
        any("acima de 145°" in a for a in laudo(sulco_d="150")["avisos"])
        and "de morfologia habitual (ângulo do sulco de 150°)." in laudo(sulco_d="150")["texto"])
confere("TT-TG 1,6: avisa que deve ser mm", any("1,60 cm = 16 mm" in a for a in laudo(tttg_d="1,6")["avisos"]))
confere("número inválido: ignorado, sem quebrar", laudo(tttg_d="abc")["ok"] and "TT-TG" not in laudo(tttg_d="abc")["texto"])
confere("lado desconhecido: recusa", lyon.montar({"lado": "x"})["motivo"] == "lado_desconhecido")
confere("opção de osso da máscara", "Estruturas ósseas:  sem outras alterações ósseas significativas."
        in laudo(ossos="sem outras alterações ósseas significativas")["texto"])

# campos (o que a aba desenha)
c = lyon.campos()
ids = [f["id"] for p in c["passos"] for f in p["campos"]]
confere("campos: os cinco passos e todos os números", [p["id"] for p in c["passos"]] ==
        ["troclea", "patela", "femoropatelar", "tttg", "ttpcl"]
        and set(lyon.NUMEROS) <= set(ids), repr(ids))

# 7. pelo roteador
import roteador  # noqa: E402
r = roteador.estruturados_montar({"tipo": "lyon", "lado": "direito",
                                  "valores": {"troclea_d": "rasa", "posicao_d": "discreta lateralização",
                                              "tttg_d": "16"}})
confere("rota /v1/estruturados com tipo lyon", r.get("ok") and "Distância TT-TG direita" in r.get("texto", ""),
        repr(r)[:200])

print()
print("lyon: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
