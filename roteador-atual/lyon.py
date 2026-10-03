# -*- coding: utf-8 -*-
"""TC dos joelhos — protocolo de Lyon, estruturado (27–28/09).

28/09: ele mandou A máscara dele ("eu quero que seja essa a máscara do joelho de
Lyon nos estruturados"): texto corrido para patela, fêmur/tíbia, espaços e
derrame, e uma TABELA de medidas por joelho, com o valor normal de cada uma:

    Ângulo do sulco troclear                ≤ 143º
    Razão troclear medial-lateral           > 40%
    Inclinação troclear lateral             > 11º
    Inclinação patelar ("tilt")             < 20º
    Inclinação patelar ("tilt") contração   10-26º
    Índice de Insall-Salvati                0,8 - 1,3
    TA-GT                                   15 mm (+/- 4)

O texto dele entra como ele escreveu (inclusive o "º"). O que é regra:

1. **Os valores normais são os da máscara dele** — é contra eles que cada medida
   é julgada (TA-GT normal de 11 a 19 mm; 20 mm já é alterado).
2. **Campo vazio não vira lacuna**: a linha da tabela sai; um joelho sem nenhuma
   medida fica sem tabela.
3. **Os dois joelhos**: título "DO JOELHO DIREITO E ESQUERDO" e ", bilateral" no
   texto corrido, como na máscara. Um joelho só: sem "bilateral".
4. **Seções do modelo dele** (INDICAÇÃO CLÍNICA, COMPARAÇÃO, CONCLUSÃO): a máscara
   que ele mandou não as tem, mas o modelo dele diz que elas não saem. A
   CONCLUSÃO lista só o que está fora do normal; sem nada, FRASE_NORMAL.

O passo a passo (onde, como, normal) também sai daqui: corrigir um texto do guia
é ATUALIZAR, sem .exe novo.
"""

TITULO = "TOMOGRAFIA COMPUTADORIZADA DO {alvo}"
TECNICA = "Foram realizados cortes tomográficos computadorizados axiais do joelho em extensão."
COMPARACAO = "estudos anteriores não disponíveis para análise comparativa."
FRASE_NORMAL = "Parâmetros femoropatelares dentro dos limites da normalidade."

LADOS = {"direito": ["d"], "esquerdo": ["e"], "ambos": ["d", "e"]}
NOME = {"d": ("direita", "direito"), "e": ("esquerda", "esquerdo")}

POSICAO = ["normoposicionada no sulco troclear",
           "discretamente lateralizada em relação ao sulco troclear",
           "subluxada lateralmente"]
WIBERG = ["1", "2", "3"]

# (id, rótulo na tabela, unidade, valor normal como na máscara, julgamento, frase da conclusão)
# julgamento(x) -> None (normal) ou a palavra do estado
LINHAS = [
    ("sulco", "Ângulo do sulco troclear", "º", "≤ 143º",
     lambda x: "aumentado" if x > 143 else None, "Ângulo do sulco troclear {estado}"),
    ("razao", "Razão troclear medial-lateral", "%", "> 40%",
     lambda x: "reduzida" if x <= 40 else None, "Razão troclear medial-lateral {estado}"),
    ("lti", "Inclinação troclear lateral", "º", "> 11º",
     lambda x: "reduzida" if x <= 11 else None, "Inclinação troclear lateral {estado}"),
    ("tilt_rel", "Inclinação patelar (\"tilt\")", "º", "< 20º",
     lambda x: "aumentada" if x >= 20 else None, "Inclinação patelar {estado}"),
    ("tilt_con", "Inclinação patelar (\"tilt\") contração", "º", "10-26º",
     lambda x: "aumentada" if x > 26 else ("reduzida" if x < 10 else None),
     "Inclinação patelar sob contração {estado}"),
    ("insall", "Índice de Insall-Salvati", "", "0,8 - 1,3",
     lambda x: "aumentado" if x > 1.3 else ("reduzido" if x < 0.8 else None),
     "Índice de Insall-Salvati {estado}"),
    ("tagt", "TA-GT", " mm", "15 mm (+/- 4)",
     lambda x: "aumentada" if x > 19 else ("reduzida" if x < 11 else None),
     "Distância TA-GT {estado}"),
]
# a ordem da CONCLUSÃO: o que mais pesa na instabilidade primeiro
ORDEM_CONCLUSAO = ["sulco", "razao", "lti", "insall", "tagt", "tilt_rel", "tilt_con"]
NUMEROS = tuple(l[0] for l in LINHAS)

# colunas da tabela (texto): rótulo até 44, "Mensurado" até 60, depois o normal
COL_1, COL_2 = 44, 60

PASSOS = [
    {"id": "troclea", "titulo": "Tróclea: sulco, razão das facetas e inclinação lateral",
     "onde": "Axial no primeiro corte proximal com a tróclea completa (intercôndilo em "
             "\"arco romano\"), em extensão.",
     "como": ["Ângulo do sulco: trace as duas facetas a partir do ponto mais profundo do sulco "
              "e meça o ângulo entre elas.",
              "Razão medial-lateral: comprimento da faceta medial ÷ comprimento da faceta "
              "lateral × 100.",
              "Inclinação troclear lateral: ângulo entre a faceta lateral e a tangente ao "
              "contorno posterior dos côndilos."],
     "corte": "normal: sulco ≤ 143º · razão > 40% · inclinação lateral > 11º",
     "campos": [{"id": "sulco", "rotulo": "sulco", "tipo": "numero", "unidade": "º"},
                {"id": "razao", "rotulo": "razão M/L", "tipo": "numero", "unidade": "%"},
                {"id": "lti", "rotulo": "inclinação lateral", "tipo": "numero", "unidade": "º"}]},
    {"id": "patela", "titulo": "Patela: posição e altura (Insall-Salvati)",
     "onde": "Axial para a posição no sulco; sagital no meio da patela para a altura.",
     "como": ["Posição: a patela está no sulco troclear, lateralizada ou subluxada?",
              "Tendão: do polo inferior da patela à inserção na tuberosidade da tíbia.",
              "Patela: o maior comprimento (diagonal) da patela.",
              "Índice = tendão ÷ patela."],
     "corte": "normal: Insall-Salvati de 0,8 a 1,3",
     "campos": [{"id": "posicao", "rotulo": "posição", "tipo": "opcao", "opcoes": POSICAO},
                {"id": "insall", "rotulo": "Insall-Salvati", "tipo": "numero", "unidade": ""}]},
    {"id": "femoropatelar", "titulo": "Inclinação patelar (\"tilt\")",
     "onde": "Axial no corte de maior largura da patela, em extensão, com o quadríceps "
             "relaxado e contraído.",
     "como": ["Trace a tangente ao contorno posterior dos dois côndilos femorais.",
              "Trace o eixo transverso da patela (a linha da sua maior largura).",
              "Meça o ângulo entre as duas; repita com o quadríceps contraído."],
     "corte": "normal: relaxado < 20º · contração de 10 a 26º",
     "campos": [{"id": "tilt_rel", "rotulo": "relaxado", "tipo": "numero", "unidade": "º"},
                {"id": "tilt_con", "rotulo": "contração", "tipo": "numero", "unidade": "º"}]},
    {"id": "tagt", "titulo": "TA-GT (tuberosidade anterior – garganta troclear)",
     "onde": "Dois axiais superpostos: o do sulco troclear (arco romano) e o da inserção do "
             "tendão patelar na tuberosidade.",
     "como": ["Tangente ao contorno posterior dos côndilos femorais.",
              "Perpendicular pelo ponto mais profundo do sulco troclear.",
              "Perpendicular pelo centro da inserção do tendão patelar na tuberosidade.",
              "Distância entre as duas, em mm. Pés em rotação neutra: 5º de abdução somam "
              "cerca de 3,4 mm."],
     "corte": "normal: 15 mm (+/- 4), ou seja, de 11 a 19 mm",
     "campos": [{"id": "tagt", "rotulo": "TA-GT", "tipo": "numero", "unidade": "mm"}]},
]

GLOBAIS = [{"id": "wiberg", "rotulo": "Morfologia da patela (Wiberg)", "opcoes": WIBERG,
            "padrao": "2", "prefixo": "tipo "}]


def campos():
    """O que a tela desenha: lados, passos (com o guia) e as escolhas do exame todo."""
    return {"ok": True, "tipo": "lyon", "lados": list(LADOS), "passos": PASSOS,
            "globais": GLOBAIS, "frase_normal": FRASE_NORMAL}


def _num(v):
    """'16', '8,5', '22.5' -> float; vazio ou texto -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(",", ".").rstrip("º°%").strip()
    if t.lower().endswith("mm"):
        t = t[:-2].strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _fmt(x, casas=1):
    """20.0 -> '20'; 8.5 -> '8,5'; 1.2 -> '1,2' (vírgula, sem zero à toa)."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return ("%.*f" % (casas, x)).rstrip("0").rstrip(".").replace(".", ",")


def _valor(chave, unidade, x):
    return _fmt(x, 2 if chave == "insall" else 1) + unidade


def _tabela(fem, masc, v):
    """As linhas da tabela de um joelho (sem as medidas vazias), ou [] sem medida nenhuma."""
    corpo = []
    for chave, rotulo, un, normal, _j, _f in LINHAS:
        if v[chave] is None:
            continue
        corpo.append(rotulo.ljust(COL_1) + _valor(chave, un, v[chave]).ljust(COL_2 - COL_1) + normal)
    if not corpo:
        return []
    return ["Medidas joelho %s" % masc, "".ljust(COL_1) + "Mensurado".ljust(COL_2 - COL_1) + "Valores normais"] + corpo


def _conclusao(fem, v):
    saida = []
    frase = {l[0]: l for l in LINHAS}
    for chave in ORDEM_CONCLUSAO:
        x = v[chave]
        if x is None:
            continue
        _c, _r, un, _n, julga, molde = frase[chave]
        estado = julga(x)
        if not estado:
            continue
        t = molde.format(estado=estado) + " à %s (%s)" % (fem, _valor(chave, un, x))
        if chave == "insall":
            t += ", compatível com patela %s" % ("alta" if estado == "aumentado" else "baixa")
        saida.append(t + ".")
    return saida


def _avisos(fem, v, avisos):
    if v["tagt"] is not None and v["tagt"] < 5:
        avisos.append("TA-GT de %s mm à %s: se o visualizador deu em cm, digite em mm (1,60 cm = 16 mm)"
                      % (_fmt(v["tagt"]), fem))
    if v["insall"] is not None and v["insall"] > 3:
        avisos.append("Insall-Salvati de %s à %s: é uma razão (0,8 a 1,3), confira" % (_fmt(v["insall"], 2), fem))
    if v["razao"] is not None and not (0 < v["razao"] <= 150):
        avisos.append("razão medial-lateral de %s%% à %s: confira" % (_fmt(v["razao"]), fem))
    if v["sulco"] is not None and not (90 <= v["sulco"] <= 180):
        avisos.append("ângulo do sulco de %sº à %s: confira" % (_fmt(v["sulco"]), fem))


def montar(pedido):
    """{'lado', 'valores': {campo_d/e}, 'globais': {'wiberg': '2'}} -> o laudo inteiro."""
    if not isinstance(pedido, dict):
        return {"ok": False, "motivo": "pedido_invalido"}
    lado = pedido.get("lado") or "direito"
    if lado not in LADOS:
        return {"ok": False, "motivo": "lado_desconhecido", "aceitos": list(LADOS)}
    valores = pedido.get("valores") or {}
    globais = pedido.get("globais") or {}
    if not isinstance(valores, dict) or not isinstance(globais, dict):
        return {"ok": False, "motivo": "valores_invalidos"}
    wiberg = str(globais.get("wiberg") or "2")
    if wiberg not in WIBERG:
        wiberg = "2"

    lados = LADOS[lado]
    dois = len(lados) == 2
    bil = ", bilateral" if dois else ""
    avisos, tabelas, conclusao, posicoes = [], [], [], {}
    for s in lados:
        fem, masc = NOME[s]
        v = {k: _num(valores.get("%s_%s" % (k, s))) for k in NUMEROS}
        pos = str(valores.get("posicao_%s" % s) or "").strip()
        posicoes[s] = pos if pos in POSICAO else POSICAO[0]
        _avisos(fem, v, avisos)
        t = _tabela(fem, masc, v)
        if t:
            tabelas.append(t)
        if posicoes[s] == POSICAO[1]:
            conclusao.append("Patela %s discretamente lateralizada em relação ao sulco troclear." % fem)
        elif posicoes[s] == POSICAO[2]:
            conclusao.append("Subluxação lateral da patela %s." % fem)
        conclusao.extend(_conclusao(fem, v))
    if not conclusao:
        conclusao = [FRASE_NORMAL]

    # patela: uma frase só quando os dois lados estão iguais (como na máscara)
    if not dois or posicoes["d"] == posicoes["e"]:
        patela = ("Patela com densidade e contornos preservados, %s, apresentando morfologia do "
                  "tipo %s de Wiberg%s." % (posicoes[lados[0]], wiberg, bil))
    else:
        patela = ("Patela com densidade e contornos preservados, apresentando morfologia do tipo %s "
                  "de Wiberg, bilateral. Patela direita %s; patela esquerda %s."
                  % (wiberg, posicoes["d"], posicoes["e"]))

    if dois:
        alvo = "JOELHO DIREITO E ESQUERDO"
    else:
        alvo = "JOELHO " + lado.upper()

    analise = [
        patela,
        "Fêmur distal e tíbia proximal sem alterações%s." % bil,
        "Espaços articulares com amplitudes anatômicas%s." % bil,
        "Não há evidências de derrame articular. Planos musculogordurosos íntegros%s." % bil,
    ]
    for t in tabelas:
        analise += [""] + t

    texto = "\n".join([
        "**" + TITULO.format(alvo=alvo) + "**",
        "",
        "**TÉCNICA:**  " + TECNICA,
        "",
        "**INDICAÇÃO CLÍNICA:**  Em anexo.",
        "",
        "**ANÁLISE:**",
    ] + analise + [
        "",
        "**COMPARAÇÃO:**  " + COMPARACAO,
        "",
        "**CONCLUSÃO:**",
    ] + conclusao)
    return {"ok": True, "tipo": "lyon", "lado": lado, "texto": texto,
            "conclusao": "\n".join(conclusao), "avisos": avisos, "completo": True}


def mascara_de_voz():
    """A máscara que o DITADO abre ("tomografia dos joelhos protocolo de Lyon").

    03/10, ele: "a parte do joelho no protocolo de Lyon não está com a máscara mais
    atual que a gente fez". Não estava: a máscara de voz dele (mascaras_usuario/tc/
    joelho/tc_joelhos_protocolo_de_lyon.txt) era a de 27/09 — Caton-Deschamps,
    TT-PCL, Dejour —, e a de 28/09 (a dele, texto corrido + tabela por joelho) só
    existia na aba Estruturados. Agora a de voz sai DAQUI: os dois joelhos, a
    tabela com a coluna "Mensurado" em branco para ele preencher, os valores normais
    dele. Mudou o Lyon? Muda num lugar só."""
    r = montar({"lado": "ambos", "valores": {}, "globais": {}})
    linhas = r["texto"].split("\n")
    i = linhas.index("**COMPARAÇÃO:**  " + COMPARACAO)
    tabelas = []
    for s_, (fem, masc) in (("d", NOME["d"]), ("e", NOME["e"])):
        corpo = [rot.ljust(COL_1) + "".ljust(COL_2 - COL_1) + normal
                 for _k, rot, _u, normal, _j, _f in LINHAS]
        tabelas += ["Medidas joelho %s" % masc,
                    "".ljust(COL_1) + "Mensurado".ljust(COL_2 - COL_1) + "Valores normais"] + corpo + [""]
    return "\n".join(linhas[:i] + tabelas + linhas[i:])

