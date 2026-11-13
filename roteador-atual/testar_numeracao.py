# -*- coding: utf-8 -*-
"""Numeração anatômica (python testar_numeracao.py).

13/11, pedido dele, com o RX do pé que ele colou: "3º, 4º e 5º metatarsos" — "é nesse formato,
numeral com o grau ... quando eu falo do segmento hepático, tem que estar em algarismo romano ...
quando eu falo de dedos, de costelas, tem também que estar o numeral com o grau". Antes saía
por extenso ou o número solto, conforme o ditado."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import formato  # noqa: E402

CASOS = [
    # o exemplo dele (RX do pé esquerdo)
    ("Fraturas desalinhadas prévias já apresentando reações periosteais adjacentes nas bases do terceiro, "
     "quarto e quinto metatarsos bem como nas porções distais do segundo, terceiro e quarto metatarsos.",
     "Fraturas desalinhadas prévias já apresentando reações periosteais adjacentes nas bases do 3º, "
     "4º e 5º metatarsos bem como nas porções distais do 2º, 3º e 4º metatarsos."),
    ("nas bases do 3, 4 e 5 metatarsos", "nas bases do 3º, 4º e 5º metatarsos"),
    ("nas bases do terceiro quarto e quinto metatarsos", "nas bases do 3º, 4º e 5º metatarsos"),
    ("nas bases do 3 4 e 5 metatarsos", "nas bases do 3º, 4º e 5º metatarsos"),
    ("Fratura do 5o metatarso e da 3a costela.", "Fratura do 5º metatarso e da 3ª costela."),
    ("Fratura da quinta costela direita e da sexta costela.", "Fratura da 5ª costela direita e da 6ª costela."),
    ("Fraturas do terceiro ao quinto arcos costais.", "Fraturas do 3º ao 5º arcos costais."),
    ("fratura da décima primeira costela", "fratura da 11ª costela"),
    ("falange proximal do segundo dedo e do quinto quirodáctilo", "falange proximal do 2º dedo e do 5º quirodáctilo"),
    ("base do primeiro metacarpo", "base do 1º metacarpo"),
    ("entre as bases do primeiro e do segundo metatarsos", "entre as bases do 1º e do 2º metatarsos"),
    ("fraturas do segundo, do terceiro e do quarto dedos", "fraturas do 2º, do 3º e do 4º dedos"),
    ("o segundo e o terceiro dedos", "o 2º e o 3º dedos"),
    ("a quinta e a sexta costelas", "a 5ª e a 6ª costelas"),
    ("Primeiro e segundo exames comparados.", "Primeiro e segundo exames comparados."),
    ("no quarto espaço intercostal", "no 4º espaço intercostal"),
    ("fragmento no primeiro espaço intermetatarsal", "fragmento no 1º espaço intermetatarsal"),
    ("hálux valgo com artrose da primeira metatarsofalângica", "hálux valgo com artrose da 1ª metatarsofalângica"),
    ("na primeira articulação metatarsofalângica", "na 1ª articulação metatarsofalângica"),
    ("Base do quinto metatarsal sem fratura.", "Base do 5º metatarsal sem fratura."),
    ("encurtamento do quarto raio", "encurtamento do 4º raio"),
    ("fratura da segunda falange do quinto dedo", "fratura da 2ª falange do 5º dedo"),
    ("Fraturas em 2 falanges.", "Fraturas em 2 falanges."),
    ("primeiro raio x do pé", "primeiro raio x do pé"),
    # o que NÃO pode mudar
    ("Fraturas em 2 costelas à direita.", "Fraturas em 2 costelas à direita."),
    ("Segundo a classificação de Kellgren-Lawrence.", "Segundo a classificação de Kellgren-Lawrence."),
    ("Ângulo de Cobb de 23° no segmento torácico.", "Ângulo de Cobb de 23° no segmento torácico."),
    ("Nódulo de 5 mm.", "Nódulo de 5 mm."),
    ("Segundo 3 costelas fraturadas.", "Segundo 3 costelas fraturadas."),
    ("grau 2 1º metatarso", "grau 2 1º metatarso"),
    # segmento hepático em romano, só no fígado
    ("**Fígado:** nódulo hipoatenuante no segmento 7, medindo 1,2 cm.",
     "**Fígado:** nódulo hipoatenuante no segmento VII, medindo 1,2 cm."),
    ("**Fígado:** lesões nos segmentos cinco e seis, e no segmento 4a.",
     "**Fígado:** lesões nos segmentos V e VI, e no segmento IVa."),
    ("Lesão hepática nos segmentos 2/3.", "Lesão hepática nos segmentos II/III."),
    ("**Fígado:** cisto no segmento VII.", "**Fígado:** cisto no segmento VII."),
    ("**Fígado:** lesões nos segmentos 5 a 8.", "**Fígado:** lesões nos segmentos V a VIII."),
    ("**Fígado:** nódulo no segmento quatro a.", "**Fígado:** nódulo no segmento IVa."),
    ("**Fígado:** nódulo no segmento 4 b.", "**Fígado:** nódulo no segmento IVb."),
    ("**Ureter:** cálculo no segmento proximal.", "**Ureter:** cálculo no segmento proximal."),
    ("**Pulmões:** nódulo no segmento 6 do lobo inferior direito.",
     "**Pulmões:** nódulo no segmento 6 do lobo inferior direito."),
    # conclusão sem a palavra fígado, num laudo que fala do fígado
    ("Fígado: nódulo no segmento 7.\n\nCONCLUSÃO:\nNódulo no segmento 7.",
     "Fígado: nódulo no segmento VII.\n\nCONCLUSÃO:\nNódulo no segmento VII."),
    ("Fígado: sem lesões.\nPulmões: nódulo no segmento 6 do lobo inferior direito.",
     "Fígado: sem lesões.\nPulmões: nódulo no segmento 6 do lobo inferior direito."),
    ("Fígado: normal.\nAorta: ectasia no segmento 2 da aorta.", "Fígado: normal.\nAorta: ectasia no segmento 2 da aorta."),
]


def main():
    falhas = []
    for antes, esperado in CASOS:
        saiu = formato.numeracao(antes)
        ok = saiu == esperado
        print(("ok      " if ok else "FALHA   ") + antes.replace("\n", " / ")[:70])
        if not ok:
            print("        saiu:     " + saiu)
            print("        esperado: " + esperado)
            falhas.append(antes)
    # o revisor local transformava "segundo" em "s" (unidade de segundos) — "do s metatarso"
    import revisor
    for antes, esperado in [("o segundo dedo", "O segundo dedo"),
                            ("porções distais do segundo, terceiro e quarto metatarsos",
                             "Porções distais do segundo, terceiro e quarto metatarsos"),
                            ("tempo de 30 segundos", "Tempo de 30 s"),
                            ("trinta segundos de apneia", "30 s de apneia")]:
        saiu = revisor.revisar(antes)
        ok = saiu == esperado
        print(("ok      " if ok else "FALHA   ") + "revisor: " + antes)
        if not ok:
            print("        saiu:     " + saiu)
            falhas.append(antes)
    src = open(os.path.join(AQUI, "roteador.py"), encoding="utf-8").read()
    for trecho, nome in [("or nw in _NUMERAIS_FALADOS", "o vocabulário do banco não troca número dito ('cinco' -> 'clinico')"),
                         ("formato.proteger_listas(protegido)", "a lista não parte no separador de achados (TC)"),
                         ("_formato.proteger_listas(texto)", "a lista não parte no separador de achados (RX)"),
                         ("fig and formato._RX_SEG_I.search(orfao)", "segmento numerado sem estrutura dita vai para o fígado")]:
        ok = trecho in src or trecho in open(os.path.join(AQUI, "rx_literal.py"), encoding="utf-8").read()
        print(("ok      " if ok else "FALHA   ") + nome)
        if not ok:
            falhas.append(nome)
    for trecho, nome in [("texto = formato.numeracao(texto)", "toda saída local (formatar_saida)"),
                         ("novo = formato.numeracao(novo)", "toda saída da IA (ia_no_texto)")]:
        ok = trecho in src
        print(("ok      " if ok else "FALHA   ") + "aplicado em " + nome)
        if not ok:
            falhas.append(nome)
    regra = open(os.path.join(AQUI, "dados", "prompts", "REDATOR_ROTRIX.md"), encoding="utf-8").read()
    ok = "segmento 7 / segmento sete → segmento VII" in regra and "5ª costela" in regra
    print(("ok      " if ok else "FALHA   ") + "a IA recebe a mesma regra (bloco NUMEROS)")
    if not ok:
        falhas.append("NUMEROS")
    print()
    print("numeração anatômica: tudo certo" if not falhas else "numeração: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
