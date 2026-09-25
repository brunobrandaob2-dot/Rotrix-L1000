# -*- coding: utf-8 -*-
"""Termo do dia a dia tem de achar o achado do banco — e o laudo nao pode se contradizer.

    python testar_sinonimos.py

Por que existe
--------------
Em 25/09, medindo o custo do Haiku, achei um defeito pior que o custo: termo leigo sem
palavra em comum com o termo tecnico NAO achava o bloco, e o laudo saia se contradizendo.

    ditado: "tomografia de torax com agua no pulmao"
    saia:   Parenquima pulmonar:  agua no pulmao.          <- a fala dele, sem acento
            Derrames:  ausencia de derrame pleural...      <- a mascara dizendo o contrario

    ditado: "tomografia de abdome com pedra no rim"
    saia:   Rins:  ... Nao ha calculos ou dilatacao...      <- a mascara negando o achado

Nenhuma conta de semelhanca resolve isso: "pedra" e "calculo" nao tem letra em comum.
dados/sinonimos.tsv resolve, custa zero e vale para sempre — um modelo de linguagem
custaria 0,13 a 0,44 centavo por achado orfao (medido, com a lista de achados da regiao
no prompt).

O que este teste tranca:
  1. o termo leigo acha o achado certo (por roteamento, no laudo inteiro);
  2. o laudo NAO fica com a frase normal que contradiz o achado;
  3. a tabela nao mexe no que ja funcionava (isso e o corpus de igualdade do
     testar_perf_roteador.py, com 800 gatilhos de verdade: mudaram 0);
  4. a lista de candidatos da oficina traz o achado certo entre os primeiros.
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador

falhas = []


def confere(nome, cond, extra=""):
    print(("ok      " if cond else "FALHOU  ") + nome + (("  " + extra) if extra and not cond else ""))
    if not cond:
        falhas.append(nome)


# (ditado, o que TEM de aparecer, a frase da mascara que NAO pode sobrar)
NO_LAUDO = [
    ("tomografia de torax com agua no pulmao", "derrame pleural",
     "ausência de derrame pleural"),
    ("tomografia de abdome com pedra no rim", "álculo", "Não há cálculos"),
    ("tomografia de torax com coracao aumentado de volume",
     "dimensões cardíacas", None),
    ("tomografia de torax com placa na aorta", "ateromatose", None),
    ("tomografia de abdome com rim inchado", "ilata", None),
]

# Estes o ROTEAMENTO ainda nao pega — a tabela entra na busca de bloco, e nestes dois o
# caminho composto resolve o segmento antes de chegar la. A lista de candidatos ACHA os
# dois (estao nos 10 de 10 abaixo), entao o conserto e o fluxo que ele aprovou: ele
# escolhe uma vez na oficina e o trecho vira gatilho de verdade, de graca e para sempre.
# Ficam listados aqui, com o motivo, em vez de escondidos.
SO_PELA_OFICINA = [
    ("intestino preso", "abdome", "fecal"),
    ("cerebro encolhido", "cranio", "atrofia"),
]

print("=== termo do dia a dia no laudo inteiro ===")
for ditado, tem, nao_pode in NO_LAUDO:
    texto, origem = roteador.rotear(ditado)
    t = texto or ""
    confere("%-52s acha o achado" % ditado[:50], tem.lower() in t.lower(),
            "não achei %r em %s" % (tem, origem))
    if nao_pode:
        confere("%-52s sem contradição" % ditado[:50], nao_pode.lower() not in t.lower(),
                "sobrou: %r" % nao_pode)
    # a fala crua nunca fica escrita como se fosse termo tecnico
    cru = ditado.split(" com ", 1)[1] if " com " in ditado else ""
    if cru:
        confere("%-52s não escreve a fala crua" % ditado[:50],
                cru.lower() not in t.lower(), "ficou: %r" % cru)

print()
print("=== os que so a oficina pega hoje (roteamento ainda nao) ===")
for trecho, regiao, esperado in SO_PELA_OFICINA:
    c = roteador.candidatos(trecho, regiao, 3)
    confere("%-30s esta na lista de candidatos" % trecho,
            any(esperado in x["titulo"].lower() for x in c),
            "candidatos: " + ", ".join(x["titulo"].rsplit("/", 1)[-1][:20] for x in c))

print()
print("=== lista de candidatos da oficina (o achado certo entre os 3 primeiros) ===")
CANDIDATOS = [
    ("pedra no rim", "abdome", "calculo_renal"),
    ("agua no pulmao", "torax", "derrame_pleural"),
    ("coracao aumentado de volume", "torax", "cardiomegalia"),
    ("placa na aorta", "torax", "ateromatose"),
    ("bico de papagaio na coluna", "coluna_lombar", "espondilose"),
    ("figado com gordura", "abdome", "esteatose"),
    ("rim inchado", "abdome", "hidronefrose"),
    ("intestino preso", "abdome", "fecal"),
    ("cerebro encolhido", "cranio", "atrofia"),
    ("disco gasto em l5 s1", "coluna_lombar", "disco"),
]
achou3 = 0
for trecho, regiao, esperado in CANDIDATOS:
    c = roteador.candidatos(trecho, regiao, 3)
    if any(esperado in x["titulo"].lower() for x in c):
        achou3 += 1
    else:
        print("        (fora dos 3) %-30s -> %s" % (
            trecho, ", ".join(x["titulo"].rsplit("/", 1)[-1][:22] for x in c[:3])))
confere("o certo está entre os 3 primeiros em pelo menos 8 de %d" % len(CANDIDATOS),
        achou3 >= 8, "deu %d" % achou3)
print("        acerto nos 3 primeiros: %d de %d" % (achou3, len(CANDIDATOS)))

print()
print("=== a lista nunca oferece máscara de exame (a lei da v0.4.3) ===")
so_achados = all(x["tipo"] in ("frase", "bloco")
                 for trecho, reg, _e in CANDIDATOS
                 for x in roteador.candidatos(trecho, reg, 8))
confere("candidatos são só frase/bloco, nunca máscara", so_achados)

print()
print("=== a tabela só acrescenta, nunca reescreve o ditado ===")
n = roteador.normalizar("pedra no rim")
amp = roteador.sinonimo_busca(n)
confere("o texto original continua dentro da chave de busca", n in amp, amp)
confere("e os termos técnicos entraram", "calculo" in amp and "nefrolitiase" in amp, amp)
confere("termo sem regra passa intacto",
        roteador.sinonimo_busca("nodulo pulmonar solido") == "nodulo pulmonar solido")

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), "; ".join(falhas[:5])))
    raise SystemExit(1)
print("sinônimos do dia a dia: tudo certo")
