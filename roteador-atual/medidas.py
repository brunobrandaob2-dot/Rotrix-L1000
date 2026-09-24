# -*- coding: utf-8 -*-
"""Exames de medida: escanometria, panorâmica de MMII e panorâmica da coluna.

Os três funcionam igual:

  1. um formulário com os campos daquele exame — ou um print colado;
  2. se veio print, a IA devolve **só os valores**, em JSON, nunca texto de laudo;
  3. a conta, o arredondamento, a conferência de sanidade e o preenchimento da
     máscara acontecem AQUI, na máquina.

A divisão é de propósito. Se a IA escrevesse o laudo, cada exame sairia com uma
redação diferente e a aritmética dependeria do humor do modelo. Devolvendo só
números, o texto é sempre a máscara do banco e a conta é sempre a mesma.

O print de visualizador tem nome de paciente gravado nos pixels: a imagem passa
pelo recorte e pela limpeza de metadados (rota /v1/imagem) ANTES de qualquer
envio. Este módulo nunca recebe imagem, só o que voltou dela.
"""
import re

# ---------------------------------------------------------------------------
# o que cada exame pede. "leitura" = valor lido na régua/no atlas; "escolha" =
# opção; "calculado" = sai de conta, o formulário mostra mas não deixa digitar.
# ---------------------------------------------------------------------------
CAMPOS = {
    "escanometria": {
        "mascara": "msk/rx/escanometria/normal",
        "titulo": "Escanometria",
        "leitura": [
            ("quadril_d", "Quadril direito"), ("quadril_e", "Quadril esquerdo"),
            ("joelho_d", "Joelho direito"), ("joelho_e", "Joelho esquerdo"),
            ("tornozelo_d", "Tornozelo direito"), ("tornozelo_e", "Tornozelo esquerdo"),
        ],
        "calculado": ["femur_d", "femur_e", "tibia_d", "tibia_e", "mi_d", "mi_e",
                      "lado_maior", "dismetria"],
    },
    "panoramica_mmii": {
        "mascara": "msk/rx/panoramica_mmii/normal",
        "titulo": "Panorâmica de membros inferiores",
        "leitura": [
            ("desvio_d", "Desvio do eixo à direita (mm)"),
            ("desvio_e", "Desvio do eixo à esquerda (mm)"),
            ("aft_d", "Ângulo femorotibial direito"),
            ("aft_e", "Ângulo femorotibial esquerdo"),
            ("comp_d", "Comprimento femorotibial direito (cm)"),
            ("comp_e", "Comprimento femorotibial esquerdo (cm)"),
        ],
        "escolha": [
            ("relacao_d", "Eixo à direita", ["medial", "lateral"]),
            ("relacao_e", "Eixo à esquerda", ["medial", "lateral"]),
            ("geno_d", "Geno à direita", ["varo", "valgo"]),
            ("geno_e", "Geno à esquerda", ["varo", "valgo"]),
        ],
        "calculado": ["lado_menor", "dismetria"],
    },
    "panoramica_coluna": {
        "mascara": "msk/rx/panoramica_coluna/normal",
        "titulo": "Panorâmica da coluna total",
        "leitura": [
            ("cobb", "Ângulo de Cobb"), ("sva", "SVA (cm)"),
            ("cifose", "Cifose torácica"), ("ferguson", "Ferguson (inclinação sacral)"),
            ("lordose", "Lordose lombar"), ("valor", "Desvio da báscula ilíaca (cm)"),
        ],
        "escolha": [
            ("risser", "Índice de Risser", ["V", "IV", "III", "II", "I", "0"]),
            ("balanco", "Balanço sagital", ["neutro", "positivo", "negativo"]),
            ("prumo", "Linha de prumo", ["próxima", "anteriormente", "posteriormente"]),
            ("sentido", "Sentido da báscula", ["horário", "anti-horário"]),
            ("convexidade", "Convexidade", ["destro-convexa", "sinistro-convexa"]),
            ("nash_moe", "Rotação (Nash-Moe)", ["I", "II", "III", "IV"]),
        ],
        "blocos": [
            ("blk_atitude_escoliotica", "Atitude escoliótica"),
            ("blk_escoliose", "Escoliose"),
            ("blk_bascula_iliaca", "Báscula ilíaca desviada"),
            ("blk_osteofitos_marginais", "Osteófitos marginais"),
            ("blk_espacos_discais_reduzidos", "Espaços discais reduzidos"),
            ("blk_artropatia_interapofisaria", "Artropatia interapofisária"),
        ],
        "calculado": [],
    },
}

# conferência de sanidade da escanometria, da habilidade salva
SANIDADE = {"femur": (43, 8), "tibia": (35, 8), "mi": (78, 14)}


def quarto(v):
    """Arredonda em quartos de centímetro: ,00 / ,25 / ,50 / ,75.

    A habilidade é explícita: arredondar na LEITURA da régua, nunca no
    resultado. Arredondadas as seis leituras, toda diferença já cai na grade,
    porque diferença entre quartos é sempre um quarto."""
    return round(float(v) * 4.0) / 4.0


def cm(v):
    """0.5 -> "0,50" — sempre com duas casas, como ele escreve."""
    return ("%.2f" % float(v)).replace(".", ",")


def escanometria(leituras):
    """Seis leituras de régua -> fêmur, tíbia, membro inferior e a dismetria."""
    faltando = [k for k, _r in CAMPOS["escanometria"]["leitura"] if leituras.get(k) in (None, "")]
    if faltando:
        return {"ok": False, "motivo": "nivel_ausente", "faltando": faltando}
    q = {k: quarto(leituras[k]) for k, _r in CAMPOS["escanometria"]["leitura"]}
    v = {
        "femur_d": q["quadril_d"] - q["joelho_d"],
        "femur_e": q["quadril_e"] - q["joelho_e"],
        "tibia_d": q["joelho_d"] - q["tornozelo_d"],
        "tibia_e": q["joelho_e"] - q["tornozelo_e"],
        "mi_d": q["quadril_d"] - q["tornozelo_d"],
        "mi_e": q["quadril_e"] - q["tornozelo_e"],
    }
    dif = v["mi_d"] - v["mi_e"]
    v["lado_maior"] = "direito" if dif >= 0 else "esquerdo"
    v["dismetria"] = abs(dif)
    return {"ok": True, "valores": v, "leituras": q, "avisos": _avisos(v)}


def _avisos(v):
    """As ressalvas da habilidade — só as que se aplicam."""
    a = []
    for seg, (esperado, tol) in SANIDADE.items():
        for lado in ("d", "e"):
            x = v["%s_%s" % (seg, lado)]
            if abs(x - esperado) > tol:
                a.append("sanidade: %s %s deu %s cm, longe do esperado (~%d cm). "
                         "Confira se o que foi lido são as leituras de régua e não "
                         "anotações do software sobrepostas à imagem."
                         % (seg, "direito" if lado == "d" else "esquerdo", cm(x), esperado))
    d = v["dismetria"]
    if abs(d - 1.0) < 0.126 and d != 0:
        a.append("a dismetria caiu em %s cm, na borda de 1,00 cm — é o único número "
                 "em que o arredondamento muda conduta. Confira as leituras na "
                 "estação antes de assinar." % cm(d))
    if 0 < d < 1.0:
        a.append("abaixo de 1 cm: cabe acrescentar \"diferença dentro da faixa de "
                 "variação fisiológica, habitualmente sem repercussão clínica\".")
    a.append("leitura sobre imagem comprimida carrega erro da ordem de ±0,3 cm por "
             "nível; a diferença entre os membros é o valor sensível.")
    return a


def panoramica_mmii(valores):
    v = dict(valores)
    try:
        dif = float(str(v.get("comp_d", "")).replace(",", ".")) - \
              float(str(v.get("comp_e", "")).replace(",", "."))
    except ValueError:
        return {"ok": True, "valores": v, "avisos": []}
    v["lado_menor"] = "direito" if dif <= 0 else "esquerdo"
    v["dismetria"] = abs(dif)
    return {"ok": True, "valores": v, "avisos": []}


def _texto_valor(k, x):
    if isinstance(x, float):
        return cm(x)
    return str(x)


# onde começam as colunas da tabela de medidas, contadas no texto final
COL_1, COL_2 = 16, 28
_LACUNA = re.compile(r"\{([a-z_0-9]+)(\|[^}]*)?\}")
_LINHA_TABELA = re.compile(r"^(FÊMUR|TÍBIA|MEMBRO INFERIOR)\s+(\S+)\s+(\S+)\s*$")


def preencher(texto, valores):
    """Troca as lacunas da máscara pelos valores e reencosta a tabela na coluna.

    A tabela da escanometria alinha por espaços. Lacuna vazia sai com 3
    caracteres ("___"), um valor tem 5 ("43,25"): sem reencostar, a segunda
    coluna anda dois caracteres para a direita em cada linha preenchida. Quem
    manda são as colunas 16 e 28, que é onde a habilidade as põe."""
    def troca(m):
        k = m.group(1)
        return _texto_valor(k, valores[k]) if k in valores else m.group(0)

    saida = []
    for linha in _LACUNA.sub(troca, texto).split("\n"):
        t = _LINHA_TABELA.match(linha)
        if t:
            rot, a, b = t.group(1), t.group(2), t.group(3)
            linha = rot.ljust(COL_1) + a.ljust(COL_2 - COL_1) + b
        saida.append(linha)
    return "\n".join(saida)


def montar(exame, dados):
    """Formulário (ou o que a IA leu do print) -> o laudo pronto.

    `dados` são as leituras cruas. A conta é feita aqui; a máscara vem do
    banco, então o texto é sempre o dele."""
    import roteador
    conf = CAMPOS[exame]
    if exame == "escanometria":
        r = escanometria(dados)
    elif exame == "panoramica_mmii":
        r = panoramica_mmii(dados)
    else:
        r = {"ok": True, "valores": dict(dados), "avisos": []}
    if not r.get("ok"):
        return r
    molde = next((it[3] for it in roteador.BANCO.itens
                  if it[0] == "mascara" and it[2] == conf["mascara"] and it[3]), None)
    if not molde:
        return {"ok": False, "motivo": "mascara_ausente", "mascara": conf["mascara"]}
    r["texto"] = preencher(molde, r["valores"])
    return r
