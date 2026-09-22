# -*- coding: utf-8 -*-
"""Normalização ortográfica determinística do banco de frases.

Regra: só corrige o que é erro objetivo — acento faltando, grafia pré-Acordo
Ortográfico de 1990, hífen indevido, erro de digitação. Nunca reescreve estilo
nem troca termo clínico por sinônimo. Toda troca é registrada para auditoria.
"""
import json, re, io, sys, collections

# (padrão, substituto, comentário)  — \b nas duas pontas, case-insensitive
# com preservação de maiúscula inicial.
REGRAS = [
    # --- erros de digitação ---
    (r"tendinpatia",        "tendinopatia",     "digitação"),
    (r"Degenearação",       "Degeneração",      "digitação"),
    (r"alteação",           "alteração",        "digitação"),
    (r"Bufford",            "Buford",           "epônimo (complexo de Buford)"),
    (r"Osgood[ -]Schlater", "Osgood-Schlatter", "epônimo"),
    (r"gaglionico",         "ganglionar",       "digitação"),
    (r"distencional",       "distensional",     "grafia"),
    (r"semimembranos\b",    "semimembranáceo",  "termo anatômico"),
    (r"liposubstituiç",     "lipossubstituiç",  "grafia (s dobrado entre vogais)"),
    (r"intra tendíneo",     "intratendíneo",    "aglutinação"),
    (r"menisco-capsula",    "menisco-cápsula",  "acento"),

    # --- acentos faltando ---
    (r"\binflamatorio\b",   "inflamatório",     "acento"),
    (r"\binflamatoria\b",   "inflamatória",     "acento"),
    (r"\bosteofito\b",      "osteófito",        "acento"),
    (r"\bosteofitos\b",     "osteófitos",       "acento"),
    (r"\bosteolise\b",      "osteólise",        "acento"),
    (r"\bclavicula\b",      "clavícula",        "acento"),
    (r"\bpoplitea\b",       "poplítea",         "acento"),
    (r"\btibia\b",          "tíbia",            "acento"),
    (r"\bobliqua\b",        "oblíqua",          "acento"),
    (r"\bobliquas\b",       "oblíquas",         "acento"),
    (r"\bmiotendinea\b",    "miotendínea",      "acento"),
    (r"\btroclea\b",        "tróclea",          "acento"),
    (r"\bcronica\b",        "crônica",          "acento"),
    (r"\bcronico\b",        "crônico",          "acento"),
    (r"\bcalcarea\b",       "calcária",         "acento"),
    (r"\bcritica\b",        "crítica",          "acento"),
    (r"\bextrusao\b",       "extrusão",         "acento"),
    (r"\bavulsao\b",        "avulsão",          "acento"),
    (r"\blesao\b",          "lesão",            "acento"),
    (r"\bossea\b",          "óssea",            "acento"),
    (r"\bosseo\b",          "ósseo",            "acento"),
    (r"\btendao\b",         "tendão",           "acento"),
    (r"\bbiceps\b",         "bíceps",           "acento"),
    (r"\bdeposito\b",       "depósito",         "acento"),
    (r"\bduvida\b",         "dúvida",           "acento"),
    (r"\bacromio\b",        "acrômio",          "acento"),
    (r"\bheterogeneo\b",    "heterogêneo",      "acento"),
    (r"\bhomogeneo\b",      "homogêneo",        "acento"),
    (r"\blabio\b",          "lábio",            "acento"),
    (r"\binsuficiencia\b",  "insuficiência",    "acento"),
    (r"\btrocanter\b",      "trocânter",        "acento"),
    (r"\bfovea\b",          "fóvea",            "acento"),
    (r"\bnecrose ossea\b",  "necrose óssea",    "acento"),

    # --- Acordo Ortográfico de 1990: ditongo aberto em paroxítona perde acento ---
    (r"\bdeltóide\b",       "deltoide",         "AO1990"),
    (r"\bdeltóides\b",      "deltoides",        "AO1990"),
    (r"\bsubdeltóide\b",    "subdeltoide",      "AO1990"),
    (r"\bglenóide\b",       "glenoide",         "AO1990"),
    (r"\bhialóide\b",       "hialoide",         "AO1990"),
    # proparoxitonas MANTEM o acento: sub-del-TOI-de-a, gle-NOI-de-a
    (r"\bsubdeltoidea\b",   "subdeltóidea",     "proparoxítona"),
    (r"\bsubaracnoidea\b",  "subaracnóidea",    "proparoxítona"),
    (r"\bglenoidea\b",      "glenóidea",        "proparoxítona"),
    (r"\bidéia\b",          "ideia",            "AO1990"),

    # --- prefixos: AO1990 aglutina quando não há choque de vogais ---
    (r"\bsupra-espinhal\b", "supraespinhal",    "AO1990 (prefixo)"),
    (r"\bsupra-espinal\b",  "supraespinal",     "AO1990 (prefixo)"),
    (r"\binfra-espinhal\b", "infraespinhal",    "AO1990 (prefixo)"),
    (r"\binfra-espinal\b",  "infraespinal",     "AO1990 (prefixo)"),
    (r"\bintra-substancial\b", "intrassubstancial", "AO1990 (prefixo + s dobrado)"),
    (r"\bintra-substanciais\b","intrassubstanciais","AO1990 (prefixo + s dobrado)"),
    (r"\bintra-substância\b",  "intrassubstância",  "AO1990 (prefixo + s dobrado)"),
    (r"\bintra-ósse",       "intraósse",        "AO1990 (prefixo)"),
    (r"\bperi-tendin",      "peritendin",       "AO1990 (prefixo)"),

    # --- pares direcionais: AO1990 aglutina, com s dobrado onde couber ---
    (r"\bântero-lateral\b",   "anterolateral",     "AO1990 (direcional)"),
    (r"\bantero-lateral\b",   "anterolateral",     "AO1990 (direcional)"),
    (r"\bântero-medial\b",    "anteromedial",      "AO1990 (direcional)"),
    (r"\bantero-medial\b",    "anteromedial",      "AO1990 (direcional)"),
    (r"\bântero-posterior\b", "anteroposterior",   "AO1990 (direcional)"),
    (r"\bantero-posterior\b", "anteroposterior",   "AO1990 (direcional)"),
    (r"\bântero-superior\b",  "anterossuperior",   "AO1990 (direcional)"),
    (r"\bantero-superior\b",  "anterossuperior",   "AO1990 (direcional)"),
    (r"\bântero-inferior\b",  "anteroinferior",    "AO1990 (direcional)"),
    (r"\bantero-inferior\b",  "anteroinferior",    "AO1990 (direcional)"),
    (r"\bpóstero-lateral\b",  "posterolateral",    "AO1990 (direcional)"),
    (r"\bpostero-lateral\b",  "posterolateral",    "AO1990 (direcional)"),
    (r"\bpóstero-medial\b",   "posteromedial",     "AO1990 (direcional)"),
    (r"\bpostero-medial\b",   "posteromedial",     "AO1990 (direcional)"),
    (r"\bpóstero-superior\b", "posterossuperior",  "AO1990 (direcional)"),
    (r"\bpostero-superior\b", "posterossuperior",  "AO1990 (direcional)"),
    (r"\bpóstero-inferior\b", "posteroinferior",   "AO1990 (direcional)"),
    (r"\bpostero-inferior\b", "posteroinferior",   "AO1990 (direcional)"),
    (r"\bsúpero-lateral\b",   "superolateral",     "AO1990 (direcional)"),
    (r"\bsupero-lateral\b",   "superolateral",     "AO1990 (direcional)"),
    (r"\bsúpero-medial\b",    "superomedial",      "AO1990 (direcional)"),
    (r"\bsupero-medial\b",    "superomedial",      "AO1990 (direcional)"),
    (r"\bínfero-lateral\b",   "inferolateral",     "AO1990 (direcional)"),
    (r"\binfero-lateral\b",   "inferolateral",     "AO1990 (direcional)"),
    (r"\bínfero-medial\b",    "inferomedial",      "AO1990 (direcional)"),
    (r"\binfero-medial\b",    "inferomedial",      "AO1990 (direcional)"),

    # --- espaçamento e pontuação ---
    (r"  +",                " ",                 "espaço duplo"),
    (r" ,",                 ",",                 "espaço antes de vírgula"),
    (r" \.",                ".",                 "espaço antes de ponto"),
]

COMPILADAS = [(re.compile(p, re.IGNORECASE), s, c) for p, s, c in REGRAS]
CAMPOS = ("titulo", "descricao", "conclusao", "obs", "estrutura")


def _casar(original, novo):
    """Preserva maiúscula inicial do trecho original."""
    if original[:1].isupper() and novo[:1].islower():
        return novo[:1].upper() + novo[1:]
    return novo


def corrigir(texto, contador=None):
    if not texto:
        return texto
    for rx, sub, motivo in COMPILADAS:
        def _rep(m):
            if contador is not None:
                contador[(m.group(0), sub, motivo)] += 1
            return _casar(m.group(0), sub)
        texto = rx.sub(_rep, texto)
    return texto.strip()


def main(entrada, saida, relatorio):
    dados = json.load(open(entrada, encoding="utf-8"))
    cont = collections.Counter()
    for reg in dados:
        for campo in CAMPOS:
            if campo in reg:
                reg[campo] = corrigir(reg[campo], cont)
    json.dump(dados, io.open(saida, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    linhas = ["RELATÓRIO DE CORREÇÃO ORTOGRÁFICA",
              "=" * 60, ""]
    total = 0
    for (de, para, motivo), n in sorted(cont.items(), key=lambda x: -x[1]):
        linhas.append("%4dx  %-28s -> %-28s  [%s]" % (n, de, para, motivo))
        total += n
    linhas += ["", "=" * 60, "total de correções: %d" % total,
               "registros: %d" % len(dados)]
    io.open(relatorio, "w", encoding="utf-8").write("\n".join(linhas))
    print("\n".join(linhas))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "frases.json",
         sys.argv[2] if len(sys.argv) > 2 else "frases_corrigidas.json",
         sys.argv[3] if len(sys.argv) > 3 else "relatorio_ortografia.txt")
