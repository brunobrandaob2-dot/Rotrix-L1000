# -*- coding: utf-8 -*-
"""Tórax 1 a 9, leito, dispositivos e arcos costais (python testar_torax_leito.py).

13/11, pedidos dele:
- "do 1 ao 9 ... o 6 vai ser no leito, o 7 no leito de idoso": o número depois do exame é a
  máscara (antes só ia até 5; "tórax 6" virava achado "6" na normal);
- "se na máscara vem cânula orotraqueal e eu falo cânula de traqueostomia, tem que mudar": o
  dispositivo ditado troca a linha do mesmo dispositivo da máscara;
- "as máscaras de arcos costais ... não delimita o lado": o título leva o lado ditado;
- achado no caminho: "radiografia dos joelhos" abria o "joelho dois" (grau 2): "dois" casava
  com "dos" por semelhança. Número só casa igual."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rx_literal  # noqa: E402

MOLDE = """**RADIOGRAFIA DO TÓRAX NO LEITO**

**TÉCNICA:**  Incidência anteroposterior, realizada no leito.

**ANÁLISE:**
Cânula endotraqueal com extremidade distal projetada acima da carina.
Cateter venoso central com extremidade projetada na topografia da veia cava superior.
Sonda enteral com extremidade distal projetada abaixo do diafragma, além dos limites do estudo.
Pulmões hipoexpandidos, sem opacidades focais.
Área cardíaca de avaliação limitada pela incidência anteroposterior.
Arcabouço ósseo sem alterações."""


def main():
    falhas = []

    def ok(cond, nome):
        print(("ok      " if cond else "FALHA   ") + nome)
        if not cond:
            falhas.append(nome)

    def comp(*ditos):
        return rx_literal.compor(MOLDE, [{"texto": d} for d in ditos]).split("**ANÁLISE:**")[1]

    t = comp("Cânula de traqueostomia com extremidade a 5 cm da carina.")
    ok("Cânula de traqueostomia com extremidade a 5 cm da carina." in t and "Cânula endotraqueal" not in t,
       "cânula de traqueostomia ditada troca a cânula endotraqueal da máscara")
    ok("Cateter venoso central com extremidade" in t and "Sonda enteral" in t,
       "os outros dispositivos da máscara ficam")
    t = comp("Tubo orotraqueal com extremidade a 4 cm da carina.")
    ok("Tubo orotraqueal" in t and "Cânula endotraqueal" not in t, "tubo orotraqueal também troca a cânula")
    t = comp("Cateter venoso central à esquerda com extremidade na veia cava superior.")
    ok(t.count("Cateter venoso central") == 1 and "à esquerda" in t, "cateter central ditado troca o da máscara")
    t = comp("Sonda nasogástrica com extremidade no estômago.", "Dreno torácico à direita.")
    ok("Sonda enteral" not in t and "Sonda nasogástrica" in t and "Dreno torácico à direita." in t
       and "Cânula endotraqueal" in t, "sonda troca sonda; dreno (que a máscara não tem) entra")
    ok(rx_literal.familia_dispositivo("tqt com extremidade") == "via_aerea"
       and rx_literal.familia_dispositivo("picc a direita") == "cateter_central"
       and rx_literal.familia_dispositivo("sne") == "sonda", "siglas: TQT, PICC, SNE")

    src = open(os.path.join(AQUI, "roteador.py"), encoding="utf-8").read()
    import re
    m = re.search(r'_SO_LADO_E_GRAU = re\.compile\(r"(.+?)"\)', src)
    rx = re.compile(m.group(1)) if m else None
    ok(rx is not None and all(rx.fullmatch(x) for x in ("6", "9", "seis", "sete", "oito", "nove", "direito 2"))
       and not rx.fullmatch("10"), "o número da máscara vai de 1 a 9 (por extenso também)")
    ok("w not in _NUMERAIS_FALADOS and perto_anat(w)" in src and "(w in _NUMERAIS_FALADOS or not perto_cont(w))" in src,
       "número só casa igual no gatilho ('dos joelhos' não abre 'joelho dois')")
    ok("(?!arcos costais|seios (?:da face|paranasais))" in src,
       "'dos arcos costais' é o nome do exame, não os dois lados")
    arc = open(os.path.join(AQUI, "dados", "mascaras", "msk", "rx", "arcos_costais", "normal.txt"),
               encoding="utf-8").read()
    ok("**RADIOGRAFIA DOS ARCOS COSTAIS {LADO_A|À DIREITA/À ESQUERDA}**" in arc, "título dos arcos costais com o lado")

    print()
    print("tórax 1-9, leito e dispositivos: tudo certo" if not falhas else "tórax/leito: %d falha(s)" % len(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
