# -*- coding: utf-8 -*-
"""Junta uma tabela .tsv nova (da atualização) com a DELE, sem perder nada dele.

    python mesclar_tsv.py <tsv_da_atualizacao> <tsv_dele>

Por que existe: dados/ouvido.tsv é onde o correcao.py grava as correções de voz
que ELE ensina ("horta" -> "aorta"). O arquivo também vem no repositório. Copiar
o do repositório por cima apagava o que ele ensinou (a revisão independente de
26/09 pegou isso no ATUALIZAR_ROTRIX.bat antes de rodar).

Regra: o arquivo dele fica inteiro, na ordem dele. Da atualização entram só as
linhas cuja chave (a 1a coluna, sem diferenciar maiúscula) ele ainda não tem.
Se ele mudou uma linha que também existe no repositório, vale a dele.

03/10 — linha RETIRADA pelo Rotrix. A regra acima tinha um furo: o que o Rotrix
tirava do repositório continuava valendo no PC dele para sempre. Em 02/10 a linha
"placa -> ateroma" saiu (fazia "avulsão da placa volar" puxar ateromatose); no PC
dele ficou, e o testar_gatilhos_trancas caiu lá (e só lá). Agora o repositório
diz o que retirou, numa linha de comentário:

    #retirada<TAB>placa<TAB>ateroma ateromatose calcificacao

e a linha IGUAL no arquivo dele (mesma chave e mesmo valor, sem diferenciar
maiúscula nem espaço) vira comentário, no mesmo lugar:

    # retirada pela atualização de 2026-10-03 (era do Rotrix): placa<TAB>ateroma ...

Nada é apagado (o texto continua no arquivo, e o ATUALIZAR guarda cópia em
backups). Linha que ELE mudou não é igual à retirada e fica valendo.
"""
import datetime
import io
import os
import sys


def _chave(linha):
    if "\t" not in linha or linha.lstrip().startswith("#"):
        return None
    return linha.split("\t", 1)[0].strip().lower()


RETIRADA = "#retirada\t"


def _igual(linha):
    """Forma de comparar: chave e valor, sem maiúscula e sem espaço sobrando."""
    partes = [" ".join(p.split()).lower() for p in linha.split("\t")]
    return "\t".join(p for p in partes if p)


def retiradas(linhas_novas):
    """As linhas que o Rotrix tirou, declaradas no arquivo novo."""
    return {_igual(l[len(RETIRADA):]) for l in linhas_novas if l.startswith(RETIRADA)}


def mesclar(novo, dele):
    """Devolve (quantas_entraram, como). `como` diz também quantas foram retiradas."""
    if not os.path.exists(novo):
        return 0, "sem arquivo novo"
    linhas_novas = io.open(novo, encoding="utf-8-sig").read().splitlines()
    if not os.path.exists(dele):
        io.open(dele, "w", encoding="utf-8", newline="\n").write("\n".join(linhas_novas) + "\n")
        return len(linhas_novas), "criado"
    with io.open(dele, encoding="utf-8-sig", newline="") as f:
        texto_dele = f.read()
    fim = "\r\n" if "\r\n" in texto_dele else "\n"
    linhas_dele = texto_dele.splitlines()
    hoje = datetime.date.today().isoformat()

    fora = retiradas(linhas_novas)
    tiradas = []
    for i, l in enumerate(linhas_dele):
        if _chave(l) and _igual(l) in fora:
            linhas_dele[i] = "# retirada pela atualização de %s (era do Rotrix): %s" % (hoje, l)
            tiradas.append(_chave(l))

    tem = {k for k in (_chave(l) for l in linhas_dele) if k}
    entram = [l for l in linhas_novas if _chave(l) and _chave(l) not in tem]
    if not entram and not tiradas:
        return 0, "nada novo"
    if entram:
        linhas_dele.append("# vindas da atualização de %s" % hoje)
        linhas_dele.extend(entram)
    with io.open(dele, "w", encoding="utf-8", newline="") as f:
        f.write(fim.join(linhas_dele) + fim)
    como = "juntadas" if entram else "nada novo"
    if tiradas:
        como += "; %d retirada(s) pelo Rotrix virou(aram) comentário: %s" % (
            len(tiradas), ", ".join(tiradas))
    return len(entram), como


def main(argv):
    if len(argv) != 3:
        print("uso: python mesclar_tsv.py <tsv_da_atualizacao> <tsv_dele>")
        return 2
    n, como = mesclar(argv[1], argv[2])
    print("%s: %d linha(s) %s" % (os.path.basename(argv[2]), n, como))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
