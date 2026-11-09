# -*- coding: utf-8 -*-
"""Densitometria óssea (DXA) — máscaras A, B e C dele, montadas na máquina (09/11/2026).

Vem da skill "densitometria" e do expoweb de 09/11, aprovado por ele. Mesma doutrina das
medidas: os números entram (formulário ou print lido pela IA), a conta, a escolha da
máscara, a classificação e as ressalvas saem daqui. O texto é o da máscara dele, sem
mudar palavra; só os @ são preenchidos e as trocas que a skill prevê.

  A  T-score, coluna + fêmur (um lado ou bilateral)
  B  A + rádio 1/3
  C  Z-score (pré-menopausa, homem < 50, menor de 20)
  D/E (corpo inteiro) ainda não: ficam para depois.

Nada de nome, data de nascimento ou identificador entra aqui: só idade, sexo e números.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CAMPOS = {
    "mascara": "densitometria (A/B/C, skill)",
    "titulo": "Densitometria óssea (DXA)",
    "leitura": [
        ("idade", "Idade (anos)"),
        ("col_bmd", "L1-L4 · BMD (g/cm²)"),
        ("col_t", "L1-L4 · T-score (Z na máscara C)"),
        ("l1_t", "L1 · T"), ("l2_t", "L2 · T"), ("l3_t", "L3 · T"), ("l4_t", "L4 · T"),
        ("colo_e_bmd", "Colo esquerdo · BMD"), ("colo_e_t", "Colo esquerdo · T/Z"),
        ("total_e_t", "Fêmur total esquerdo · T/Z"), ("total_e_bmd", "Fêmur total esquerdo · BMD"),
        ("colo_d_bmd", "Colo direito · BMD"), ("colo_d_t", "Colo direito · T/Z"),
        ("total_d_t", "Fêmur total direito · T/Z"), ("total_d_bmd", "Fêmur total direito · BMD"),
        ("radio_bmd", "Rádio 1/3 (33%) · BMD"), ("radio_t", "Rádio 1/3 (33%) · T"),
        ("ant_col_bmd", "Anterior · L1-L4 BMD"), ("ant_total_bmd", "Anterior · fêmur total BMD"),
        ("ant_data", "Anterior · data (dd/mm/aaaa)"),
        ("lsc_col", "LSC do serviço · coluna (%)"), ("lsc_total", "LSC do serviço · fêmur total (%)"),
    ],
    "escolha": [
        ("sexo", "Sexo", ["feminino", "masculino"]),
        ("menopausa", "Menopausa", ["pós ou transição", "pré-menopausa", "não informado"]),
        ("fratura", "Fratura por fragilidade", ["não", "sim"]),
    ],
    "blocos": [],
    "calculado": [],
}

REF_T = "em relação a quantidade média de massa óssea esperada para uma população de adultos jovens (pico da massa óssea)."
IMP_T = {
    "normal": "- Densidade mineral óssea está dentro dos valores normais, o que indica MASSA ÓSSEA NORMAL.",
    "osteopenia": "- Densitometria evidencia perda óssea compatível com OSTEOPENIA.",
    "osteoporose": "- Densitometria evidencia perda óssea compatível com OSTEOPOROSE.",
    "estabelecida": "- Densitometria, associada ao relato da fratura prévia, é compatível com OSTEOPOROSE ESTABELECIDA.",
}
IMP_Z = {
    "normal": "- Densidade mineral óssea está dentro do esperado para idade.",
    "baixa": "- Densitometria abaixo do esperado para a idade.",
}
VR_T = [("Até (-)1 DP (Desvio Padrão)", "NORMAL"), ("Entre (-)1 e (-)2,4 DP", "OSTEOPENIA"),
        ("Igual ou abaixo de (-)2,5 DP", "OSTEOPOROSE"),
        ("Abaixo de (-)2,5 DP e na presença de uma ou mais fraturas", "OSTEOPOROSE ESTABELECIDA")]
VR_Z = [("Maior que -2 DP", "DENTRO DO ESPERADO PARA A IDADE"),
        ("Menor ou igual a -2 DP", "ABAIXO DO ESPERADO PARA A IDADE")]
# ISCD, quando o relatório não traz o LSC do serviço
LSC_ISCD = {"col": 5.3, "total": 5.0}


def num(v):
    s = str(v if v is not None else "").strip().replace(",", ".").replace("−", "-")
    if not s:
        return None
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return None


def arred(x, casas):
    """Meio para longe do zero, como a skill: -2,45 -> -2,5."""
    q = Decimal(1).scaleb(-casas)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def br(x, casas):
    s = "%.*f" % (casas, arred(x, casas))
    if s.startswith("-") and float(s) == 0:
        s = s[1:]
    return s.replace(".", ",")


def sinal(x, casas):
    t = br(x, casas)
    return t if t.startswith("-") or float(t.replace(",", ".")) == 0 else "+" + t


def _tabela(linhas):
    """Duas colunas alinhadas por espaço, como a tabela da escanometria."""
    larg = max(len(a) for a, _b in linhas) + 2
    return "\n".join(a.ljust(larg) + b for a, b in linhas)


def criterio(v):
    """-> ("T"|"Z", ressalva ou "")"""
    sexo = (v.get("sexo") or "").lower()
    meno = (v.get("menopausa") or "").lower()
    idade = num(v.get("idade"))
    if idade is not None and idade < 20:
        return "Z", ("menor de 20 anos: Z-score, e nunca \"osteopenia/osteoporose\" só pela DXA. A skill "
                     "troca os sítios por coluna lombar e corpo total sem cabeça — confira os sítios.")
    if sexo.startswith("m"):
        if idade is None:
            return "T", "homem sem idade informada: assumi ≥ 50 anos (T-score). Abaixo de 50 seria Z-score."
        return ("Z", "") if idade < 50 else ("T", "")
    if meno.startswith("pré") or meno.startswith("pre"):
        return "Z", ""
    if meno.startswith("pós") or meno.startswith("pos"):
        return "T", ""
    # mulher sem informação de menopausa (ou sem sexo): pela idade, com ressalva
    if idade is None:
        return "T", ("sem idade nem status menopausal: assumi T-score (pós-menopausa). Se for "
                     "pré-menopausa, a máscara é a C (Z-score).")
    if idade >= 50:
        return "T", "menopausa não informada: ≥ 50 anos, usei T-score. Se pré-menopausa, a máscara é a C."
    return "Z", "menopausa não informada: < 50 anos, usei Z-score. Se pós-menopausa, a máscara é a A."


def laudo(v):
    v = dict(v or {})
    n = {k: num(v.get(k)) for k, _r in CAMPOS["leitura"] if k != "ant_data"}
    avisos = []
    tipo, ress = criterio(v)
    if ress:
        avisos.append(ress)
    com_radio = n["radio_t"] is not None or n["radio_bmd"] is not None
    masc = "C" if tipo == "Z" else ("B" if com_radio else "A")
    if tipo == "Z" and com_radio:
        avisos.append("rádio 1/3 informado, mas a máscara C (Z-score) não tem a linha do rádio: ficou fora.")

    # lados do fêmur: pelo que foi preenchido (no print, pelo rótulo do software, nunca pela imagem)
    lados = [l for l in ("d", "e") if any(n[k % l] is not None for k in ("colo_%s_bmd", "colo_%s_t", "total_%s_t"))]
    nome = {"d": "direito", "e": "esquerdo"}

    def f3(k):
        return br(n[k], 3) if n[k] is not None else "@"

    def f1(k):
        return br(n[k], 1) if n[k] is not None else "@"

    # arredondamento que cruza limiar (escore veio com duas casas)
    def faixa(x):
        if tipo == "Z":
            return x <= -2.0
        return 0 if x >= -1.0 else (1 if x > -2.5 else 2)
    for k in ("col_t", "colo_e_t", "total_e_t", "colo_d_t", "total_d_t", "radio_t"):
        x = n[k]
        if x is None:
            continue
        r = arred(x, 1)
        if faixa(x) != faixa(r):
            avisos.append("%s veio com duas casas (%s) e só mudou de faixa no arredondamento (%s)."
                          % (k, str(x).replace(".", ","), br(r, 1)))

    # plausibilidade: coluna de % lida no lugar do valor
    for k in ("col_bmd", "colo_e_bmd", "colo_d_bmd", "total_e_bmd", "total_d_bmd", "radio_bmd"):
        x = n[k]
        if x is not None and not (0.4 <= x <= 1.6):
            avisos.append("BMD %s fora de 0,4–1,6 g/cm² (%s): provavelmente foi lida a coluna de %%." % (br(x, 3), k))
    for k in ("col_t", "colo_e_t", "total_e_t", "colo_d_t", "total_d_t", "radio_t", "l1_t", "l2_t", "l3_t", "l4_t"):
        x = n[k]
        if x is not None and not (-5.0 <= x <= 4.0):
            avisos.append("escore %s fora de −5,0 a +4,0 (%s): provavelmente foi lida a coluna de %%." % (br(x, 1), k))

    # exclusão de vértebra: T que difere mais de 1,0 da(s) adjacente(s)
    ts = [n["l%d_t" % i] for i in range(1, 5)]
    if all(x is not None for x in ts):
        fora = []
        for i, x in enumerate(ts):
            viz = [ts[j] for j in (i - 1, i + 1) if 0 <= j < 4]
            if viz and all(abs(x - y) > 1.0 for y in viz):
                fora.append("L%d" % (i + 1))
        if fora:
            avisos.append("%s difere mais de 1,0 da(s) adjacente(s): excluir e usar a combinação do software "
                          "(ex.: L1-L3), trocando \"das vértebras L1, L2, L3 e L4\" pelas usadas e acrescentando "
                          "em COMENTÁRIOS \"Excluída da análise a vértebra @, por @.\". A DMO combinada não é "
                          "recalculada aqui." % ", ".join(fora))
    elif any(x is not None for x in ts):
        avisos.append("faltam vértebras isoladas: a regra de exclusão (diferença > 1,0) não foi conferida.")

    # classificação pelo menor escore
    sitios = {"col_t": "L1-L4"}
    for l in lados:
        sitios["colo_%s_t" % l] = "colo %s" % nome[l]
        sitios["total_%s_t" % l] = "fêmur total %s" % nome[l]
    if masc == "B":
        sitios["radio_t"] = "rádio 1/3"
    escores = {k: arred(n[k], 1) for k in sitios if n[k] is not None}
    menor = min(escores.values()) if escores else None
    fx = (v.get("fratura") or "").lower().startswith("s")
    if menor is None:
        imp = "@"
        avisos.append("sem escores: a impressão ficou com @.")
    elif tipo == "Z":
        imp = IMP_Z["baixa"] if menor <= -2.0 else IMP_Z["normal"]
        if -2.1 <= menor <= -1.9:
            avisos.append("menor Z-score (%s) no limiar de -2,0: confira no relatório antes de assinar." % br(menor, 1))
    else:
        if menor <= -2.5:
            imp = IMP_T["estabelecida"] if fx else IMP_T["osteoporose"]
        elif menor < -1.0:
            imp = IMP_T["osteopenia"]
        else:
            imp = IMP_T["normal"]
        if -1.1 <= menor <= -0.9 or -2.6 <= menor <= -2.4:
            avisos.append("menor T-score (%s) no limiar: confira o arredondamento no relatório antes de assinar." % br(menor, 1))
        if fx and menor > -2.5:
            avisos.append("fratura por fragilidade informada com T > -2,5: é osteoporose clínica independentemente "
                          "do T-score (a impressão da máscara segue o T).")
    if len(escores) >= 2 and max(escores.values()) - min(escores.values()) > 1.0:
        avisos.append("discordância entre sítios > 1,0 DP (comum em artefato degenerativo da coluna); a "
                      "classificação já segue o pior sítio (%s)." % sitios[min(escores, key=escores.get)])
    if not lados:
        avisos.append("fêmur sem valores: lado e colo ficaram com @.")
    for k, rot in (("col_bmd", "L1-L4 BMD"), ("col_t", "L1-L4 escore")):
        if n[k] is None:
            avisos.append("%s em branco: ficou @ no laudo." % rot)

    # ---- texto
    if tipo == "Z":
        sexo = (v.get("sexo") or "").lower()
        quem = "da paciente" if sexo.startswith("f") else ("do paciente" if sexo.startswith("m") else "@da paciente @do paciente")
        ref = ("em relação a quantidade média de massa óssea esperada para uma população da mesma faixa "
               "etária %s (Z- Score)." % quem)
        dp = "desvio padrão"
    else:
        ref, dp = REF_T, "desvio-padrão"

    if masc == "B":
        coment = "Exame realizado em condições técnicas adequadas, sendo examinada a coluna lombar em AP, fêmur e rádio 1/3."
    elif len(lados) == 2:
        coment = ("Exame realizado em condições técnicas adequadas, sendo examinada a coluna lombar e o segmento "
                  "proximal de ambos os fêmures.")
    else:
        coment = ("Exame realizado em condições técnicas adequadas, sendo examinada a coluna lombar e o segmento "
                  "proximal do fêmur %s." % (nome[lados[0]] if lados else "@direito @esquerdo"))

    res = ["Valor médio da DENSIDADE MINERAL ÓSSEA (BMD em g/cm²) das vértebras L1, L2, L3 e L4 é de %s g/cm² "
           "e corresponde ao %s de %s %s" % (f3("col_bmd"), dp, f1("col_t"), ref)]
    for l in (lados or ["?"]):
        if l == "?":
            res.append("Valor médio da DENSIDADE MINERAL ÓSSEA (BMD em g/cm²) do colo femoral @direito @esquerdo é "
                       "de @ g/cm² e corresponde ao %s de @ %s Utilizando-se a mesma tabela, observa-se desvio "
                       "padrão de @ no fêmur total." % (dp, ref))
            continue
        res.append("Valor médio da DENSIDADE MINERAL ÓSSEA (BMD em g/cm²) do colo femoral %s é de %s g/cm² e "
                   "corresponde ao %s de %s %s Utilizando-se a mesma tabela, observa-se desvio padrão de %s no "
                   "fêmur total." % (nome[l], f3("colo_%s_bmd" % l), dp, f1("colo_%s_t" % l), ref,
                                     f1("total_%s_t" % l)))
    if masc == "B":
        res.append("Valor médio da DENSIDADE MINERAL ÓSSEA (BMD em g/cm²) do rádio 1/3 que é de %s g/cm² e "
                   "corresponde ao desvio-padrão de %s %s" % (f3("radio_bmd"), f1("radio_t"), REF_T))

    # comparação: pela DMO, nunca pelo T; significativa só acima do LSC
    cmp_ = _comparar(v, n, lados, avisos)
    if cmp_:
        res.append(cmp_)

    vr = _tabela(VR_Z if tipo == "Z" else VR_T)
    partes = ["**DENSITOMETRIA ÓSSEA**", "**COMENTÁRIOS:**", coment, "**RESULTADOS:**"] + res + \
             ["**IMPRESSÃO DIAGNÓSTICA:**", imp, "**VALORES DE REFERÊNCIA EM RELAÇÃO AO DESVIO PADRÃO:**", vr]
    avisos.append("marcação das vértebras e posicionamento do fêmur não conferidos aqui (sem imagem da varredura).")
    return {"ok": True, "pronto": True, "texto": "\n\n".join(partes), "avisos": avisos,
            "valores": {"mascara": masc, "criterio": tipo, "menor": menor,
                        "lados": [nome[l] for l in lados]}}


def _comparar(v, n, lados, avisos):
    a_col, c_col = n["ant_col_bmd"], n["col_bmd"]
    a_tot = n["ant_total_bmd"]
    lado_tot = "e" if n["total_e_bmd"] is not None else ("d" if n["total_d_bmd"] is not None else None)
    c_tot = n["total_%s_bmd" % lado_tot] if lado_tot else None
    tem_col = a_col is not None and c_col is not None
    tem_tot = a_tot is not None and c_tot is not None
    if not (tem_col or tem_tot):
        if a_col is not None or a_tot is not None:
            avisos.append("exame anterior informado sem a BMD atual do mesmo sítio: comparação não feita.")
        return ""
    if tem_tot and len(lados) == 2:
        avisos.append("fêmur bilateral: comparei o fêmur total %s; confira se o anterior é do mesmo lado."
                      % ("esquerdo" if lado_tot == "e" else "direito"))
    lsc_c = n["lsc_col"] if n["lsc_col"] is not None else LSC_ISCD["col"]
    lsc_t = n["lsc_total"] if n["lsc_total"] is not None else LSC_ISCD["total"]
    if n["lsc_col"] is None or n["lsc_total"] is None:
        avisos.append("LSC: sem o do serviço, usei a referência ISCD (coluna 5,3%, fêmur total 5,0%).")
    sentidos, trechos = [], []
    if tem_col:
        d = c_col - a_col
        p = d / a_col * 100
        if abs(p) > lsc_c:
            sentidos.append("perda" if d < 0 else "ganho")
        trechos.append("de %s g/cm² (%s%%) na coluna lombar" % (sinal(d, 3), sinal(p, 1)))
    if tem_tot:
        d = c_tot - a_tot
        p = d / a_tot * 100
        if abs(p) > lsc_t:
            sentidos.append("perda" if d < 0 else "ganho")
        trechos.append("de %s g/cm² (%s%%) no fêmur total" % (sinal(d, 3), sinal(p, 1)))
    if not sentidos:
        sentido = "estabilidade"
    elif len(set(sentidos)) == 1:
        sentido = sentidos[0]
    else:
        sentido = "@ganho @perda"
        avisos.append("coluna e fêmur variaram em sentidos opostos acima do LSC: escolha a frase.")
    data = (v.get("ant_data") or "").strip() or "@"
    avisos.append("comparação pela DMO (g/cm²), nunca pelo T; só vale no mesmo equipamento.")
    return ("Em relação ao exame de %s, realizado no mesmo equipamento, observa-se %s da massa óssea, com "
            "variação %s." % (data, sentido, " e ".join(trechos)))


REGRAS_PRINT = """PRINT DO DENSITÔMETRO (DXA) — tabela de resultados do software

Leia CADA linha pelo nome da região e CADA número pelo cabeçalho da coluna.
- GE Lunar / iMax: BMD (g/cm²) · Ref. Jovem/Young-Adult (%) · T-score · Idade compatível/
  Age-Matched (%) · Z-score. As colunas de % NÃO são escores; "-1.9 (-26%)" -> T = -1,9.
- Hologic: BMD · T-score · PR (%) · Z-score · AM (%).
- Coluna: a linha L1-L4 (ou a combinação mostrada) e as vértebras isoladas (só o T).
- Fêmur: Colo (Neck) e Total (Total Hip). Trocânter, intertrocantérica e Ward NÃO.
- LADO DO FÊMUR: pelo rótulo do software ("Fêmur Direito", "Left Femur"), nunca pela
  posição na imagem. Sem rótulo de lado: deixe o fêmur fora e diga em "obs".
- Rádio: só o 33% (1/3).
- Na máscara de Z-score (pré-menopausa, homem < 50), os campos "_t" recebem o Z.
- Idade: só se estiver na tabela (nunca data de nascimento nem nome).

CAMPOS (chave: o que é):
{campos}

Regras: só o número, vírgula decimal, como o software mostra (BMD com 3 casas, escore
com 1 ou 2). Campo que não está na imagem: fora de "valores" e em "nao_achei".
Devolva: {{"valores": {{"col_bmd": "0,912"}}, "nao_achei": ["chave"], "obs": "texto curto"}}"""
