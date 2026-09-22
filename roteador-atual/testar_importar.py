# -*- coding: utf-8 -*-
"""Testa o importador de máscaras/laudos próprios SEM mexer na pasta real
(usa pastas temporárias). Roda no GitHub a cada envio: python testar_importar.py"""
import io, json, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import importar_usuario as iu

tmp = tempfile.mkdtemp()
iu.PASTA_MASC = os.path.join(tmp, "mascaras_usuario")
iu.PASTA_ESTILO = os.path.join(tmp, "estilo")
iu.CONFIG = os.path.join(tmp, "config.json")
iu.DADOS = tmp
iu.refazer_base = lambda: (True, "base (simulada)")
falhas = []
def confere(nome, cond, extra=""):
    print(("ok    " if cond else "FALHOU") + "  " + nome + (("  " + str(extra)) if extra and not cond else ""))
    if not cond:
        falhas.append(nome)

MASC = """gatilhos: minha tc de torax
TOMOGRAFIA COMPUTADORIZADA DO TÓRAX
TÉCNICA: sem contraste.
RELATÓRIO:
Parênquima pulmonar normal.

RADIOGRAFIA DO JOELHO DIREITO
ANÁLISE:
Espaços articulares do joelho direito preservados.

RADIOGRAFIA DA MÃO ESQUERDA
Paciente: Fulano
ANÁLISE:
Ossos normais.

ULTRASSONOGRAFIA DE ABDOME TOTAL
ANÁLISE:
Rim direito e rim esquerdo sem alterações, com dimensões normais.
"""
arq = os.path.join(tmp, "minhas.txt")
open(arq, "w", encoding="utf-8").write(MASC)
r = iu.importar_mascaras(arq)
tit = [x["titulo"] for x in r["importadas"]]
confere("separa pelo título em CAIXA ALTA", len(tit) == 3, tit)
confere("recusa máscara com dado de paciente", len(r["recusadas"]) == 1 and "paciente" in r["recusadas"][0]["motivo"])
confere("comando escrito pelo usuário entra", "minha tc de torax" in r["importadas"][0]["comandos"])
joelho = open(os.path.join(iu.PASTA_MASC, "rx", "joelho", "normal.txt"), encoding="utf-8").read()
confere("lado do título vira lacuna", "{LADO|DIREITO/ESQUERDO}" in joelho and "DIREITO**" not in joelho)
confere("lado do texto vira lacuna (um lado só)", "joelho {lado|direito/esquerdo}" in joelho)
us = open(os.path.join(iu.PASTA_MASC, "us", "abdome_total", "normal.txt"), encoding="utf-8").read()
confere("dois lados no texto: fica como está", "Rim direito e rim esquerdo" in us)
confere("cabeçalho em negrito", "**ANÁLISE:**" in joelho and joelho.split("\n")[6].startswith("**RADIOGRAFIA"))

# docx com quebra de página
doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
       '<w:body><w:p><w:r><w:t>TOMOGRAFIA DE CRÂNIO</w:t></w:r></w:p><w:p><w:r><w:t>ANÁLISE: normal.</w:t></w:r></w:p>'
       '<w:p><w:r><w:br w:type="page"/></w:r></w:p><w:p><w:r><w:t>RADIOGRAFIA DE TÓRAX</w:t></w:r></w:p>'
       '<w:p><w:r><w:t>ANÁLISE: normal.</w:t></w:r></w:p></w:body></w:document>')
dx = os.path.join(tmp, "m.docx")
with zipfile.ZipFile(dx, "w") as z:
    z.writestr("word/document.xml", doc)
confere("lê .docx e separa na quebra de página", len(iu.separar(iu.ler_arquivo(dx))) == 2)
rtf = os.path.join(tmp, "m.rtf")
open(rtf, "w", encoding="latin-1").write(r"{\rtf1\ansi{\fonttbl{\f0 Arial;}}RADIOGRAFIA DE T\'d3RAX\par AN\'c1LISE: normal.\par}")
confere("lê .rtf com acento", "RADIOGRAFIA DE TÓRAX" in iu.ler_arquivo(rtf))

# laudos de estilo
LAUDOS = """Paciente: Fulano
Data: 01/02/2025
TOMOGRAFIA DO CRÂNIO
ANÁLISE:
Redução volumétrica encefálica difusa, com alargamento dos sulcos.
---
RADIOGRAFIA DO TÓRAX
Prontuário 123456789
ANÁLISE:
Consolidação no lobo inferior direito.
"""
la = os.path.join(tmp, "laudos.txt")
open(la, "w", encoding="utf-8").write(LAUDOS)
r = iu.importar_laudos(la)
salvos = [open(os.path.join(iu.PASTA_ESTILO, a), encoding="utf-8").read() for a in os.listdir(iu.PASTA_ESTILO)]
confere("laudo: tira o cabeçalho do paciente e entra", r["importados"] == 1 and "Fulano" not in salvos[0]
        and "01/02/2025" not in salvos[0])
confere("laudo com identificador no corpo não entra", len(r["recusados"]) == 1)

# fonte e assinatura
confere("fonte padrão é rotrix", iu.fonte_atual() == "rotrix" and iu.assinatura_usuario() == "rotrix|0|0|0")
iu.definir_fonte("ambas")
confere("assinatura muda com as máscaras do usuário", iu.assinatura_usuario().startswith("ambas|3|"))

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), ", ".join(falhas)))
    sys.exit(1)
print("importador: tudo certo")
