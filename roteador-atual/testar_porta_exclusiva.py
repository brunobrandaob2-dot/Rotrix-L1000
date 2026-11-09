# -*- coding: utf-8 -*-
"""Um roteador só na porta (python testar_porta_exclusiva.py).

09/11: no Windows dele o LIGAR subiu o 2026-11-08.1, mas o Rotrix seguiu falando com o
2026-11-03.1. Duas causas: o LIGAR procurava "LISTENING" no netstat, que no Windows em
português escreve "ESCUTANDO" (nunca achava o processo velho para derrubar); e o servidor
usava SO_REUSEADDR, que no Windows deixa o segundo roteador escutar a mesma porta calado.
Aqui: no Windows o servidor não reaproveita a porta, e o segundo roteador desiste e avisa."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador as r  # noqa: E402


def main():
    falhas = []
    if r._Servidor.allow_reuse_address != (os.name != "nt"):
        falhas.append("no Windows o servidor não pode reaproveitar a porta (allow_reuse_address)")

    primeiro = r._Servidor(("127.0.0.1", 0), r.Handler)        # porta livre qualquer
    porta = primeiro.server_address[1]
    try:
        segundo = r._abrir_servidor(tentativas=2, espera=0.05, porta=porta)
        if segundo is not None:
            segundo.server_close()
            falhas.append("um segundo roteador abriu a porta %d ocupada" % porta)
    finally:
        primeiro.server_close()

    terceiro = r._abrir_servidor(tentativas=5, espera=0.2, porta=porta)
    if terceiro is None:
        falhas.append("com a porta livre de novo, o roteador não abriu")
    else:
        terceiro.server_close()

    # o roteador abre a porta ANTES de pegar o Ctrl+Alt+A: duplicado não rouba o atalho
    src = open(r.__file__, encoding="utf-8").read()
    i_srv, i_at = src.find("srv = _abrir_servidor()"), src.find("atalho_win.iniciar(")
    if not (0 <= i_srv < i_at):
        falhas.append("a porta tem de abrir antes do atalho Ctrl+Alt+A")

    for f in falhas:
        print("FALHOU", f)
    print()
    print("porta exclusiva: tudo certo" if not falhas else "porta: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
