# -*- coding: utf-8 -*-
"""TC dos joelhos — protocolo de Lyon, estruturado (27/09).

Ele pediu o Lyon na aba Estruturados, com o passo a passo de como medir ao lado
de cada campo (o infográfico). Mesma regra dos outros estruturados:

1. **A frase sai por regra, não pela IA.** Os mesmos números dão sempre o mesmo
   laudo. Os cortes são os do infográfico:
   - ângulo do sulco acima de 145° = aumentado;
   - Caton-Deschamps acima de 1,2 = patela alta, abaixo de 0,6 = patela baixa;
   - inclinação patelar acima de 20° (quadríceps relaxado) = aumentada;
   - TT-TG até 15 mm normal, de 15 a 19 limítrofe, 20 ou mais aumentada;
   - TT-PCL acima de 24 mm = aumentada.
2. **Campo vazio não vira lacuna**: a linha sai (regra de urgência dele). Só a
   tróclea, a patela e as estruturas ósseas têm frase normal por padrão.
3. **A CONCLUSÃO só tem o que está alterado ou limítrofe**, lado a lado. Sem nada
   alterado, a frase normal (FRASE_NORMAL) — a dele, quando ele disser outra.
4. **O que ele corrigiu fica**: "tróclea rasa" existe sem ser displasia (27/09,
   o caso do TT-TG de 16 mm). A tela avisa, sem trocar a escolha dele, quando o
   ângulo do sulco passa de 145° com a tróclea marcada como habitual ou rasa.

O passo a passo (onde, como, corte) também sai daqui, para a tela só desenhar:
corrigir um texto do guia é ATUALIZAR, sem .exe novo.
"""

TITULO = "TOMOGRAFIA COMPUTADORIZADA {alvo} - PROTOCOLO DE LYON"
TECNICA = ("aquisições tomográficas {alvo_min} conforme protocolo de Lyon, sem injeção "
           "intravenosa de meio de contraste iodado.")
COMPARACAO = "estudos anteriores não disponíveis para análise comparativa."
FRASE_NORMAL = "Parâmetros femoropatelares dentro dos limites da normalidade."

LADOS = {"direito": ["d"], "esquerdo": ["e"], "ambos": ["d", "e"]}
NOME = {"d": ("direita", "direito"), "e": ("esquerda", "esquerdo")}

TROCLEA = ["habitual", "rasa", "displasia A", "displasia B", "displasia C", "displasia D"]
POSICAO = ["centrada", "discreta lateralização", "subluxação lateral"]
OSSOS = ["sem fraturas ou lesões ósseas focais evidentes",
         "sem outras alterações ósseas significativas"]

# O guia: um passo por linha da máscara. Os ids dos campos são os do formulário.
PASSOS = [
    {"id": "troclea", "titulo": "Tróclea femoral: displasia de Dejour",
     "onde": "Sagital em perfil verdadeiro, pelo sulco; e axial no corte proximal da tróclea.",
     "como": ["Na sagital, procure três sinais: cruzamento (a linha do fundo do sulco cruza o "
              "contorno anterior dos côndilos), esporão supratroclear e duplo contorno.",
              "No axial, trace as duas facetas a partir do ponto mais profundo do sulco e meça "
              "o ângulo entre elas.",
              "A: só cruzamento, rasa e simétrica · B: cruzamento e esporão, plana ou convexa · "
              "C: cruzamento e duplo contorno, faceta lateral convexa e medial hipoplásica · "
              "D: os três sinais e um degrau vertical (\"penhasco\")."],
     "corte": "ângulo do sulco acima de 145° = displasia",
     "campos": [{"id": "troclea", "rotulo": "tróclea", "tipo": "opcao", "opcoes": TROCLEA},
                {"id": "sulco", "rotulo": "ângulo do sulco", "tipo": "numero", "unidade": "°"}]},
    {"id": "patela", "titulo": "Patela: altura (Caton-Deschamps)",
     "onde": "Sagital no meio da patela, com a maior superfície articular e o planalto tibial.",
     "como": ["AP: comprimento da superfície articular da patela.",
              "AT: da margem inferior da superfície articular ao ângulo anterossuperior do "
              "planalto tibial.",
              "Índice = AT ÷ AP. Em hiperextensão ele sai artificialmente baixo."],
     "corte": "0,6 a 1,2 normal · acima de 1,2 alta · abaixo de 0,6 baixa",
     "campos": [{"id": "cd", "rotulo": "Caton-Deschamps", "tipo": "numero", "unidade": ""}]},
    {"id": "femoropatelar", "titulo": "Articulação femoropatelar: inclinação patelar",
     "onde": "Axial no corte de maior largura da patela, em extensão, quadríceps relaxado e "
             "contraído.",
     "como": ["Trace a tangente ao contorno posterior dos dois côndilos femorais.",
              "Trace o eixo transverso da patela (a linha da sua maior largura).",
              "Meça o ângulo entre as duas; repita com o quadríceps contraído."],
     "corte": "acima de 20° (relaxado) = patológica",
     "campos": [{"id": "posicao", "rotulo": "posição da patela", "tipo": "opcao", "opcoes": POSICAO},
                {"id": "tilt_rel", "rotulo": "inclinação, relaxado", "tipo": "numero", "unidade": "°"},
                {"id": "tilt_con", "rotulo": "inclinação, contraído", "tipo": "numero", "unidade": "°"}]},
    {"id": "tttg", "titulo": "Distância TT-TG",
     "onde": "Dois axiais superpostos: o primeiro corte com o intercôndilo em \"arco romano\" "
             "completo e o corte da inserção do tendão patelar na tuberosidade (TAT).",
     "como": ["Tangente ao contorno posterior dos côndilos femorais.",
              "Perpendicular pelo ponto mais profundo do sulco troclear (TG).",
              "Perpendicular pelo centro da inserção do tendão patelar na TAT (TT).",
              "Distância entre as duas perpendiculares, em mm. Pés em rotação neutra: 5° de "
              "abdução somam cerca de 3,4 mm."],
     "corte": "até 15 mm normal · 15 a 19 limítrofe · 20 mm ou mais patológica (TC)",
     "campos": [{"id": "tttg", "rotulo": "TT-TG", "tipo": "numero", "unidade": "mm"}]},
    {"id": "ttpcl", "titulo": "Distância TT-PCL",
     "onde": "Axial da tíbia logo abaixo da cartilagem e acima da cabeça da fíbula, superposto "
             "ao corte da TAT.",
     "como": ["Tangente ao contorno posterior dos côndilos tibiais.",
              "Perpendicular pela borda medial da inserção do LCP.",
              "Perpendicular pelo centro da inserção do tendão patelar na TAT.",
              "Distância entre as duas, em mm. Só usa a tíbia: não muda com a rotação."],
     "corte": "acima de 24 mm = patológica",
     "campos": [{"id": "ttpcl", "rotulo": "TT-PCL", "tipo": "numero", "unidade": "mm"}]},
]

NUMEROS = ("sulco", "cd", "tilt_rel", "tilt_con", "tttg", "ttpcl")


def campos():
    """O que a tela desenha: lados, passos (com o guia) e as opções das estruturas ósseas."""
    return {"ok": True, "tipo": "lyon", "lados": list(LADOS), "passos": PASSOS,
            "ossos": OSSOS, "frase_normal": FRASE_NORMAL}


def _num(v):
    """'16', '1,60', '22.5' -> float; vazio ou texto -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _fmt(x, casas=1):
    """16.0 -> '16'; 1.3 -> '1,3'; 22.5 -> '22,5' (vírgula, sem zero à toa)."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return ("%.*f" % (casas, x)).rstrip("0").rstrip(".").replace(".", ",")


def _lado(valores, s):
    """Os valores de um lado: {'troclea': ..., 'sulco': float|None, ...}."""
    v = {}
    for k in ("troclea", "posicao"):
        v[k] = str(valores.get("%s_%s" % (k, s)) or "").strip()
    for k in NUMEROS:
        v[k] = _num(valores.get("%s_%s" % (k, s)))
    return v


def _linhas_do_lado(v, s, avisos):
    """{secao: frase} de um lado + [linhas da conclusão] desse lado."""
    fem, masc = NOME[s]
    frases, conc = {}, []

    # --- tróclea
    tro = v["troclea"] or "habitual"
    if tro not in TROCLEA:
        tro = "habitual"
    if tro == "habitual":
        t = "de morfologia habitual"
    elif tro == "rasa":
        t = "rasa, sem outras alterações morfológicas"
    else:
        t = "displasia troclear tipo %s de Dejour" % tro.split()[-1]
    if v["sulco"] is not None:
        t += " (ângulo do sulco de %s°)" % _fmt(v["sulco"])
        if v["sulco"] > 145 and tro in ("habitual", "rasa"):
            avisos.append("ângulo do sulco de %s° à %s com a tróclea marcada como %s: acima de 145° "
                          "é displasia (tipo A de Dejour)" % (_fmt(v["sulco"]), fem, tro))
    frases["troclea"] = t + "."

    # --- posição da patela (vai para a articulação femoropatelar e, alterada, para a conclusão)
    pos = v["posicao"] if v["posicao"] in POSICAO else "centrada"
    pos_frase = {"centrada": "patela centrada, sem subluxação",
                 "discreta lateralização": "discreta lateralização da patela, sem subluxação franca",
                 "subluxação lateral": "subluxação lateral da patela"}[pos]
    pos_conc = {"discreta lateralização": "discreta lateralização da patela",
                "subluxação lateral": "subluxação lateral da patela"}.get(pos)
    if tro != "habitual":
        base = ("Tróclea femoral %s rasa" % fem) if tro == "rasa" else \
               ("Displasia troclear tipo %s de Dejour à %s" % (tro.split()[-1], fem))
        conc.append(base + (", com %s" % pos_conc if pos_conc else "") + ".")
    elif pos_conc:
        conc.append("%s %s." % (pos_conc[0].upper() + pos_conc[1:], fem))

    # --- patela: altura
    p = "de morfologia habitual"
    if v["cd"] is not None:
        cd = v["cd"]
        if cd > 1.2:
            classe = "patela alta"
            conc.append("Patela alta à %s (índice de Caton-Deschamps de %s)." % (fem, _fmt(cd, 2)))
        elif cd < 0.6:
            classe = "patela baixa"
            conc.append("Patela baixa à %s (índice de Caton-Deschamps de %s)." % (fem, _fmt(cd, 2)))
        else:
            classe = "altura normal"
        p += ", com índice de Caton-Deschamps de %s (%s)" % (_fmt(cd, 2), classe)
        if cd > 3:
            avisos.append("Caton-Deschamps de %s à %s: índice é uma razão (0,6 a 1,2), confira"
                          % (_fmt(cd, 2), fem))
    frases["patela"] = p + "."

    # --- inclinação patelar
    inc = ""
    if v["tilt_rel"] is not None:
        inc = "inclinação patelar de %s° com o quadríceps relaxado" % _fmt(v["tilt_rel"])
        if v["tilt_con"] is not None:
            inc += " e de %s° contraído" % _fmt(v["tilt_con"])
        if v["tilt_rel"] > 20:
            inc += " (aumentada; patológica acima de 20°)"
            conc.append("Inclinação patelar aumentada à %s (%s°)." % (fem, _fmt(v["tilt_rel"])))
        else:
            inc += " (patológica acima de 20°)"
    elif v["tilt_con"] is not None:
        inc = "inclinação patelar de %s° com o quadríceps contraído" % _fmt(v["tilt_con"])
    frases["femoropatelar"] = pos_frase + ("; " + inc if inc else "") + "."

    # --- TT-TG
    if v["tttg"] is not None:
        x = v["tttg"]
        if x <= 15:
            classe = "dentro dos limites da normalidade"
        elif x < 20:
            classe = "limítrofe"
            conc.append("Distância TT-TG %s limítrofe (%s mm)." % (fem, _fmt(x)))
        else:
            classe = "aumentada"
            conc.append("Distância TT-TG %s aumentada (%s mm)." % (fem, _fmt(x)))
        frases["tttg"] = "%s mm, %s (normal até 15 mm; patológica a partir de 20 mm)." % (_fmt(x), classe)
        if x < 5:
            avisos.append("TT-TG de %s mm à %s: se o visualizador deu em cm, digite em mm "
                          "(1,60 cm = 16 mm)" % (_fmt(x), fem))
    # --- TT-PCL
    if v["ttpcl"] is not None:
        x = v["ttpcl"]
        if x > 24:
            classe = "aumentada"
            conc.append("Distância TT-PCL %s aumentada (%s mm)." % (fem, _fmt(x)))
        else:
            classe = "dentro dos limites da normalidade"
        frases["ttpcl"] = "%s mm, %s (patológica acima de 24 mm)." % (_fmt(x), classe)
        if x < 5:
            avisos.append("TT-PCL de %s mm à %s: se o visualizador deu em cm, digite em mm"
                          % (_fmt(x), fem))
    return frases, conc


ROTULOS = [("troclea", "Tróclea femoral"), ("patela", "Patela"),
           ("femoropatelar", "Articulação femoropatelar"),
           ("tttg", "Distância TT-TG"), ("ttpcl", "Distância TT-PCL")]


def montar(pedido):
    """{'lado': 'direito'|'esquerdo'|'ambos', 'valores': {campo_d/e: ...}, 'ossos': str}
    -> {'ok', 'texto', 'conclusao', 'avisos'}. O laudo inteiro, com ** nos títulos."""
    if not isinstance(pedido, dict):
        return {"ok": False, "motivo": "pedido_invalido"}
    lado = pedido.get("lado") or "direito"
    if lado not in LADOS:
        return {"ok": False, "motivo": "lado_desconhecido", "aceitos": list(LADOS)}
    valores = pedido.get("valores") or {}
    if not isinstance(valores, dict):
        return {"ok": False, "motivo": "valores_invalidos"}
    ossos = pedido.get("ossos") if pedido.get("ossos") in OSSOS else OSSOS[0]

    avisos, por_lado, conclusao = [], {}, []
    for s in LADOS[lado]:
        frases, conc = _linhas_do_lado(_lado(valores, s), s, avisos)
        por_lado[s] = frases
        conclusao.extend(conc)
    if not conclusao:
        conclusao = [FRASE_NORMAL]

    if lado == "ambos":
        alvo, alvo_min = "DOS JOELHOS", "dos joelhos"
    else:
        alvo, alvo_min = "DO JOELHO " + lado.upper(), "do joelho " + lado

    analise = []
    for chave, rotulo in ROTULOS:
        for s in LADOS[lado]:
            f = por_lado[s].get(chave)
            if f:
                analise.append("%s %s:  %s" % (rotulo, NOME[s][0], f))
    analise.append("Estruturas ósseas:  %s." % ossos)

    texto = "\n".join([
        "**" + TITULO.format(alvo=alvo) + "**",
        "",
        "**TÉCNICA:**  " + TECNICA.format(alvo_min=alvo_min),
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
