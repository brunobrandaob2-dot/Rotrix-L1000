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
