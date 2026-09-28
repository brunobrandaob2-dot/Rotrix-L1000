# -*- coding: utf-8 -*-
"""Protocolo de Lyon estruturado, na máscara DELE (28/09).

    python testar_lyon.py

28/09: ele mandou a máscara do Lyon que quer nos estruturados — texto corrido
(patela, fêmur/tíbia, espaços, derrame) e uma tabela de medidas por joelho com
o valor normal ao lado. Este teste exige:
  1. o exemplo dele (os dois joelhos, com os números dele) sai com o texto dele,
     as duas tabelas e os valores normais dele
  2. cada medida é julgada pelo valor normal da máscara dele (limites inclusos)
  3. campo vazio: a linha da tabela sai; joelho sem medida: sem tabela
  4. um joelho só: título e texto sem "bilateral"
  5. conclusão só com o que está fora do normal; sem nada, a frase normal
  6. avisos (TA-GT em cm) e a rota do roteador
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


def laudo(lado="direito", globais=None, **valores):
    return lyon.montar({"lado": lado, "valores": valores, "globais": globais or {}})


def linha(rotulo, valor, normal):
    return rotulo.ljust(lyon.COL_1) + valor.ljust(lyon.COL_2 - lyon.COL_1) + normal


# 1. o exemplo dele, os dois joelhos
EXEMPLO = dict(sulco_d="132", razao_d="63", lti_d="21", tilt_rel_d="17", tilt_con_d="28", insall_d="1,2", tagt_d="20",
               sulco_e="121", razao_e="71", lti_e="23", tilt_rel_e="8,5", tilt_con_e="26", insall_e="1,2", tagt_e="15")
r = laudo("ambos", **EXEMPLO)
t = r["texto"]
confere("título dos dois joelhos", t.startswith("**TOMOGRAFIA COMPUTADORIZADA DO JOELHO DIREITO E ESQUERDO**"), t[:80])
confere("técnica dele", "**TÉCNICA:**  Foram realizados cortes tomográficos computadorizados axiais do joelho em extensão." in t)
for frase in ["Patela com densidade e contornos preservados, normoposicionada no sulco troclear, apresentando "
              "morfologia do tipo 2 de Wiberg, bilateral.",
              "Fêmur distal e tíbia proximal sem alterações, bilateral.",
              "Espaços articulares com amplitudes anatômicas, bilateral.",
              "Não há evidências de derrame articular. Planos musculogordurosos íntegros, bilateral."]:
    confere("texto corrido dele: " + frase[:40] + "…", frase in t)
confere("tabela do joelho direito, com os normais dele", "\n".join([
    "Medidas joelho direito",
    linha("", "Mensurado", "Valores normais"),
    linha("Ângulo do sulco troclear", "132º", "≤ 143º"),
    linha("Razão troclear medial-lateral", "63%", "> 40%"),
    linha("Inclinação troclear lateral", "21º", "> 11º"),
    linha("Inclinação patelar (\"tilt\")", "17º", "< 20º"),
    linha("Inclinação patelar (\"tilt\") contração", "28º", "10-26º"),
    linha("Índice de Insall-Salvati", "1,2", "0,8 - 1,3"),
    linha("TA-GT", "20 mm", "15 mm (+/- 4)")]) in t, t)
confere("tabela do esquerdo (8,5º com vírgula)", linha("Inclinação patelar (\"tilt\")", "8,5º", "< 20º") in t
        and "Medidas joelho esquerdo" in t and t.index("Medidas joelho direito") < t.index("Medidas joelho esquerdo"))
confere("conclusão do exemplo: só o que está fora (tilt com contração 28º, TA-GT 20 mm à direita)",
        r["conclusao"].split("\n") == ["Distância TA-GT aumentada à direita (20 mm).",
                                       "Inclinação patelar sob contração aumentada à direita (28º)."], r["conclusao"])
confere("seções do modelo dele", "**INDICAÇÃO CLÍNICA:**  Em anexo." in t and "**COMPARAÇÃO:**" in t and "**CONCLUSÃO:**" in t)
confere("nada de lacuna", "___" not in t and "[" not in t and "{" not in t)


# 2. limites (os valores normais da máscara dele)
def conc(**v):
    return laudo(**v)["conclusao"]

N = lyon.FRASE_NORMAL
confere("sulco 143 normal, 144 aumentado", conc(sulco_d="143") == N and "Ângulo do sulco troclear aumentado à direita (144º)." in conc(sulco_d="144"))
confere("razão 41 normal, 40 reduzida", conc(razao_d="41") == N and "reduzida à direita (40%)" in conc(razao_d="40"))
confere("inclinação lateral 12 normal, 11 reduzida", conc(lti_d="12") == N and "Inclinação troclear lateral reduzida" in conc(lti_d="11"))
confere("tilt 19 normal, 20 aumentado", conc(tilt_rel_d="19") == N and "Inclinação patelar aumentada à direita (20º)." in conc(tilt_rel_d="20"))
confere("tilt com contração: 10 e 26 normais, 9 reduzida, 27 aumentada",
        conc(tilt_con_d="10") == N and conc(tilt_con_d="26") == N and "reduzida" in conc(tilt_con_d="9")
        and "aumentada" in conc(tilt_con_d="27"))
confere("Insall-Salvati: 0,8 e 1,3 normais; 1,4 = patela alta; 0,7 = patela baixa",
        conc(insall_d="0,8") == N and conc(insall_d="1,3") == N
        and "Índice de Insall-Salvati aumentado à direita (1,4), compatível com patela alta." in conc(insall_d="1,4")
        and "patela baixa" in conc(insall_d="0,7"))
confere("TA-GT: 11 e 19 normais; 20 aumentada; 10 reduzida",
        conc(tagt_d="11") == N and conc(tagt_d="19") == N and "aumentada à direita (20 mm)" in conc(tagt_d="20")
        and "reduzida" in conc(tagt_d="10"))

# 3. vazio
r = laudo(tagt_d="16")
confere("só o TA-GT: a tabela tem uma linha", "Medidas joelho direito" in r["texto"]
        and "Ângulo do sulco" not in r["texto"] and linha("TA-GT", "16 mm", "15 mm (+/- 4)") in r["texto"], r["texto"])
r = laudo()
confere("nada medido: sem tabela e a frase normal", "Medidas joelho" not in r["texto"] and r["conclusao"] == N)
r = laudo("ambos", tagt_d="16")
confere("os dois joelhos, só o direito medido: só a tabela do direito",
        "Medidas joelho direito" in r["texto"] and "Medidas joelho esquerdo" not in r["texto"])

# 4. um joelho só
r = laudo("esquerdo", tagt_e="15", tagt_d="30")
confere("só o esquerdo: título, sem 'bilateral', e o direito digitado não entra",
        "**TOMOGRAFIA COMPUTADORIZADA DO JOELHO ESQUERDO**" in r["texto"] and "bilateral" not in r["texto"]
        and "Medidas joelho direito" not in r["texto"] and r["conclusao"] == N, r["texto"][:400])

# 5. posição da patela e Wiberg
r = laudo(posicao_d="discretamente lateralizada em relação ao sulco troclear", globais={"wiberg": "3"})
confere("lateralização entra no texto e na conclusão; Wiberg 3",
        "Patela com densidade e contornos preservados, discretamente lateralizada em relação ao sulco troclear, "
        "apresentando morfologia do tipo 3 de Wiberg." in r["texto"]
        and "Patela direita discretamente lateralizada em relação ao sulco troclear." in r["conclusao"], r["texto"])
r = laudo("ambos", posicao_e="subluxada lateralmente")
confere("lados diferentes: uma frase por lado",
        "Patela direita normoposicionada no sulco troclear; patela esquerda subluxada lateralmente." in r["texto"]
        and "Subluxação lateral da patela esquerda." in r["conclusao"], r["texto"])

# 6. avisos e rota
confere("TA-GT 1,6: avisa que deve ser mm", any("1,60 cm = 16 mm" in a for a in laudo(tagt_d="1,6")["avisos"]))
confere("número com unidade digitada ('20 mm', '132º') entra", "20 mm" in laudo(tagt_d="20 mm")["texto"]
        and "132º" in laudo(sulco_d="132º")["texto"])
confere("texto que não é número: ignorado", laudo(tagt_d="abc")["ok"] and "Medidas joelho" not in laudo(tagt_d="abc")["texto"])
confere("lado desconhecido: recusa", lyon.montar({"lado": "x"})["motivo"] == "lado_desconhecido")
c = lyon.campos()
ids = [f["id"] for p in c["passos"] for f in p["campos"]]
confere("campos: os quatro passos, todas as medidas e o Wiberg",
        [p["id"] for p in c["passos"]] == ["troclea", "patela", "femoropatelar", "tagt"]
        and set(lyon.NUMEROS) <= set(ids) and c["globais"][0]["id"] == "wiberg", repr(ids))

import roteador  # noqa: E402
r = roteador.estruturados_montar({"tipo": "lyon", "lado": "ambos", "valores": EXEMPLO})
confere("rota /v1/estruturados com tipo lyon", r.get("ok") and "Medidas joelho esquerdo" in r.get("texto", ""),
        repr(r)[:200])

print()
print("lyon: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
