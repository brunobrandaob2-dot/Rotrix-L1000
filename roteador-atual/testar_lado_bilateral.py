# -*- coding: utf-8 -*-
"""'bilateral' não entra em frase de achado único.

26/09, laudo assinado dele, TC de tórax:
    "Nódulo sólido de margens regulares e densidade cálcica, bilateral, ..."

O bloco é {lado|direito/esquerdo} — substantivo no singular, regido por
preposição. Ele ditou "bilateral"; o _lado() devolvia "bilateral" e o
preencher() injetava sem conferir a lista da lacuna. Saía "nódulo sólido no
bilateral", "rim bilateral", "artéria renal bilateral", "colapso do pulmão
bilateral" — 233 frases do banco, e nenhuma dá para assinar.

Esta trava guarda os três lados da regra:
  1. lado ADJETIVO ({lado}, {lado_f}) sem bilateral na lista -> lacuna visível
  2. lado ADVÉRBIO ({lado_a}) continua aceitando "bilateralmente"
  3. lacuna que OFERECE bilateral continua preenchendo
"""
import io, os, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador

falhas = []
def confere(nome, cond, extra=""):
    print(("ok      " if cond else "FALHOU  ") + nome + (("  " + extra) if extra and not cond else ""))
    if not cond:
        falhas.append(nome)

print("=== 1. achado único + 'bilateral' = lacuna visível, nunca prosa errada ===")
UNICOS = [
    ("tomografia de torax com nodulo pulmonar benigno bilateral", "nódulo"),
    ("tomografia de abdome com pielonefrite bilateral", "rim"),
    ("tomografia de abdome com calculo ureteral bilateral", "rim"),
    ("angio de renais com estenose de arteria renal bilateral", "artéria renal"),
]
for ditado, pista in UNICOS:
    texto, _o = roteador.rotear(ditado)
    t = texto or ""
    ruim = re.search(r"\b(no|na|do|da|ao|à)\s+bilateral\b", t) or \
           re.search(r"\b(rim|nódulo|artéria|pulmão|ureter)\s+bilateral\b", t, re.I)
    confere("%-52s sem 'X bilateral'" % ditado[:52], not ruim,
            "saiu: %s" % (ruim.group(0) if ruim else ""))

print()
print("=== 2. o advérbio continua entrando (essas frases já estavam certas) ===")
ADVERBIO = [
    ("tomografia de abdome com litiase renal bilateral", "bilateralmente"),
    ("tomografia de abdome com alteracoes cronicas bilateral", "bilateralmente"),
]
for ditado, esperado in ADVERBIO:
    texto, _o = roteador.rotear(ditado)
    confere("%-52s diz '%s'" % (ditado[:52], esperado), esperado in (texto or ""))

print()
print("=== 3. quando a lacuna OFERECE bilateral, nada muda ===")
OFERECEM = [
    ("tomografia de torax com derrame pleural bilateral", "derrame pleural bilateral"),
    ("tomografia de torax com nodulos esparsos bilaterais", "nódulos pulmonares esparsos"),
]
for ditado, esperado in OFERECEM:
    texto, _o = roteador.rotear(ditado)
    confere("%-52s diz '%s'" % (ditado[:52], esperado[:30]), esperado in (texto or ""))

print()
print("=== 4. um lado só continua preenchendo como sempre ===")
UM_LADO = [
    ("tomografia de torax com nodulo pulmonar benigno no lobo superior direito medindo 5 mm",
     "no lobo superior direito"),
    ("tomografia de abdome com pielonefrite a esquerda", "rim esquerdo"),
]
for ditado, esperado in UM_LADO:
    texto, _o = roteador.rotear(ditado)
    confere("%-52s diz '%s'" % (ditado[:52], esperado[:30]), esperado in (texto or ""),
            "não achei no texto")

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), "; ".join(falhas[:4])))
    raise SystemExit(1)
print("lado bilateral: nenhum achado único sai com 'bilateral' colado")
