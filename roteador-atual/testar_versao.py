# -*- coding: utf-8 -*-
"""O roteador diz quando está rodando código VELHO.   python testar_versao.py

26/09: o VERSAO ficou "2026-09-26.1" por cinco commits. O LIGAR_ROTEADOR_NOVO
olhava só o número, achava que já estava o certo e não reiniciava; o processo
seguia com o código de antes na memória — e a correção da chave da OpenAI
(04779b8) nunca valeu no PC dele. /v1/versao agora diz "desatualizado".
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roteador  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


v = roteador.versao_info()
confere("a versão saiu de 2026-09-26.1", v["versao"] != "2026-09-26.1", v["versao"])
confere("impressão digital do código presente", len(v.get("codigo") or "") == 12, repr(v.get("codigo")))
confere("recém-carregado: não está desatualizado", v["desatualizado"] is False, repr(v))
carregado = roteador.CODIGO_CARREGADO
try:
    roteador.CODIGO_CARREGADO = "000000000000"      # como se a pasta tivesse mudado depois
    confere("pasta atualizada e processo velho: desatualizado", roteador.versao_info()["desatualizado"] is True)
finally:
    roteador.CODIGO_CARREGADO = carregado
confere("a impressão ignora os testes (mudar teste não pede reinício)",
        "testar" not in "".join(n for n in os.listdir(os.path.dirname(os.path.abspath(roteador.__file__)))
                                if n.endswith(".py") and not n.startswith("testar")))
print()
print("versão do roteador: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
