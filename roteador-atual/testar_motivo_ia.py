# -*- coding: utf-8 -*-
"""O motivo de a IA não responder vem em português (python testar_motivo_ia.py).

20/11, ele, com a tela "a IA não respondeu (nuvem_teto)": "não sei que informação é essa".
Era o limite de gasto do mês (US$ 15) atingido. O motivo continua começando pelo código (o
app reconhece por ele) e traz depois a explicação com os valores e onde aumentar; o recibo
de cada chamada leva o limite, para a tela avisar perto dele."""
import io
import os
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import roteador as r  # noqa: E402


def main():
    falhas = []

    def ok(cond, nome, extra=""):
        print(("ok      " if cond else "FALHA   ") + nome + (("   (" + extra + ")") if extra and not cond else ""))
        if not cond:
            falhas.append(nome)

    tmp = tempfile.mkdtemp()
    r.nuvem.GASTO = os.path.join(tmp, "gasto.json")
    with open(r.nuvem.GASTO, "w", encoding="utf-8") as f:
        f.write('{"mes": "%s", "usd": 15.01, "chamadas": 915}' % r.nuvem._mes())
    m = r._motivo_legivel("nuvem_teto", {"limite_mes_usd": 15.0})
    ok(m.startswith("nuvem_teto: "), "o código continua no começo (o app reconhece)", m)
    ok("US$ 15,01 de US$ 15,00" in m, "diz quanto gastou e qual é o limite", m)
    ok("Configurações › IA › Limite do mês" in m, "diz onde aumentar", m)
    ok(r._motivo_legivel("nuvem_vazia") == "nuvem_vazia", "outros motivos passam como vieram")

    src = open(os.path.join(AQUI, "roteador.py"), encoding="utf-8").read()
    ok('"motivo": _motivo_legivel(origem, c)' in src, "ia_no_texto usa o motivo legível")
    ok('"limite_mes_usd": float(c.get("limite_mes_usd", 0) or 0)}' in src, "recibo leva o limite do mês")

    print()
    print("motivo da IA: tudo certo" if not falhas else "motivo da IA: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
