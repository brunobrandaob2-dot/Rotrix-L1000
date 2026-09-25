# -*- coding: utf-8 -*-
"""Os rotulos de estrutura do banco tem de bater com a lista que o app testa.

    python conferir_rotulos.py            confere (sai 1 se divergiu)
    python conferir_rotulos.py --gravar   regrava a lista

Por que existe
--------------
O modelo de laudo dele e: TITULO, TECNICA, INDICACAO CLINICA, ANALISE, COMPARACAO,
CONCLUSAO — e, dentro da ANALISE, uma linha por estrutura, com o ROTULO EM NEGRITO:

    Figado:  de dimensoes normais, contornos regulares e densidade normal.

O renderizador do app (app/src/components/rotrix2/formatar.ts) decide o negrito por
regra, nao por lista. A regra foi calibrada nos rotulos que existem de verdade no banco.
Se alguem acrescentar uma mascara com um rotulo de forma nova ("Rotulo com 3 numeros:")
a regra pode nao pegar, o negrito some e ninguem percebe — porque o teste do app conhece
so a lista gravada.

Este conferidor fecha esse buraco: ele reextrai os rotulos do banco e falha quando a
lista gravada ficou velha. O app tem o teste (formatar.test.ts) que passa TODOS os
rotulos dessa lista pelo renderizador.
"""

import glob
import io
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
# o .json fica junto do teste que o consome, no lado do app
DESTINOS = [
    os.path.join(AQUI, "..", "app", "src", "components", "rotrix2", "rotulos_do_banco.json"),
    os.path.join(AQUI, "dados", "rotulos_do_banco.json"),
]

LEIA = ("Gerado por conferir_rotulos.py a partir de dados/mascaras. Rotulos de estrutura "
        "da ANALISE das 70 regioes: cada um tem de sair em NEGRITO na folha e no RIS. "
        "As frases complementares (prosa, sem caixa alta) nao podem virar rotulo. "
        "Para regravar: python conferir_rotulos.py --gravar")

_ANALISE = re.compile(r"\*\*AN[ÁA]LISE:\*\*")
_OUTRA_SECAO = re.compile(r"\*\*(COMPARA|CONCLUS|T[ÉE]CNICA|INDICA)")
_ROTULO = re.compile(r"^([A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][^:]{2,60}):  (.*)$")
_SO_LETRA = re.compile(r"[^A-Za-zÁ-Úá-ú]")


def extrair(raiz=None):
    """({rotulos}, {prosa}) lidos das mascaras."""
    pasta = raiz or os.path.join(AQUI, "dados", "mascaras")
    rot, prosa = set(), set()
    for f in sorted(glob.glob(os.path.join(pasta, "*", "*", "*", "*.txt"))):
        dentro = False
        try:
            linhas = io.open(f, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for s in linhas:
            s = s.rstrip()
            if s.startswith("#") or not s.strip():
                continue
            if _ANALISE.match(s):
                dentro = True
                continue
            if _OUTRA_SECAO.match(s):
                dentro = False
                continue
            if not dentro:
                continue
            m = _ROTULO.match(s)
            if m and m.group(1).upper() != m.group(1):
                rot.add(m.group(1))
                continue
            if ":" in s or "*" in s:
                continue
            letras = _SO_LETRA.sub("", s)
            if len(letras) >= 4 and letras == letras.upper():
                continue                      # linha em CAIXA ALTA ja era negrito antes
            if len(s.strip()) > 20:
                prosa.add(s.strip())
    return rot, prosa


def montar(rot, prosa):
    return {"_leia": LEIA, "rotulos": sorted(rot), "prosa": sorted(prosa)[:120]}


def gravar(d):
    escritos = []
    for p in DESTINOS:
        p = os.path.normpath(p)
        if not os.path.isdir(os.path.dirname(p)):
            continue
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        escritos.append(p)
    return escritos


def main():
    rot, prosa = extrair()
    if not rot:
        print("ERRO: nao achei nenhum rotulo de estrutura em dados/mascaras")
        return 1
    novo = montar(rot, prosa)
    if "--gravar" in sys.argv:
        for p in gravar(novo):
            print("gravado:", p)
        print("%d rotulos, %d frases de prosa" % (len(novo["rotulos"]), len(novo["prosa"])))
        return 0
    faltando, divergentes = [], []
    for p in DESTINOS:
        p = os.path.normpath(p)
        if not os.path.exists(p):
            if os.path.isdir(os.path.dirname(p)):
                faltando.append(p)
            continue
        try:
            velho = json.load(io.open(p, encoding="utf-8"))
        except Exception as e:
            divergentes.append((p, "nao consegui ler (%s)" % type(e).__name__))
            continue
        a, b = set(velho.get("rotulos") or []), set(novo["rotulos"])
        if a != b:
            divergentes.append((p, "entraram: %s | sairam: %s" % (
                sorted(b - a)[:6] or "-", sorted(a - b)[:6] or "-")))
    if faltando or divergentes:
        print("A lista de rotulos do renderizador esta velha:")
        for p in faltando:
            print("  nao existe:", p)
        for p, motivo in divergentes:
            print("  %s -> %s" % (p, motivo))
        print()
        print("Rode:  python conferir_rotulos.py --gravar")
        print("e rode o teste do app:  bun src/components/rotrix2/formatar.test.ts")
        return 1
    print("rotulos de estrutura: %d, em dia com o renderizador" % len(novo["rotulos"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
