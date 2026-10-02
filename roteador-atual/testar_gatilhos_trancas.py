# -*- coding: utf-8 -*-
"""Gatilho não entra onde não deve (auditoria de 02/10).

    python testar_gatilhos_trancas.py

Ele: "os gatilhos das máscaras do roteador estão atrapalhando ... tem que haver uma
auditoria completa". auditar_cruzamentos.py ditou cada achado do banco dele no exame
de cada região: 1.460 ditados entravam em bloco SEM relação. Depois das trancas, 42
(quase todos de mesma família, "placa" na aorta). Este teste segura as trancas:
  1. palavra que o banco conhece não casa por semelhança: artrodese não vira artrose,
     pneumonia não vira pneumotórax, apêndice não vira apendicite
  2. o núcleo do trecho tem de estar no gatilho: "avulsão da placa volar" não puxa
     "placas ateromatosas"
  3. flexão e erro de voz continuam casando (atelectasias, atelectazia)
  4. variante de máscara só abre com os achados do nome dela ditados
  5. pontuação depois do nome do exame é fronteira ("... e pelve. apendicite")
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import roteador as R  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


def regiao(mod, reg):
    return lambda m: m[1] == mod and m[2] == reg


def bloco(seg, mod, reg):
    b = R._bloco_do_segmento(seg, regiao(mod, reg))
    return b[0] if b else None


# 0. família de palavras
for a, b, esperado in [("pneumonia", "pneumotorax", False), ("apendice", "apendicite", False),
                       ("artrose", "artrodese", False), ("espondilolise", "espondilolistese", False),
                       ("colica", "colonica", False), ("atelectasia", "atelectasias", True),
                       ("carotida", "carotidea", True), ("nodular", "nodulo", True),
                       ("ateromatose", "ateromatosas", True), ("placa", "placas", True)]:
    confere("família %s/%s = %s" % (a, b, esperado), R._mesma_familia(a, b) == esperado)

# 1. palavra conhecida não casa por semelhança
x = bloco("artrodese cervical", "tc", "quadril")
confere("'artrodese' não puxa coxartrose", x is None or "coxartrose" not in x, str(x))
x = bloco("pneumonia pequeno à direita", "tc", "torax")
confere("'pneumonia, pequeno à direita' não vira pneumotórax", x is None or "pneumotorax" not in x, str(x))

# 2. núcleo do trecho
x = bloco("avulsão da placa volar na mão", "tc", "pelve")
confere("'avulsão da placa volar' não puxa ateromatose", x is None or "ateroma" not in x, str(x))
x = bloco("placas ateromatosas calcificadas", "tc", "pelve")
confere("mas 'placas ateromatosas calcificadas' continua no bloco de ateromatose",
        x is not None and "ateroma" in x, str(x))

# 3. flexão e erro de voz continuam casando
gat = [(g, tit) for t, g, tit, *_ in R.BANCO.itens if t == "bloco" and "atelectasia laminar" in g
       and "/tc/torax/" in tit]
if gat:
    g, tit = gat[0]
    confere("plural casa ('atelectasias laminares')", bloco("atelectasias laminares", "tc", "torax") == tit,
            str(bloco("atelectasias laminares", "tc", "torax")))
    confere("erro de voz casa ('atelectazia laminar')", bloco("atelectazia laminar", "tc", "torax") == tit,
            str(bloco("atelectazia laminar", "tc", "torax")))

# 4. variante só com os achados do nome
confere("variante sem o achado do nome: não abre",
        not R._variante_so_com_o_ditado("medicina_interna/tc/torax/aguda_derrame_atelectasia",
                                        R.normalizar("tomografia de torax com derrame pleural")))
confere("variante com os achados do nome: abre",
        R._variante_so_com_o_ditado("medicina_interna/tc/torax/aguda_derrame_atelectasia",
                                    R.normalizar("tomografia de torax com derrame pleural e atelectasia")))
t, o = R.rotear("tomografia de tórax com derrame pleural bilateral")
confere("'tc de tórax com derrame' não abre a variante com atelectasia", "aguda_derrame_atelectasia" not in o, o)

# 5. pontuação depois do nome do exame
t, o = R.rotear("tomografia de abdome superior e pelve. apendicite")
confere("'... e pelve.' abre ABDOME SUPERIOR E PELVE", "ABDOME SUPERIOR E PELVE" in t.upper()
        and "abdome_superior" not in o, o)
t, o = R.rotear("tomografia de tórax. derrame pleural bilateral")
confere("'tomografia de tórax.' abre a máscara normal do tórax", "/tc/torax/normal" in o, o)

# nenhum bloco para trecho só de qualificador
for q in ("pequeno à direita", "bilateral", "de pequeno volume", "medindo 5 mm", "no lobo inferior direito"):
    confere("'%s' sozinho não puxa bloco" % q, R._bloco_do_segmento(q, lambda _m: True) is None)

print()
print("trancas dos gatilhos: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
