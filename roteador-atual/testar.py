# -*- coding: utf-8 -*-
"""Testa o roteador sem precisar do Handy."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import roteador

CASOS = [
 "máscara tomografia de abdome normal",
 "mascara tc de torax normal",
 "máscara tomografia de cranio normal",
 "máscara angiotomografia de aorta normal",
 "adendo variante anatômica",
 "ressalva de parede abdominal à direita",
 "frase bursite",
 "frase tendinopatia do supraespinhal",
 "máscara ressonância de cotovelo",             # nao existe -> avisa
 "havia uma discreta quantidade de líquido livre na pelve",  # prosa -> passa
 "",
]
for c in CASOS:
    txt, origem = roteador.rotear(c)
    prim = txt.split("\n")[0] if txt else "(vazio)"
    print(f"{c[:46]:<48} | {origem:<34} | {prim[:64]}")
