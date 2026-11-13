# -*- coding: utf-8 -*-
"""Padrão de formatação do laudo do Bruno — aplicado a TUDO que sai.

    **TÍTULO EM CAIXA ALTA**

    **TÉCNICA:**  texto na mesma linha.

    **INDICAÇÃO CLÍNICA:**  Em anexo.

    **ANÁLISE:**
    **Fígado:**  texto.
    **Baço:**  texto.

    **COMPARAÇÃO:**  texto na mesma linha.

    **CONCLUSÃO:**
    Achado um.
    Achado dois.

Radiografia: só título, TÉCNICA e ANÁLISE (frases diretas, sem rótulo).
O texto que volta da nuvem passa por padronizar(): não importa como o modelo
devolveu (markdown, linhas em branco a mais, cabeçalho em outra linha, lista
numerada), sai sempre neste formato.
"""
import re, unicodedata


def _sa(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper()


# cabeçalho canônico -> (formas aceitas sem acento, tipo)
#   tipo "linha": o texto vem na MESMA linha;  "bloco": o texto vem abaixo
CABECALHOS = [
    ("TÉCNICA", ("TECNICA", "TECNICA DO EXAME", "PROTOCOLO"), "linha"),
    ("INDICAÇÃO CLÍNICA", ("INDICACAO CLINICA", "INDICACAO", "INFORMACOES CLINICAS",
                           "DADOS CLINICOS", "HISTORIA CLINICA"), "linha"),
    ("ANÁLISE", ("ANALISE", "RELATORIO", "ACHADOS", "DESCRICAO"), "bloco"),
    ("COMPARAÇÃO", ("COMPARACAO", "COMPARATIVO", "ESTUDO COMPARATIVO"), "linha"),
    ("CONCLUSÃO", ("CONCLUSAO", "IMPRESSAO", "IMPRESSAO DIAGNOSTICA", "OPINIAO"), "bloco"),
]
_FORMAS = {}
for canon, formas, tipo in CABECALHOS:
    for f in formas + (_sa(canon),):
        _FORMAS[f] = (canon, tipo)
_RX_CAB = re.compile(r"^\s*(%s)\s*:\s*(.*)$" % "|".join(
    sorted((re.escape(f) for f in _FORMAS), key=len, reverse=True)))

# "Fígado:  texto" — rótulo curto (até 6 palavras) antes de dois-pontos
_RX_ROTULO = re.compile(r"^\s*([^\W\d_][^:.;!?()\[\]]{0,60}?)\s*:\s+(\S.*)$")


def _cab(linha):
    m = _RX_CAB.match(_sa(linha.replace("**", "")))
    if not m:
        return None
    canon, tipo = _FORMAS[m.group(1)]
    # o resto da linha, com acentos, a partir da posição do ':'
    crua = linha.replace("**", "")
    i = crua.find(":")
    resto = crua[i + 1:].strip() if i >= 0 else ""
    return canon, tipo, resto


def _limpa(l):
    l = l.replace("**", "").replace("__", "").rstrip()
    l = re.sub(r"^\s*#{1,6}\s*", "", l)                     # markdown
    l = re.sub(r"^\s*(?:[-•*·–—]|\d+[.)])\s+", "", l)        # listas e numeração
    return l.strip().strip('"').strip()


def _minuscula(t):
    """Padrao do Bruno: depois de 'Rotulo:' / 'TECNICA:' o texto comeca minusculo
    ("de dimensoes normais"). Sigla ou nome proprio (2a letra maiuscula) fica."""
    if len(t) > 1 and t[0].isupper() and t[1].islower():
        return t[0].lower() + t[1:]
    return t


def rotulo_negrito(linha):
    m = _RX_ROTULO.match(linha)
    if not m or len(m.group(1).split()) > 6:
        return linha
    return "**%s:**  %s" % (m.group(1).strip(), _minuscula(m.group(2).strip()))


def padronizar(texto):
    """Qualquer laudo (vindo da nuvem ou do banco) -> formato do Bruno, com **."""
    linhas = [_limpa(l) for l in re.split(r"\r?\n", texto or "")]
    linhas = [l for l in linhas if l and not l.startswith("```")]
    if not linhas:
        return texto
    # avisos no topo ("[conferir — a IA acrescentou: ...]") ficam como vieram,
    # numa linha própria, antes do título
    avisos = []
    while linhas and linhas[0].startswith("["):
        avisos.append(linhas.pop(0))
    if not linhas:
        return "\n".join(avisos)
    if not any(_cab(l) for l in linhas):
        return "\n".join(avisos + linhas)   # não é laudo estruturado: só limpa

    titulo, secoes, atual = [], [], None
    for l in linhas:
        c = _cab(l)
        if c:
            atual = [c[0], c[1], [c[2]] if c[2] else []]
            secoes.append(atual)
        elif atual is None:
            titulo.append(l)
        else:
            atual[2].append(l)

    out = []
    if titulo:
        out.append("**%s**" % " ".join(titulo).upper().rstrip(":"))
    for canon, tipo, corpo in secoes:
        if out:
            out.append("")
        if tipo == "linha":
            txt = " ".join(corpo).strip()
            if canon in ("TÉCNICA", "COMPARAÇÃO"):
                txt = _minuscula(txt)
            out.append("**%s:**" % canon + ("  " + txt if txt else ""))
        else:
            out.append("**%s:**" % canon)
            for l in corpo:
                out.append(rotulo_negrito(l) if canon == "ANÁLISE" else l)
    return "\n".join(avisos + out)


def negritar_rotulos(texto):
    """Só os rótulos da ANÁLISE ("Fígado:" -> "**Fígado:**"), sem mexer no resto.
    Usado no texto que sai do banco, que já vem no formato."""
    linhas = texto.split("\n")
    dentro = False
    for i, l in enumerate(linhas):
        s = l.strip()
        c = _cab(s) if s else None
        if c:
            dentro = c[0] == "ANÁLISE"
            continue
        if dentro and s and not s.startswith("**") and not s.startswith("["):
            linhas[i] = rotulo_negrito(l)
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# 13/11 (pedido dele): numeração anatômica. Ditado vem "terceira costela", "quinto
# metatarso", "segmento cinco"; o padrão dele é:
#   - metatarsos, metacarpos, dedos, arcos costais, costelas, espaços intercostais:
#     numeral com o indicador — 3º, 4º e 5º metatarsos; 5ª costela;
#   - segmento hepático: algarismo romano — segmento VII; segmentos V e VI; IVa.
# Vale para TUDO o que sai (banco, ditado, IA).
# ---------------------------------------------------------------------------
_ORD_PAL = {"primeir": 1, "segund": 2, "terceir": 3, "quart": 4, "quint": 5, "sext": 6,
            "setim": 7, "sétim": 7, "oitav": 8, "non": 9, "decim": 10, "décim": 10}
_ORD_PALAVRA = (r"(?:d[eé]cim[oa]\s+(?:primeir[oa]|segund[oa])|primeir[oa]|segund[oa]|terceir[oa]|"
                r"quart[oa]|quint[oa]|sext[oa]|s[eé]tim[oa]|oitav[oa]|non[oa]|d[eé]cim[oa])")
_ORD_DIG = r"(?:1[0-2]|[1-9])(?:\s?[ºª°]|[oa](?![a-zà-ú]))?"
_ORD_TOK = r"(?:%s|%s)" % (_ORD_PALAVRA, _ORD_DIG)
# "do primeiro e do segundo metatarsos", "o segundo e o terceiro dedos": o artigo repete
# "terceiro quarto e quinto metatarsos" (a voz não pôs a vírgula): o espaço também separa
_ORD_SEP = (r"(?:\s*,\s*(?:e\s+)?(?:d?[oa]s?\s+)?|\s+e\s+(?:d?[oa]s?\s+)?|\s+a\s+|\s+ao\s+|"
            r"\s+at[eé]\s+o\s+|\s*/\s*|\s*-\s*|\s+)")
# substantivo -> gênero (o indicador segue o gênero: 3º metatarso, 5ª costela)
_ORD_NOMES = [(r"metatars(?:o|os|iano|ianos)", "m"), (r"metacarp(?:o|os|iano|ianos)", "m"),
              (r"dedos?", "m"), (r"pododá?a?ctilos?|pododactilos?", "m"), (r"quirodá?a?ctilos?|quirodactilos?", "m"),
              (r"artelhos?", "m"), (r"arcos?\s+costa(?:l|is)", "m"), (r"espa[çc]os?\s+intercosta(?:l|is)", "m"),
              (r"espa[çc]os?\s+inter(?:metatarsa|metacarpa|digita)(?:l|is)", "m"),
              (r"metatarsa(?:l|is)", "m"), (r"metacarpa(?:l|is)", "m"), (r"raios?(?![\s-]*x\b)", "m"),
              (r"(?:articula[çc](?:[ãa]o|[õo]es)\s+)?meta(?:tarso|carpo)-?fal[aâ]ng(?:[ií]ca|eana)s?", "f"),
              (r"falanges?", "f"), (r"costelas?", "f")]
_RX_ORD = re.compile(r"(?<![\w/])(%s(?:%s%s)*)\s+(%s)\b" % (
    _ORD_TOK, _ORD_SEP, _ORD_TOK, "|".join("(?:%s)" % n for n, _g in _ORD_NOMES)), re.IGNORECASE)
_RX_TOK = re.compile(_ORD_TOK, re.IGNORECASE)


def _valor_ordinal(tok):
    t = tok.strip().lower()
    m = re.match(r"(\d+)", t)
    if m:
        return int(m.group(1)), bool(re.search(r"[ºª°oa]$", t.replace(" ", "")))
    t = _sa(t).lower()
    base = 10 if t.startswith("decim") and " " in t else 0
    ult = t.split()[-1]
    for raiz, v in _ORD_PAL.items():
        r = _sa(raiz).lower()
        if ult.startswith(r):
            return (base + v if base else v), True
    return None, False


def _genero(nome):
    n = _sa(nome).lower()
    for padrao, g in _ORD_NOMES:
        if re.fullmatch(_sa(padrao).lower(), n):
            return g
    return "m"


def ordinais_anatomicos(texto):
    """'terceiro, quarto e quinto metatarsos' -> '3º, 4º e 5º metatarsos'; 'quinta costela' -> '5ª costela'.
    Número sem indicador só vira ordinal em lista ("3, 4 e 5 metatarsos") ou com o substantivo no
    singular ("5 metatarso"): "fraturas em 2 costelas" é quantidade e fica."""
    def troca(m):
        corrida, nome = m.group(1), m.group(2)
        toks = list(_RX_TOK.finditer(corrida))
        # só espaço entre dois ordinais vale para palavra com palavra ("terceiro quarto e quinto") ou
        # número com número ("3 4 e 5"); misturado ("grau 2 1º metatarso", "segundo 3 costelas")
        # a lista começa no último corte
        for i in range(len(toks) - 1, 0, -1):
            sep = corrida[toks[i - 1].end():toks[i].start()]
            a_, b_ = toks[i - 1].group(0).replace(" ", ""), toks[i].group(0).replace(" ", "")
            if not sep.strip() and not ((a_.isalpha() and b_.isalpha()) or (a_.isdigit() and b_.isdigit())):
                corte = toks[i].start()
                return corrida[:corte] + ordinais_anatomicos(corrida[corte:] + m.group(0)[len(corrida):])
        so_digitos_sem_marca = all(_valor_ordinal(t.group(0))[0] is not None and
                                   not _valor_ordinal(t.group(0))[1] for t in toks)
        plural = _sa(nome).lower().rstrip().endswith(("s", "is"))
        if so_digitos_sem_marca and len(toks) == 1 and plural:
            return m.group(0)                     # "2 costelas": quantidade
        ind = "ª" if _genero(nome) == "f" else "º"
        partes, pos = [], 0
        for t in toks:
            v, _marca = _valor_ordinal(t.group(0))
            if v is None:
                return m.group(0)
            sep = corrida[pos:t.start()]
            partes.append(", " if partes and sep and not sep.strip() else sep)   # "3º 4º e 5º" -> "3º, 4º e 5º"
            palavra = t.group(0).strip().lower()
            # dito por extenso, o gênero é o da palavra ("primeira metatarsofalângica")
            ind_t = (("ª" if palavra.endswith("a") else "º") if palavra[-1:].isalpha() and
                     not re.fullmatch(r"\d+\s?[oa]", palavra) else ind)
            partes.append("%d%s" % (v, ind_t))
            pos = t.end()
        partes.append(corrida[pos:])
        return "".join(partes) + " " + nome
    return _RX_ORD.sub(troca, texto or "")


_ROMANO = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
_CARD = {"um": 1, "dois": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8}
# "4a"/"4 a"/"quatro a" = IVa; mas "segmentos 5 a 8" é intervalo (o "a" seguido de outro segmento)
_SUB = r"(?:\s?[ab](?![\w])(?!\s+(?:[1-8]|VIII|VII|VI|IV|V|III|II|I|um|dois|tr[eê]s|quatro|cinco|seis|sete|oito)\b))"
_SEG_TOK = (r"(?:[1-8]%s?(?![\d])|(?:VIII|VII|VI|IV|V|III|II|I)%s?(?![A-Za-z])|quatro%s?|"
            r"um|dois|tr[eê]s|cinco|seis|sete|oito|primeiro|segundo|terceiro|quarto|quinto|sexto|"
            r"s[eé]timo|oitavo)") % (_SUB, _SUB, _SUB)
_SEG_SEP = r"(?:\s*,\s*|\s+e\s+|\s+a\s+|\s+ao\s+|\s*/\s*|\s*-\s*)"
_RX_SEG = re.compile(r"\b(segmentos?)\s+(%s(?:%s%s)*)" % (_SEG_TOK, _SEG_SEP, _SEG_TOK))
_RX_SEG_TOK = re.compile(_SEG_TOK)
# segmento de outra estrutura: pulmão, duodeno, ureter, alças, vasos, coluna
_RX_SEG_OUTRO = re.compile(r"\blobo\s+(?:inferior|superior|medio)|pulm|bronc|lingula|duoden|ureter|intestin|"
                           r"colon|\bileo|jejun|alca|coluna|medula|vertebr|aort|arteri|\bveia|carot|basilar|"
                           r"coronar|ventric|\bm[1-4]\b|\b[av][1-4]\b|\bp[1-3]\b")
_RX_FIGADO = re.compile(r"f[ií]gado|hep[aá]tic|hepatoc|lobo\s+(?:direito|esquerdo|caudado)", re.IGNORECASE)


def _romano_do_segmento(tok):
    t = tok.strip()
    m = re.fullmatch(r"([1-8])\s?([ab])?", t)
    if m:
        return _ROMANO[int(m.group(1))] + (m.group(2) or "")
    if re.fullmatch(r"(?:VIII|VII|VI|IV|V|III|II|I)(?:\s?[ab])?", t):
        return t.replace(" ", "")
    m = re.fullmatch(r"quatro\s?([ab])", t, re.IGNORECASE)
    if m:
        return "IV" + m.group(1).lower()
    s = _sa(t).lower()
    if s in {_sa(k).lower(): v for k, v in _CARD.items()}:
        return _ROMANO[{_sa(k).lower(): v for k, v in _CARD.items()}[s]]
    v, _m = _valor_ordinal(t)
    return _ROMANO.get(v) if v else None


def segmentos_hepaticos(texto):
    """No fígado, 'segmento 7' / 'segmento sete' / 'segmentos 5 e 6' / 'segmento 4a' -> romano.
    Só nas linhas que falam do fígado: 'segmento proximal do ureter' e segmentos pulmonares ficam."""
    saida = []
    # a CONCLUSÃO repete "Nódulo no segmento 7." sem dizer fígado: no laudo que fala do fígado,
    # segmento numerado sem outra estrutura na linha também é do fígado
    laudo_do_figado = bool(_RX_FIGADO.search(texto or ""))
    for linha in (texto or "").split("\n"):
        if _RX_FIGADO.search(linha) or (laudo_do_figado and not _RX_SEG_OUTRO.search(_sa(linha).lower())):
            def troca(m):
                corrida = m.group(2)
                partes, pos = [], 0
                for t in _RX_SEG_TOK.finditer(corrida):
                    r = _romano_do_segmento(t.group(0))
                    if r is None:
                        return m.group(0)
                    partes.append(corrida[pos:t.start()])
                    partes.append(r)
                    pos = t.end()
                partes.append(corrida[pos:])
                return m.group(1) + " " + "".join(partes)
            linha = _RX_SEG.sub(troca, linha)
        saida.append(linha)
    return "\n".join(saida)


def numeracao(texto):
    """Os dois padrões juntos — chamado no fim de toda saída do roteador."""
    return segmentos_hepaticos(ordinais_anatomicos(texto))


# 13/11: a lista é UM achado. No ditado "nas bases do terceiro, quarto e quinto metatarsos"
# o separador de achados (vírgula, " e ") partia em "nas bases do terceiro." / "4º e 5º
# metatarsos..." — três linhas no laudo; "nódulos nos segmentos cinco e seis do fígado"
# partia no " e " e o "nódulos nos segmentos 5" ia parar nas adrenais. Os separadores de
# dentro da lista ficam trancados enquanto o ditado é partido e voltam em cada pedaço.
_LISTA_VIRG, _LISTA_E = "\x05", "\x06"
_RX_SEG_I = re.compile(_RX_SEG.pattern, re.IGNORECASE)


def proteger_listas(texto):
    def tranca(m):
        t = re.sub(r"\s*,\s*", _LISTA_VIRG, m.group(0))
        return re.sub(r"\s+e\s+", _LISTA_E, t)
    return _RX_SEG_I.sub(tranca, _RX_ORD.sub(tranca, texto or ""))


def soltar_listas(texto):
    return (texto or "").replace(_LISTA_VIRG, ", ").replace(_LISTA_E, " e ")
