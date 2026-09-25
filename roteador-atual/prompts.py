# -*- coding: utf-8 -*-
"""Prompt de sistema montado por bloco, a partir de dados/prompts/REDATOR_ROTRIX.md.

Por que existe
--------------
Até a v0.4.5 o prompt de sistema era uma pilha de strings escritas a mao dentro do
nuvem.py (SISTEMA_LAUDO, SISTEMA_REVISAO, SISTEMA_FORMATAR, SISTEMA_BARATO...) e o
REDATOR_ROTRIX.md era um documento paralelo que ninguem lia em tempo de execucao.
Duas fontes de verdade: corrigir o .md nao mudava nada, e corrigir o .py fazia o .md
mentir.

Agora o .md e o prompt. Ele e cortado nos marcadores

    <!-- BLOCO: NOME -->

e cada rota recebe SO os blocos de que precisa. Isso e o que faz o prompt inteiro caber
no caminho barato: conserto de ortografia nao paga pelas regras de conclusao.

Se o arquivo faltar (pacote antigo, instalacao pela metade), `montar` devolve None e o
nuvem.py cai nas constantes antigas. Prompt nunca pode ser ponto unico de falha.
"""

import io
import os
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(AQUI, "dados", "prompts", "REDATOR_ROTRIX.md")

_MARCA = re.compile(r"^<!--\s*BLOCO:\s*([A-Z_]+)\s*-->\s*$", re.M)

# Quais blocos cada rota manda. A ordem aqui e a ordem no prompt.
RECEITAS = {
    # caminho barato (Haiku): conserto de texto, sem regra de laudo inteiro
    "formatar":  ("PAPEL", "TRECHO", "NUMEROS", "VOZ", "COMANDOS", "SEM_LACUNAS", "SAIDA"),
    "revisao":   ("PAPEL", "TRECHO", "NUMEROS", "VOZ", "COMANDOS", "SEM_LACUNAS", "SAIDA"),
    # caminho forte: laudo inteiro, ordens sobre o laudo
    "laudo":     ("PAPEL", "DECISAO", "TRECHO", "LAUDO", "NUMEROS", "VOZ", "COMANDOS",
                  "SEM_LACUNAS", "CONFERENCIA", "SAIDA"),
    "instrucao": ("PAPEL", "DECISAO", "TRECHO", "LAUDO", "NUMEROS", "VOZ", "COMANDOS",
                  "SEM_LACUNAS", "CONFERENCIA", "SAIDA"),
    # comparativo / RECIST: raciocinio sobre dois exames, sem lista de erro de voz
    "analise":   ("PAPEL", "COMPARATIVO", "NUMEROS", "SEM_LACUNAS", "SAIDA"),
}

_cache = {"mtime": None, "blocos": None}


def blocos(arquivo=None):
    """{NOME: texto}. Recarrega quando o arquivo muda no disco (editar o .md basta)."""
    caminho = arquivo or ARQUIVO
    try:
        mt = os.path.getmtime(caminho)
    except OSError:
        return {}
    chave = (caminho, mt)
    if _cache["mtime"] == chave and _cache["blocos"] is not None:
        return _cache["blocos"]
    try:
        with io.open(caminho, encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return {}
    d = {}
    partes = _MARCA.split(txt)
    # partes = [cabecalho, NOME1, corpo1, NOME2, corpo2, ...]
    # o cabecalho (documentacao) e descartado de proposito: nunca vai para a nuvem
    for i in range(1, len(partes) - 1, 2):
        nome = partes[i].strip()
        corpo = partes[i + 1].strip()
        if nome and corpo:
            d[nome] = corpo
    _cache["mtime"] = chave
    _cache["blocos"] = d
    return d


def montar(modo, arquivo=None):
    """Prompt de sistema da rota, ou None quando o arquivo nao da para usar.

    None e a diferenca entre "prompt vazio" e "sem prompt": o chamador precisa saber
    para poder cair nas constantes de reserva em vez de chamar a nuvem sem regra."""
    d = blocos(arquivo)
    if not d:
        return None
    receita = RECEITAS.get(modo)
    if not receita:
        return None
    partes = [d[n] for n in receita if d.get(n)]
    # bloco da receita que nao existe no arquivo = arquivo editado errado. Nao monta
    # prompt pela metade: o laudo sairia sem a regra que faltou e ninguem veria.
    if len(partes) != len(receita):
        return None
    return "\n\n".join(partes)


def conferir(arquivo=None):
    """(ok, problemas). Usado pelo teste e pelo VALIDAR_TUDO."""
    d = blocos(arquivo)
    problemas = []
    if not d:
        problemas.append("nao consegui ler %s" % (arquivo or ARQUIVO))
        return False, problemas
    precisa = set()
    for r in RECEITAS.values():
        precisa.update(r)
    for n in sorted(precisa):
        if n not in d:
            problemas.append("bloco %s nao existe no arquivo" % n)
    for n in sorted(d):
        if n not in precisa:
            problemas.append("bloco %s existe no arquivo e nao entra em nenhuma rota" % n)
    for modo in RECEITAS:
        if montar(modo, arquivo) is None:
            problemas.append("rota %s nao monta" % modo)
    return (not problemas), problemas


def tamanhos(arquivo=None):
    """{modo: (chars, tokens_aprox)} — para a auditoria de custo."""
    out = {}
    for modo in RECEITAS:
        t = montar(modo, arquivo) or ""
        out[modo] = (len(t), int(round(len(t) / 3.3)))
    return out


if __name__ == "__main__":
    ok, probs = conferir()
    for m, (c, t) in sorted(tamanhos().items()):
        print("%-10s %6d chars  ~%5d tokens" % (m, c, t))
    print()
    print("OK" if ok else "PROBLEMAS:")
    for p in probs:
        print(" -", p)
    raise SystemExit(0 if ok else 1)
