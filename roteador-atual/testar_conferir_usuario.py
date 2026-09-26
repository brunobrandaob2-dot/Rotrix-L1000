# -*- coding: utf-8 -*-
"""conferir_usuario acha a disputa pelos ARQUIVOS, não pelo banco.

    python testar_conferir_usuario.py

A primeira versão (85699da) procurava a disputa no base.sqlite, onde o perdedor
nem entra — e respondia "nenhum gatilho seu está na frente" na máquina em que
três regiões estavam. Este teste monta uma pasta dados/ falsa e exige que:
  1. a sua máscara com gatilho do Rotrix apareça como disputa, com as duas TÉCNICAS;
  2. a sua máscara que repete os gatilhos de outra sua apareça como "nunca sai";
  3. bloco (# tipo: bloco), frases.txt e _legado não entrem na conta.
"""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conferir_usuario as cu

falhas = 0


def confere(nome, ok, extra=""):
    global falhas
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas += 1


def grava(raiz, rel, texto):
    p = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(texto)


tmp = tempfile.mkdtemp(prefix="rotrix_conferir_")
try:
    d = os.path.join(tmp, "dados")
    grava(d, "mascaras/msk/rx/ombro/normal.txt",
          "# gatilhos: raio x de ombro | rx do ombro\n# categoria: msk\n"
          "**RADIOGRAFIA DO OMBRO**\n\n**TÉCNICA:**  incidências anteroposterior e perfil de Neer.\n"
          "Exame realizado nas incidências anteroposterior, perfil de Neer e axilar.\n\n**ANÁLISE:**\nx.\n")
    grava(d, "mascaras/msk/rx/ombro/blk_x.txt", "# tipo: bloco\n# gatilhos: raio x de ombro\nx.\n")
    grava(d, "mascaras/msk/rx/ombro/frases.txt", "# gatilhos: raio x de ombro\n")
    grava(d, "mascaras/_legado/velho.txt", "# gatilhos: rx de joelho\nx\n")
    grava(d, "mascaras_usuario/rx/ombro/normal.txt",
          "# gatilhos: Raio-X de Ombro | rx do ombro\n# categoria: usuario\n"
          "**RADIOGRAFIA DO OMBRO**\n\n**TÉCNICA:** \nExame realizado nas incidências anteroposterior e perfil da escápula.\n\n"
          "**ANÁLISE:**\nx.\n")
    grava(d, "mascaras_usuario/rx/torax/normal.txt",
          "# gatilhos: rx de torax\n**RADIOGRAFIA DO TÓRAX**\n\n"
          "**TÉCNICA:**  Incidências em póstero-anterior e perfil.\nIncidência em anteroposterior.\n\n"
          "**ANÁLISE:**\nx.\n")
    grava(d, "mascaras_usuario/rx/ombro/normal_2.txt",
          "# gatilhos: raio x de ombro | rx do ombro\n**TÉCNICA:**  outra.\n")
    grava(d, "mascaras_usuario/rx/joelho/normal.txt", "# gatilhos: rx de joelho\n**TÉCNICA:**  y.\n")

    pares, mortas, suas, rotrix = cu.disputas(d)
    chave = ("usuario/rx/ombro/normal", "msk/rx/ombro/normal")
    confere("disputa achada pelos arquivos (acento e hífen normalizados)",
            chave in pares and sorted(pares[chave]) == ["raio x de ombro", "rx do ombro"], repr(pares))
    confere("a sua que repete outra sua aparece como 'nunca sai'",
            mortas.get("usuario/rx/ombro/normal_2") == "usuario/rx/ombro/normal", repr(mortas))
    confere("a que nunca sai não entra como disputa",
            not any(k[0] == "usuario/rx/ombro/normal_2" for k in pares))
    confere("bloco, frases.txt e _legado ficam fora",
            set(rotrix) == {"msk/rx/ombro/normal"}, repr(sorted(rotrix)))
    confere("joelho seu sem máscara do Rotrix: sem disputa",
            not any(k[0] == "usuario/rx/joelho/normal" for k in pares))
    confere("TÉCNICA lida dos dois lados",
            cu.tecnica(suas["usuario/rx/ombro/normal"][1]) ==
            ["Exame realizado nas incidências anteroposterior e perfil da escápula."]
            and cu.tecnica(rotrix["msk/rx/ombro/normal"][1])[0] ==
            "incidências anteroposterior e perfil de Neer.")
    confere("TÉCNICA de duas linhas sem 'Exame realizado' vem inteira",
            cu.tecnica(suas["usuario/rx/torax/normal"][1]) ==
            ["Incidências em póstero-anterior e perfil.", "Incidência em anteroposterior."],
            repr(cu.tecnica(suas["usuario/rx/torax/normal"][1])))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("conferir_usuario: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % falhas))
sys.exit(1 if falhas else 0)
