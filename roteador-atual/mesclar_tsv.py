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
"""
import datetime
import io
import os
import sys


def _chave(linha):
    if "\t" not in linha or linha.lstrip().startswith("#"):
        return None
    return linha.split("\t", 1)[0].strip().lower()


def mesclar(novo, dele):
    if not os.path.exists(novo):
        return 0, "sem arquivo novo"
    linhas_novas = io.open(novo, encoding="utf-8-sig").read().splitlines()
    if not os.path.exists(dele):
        io.open(dele, "w", encoding="utf-8", newline="\n").write("\n".join(linhas_novas) + "\n")
        return len(linhas_novas), "criado"
    texto_dele = io.open(dele, encoding="utf-8-sig").read()
    tem = {k for k in (_chave(l) for l in texto_dele.splitlines()) if k}
    entram = [l for l in linhas_novas if _chave(l) and _chave(l) not in tem]
    if not entram:
        return 0, "nada novo"
    with io.open(dele, "a", encoding="utf-8", newline="\n") as f:
        if texto_dele and not texto_dele.endswith("\n"):
            f.write("\n")
        f.write("# vindas da atualização de %s\n" % datetime.date.today().isoformat())
        f.write("\n".join(entram) + "\n")
    return len(entram), "juntadas"


def main(argv):
    if len(argv) != 3:
        print("uso: python mesclar_tsv.py <tsv_da_atualizacao> <tsv_dele>")
        return 2
    n, como = mesclar(argv[1], argv[2])
    print("%s: %d linha(s) %s" % (os.path.basename(argv[2]), n, como))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
