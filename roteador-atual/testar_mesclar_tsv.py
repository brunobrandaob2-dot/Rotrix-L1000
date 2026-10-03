# -*- coding: utf-8 -*-
"""ATUALIZAR: a tabela dele (.tsv) recebe o novo e desliga o que o Rotrix retirou.

    python testar_mesclar_tsv.py

03/10: o ATUALIZAR de 14h39 rodou a bateria no PC dele e o testar_gatilhos_trancas
caiu SÓ lá: "avulsão da placa volar" ainda puxava ateromatose. A linha
"placa -> ateroma" tinha saído do repositório em 02/10, mas o mesclar_tsv só
acrescenta — nunca tirava — e ela continuou valendo no PC. Este teste exige:
  1. linha retirada pelo Rotrix (igual à que ele tinha) vira comentário, no lugar
  2. nenhuma linha some do arquivo (conferido linha a linha)
  3. linha que ELE mudou (mesma chave, outro valor) continua valendo
  4. rodar duas vezes não comenta de novo nem acrescenta de novo
  5. as linhas novas continuam entrando; CRLF do Windows fica CRLF
  6. o sinonimos.tsv do repositório declara as duas retiradas de 02/10
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import mesclar_tsv as M  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
NO_REPOSITORIO = os.path.isdir(os.path.join(AQUI, "..", ".git"))
falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


tmp = tempfile.mkdtemp()
novo = os.path.join(tmp, "novo.tsv")
dele = os.path.join(tmp, "dele.tsv")

NOVO = ("# cabecalho\n"
        "#retirada\tplaca\tateroma ateromatose calcificacao\n"
        "#retirada\tplacas\tateromas ateromatose calcificacoes\n"
        "#retirada\tcoisa velha\tachado velho\n"
        "pedra no rim\tcalculo renal nefrolitiase\n"
        "placa na aorta\tateroma ateromatose calcificacao\n")
# o dele: Windows (CRLF), com a linha velha do Rotrix, uma linha que ELE mudou, e
# uma linha só dele
DELE = ("# meu cabecalho\r\n"
        "Placa \t ateroma  ateromatose calcificacao\r\n"        # igual (maiúscula/espaço)
        "placas\tateromas ateromatose calcificacoes e mais o meu\r\n"   # ELE mudou
        "pedra no rim\tcalculo renal nefrolitiase\r\n"
        "minha troca\tminha coisa\r\n")
io.open(novo, "w", encoding="utf-8", newline="").write(NOVO)
io.open(dele, "w", encoding="utf-8", newline="").write(DELE)

n, como = M.mesclar(novo, dele)
depois = io.open(dele, encoding="utf-8", newline="").read()
linhas = depois.split("\r\n")

confere("retirada igual vira comentário", any(l.startswith("# retirada pela atualização de ")
                                               and l.endswith("Placa \t ateroma  ateromatose calcificacao")
                                               for l in linhas), depois)
confere("no mesmo lugar (2a linha)", linhas[1].startswith("# retirada pela atualização"), linhas[1])
confere("nenhuma linha some", all(l in depois for l in DELE.split("\r\n") if l), depois)
confere("a que ELE mudou continua valendo",
        "placas\tateromas ateromatose calcificacoes e mais o meu" in linhas, depois)
confere("a nova entra", "placa na aorta\tateroma ateromatose calcificacao" in linhas and n == 1, repr((n, como)))
confere("o resumo diz o que foi retirado", "1 retirada(s)" in como and "placa" in como, como)
confere("CRLF continua CRLF", "\r\n" in depois and "\n" not in depois.replace("\r\n", ""), repr(depois[:80]))

n2, como2 = M.mesclar(novo, dele)
depois2 = io.open(dele, encoding="utf-8", newline="").read()
confere("de novo: nada muda", n2 == 0 and como2 == "nada novo" and depois2 == depois, repr((n2, como2)))

# o arquivo dele ausente: cria (como antes)
outro = os.path.join(tmp, "nao_existe.tsv")
confere("sem arquivo dele: cria", M.mesclar(novo, outro)[1] == "criado" and os.path.exists(outro))

# o carregador do roteador ignora a linha "#retirada" (começa com #)
for nome in (os.path.join(AQUI, "dados", "sinonimos.tsv"), os.path.join(AQUI, "sinonimos.tsv")):
    if not os.path.exists(nome):
        continue
    t = io.open(nome, encoding="utf-8").read().splitlines()
    fora = M.retiradas(t)
    # no repositório o arquivo é o do Rotrix e tem de declarar; no PC dele o arquivo é
    # o DELE (já mesclado), sem as linhas "#retirada" — lá vale só a regra de baixo
    if NO_REPOSITORIO:
        confere("%s declara as retiradas de 02/10" % os.path.relpath(nome, AQUI),
                M._igual("placa\tateroma ateromatose calcificacao") in fora
                and M._igual("placas\tateromas ateromatose calcificacoes") in fora, repr(fora))
    confere("%s não tem mais 'placa' solta valendo" % os.path.relpath(nome, AQUI),
            not any(M._chave(l) in ("placa", "placas") for l in t))

print()
print("mesclar tsv: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
