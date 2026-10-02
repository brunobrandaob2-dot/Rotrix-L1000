# -*- coding: utf-8 -*-
"""Coluna estruturada: mais de uma herniação no mesmo nível.

    python testar_coluna_hernias.py

02/10, pedido dele: "às vezes eu quero colocar mais de uma protrusão, mais de uma
extrusão. Eu quero que ela seja central e também exista outra lateral ... só consigo
marcar uma por vez. Tem que ampliar." A frase e a conclusão abaixo foram aprovadas
por ele ("a frase da coluna está ok"):

    L4-L5:  abaulamento discal difuso, associado a componente protruso central e a
            componente extruso foraminal à esquerda, medindo 6 mm, com compressão radicular.
    CONCLUSÃO: Protrusão discal central e extrusão discal foraminal à esquerda em L4-L5,
            com compressão radicular.

Este teste exige essas duas frases ao pé da letra, as variações sem abaulamento e com
redução de altura, três herniações, só "as outras" sem a primeira, e que o nível com
uma herniação só continue saindo como antes.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import estruturados as E  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


DELE = {"zona": "central",
        "extra": [{"tipo": "extrusao", "zona": "foraminal", "lado": "à esquerda", "medida": "6",
                   "contato": "com compressão radicular"}]}

f = E.frase_do_nivel("L4-L5", ["abaulamento", "protrusao"], DELE)
confere("a frase que ele aprovou", f == "L4-L5:  abaulamento discal difuso, associado a componente protruso "
        "central e a componente extruso foraminal à esquerda, medindo 6 mm, com compressão radicular.", f)
c = E.conclusao_do_nivel("L4-L5", ["abaulamento", "protrusao"], DELE)
confere("a conclusão que ele aprovou", c == "Protrusão discal central e extrusão discal foraminal à esquerda "
        "em L4-L5, com compressão radicular.", c)

f = E.frase_do_nivel("L4-L5", ["protrusao"], DELE)
confere("sem abaulamento: as duas herniações pelo nome", f == "L4-L5:  protrusão discal central e extrusão "
        "discal foraminal à esquerda, medindo 6 mm, com compressão radicular.", f)
f = E.frase_do_nivel("L4-L5", ["altura", "abaulamento", "protrusao"], DELE)
confere("com redução de altura", f.startswith("L4-L5:  redução da altura discal, com abaulamento difuso associado "
        "a componente protruso central e a componente extruso foraminal à esquerda"), f)

TRES = {"zona": "central", "medida": "4",
        "extra": [{"tipo": "protrusao", "zona": "foraminal", "lado": "à direita"},
                  {"tipo": "extrusao", "zona": "subarticular", "lado": "à esquerda", "migracao": "caudal"}]}
f = E.frase_do_nivel("L5-S1", ["abaulamento", "protrusao"], TRES)
confere("três herniações: 'a X, a Y e a Z', cada uma com o seu detalhe",
        "associado a componente protruso central, medindo 4 mm, a componente protruso foraminal à direita e "
        "a componente extruso subarticular à esquerda, com migração caudal." in f, f)
c = E.conclusao_do_nivel("L5-S1", ["abaulamento", "protrusao"], TRES)
confere("três na conclusão, na ordem", c == "Protrusão discal central, protrusão discal foraminal à direita e "
        "extrusão discal subarticular à esquerda em L5-S1.", c)

so_outra = {"extra": [{"tipo": "protrusao", "zona": "foraminal", "lado": "à direita"}]}
confere("só 'a outra', sem a primeira: o nível não fica vazio",
        E.frase_do_nivel("L3-L4", [], so_outra) == "L3-L4:  protrusão discal foraminal à direita.")
confere("e entra na conclusão", E.conclusao_do_nivel("L3-L4", [], so_outra)
        == "Protrusão discal foraminal à direita em L3-L4.")

# uma só: igual a antes
confere("uma herniação só continua igual", E.frase_do_nivel("L3-L4", ["abaulamento", "protrusao"],
        {"zona": "central"}) == "L3-L4:  abaulamento discal difuso, associado a componente protruso central.")
confere("conclusão de uma só continua igual", E.conclusao_do_nivel("L3-L4", ["extrusao"],
        {"zona": "central", "contato": "em contato com o saco dural"})
        == "Extrusão discal central em L3-L4, em contato com o saco dural.")
confere("'sem contato' não vai para a conclusão", "sem contato" not in E.conclusao_do_nivel(
        "L3-L4", ["protrusao"], {"zona": "central", "contato": "sem contato radicular"}))
confere("item 'extra' estranho é ignorado", E.frase_do_nivel("L3-L4", ["protrusao"], {
        "zona": "central", "extra": [{"tipo": "outra"}, "x"]}) == "L3-L4:  protrusão discal central.")

# o laudo inteiro pela montagem
r = E.montar({"segmento": "lombar", "modalidade": "rm",
              "niveis": {"L4-L5": dict(DELE, marcados=["abaulamento", "protrusao"]),
                         "L3-L4": so_outra}})
confere("montar: os dois níveis entram e são contados", r.get("ok") and "L3-L4" in r["niveis_usados"]
        and "L4-L5" in r["niveis_usados"] and "componente extruso foraminal à esquerda" in r["texto"], repr(r)[:300])

print()
print("coluna, várias herniações: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
