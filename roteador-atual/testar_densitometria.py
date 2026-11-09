# -*- coding: utf-8 -*-
"""Densitometria (máscaras A/B/C dele) montada na máquina (python testar_densitometria.py).

09/11: veio da skill densitometria e do expoweb aprovado. Os números entram, a máscara,
a classificação pelo menor escore e as ressalvas saem daqui; o texto é o da máscara
dele sem trocar palavra. O exemplo 1 é o mesmo do expoweb (print simulado)."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import densitometria as d  # noqa: E402
import medidas  # noqa: E402

EXPOWEB = {"sexo": "feminino", "menopausa": "pós ou transição", "idade": "62",
           "col_bmd": "0,912", "col_t": "-1,9", "l1_t": "-1,2", "l2_t": "-1,8", "l3_t": "-2,1",
           "l4_t": "-0,6", "colo_e_bmd": "0,701", "colo_e_t": "-2,3", "total_e_t": "-1,7",
           "total_e_bmd": "0,812", "ant_col_bmd": "0,948", "ant_total_bmd": "0,826",
           "ant_data": "14/10/2024"}


def main():
    falhas = []

    def ok(cond, nome):
        print(("ok      " if cond else "FALHA   ") + nome)
        if not cond:
            falhas.append(nome)

    r = d.laudo(EXPOWEB)
    t, av = r["texto"], " | ".join(r["avisos"])
    ok(r["valores"]["mascara"] == "A" and r["valores"]["criterio"] == "T", "pós-menopausa, sem rádio: máscara A (T)")
    ok("- Densitometria evidencia perda óssea compatível com OSTEOPENIA." in t, "menor T -2,3 (colo): OSTEOPENIA")
    ok("proximal do fêmur esquerdo." in t and "colo femoral esquerdo é de 0,701 g/cm²" in t, "lado esquerdo pelo campo preenchido")
    ok("das vértebras L1, L2, L3 e L4 é de 0,912 g/cm² e corresponde ao desvio-padrão de -1,9 em relação" in t,
       "parágrafo da coluna = texto da máscara A")
    ok("L4 difere mais de 1,0" in av, "L4 (-0,6) difere > 1,0 de L3 (-2,1): ressalva de exclusão")
    ok("Em relação ao exame de 14/10/2024, realizado no mesmo equipamento, observa-se perda da massa óssea, "
       "com variação de -0,036 g/cm² (-3,8%) na coluna lombar e de -0,014 g/cm² (-1,7%) no fêmur total." not in t
       and "observa-se estabilidade da massa óssea, com variação de -0,036 g/cm² (-3,8%) na coluna lombar e de "
       "-0,014 g/cm² (-1,7%) no fêmur total." in t, "comparação pela DMO abaixo do LSC ISCD: estabilidade")
    ok("ISCD" in av, "sem LSC do serviço: ressalva ISCD")
    ok("**IMPRESSÃO DIAGNÓSTICA:**\n\n- Densitometria" in t and t.startswith("**DENSITOMETRIA ÓSSEA**\n\n**COMENTÁRIOS:**"),
       "cabeçalhos em negrito, linha em branco entre as linhas")
    ok("Até (-)1 DP (Desvio Padrão)" in t and "OSTEOPOROSE ESTABELECIDA" in t.split("REFERÊNCIA")[-1], "tabela de referência T")

    z = d.laudo({"sexo": "feminino", "menopausa": "pré-menopausa", "idade": "38", "col_bmd": "1,010",
                 "col_t": "-2,1", "colo_d_bmd": "0,820", "colo_d_t": "-1,2", "total_d_t": "-0,9"})
    ok(z["valores"]["mascara"] == "C" and "(Z- Score)" in z["texto"] and "da paciente" in z["texto"], "pré-menopausa: máscara C, 'da paciente'")
    ok("- Densitometria abaixo do esperado para a idade." in z["texto"], "Z -2,1 ≤ -2,0: abaixo do esperado")
    ok("limiar de -2,0" in " ".join(z["avisos"]), "Z no limiar: ressalva")
    ok("Maior que -2 DP" in z["texto"] and "Até (-)1 DP" not in z["texto"], "tabela de referência Z")

    h = d.laudo({"sexo": "masculino", "idade": "44", "col_t": "-0,5", "col_bmd": "1,100"})
    ok(h["valores"]["criterio"] == "Z" and "do paciente" in h["texto"], "homem < 50: Z, 'do paciente'")

    b = d.laudo({"sexo": "feminino", "menopausa": "pós ou transição", "col_t": "-1,0", "col_bmd": "0,980",
                 "colo_e_t": "-1,4", "colo_e_bmd": "0,780", "total_e_t": "-0,8", "colo_d_t": "-2,6",
                 "colo_d_bmd": "0,610", "total_d_t": "-2,0", "radio_t": "-1,1", "radio_bmd": "0,700",
                 "fratura": "sim"})
    tb = b["texto"]
    ok(b["valores"]["mascara"] == "B" and "coluna lombar em AP, fêmur e rádio 1/3." in tb, "com rádio: máscara B")
    ok(tb.index("colo femoral direito") < tb.index("colo femoral esquerdo"), "bilateral: direito primeiro")
    ok("do rádio 1/3 que é de 0,700 g/cm² e corresponde ao desvio-padrão de -1,1" in tb, "linha do rádio da máscara B")
    ok("OSTEOPOROSE ESTABELECIDA." in tb.split("IMPRESSÃO DIAGNÓSTICA:**")[1].split("**VALORES")[0],
       "T -2,6 + fratura: osteoporose estabelecida")
    ok("discordância entre sítios" in " ".join(b["avisos"]), "discordância > 1,0 DP entre sítios")

    a = d.laudo({"sexo": "feminino", "menopausa": "pós ou transição", "col_t": "-2,45", "col_bmd": "0,780"})
    ok("OSTEOPOROSE." in a["texto"] and "mudou de faixa no arredondamento" in " ".join(a["avisos"]),
       "-2,45 -> -2,5 (meio para longe do zero) e ressalva do arredondamento")
    ok("-2,5 em relação" in a["texto"], "escore com uma casa no laudo")
    ok("@direito @esquerdo" in a["texto"] and "fêmur sem valores" in " ".join(a["avisos"]), "sem fêmur: @ e ressalva")

    p = d.laudo({"sexo": "feminino", "menopausa": "pós ou transição", "col_t": "-26", "col_bmd": "74"})
    ok("coluna de %" in " ".join(p["avisos"]), "valor de % lido como escore/BMD: ressalva de plausibilidade")

    s = d.laudo({"sexo": "feminino", "idade": "55", "col_t": "-1,2", "col_bmd": "0,9"})
    ok(s["valores"]["criterio"] == "T" and "menopausa não informada" in " ".join(s["avisos"]),
       "mulher ≥ 50 sem menopausa: T com ressalva do critério")

    g = d.laudo(dict(EXPOWEB, col_bmd="0,880", ant_col_bmd="0,948", lsc_col="2,8", lsc_total="2,5"))
    ok("observa-se perda da massa óssea" in g["texto"], "LSC do serviço: -7,2% na coluna > 2,8% -> perda")

    # mesmo caminho das medidas: formulário, print, conta local
    ok("densitometria" in medidas.CAMPOS and medidas.montar("densitometria", EXPOWEB)["pronto"] is True,
       "medidas.CAMPOS tem a densitometria; montar devolve texto pronto")
    ok(all("nome" not in k and "nasc" not in k for k, _r in d.CAMPOS["leitura"]), "nenhum campo de nome ou nascimento (§17)")
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteador.py"), encoding="utf-8").read()
    ok('not r.get("pronto")' in src, "o padronizar não desmonta a máscara da densitometria")
    ok("medidas.densitometria.REGRAS_PRINT" in src and "_data_lida" in src, "print do densitômetro com regra própria; data lida como data")

    print()
    print("densitometria: tudo certo" if not falhas else "densitometria: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
