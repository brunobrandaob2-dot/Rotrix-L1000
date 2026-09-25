# -*- coding: utf-8 -*-
"""Auditoria de custo da rota de nuvem. Roda sem chave e sem gastar nada.

    python auditar_custo.py              relatorio completo
    python auditar_custo.py --log        so o que o log dele diz (gasto real)

O que mede:
  1. tamanho REAL do prompt de sistema de cada rota, montado do REDATOR_ROTRIX.md
  2. centavos por chamada, por rota e por modelo, ANTES (v0.4.5) e DEPOIS (v0.4.6)
  3. decisao de cache que sai do log dele (releitura por escrita medida, nao chutada)
  4. para onde foi o dinheiro, lido de dados/gasto.json e do log

A conversao caractere->token e aproximada (3,3 chars por token, medida em texto medico
em portugues). Onde existe numero REAL da API — gasto.json e o log — o relatorio usa o
numero real e diz que e real.
"""

import io
import json
import os
import sys

import nuvem
import prompts

AQUI = os.path.dirname(os.path.abspath(__file__))
CHARS_POR_TOKEN = 3.3

# Como era na v0.4.5, para a coluna "antes" nao ser chute:
#   barato  = SISTEMA_BARATO + SEM_LACUNAS
#   forte   = SISTEMA_LAUDO + FORMATO_SAIDA + SEM_LACUNAS + 24.000 chars de exemplo
#   analise = SISTEMA_ANALISE + FORMATO_SAIDA + SEM_LACUNAS   (sem regra de comparativo)
ANTES = {
    "revisao": len(nuvem.SISTEMA_BARATO) + len(nuvem.SEM_LACUNAS),
    "formatar": len(nuvem.SISTEMA_BARATO) + len(nuvem.SEM_LACUNAS),
    "laudo": (len(nuvem.SISTEMA_LAUDO) + len(nuvem.FORMATO_SAIDA)
              + len(nuvem.SEM_LACUNAS) + 24000),
    "instrucao": (len(nuvem.SISTEMA_INSTRUCAO) + len(nuvem.FORMATO_SAIDA)
                  + len(nuvem.SEM_LACUNAS) + 24000),
    "analise": (len(nuvem.SISTEMA_ANALISE) + len(nuvem.FORMATO_SAIDA)
                + len(nuvem.SEM_LACUNAS)),
}

# Trabalho tipico dele, em caracteres: um laudo montado pelo roteador + o ditado solto.
PEDIDO_CHARS = {"revisao": 900, "formatar": 900, "laudo": 3000,
                "instrucao": 3000, "analise": 5000}
SAIDA_CHARS = {"revisao": 900, "formatar": 900, "laudo": 3000,
               "instrucao": 3000, "analise": 3500}

MODELOS = [
    ("Fable 5",    "claude-fable-5-20260301"),
    ("Opus 5.5",   "claude-opus-5-5-20260815"),
    ("Sonnet 5",   "claude-sonnet-5-20260201"),
    ("Haiku 4.5",  "claude-haiku-4-5-20251001"),
]


def tok(chars):
    return int(round(chars / CHARS_POR_TOKEN))


def _centavos(modelo, n_in, n_out):
    return nuvem.custo(modelo, n_in, n_out) * 100.0


def tabela_precos():
    print("1. PRECO POR MILHAO DE TOKENS — conferido em platform.claude.com, 25/09/2026")
    print()
    print("   %-16s %8s %8s %10s %10s" % ("modelo", "entrada", "saida", "le cache", "antes"))
    velho = {"claude-fable": (10.0, 50.0), "claude-opus-5-5": (5.0, 25.0),
             "claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0),
             "claude-haiku": (1.0, 5.0)}
    for nome, mid in MODELOS:
        pin, pout = nuvem.preco(mid)
        mr = nuvem.mult_leitura_cache(mid)
        v = ""
        for pref, (a, b) in velho.items():
            if nuvem._id_curto(mid).startswith(pref):
                v = "" if (a, b) == (pin, pout) else "era %.0f/%.0f" % (a, b)
                break
        print("   %-16s %8.2f %8.2f %9.0f%% %10s" % (nome, pin, pout, mr * 100, v))
    print()
    print("   O erro: a tabela tinha o prefixo 'claude-opus' valendo 5,00/25,00 e nao")
    print("   tinha 'claude-opus-5-5'. Opus 5.5 custa 4,00/20,00. O recibo da tela e o")
    print("   teto do mes cobravam 25% a mais do que a Anthropic cobra.")
    print()


def tabela_prompt():
    print("2. PROMPT DE SISTEMA POR ROTA — medido, nao estimado")
    print()
    print("   %-11s %22s %22s %9s" % ("rota", "antes (v0.4.5)", "depois (v0.4.6)", "delta"))
    for modo in ("revisao", "formatar", "laudo", "instrucao", "analise"):
        novo = len(prompts.montar(modo) or "")
        if modo in ("laudo", "instrucao"):
            novo += min(nuvem.TETO_EXEMPLOS, _chars_estilo())
        a, d = tok(ANTES[modo]), tok(novo)
        print("   %-11s %12d chars %5d tok %12d chars %5d tok %+8d" % (modo, ANTES[modo], a, novo, d, d - a))
    print()
    print("   Onde estava o peso do caminho forte: 24.000 caracteres de laudo dele")
    print("   (~7.270 tokens) em TODA chamada — mais que o prompt inteiro. As regras")
    print("   de estilo que aqueles exemplos ensinavam por imitacao agora estao escritas")
    print("   no REDATOR_ROTRIX.md, e o teto caiu para %d." % nuvem.TETO_EXEMPLOS)
    print()


def _chars_estilo():
    pasta = os.path.join(AQUI, "dados", "estilo")
    try:
        return sum(os.path.getsize(os.path.join(pasta, f))
                   for f in os.listdir(pasta) if f.endswith(".txt") and f != "LEIA.txt")
    except OSError:
        return 0


def tabela_custo():
    print("3. CENTAVOS POR CHAMADA — sem cache, entrada e saida tipicas dele")
    print()
    cab = "   %-11s %-10s" % ("rota", "modelo")
    print(cab + "%10s %10s %9s" % ("antes", "depois", "corte"))
    totais = {}
    for modo in ("revisao", "laudo", "analise"):
        novo_sis = len(prompts.montar(modo) or "")
        if modo in ("laudo", "instrucao"):
            novo_sis += min(nuvem.TETO_EXEMPLOS, _chars_estilo())
        for nome, mid in MODELOS:
            a = _centavos(mid, tok(ANTES[modo] + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
            d = _centavos(mid, tok(novo_sis + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
            totais[(modo, nome)] = (a, d)
            print("   %-11s %-10s %9.2f¢ %9.2f¢ %8s" % (
                modo, nome, a, d, "%+.0f%%" % ((d - a) / a * 100) if a else "-"))
        print()
    print("   O caminho barato SUBIU de proposito: o prompt novo leva a lista de erro de")
    print("   reconhecimento de voz e os comandos falados, que e o defeito que ele mais")
    print("   reclama. Custa ~0,1 centavo a mais por chamada no Haiku.")
    print()
    return totais


def tabela_rota_real():
    print("4. O QUE MUDA NA PRATICA — a mesma tarefa, no modelo certo")
    print()
    linhas = [
        ("conserto de texto ditado", "revisao", "Fable 5", "Haiku 4.5"),
        ("laudo montado + achado solto", "laudo", "Fable 5", "Haiku 4.5"),
        ("comparativo / RECIST", "analise", "Fable 5", "Opus 5.5"),
    ]
    for rotulo, modo, antes_m, depois_m in linhas:
        mid_a = dict((n, m) for n, m in MODELOS)[antes_m]
        mid_d = dict((n, m) for n, m in MODELOS)[depois_m]
        novo_sis = len(prompts.montar(modo) or "")
        if modo in ("laudo", "instrucao"):
            novo_sis += min(nuvem.TETO_EXEMPLOS, _chars_estilo())
        a = _centavos(mid_a, tok(ANTES[modo] + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
        d = _centavos(mid_d, tok(novo_sis + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
        print("   %-30s %-10s %7.2f¢  ->  %-10s %7.2f¢   %s" % (
            rotulo, antes_m, a, depois_m, d,
            ("-%.0f%%" % ((a - d) / a * 100)) if a and d < a else "+%.0f%%" % ((d - a) / a * 100)))
    print()
    print("   'Fable 5' e o que estava selecionado sem ele saber: o botao leve pegava")
    print("   listaModelos[0], o primeiro da lista do provedor.")
    print()


# Mistura de trabalho de um dia. NAO e medida — e a hipotese que o relatorio usa e que
# ele pode corrigir aqui. Os centavos por chamada ao lado sao medidos.
MISTURA = [("conserto de texto", "revisao", 20),
           ("laudo montado + achado", "laudo", 8),
           ("comparativo", "analise", 2)]


def projecao():
    print("6. PROJECAO DO MES — a mistura e hipotese, os centavos sao medidos")
    print()
    print("   hipotese de um dia de plantao: %s" % ", ".join(
        "%d %s" % (n, r) for r, _m, n in MISTURA))
    print()
    antes_dia = depois_dia = 0.0
    print("   %-24s %7s %12s %12s" % ("tarefa", "n/dia", "antes/dia", "depois/dia"))
    for rotulo, modo, n in MISTURA:
        mid_a = "claude-fable-5-20260301"                    # o que estava selecionado
        mid_d = ("claude-opus-5-5-20260815" if modo == "analise"
                 else "claude-haiku-4-5-20251001")
        novo_sis = len(prompts.montar(modo) or "")
        if modo in ("laudo", "instrucao"):
            novo_sis += min(nuvem.TETO_EXEMPLOS, _chars_estilo())
        a = n * _centavos(mid_a, tok(ANTES[modo] + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
        d = n * _centavos(mid_d, tok(novo_sis + PEDIDO_CHARS[modo]), tok(SAIDA_CHARS[modo]))
        antes_dia += a
        depois_dia += d
        print("   %-24s %7d %11.1f¢ %11.1f¢" % (rotulo, n, a, d))
    print("   %-24s %7s %11.1f¢ %11.1f¢" % ("TOTAL", "", antes_dia, depois_dia))
    print()
    print("   por dia   US$ %.2f  ->  US$ %.2f" % (antes_dia / 100, depois_dia / 100))
    print("   22 dias   US$ %.2f  ->  US$ %.2f     (-%.0f%%)" % (
        antes_dia * 22 / 100, depois_dia * 22 / 100,
        (antes_dia - depois_dia) / antes_dia * 100))
    print()
    print("   O teto do config esta em US$ %.2f por mes." % float(
        (nuvem.config() or {}).get("limite_mes_usd", 0) or 0))
    print()


def relatorio_cache():
    print("7. CACHE — decidido pelo log dele, nao por chute")
    print()
    k5 = nuvem.releituras_por_escrita(5 * 60)
    k60 = nuvem.releituras_por_escrita(60 * 60)
    if k5 is None:
        print("   Log com menos de 20 chamadas: sem dado para decidir. Padrao = 5 min.")
    else:
        print("   releitura por escrita, janela de  5 min: %.2f" % k5)
        print("   releitura por escrita, janela de 1 hora: %.2f" % k60)
        print()
        print("   custo do bloco de sistema POR CHAMADA (1,00 = sem cache):")
        print("     sem cache        %.3f" % nuvem.gasto_por_chamada(0, None))
        print("     cache de 5 min   %.3f" % nuvem.gasto_por_chamada(k5, "5m"))
        print("     cache de 1 hora  %.3f" % nuvem.gasto_por_chamada(k60, "1h"))
    print()
    print("   Piso de tamanho (abaixo dele a Anthropic ignora cache_control em silencio):")
    for nome, mid in MODELOS:
        piso = nuvem.min_cache(mid)
        for modo in ("revisao", "laudo"):
            sis = len(prompts.montar(modo) or "")
            if modo == "laudo":
                sis += min(nuvem.TETO_EXEMPLOS, _chars_estilo())
            marca = nuvem.cache_de("x" * sis, mid, {})
            print("     %-10s %-9s prompt ~%5d tok, piso %5d -> %s" % (
                nome, modo, tok(sis), piso, marca or "SEM cache"))
    print()
    print("   Era assim: cache_control marcado em TODA chamada. No Haiku o prompt fica")
    print("   abaixo do piso de 4.096 e a marca era ignorada; onde nao era, a validade de")
    print("   5 minutos vencia entre um laudo e outro e a escrita de 1,25x virava prejuizo.")
    print()


def relatorio_log():
    print("8. PARA ONDE FOI O DINHEIRO — numeros REAIS da API, do gasto.json e do log")
    print()
    g = os.path.join(AQUI, "dados", "gasto.json")
    if not os.path.exists(g):
        g = os.path.join(AQUI, "gasto.json")
    if os.path.exists(g):
        try:
            d = json.load(io.open(g, encoding="utf-8"))
        except Exception as e:
            print("   nao consegui ler %s (%s)" % (g, type(e).__name__)); d = None
        if d:
            print("   mes %s: US$ %.2f em %d chamadas (%d tok entrada, %d saida)" % (
                d.get("mes", "?"), float(d.get("usd") or 0), int(d.get("chamadas") or 0),
                int(d.get("tokens_in") or 0), int(d.get("tokens_out") or 0)))
            pm = d.get("por_modelo") or {}
            if pm:
                print()
                print("   %-34s %9s %8s %9s" % ("modelo", "USD", "chamadas", "USD/chamada"))
                for m, v in sorted(pm.items(), key=lambda x: -float((x[1] or {}).get("usd") or 0)):
                    usd = float((v or {}).get("usd") or 0)
                    n = int((v or {}).get("chamadas") or 0)
                    print("   %-34s %9.3f %8d %9.4f" % (m, usd, n, usd / n if n else 0))
            if int(d.get("chamadas") or 0):
                print()
                print("   media de entrada por chamada: %d tokens" % (
                    int(d.get("tokens_in") or 0) // int(d["chamadas"])))
    else:
        print("   dados/gasto.json nao esta nesta copia (fica na maquina dele).")
    print()
    hs = nuvem._horas_de_chamada()
    if hs:
        hs = sorted(hs)
        print("   log: %d chamadas registradas, de %s a %s" % (
            len(hs), hs[0].isoformat(" "), hs[-1].isoformat(" ")))
    else:
        print("   log de chamadas vazio nesta copia.")
    print()


def main():
    so_log = "--log" in sys.argv
    print("=" * 78)
    print("AUDITORIA DE CUSTO — Rotrix L-1000 / rota de nuvem")
    print("=" * 78)
    print()
    if not so_log:
        tabela_precos()
        tabela_prompt()
        tabela_custo()
        tabela_rota_real()
        projecao()
        relatorio_cache()
    relatorio_log()


if __name__ == "__main__":
    main()
