# -*- coding: utf-8 -*-
"""Cálculos de volume — o quarto botão da barra da folha.

Três eixos entram, o volume sai, e sai também a FRASE pronta para o laudo, na
forma que ele escreve. Como na escanometria e na idade óssea: a aritmética
acontece aqui, na máquina. Nada disto passa por IA — não faz sentido pedir a um
modelo de linguagem que multiplique três números, e o resultado tem que ser o
mesmo toda vez.

A fórmula é a do elipsoide: V = L × AP × T × 0,523. É a mesma para próstata,
tireoide, rim, baço, útero, ovário e nódulo — o que muda de um para outro é a
frase e o que se calcula junto (densidade de PSA na próstata, soma dos lobos na
tireoide, variação em relação ao exame anterior num nódulo).
"""
import math

# Fator do elipsoide: (4/3)·π/8 = π/6 = 0,5236. O valor de uso consagrado em
# radiologia é 0,523, e é o que fica — mudar a terceira casa por elegância
# faria os laudos dele deixarem de bater com os antigos.
FATOR = 0.523

ORGAOS = {
    "generico": {
        "titulo": "Volume (elipsoide)",
        "frase": "Volume estimado de {volume} cm³.",
        "extras": [],
    },
    "prostata": {
        "titulo": "Próstata",
        "frase": "Próstata com dimensões de {l} x {ap} x {t} cm, "
                 "correspondendo a um volume estimado de {volume} cm³.",
        "extras": ["psa"],
    },
    "tireoide": {
        "titulo": "Tireoide (lobo)",
        "frase": "Lobo {lado} medindo {l} x {ap} x {t} cm, "
                 "com volume estimado de {volume} cm³.",
        "extras": ["lado"],
    },
    "rim": {
        "titulo": "Rim",
        "frase": "Rim {lado} medindo {l} x {ap} x {t} cm, "
                 "com volume estimado de {volume} cm³.",
        "extras": ["lado"],
    },
    "baco": {
        "titulo": "Baço",
        "frase": "Baço medindo {l} x {ap} x {t} cm, "
                 "com volume estimado de {volume} cm³.",
        "extras": [],
    },
    "utero": {
        "titulo": "Útero",
        "frase": "Útero medindo {l} x {ap} x {t} cm, "
                 "com volume estimado de {volume} cm³.",
        "extras": [],
    },
    "ovario": {
        "titulo": "Ovário",
        "frase": "Ovário {lado} medindo {l} x {ap} x {t} cm, "
                 "com volume estimado de {volume} cm³.",
        "extras": ["lado"],
    },
    "bexiga": {
        "titulo": "Bexiga / resíduo",
        "frase": "Resíduo pós-miccional estimado em {volume} cm³.",
        "extras": [],
    },
    "lesao": {
        "titulo": "Nódulo ou lesão",
        "frase": "Lesão medindo {l} x {ap} x {t} cm, com volume estimado de "
                 "{volume} cm³ e diâmetro médio de {media} cm.",
        "extras": ["anterior"],
    },
}

LADOS = ["direito", "esquerdo"]


def _num(v):
    """Aceita "4,2" e "4.2". Devolve None quando não é número."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def n(x, casas=1):
    """Número como ele escreve: vírgula decimal, sem zero à toa no fim."""
    if x is None:
        return ""
    s = ("%." + str(casas) + "f") % float(x)
    return s.replace(".", ",")


def volume(l, ap, t, em_mm=False):
    """V = L × AP × T × 0,523, em cm³."""
    vals = [_num(l), _num(ap), _num(t)]
    if any(v is None or v <= 0 for v in vals):
        return None
    if em_mm:
        vals = [v / 10.0 for v in vals]
    return vals[0] * vals[1] * vals[2] * FATOR


def calcular(orgao="generico", l=None, ap=None, t=None, em_mm=False,
             lado="", psa=None, anterior=None):
    """Volume, o que vem junto, e a frase pronta para a folha."""
    conf = ORGAOS.get(orgao)
    if conf is None:
        return {"ok": False, "motivo": "orgao_desconhecido", "aceitos": sorted(ORGAOS)}
    v = volume(l, ap, t, em_mm)
    if v is None:
        return {"ok": False, "motivo": "medidas_invalidas",
                "detalhe": "os três eixos precisam de número maior que zero"}
    eixos = [_num(l), _num(ap), _num(t)]
    if em_mm:
        eixos = [x / 10.0 for x in eixos]
    r = {
        "ok": True,
        "orgao": orgao,
        "volume": round(v, 1),
        "eixos_cm": [round(x, 1) for x in eixos],
        "media": round(sum(eixos) / 3.0, 1),
        "avisos": [],
    }

    if orgao == "prostata":
        p = _num(psa)
        if p is not None and p >= 0 and v > 0:
            r["densidade_psa"] = round(p / v, 3)
            r["psa"] = p

    if anterior not in (None, ""):
        va = _num(anterior)
        if va is not None and va > 0:
            r["volume_anterior"] = round(va, 1)
            r["variacao_pct"] = round((v - va) / va * 100.0, 1)
            # O diâmetro cresce com a raiz cúbica do volume: 20% de volume é
            # 6% de diâmetro, dentro do erro de medida. Dizer "aumentou 20%"
            # sem essa ressalva faz um nódulo estável parecer em crescimento.
            r["variacao_diametro_pct"] = round(
                ((v / va) ** (1.0 / 3.0) - 1.0) * 100.0, 1)
            if abs(r["variacao_pct"]) < 20:
                r["avisos"].append(
                    "variação de volume abaixo de 20%% (%s%%) corresponde a menos de "
                    "6%% no diâmetro — está dentro do erro de medida, e não sustenta "
                    "crescimento." % n(r["variacao_pct"]))

    if em_mm:
        r["avisos"].append("medidas convertidas de mm para cm antes do cálculo.")

    r["frase"] = _frase(conf, r, lado)
    return r


def _frase(conf, r, lado):
    lado = (lado or "").strip().lower()
    if "lado" in conf["extras"] and lado not in LADOS:
        lado = LADOS[0]
    texto = conf["frase"].format(
        volume=n(r["volume"]),
        media=n(r["media"]),
        l=n(r["eixos_cm"][0]), ap=n(r["eixos_cm"][1]), t=n(r["eixos_cm"][2]),
        lado=lado,
    )
    if "densidade_psa" in r:
        texto += (" Densidade de PSA de %s ng/mL/cm³ (PSA de %s ng/mL)."
                  % (n(r["densidade_psa"], 3), n(r["psa"], 2)))
    if "variacao_pct" in r:
        rumo = "aumento" if r["variacao_pct"] > 0 else "redução"
        if abs(r["variacao_pct"]) < 0.05:
            texto += (" Sem variação volumétrica em relação ao estudo anterior (%s cm³)."
                      % n(r["volume_anterior"]))
        else:
            texto += (" Em relação ao estudo anterior (%s cm³), %s de %s%% do volume."
                      % (n(r["volume_anterior"]), rumo, n(abs(r["variacao_pct"]))))
    return texto


def campos():
    """O que o app precisa para montar o formulário."""
    return {
        "ok": True,
        "fator": FATOR,
        "formula": "L × AP × T × 0,523",
        "lados": LADOS,
        "orgaos": [
            {"id": k, "titulo": v["titulo"], "extras": v["extras"]}
            for k, v in ORGAOS.items()
        ],
    }
