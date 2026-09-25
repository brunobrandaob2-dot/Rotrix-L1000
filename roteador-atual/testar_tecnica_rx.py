# -*- coding: utf-8 -*-
"""As incidencias da TECNICA de cada RX, como ele ditou em 25/09/2026.

Trava para nao voltar atras: cada regiao de RX que ele nomeou tem de sair com aquela
TECNICA, e as mascaras alteradas da mesma regiao tem de dizer a MESMA coisa que a normal
(se divergirem, o laudo muda de tecnica quando entra um achado, e ninguem ve).

Duas mascaras ficam de fora de proposito, por terem tecnica propria:
  torax/aguda_leito              -> anteroposterior, no leito, com aparelho portatil
  punho/aguda*fratura_escafoide  -> serie do escafoide, com incidencias complementares
"""

import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import roteador

AQUI = os.path.dirname(os.path.abspath(__file__))
falhas = []


def confere(nome, cond, extra=""):
    print(("ok      " if cond else "FALHOU  ") + nome + (("  " + extra) if extra and not cond else ""))
    if not cond:
        falhas.append(nome)


# (ditado, regiao, primeira linha da TECNICA, segunda linha ou None)
ESPERADO = [
    ("raio x de torax", "medicina_interna/rx/torax",
     "incidências posteroanterior e perfil, em ortostase.",
     "Exame realizado na incidência anteroposterior."),
    ("raio x de abdome", "medicina_interna/rx/abdome",
     "incidência anteroposterior em decúbito dorsal.", None),
    ("raio x de abdome agudo", "medicina_interna/rx/abdome_agudo",
     "incidências posteroanterior do tórax, abdome em ortostase e abdome em decúbito dorsal.",
     None),
    ("raio x de tornozelo direito", "msk/rx/tornozelo",
     "incidências anteroposterior e perfil.", None),
    ("raio x de pe esquerdo", "msk/rx/pe",
     "incidências anteroposterior e oblíqua.", None),
    ("raio x de punho direito", "msk/rx/punho",
     "incidências posteroanterior e perfil.", None),
    ("raio x de bacia", "msk/rx/bacia",
     "incidência anteroposterior da bacia.",
     "Exame realizado nas incidências anteroposterior e em rã (Lauenstein)."),
    ("raio x de clavicula direita", "msk/rx/clavicula",
     "incidências anteroposterior e Zanca (anteroposterior com inclinação cranial de 15 graus).",
     None),
    ("raio x de ombro esquerdo", "msk/rx/ombro",
     "incidências anteroposterior, perfil de Neer e axilar.", None),
    # as que ele confirmou que já estavam certas
    ("raio x de coluna lombar", "msk/rx/coluna_lombar",
     "incidências anteroposterior e perfil.", None),
    ("raio x de femur direito", "msk/rx/femur",
     "incidências anteroposterior e perfil.", None),
    ("raio x de antebraco esquerdo", "msk/rx/antebraco",
     "incidências anteroposterior e perfil.", None),
]

# mascaras que guardam TECNICA propria de proposito
EXCECOES = {
    # torax no leito: aparelho portatil, incidencia unica
    "medicina_interna/rx/torax": {"aguda_leito.txt"},
    # serie do escafoide: precisa das incidencias complementares
    "msk/rx/punho": {"aguda_fratura_escafoide.txt", "aguda_suspeita_fratura_escafoide.txt"},
    # pneumoperitonio ja vinha com a tecnica de abdome agudo (decubito + ortostase +
    # torax em PA). Fica como esta ate ele decidir se essa mascara muda de regiao.
    "medicina_interna/rx/abdome": {"aguda_pneumoperitonio.txt"},
    # dinamicas: perfis em flexao e extensao, tecnica propria
    "msk/rx/coluna_lombar": {"normal_dinamicas.txt"},
}

print("=== a TÉCNICA que sai ao ditar ===")
for ditado, regiao, linha1, linha2 in ESPERADO:
    texto, origem = roteador.rotear(ditado)
    linhas = (texto or "").split("\n")
    tec = [l for l in linhas if l.startswith("**TÉCNICA:**")]
    ok_regiao = regiao in (origem or "")
    confere("%-30s cai em %s" % (ditado, regiao), ok_regiao, "caiu em %s" % origem)
    if not tec:
        confere("%-30s tem TÉCNICA" % ditado, False, "sem TÉCNICA")
        continue
    i = linhas.index(tec[0])
    confere("%-30s linha 1 da TÉCNICA" % ditado,
            tec[0] == "**TÉCNICA:**  " + linha1, "saiu: %s" % tec[0])
    seguinte = linhas[i + 1] if i + 1 < len(linhas) else ""
    if linha2:
        confere("%-30s linha 2 da TÉCNICA" % ditado, seguinte == linha2,
                "saiu: %r" % seguinte)
    else:
        confere("%-30s NÃO tem linha 2" % ditado, not seguinte.startswith("Exame realizado"),
                "saiu sobrando: %r" % seguinte)

print()
print("=== normal e alteradas da mesma região dizem a mesma TÉCNICA ===")
for _ditado, regiao, linha1, linha2 in ESPERADO:
    pasta = os.path.join(AQUI, "dados", "mascaras", regiao)
    esperado = ["**TÉCNICA:**  " + linha1] + ([linha2] if linha2 else [])
    divergentes = []
    for a in sorted(glob.glob(os.path.join(pasta, "*.txt"))):
        nome = os.path.basename(a)
        if nome == "frases.txt" or nome in EXCECOES.get(regiao, set()):
            continue
        linhas = io.open(a, encoding="utf-8").read().split("\n")
        alvo = [i for i, l in enumerate(linhas) if l.startswith("**TÉCNICA:**")]
        if not alvo:
            continue                          # bloco, não tem TÉCNICA
        i = alvo[0]
        fim = i + 1
        while fim < len(linhas) and linhas[fim].startswith("Exame realizado"):
            fim += 1
        if [l.rstrip() for l in linhas[i:fim]] != esperado:
            divergentes.append(nome)
    confere("%-34s todas as máscaras iguais" % regiao, not divergentes,
            "divergem: " + ", ".join(divergentes))

print()
print("=== a mortise saiu do tornozelo e não voltou ===")
sobrou = [f for f in glob.glob(os.path.join(AQUI, "dados", "mascaras", "msk", "rx",
                                            "tornozelo", "*.txt"))
          if "mortise" in io.open(f, encoding="utf-8").read().lower()]
confere("nenhuma máscara de tornozelo fala de mortise", not sobrou,
        "ainda fala: " + ", ".join(os.path.basename(f) for f in sobrou))

print()
print("=== abdome agudo é máscara própria, e não rouba o abdome simples ===")
t_ag, o_ag = roteador.rotear("rotina de abdome agudo")
t_s, o_s = roteador.rotear("rx de abdome")
confere("abdome agudo tem máscara própria", "abdome_agudo" in (o_ag or ""), o_ag or "")
confere("abdome simples continua no abdome simples",
        "rx/abdome/" in (o_s or ""), o_s or "")
confere("abdome agudo menciona o tórax na TÉCNICA", "tórax" in (t_ag or ""))
confere("abdome simples NÃO menciona o tórax", "tórax" not in (t_s or ""))

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), "; ".join(falhas[:6])))
    raise SystemExit(1)
print("técnica das radiografias: tudo certo")
