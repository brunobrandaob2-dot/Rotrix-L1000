# -*- coding: utf-8 -*-
"""Idade óssea — cálculo local, nada sai do computador.

Entra: data de nascimento, data do exame, sexo e a idade óssea observada no
atlas (anos + meses). Sai: idade cronológica, desvio padrão esperado naquela
idade (Brush Foundation), faixa de ±2 DP, Z-score, percentil e o laudo pronto.

É aritmética pura: não chama a nuvem, não manda nada para lugar nenhum. A data
de nascimento aparece no laudo porque é o laudo dele, na máquina dele.
"""
import datetime
import json
import math
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
_TAB = None


def tabela():
    global _TAB
    if _TAB is None:
        with open(os.path.join(AQUI, "dados", "idade_ossea.json"), encoding="utf-8") as f:
            _TAB = json.load(f)
    return _TAB


def _sexo(s):
    s = (s or "").strip().lower()
    return "feminino" if s.startswith(("f", "m" + "ulher")) and not s.startswith("mas") else \
        ("feminino" if s.startswith("f") else "masculino")


def desvio_padrao(meses, sexo):
    """DP da idade óssea naquela idade cronológica, interpolado."""
    pontos = tabela()["desvio_padrao"][_sexo(sexo)]
    if meses <= pontos[0][0]:
        return pontos[0][1]
    if meses >= pontos[-1][0]:
        return pontos[-1][1]
    for (x0, y0), (x1, y1) in zip(pontos, pontos[1:]):
        if x0 <= meses <= x1:
            return y0 + (y1 - y0) * (meses - x0) / float(x1 - x0)
    return pontos[-1][1]


def meses_entre(nascimento, exame):
    """Idade em meses cheios entre duas datas (aaaa-mm-dd ou date)."""
    n = _data(nascimento)
    e = _data(exame)
    m = (e.year - n.year) * 12 + (e.month - n.month)
    if e.day < n.day:
        m -= 1
    return max(m, 0)


def _data(d):
    if isinstance(d, datetime.date):
        return d
    d = str(d).strip()
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(d, f).date()
        except ValueError:
            pass
    raise ValueError("data não reconhecida: %r" % d)


def por_extenso(meses):
    """17 -> "1 ano e 5 meses"; 24 -> "2 anos"; 5 -> "5 meses"."""
    meses = int(round(meses))
    a, m = divmod(meses, 12)
    if a and m:
        return "%d %s e %d %s" % (a, "ano" if a == 1 else "anos", m, "mês" if m == 1 else "meses")
    if a:
        return "%d %s" % (a, "ano" if a == 1 else "anos")
    return "%d %s" % (m, "mês" if m == 1 else "meses")


def _com_meses(meses):
    meses = int(round(meses))
    return "%s (%d meses)" % (por_extenso(meses), meses)


def percentil(z):
    return 100.0 * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def calcular(nascimento, exame, sexo, io_anos=0, io_meses=0):
    crono = meses_entre(nascimento, exame)
    dp = desvio_padrao(crono, sexo)
    obs = int(io_anos) * 12 + int(io_meses)
    z = (obs - crono) / dp if dp else 0.0
    return {
        "nascimento": _data(nascimento),
        "exame": _data(exame),
        "sexo": _sexo(sexo),
        "cronologica_meses": crono,
        "esperada_meses": crono,
        "dp_meses": round(dp, 2),
        "limite_inferior_meses": max(int(round(crono - 2 * dp)), 0),
        "limite_superior_meses": int(round(crono + 2 * dp)),
        "observada_meses": obs,
        "z": round(z, 2),
        "percentil": round(percentil(z), 1),
    }


def classificar(r):
    """Três faixas, pelo ±2 DP — o mesmo critério que desenha a faixa de normalidade."""
    if r["observada_meses"] < r["limite_inferior_meses"]:
        return "atrasada"
    if r["observada_meses"] > r["limite_superior_meses"]:
        return "avancada"
    return "compativel"


_CONCLUSAO = {
    "compativel": "A idade óssea observada é compatível com a idade média esperada "
                  "segundo o método de Greulich e Pyle.",
    "atrasada": "A idade óssea observada encontra-se abaixo da faixa de normalidade "
                "(±2 desvios padrão) esperada para a idade cronológica, segundo o "
                "método de Greulich e Pyle.",
    "avancada": "A idade óssea observada encontra-se acima da faixa de normalidade "
                "(±2 desvios padrão) esperada para a idade cronológica, segundo o "
                "método de Greulich e Pyle.",
}


def laudo(nascimento, exame, sexo, io_anos=0, io_meses=0):
    r = calcular(nascimento, exame, sexo, io_anos, io_meses)
    linhas = [
        "**RADIOGRAFIA DA MÃO E PUNHO PARA IDADE ÓSSEA**",
        "",
        "**ANÁLISE:**",
        "Data de nascimento: %s" % r["nascimento"].strftime("%d/%m/%Y"),
        "Sexo: %s" % r["sexo"].capitalize(),
        "Idade cronológica: %s" % _com_meses(r["cronologica_meses"]),
        "Idade óssea esperada (Brush Foundation): %s, DP %.2f meses"
        % (_com_meses(r["esperada_meses"]), r["dp_meses"]),
        "Faixa de normalidade (±2 DP): %s a %s"
        % (_com_meses(r["limite_inferior_meses"]), _com_meses(r["limite_superior_meses"])),
        "Idade óssea observada (Greulich & Pyle): %s" % _com_meses(r["observada_meses"]),
        "",
        "**CONCLUSÃO:**",
        _CONCLUSAO[classificar(r)],
        "",
        "Dados de variabilidade da idade óssea segundo o Brush Foundation Study "
        "(Greulich & Pyle, 1959).",
    ]
    r["texto"] = "\n".join(linhas)
    return r
