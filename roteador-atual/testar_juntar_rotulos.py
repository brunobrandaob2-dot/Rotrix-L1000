# -*- coding: utf-8 -*-
"""A mesma estrutura numa linha só, antes de o laudo ir para a IA.

    python testar_juntar_rotulos.py

27/09: frases prontas ditadas uma a uma ("bandas parenquimatosas basais", depois
outra, depois "enfisema centrolobular nos lobos superiores") viravam três linhas
"Parênquima pulmonar:". O Terra, proibido de reordenar a ANÁLISE, mantinha as três.
Ele quer o parênquima numa linha só com todas as frases. Este teste exige:
  1. as linhas repetidas da ANÁLISE viram uma, na posição da primeira, na ordem ditada
  2. a normalidade da estrutura sai quando chega achado; frase repetida não duplica
  3. CONCLUSÃO, TÉCNICA e linhas sem rótulo não são mexidas
  4. o que vai para a IA (ia_no_texto) já chega junto
Sem rede.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + extra) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


LAUDO = """TOMOGRAFIA COMPUTADORIZADA DO TÓRAX

TÉCNICA:  aquisição volumétrica sem contraste.

ANÁLISE:
Parênquima pulmonar:  sem alterações significativas.
Pleura:  sem derrames.
Parênquima pulmonar:  bandas parenquimatosas basais.
Parênquima pulmonar:  estrias fibroatelectásicas nas bases pulmonares.
Parênquima pulmonar:  enfisema centrolobular nos lobos superiores.

CONCLUSÃO:
Enfisema centrolobular."""

saida = roteador.juntar_rotulos_repetidos(LAUDO)
linhas = saida.split("\n")
par = [l for l in linhas if l.startswith("Parênquima pulmonar:")]
confere("uma linha só de parênquima", len(par) == 1, saida)
confere("com as três frases, na ordem ditada, e sem a normalidade",
        par and par[0] == "Parênquima pulmonar:  bandas parenquimatosas basais. Estrias fibroatelectásicas "
        "nas bases pulmonares. Enfisema centrolobular nos lobos superiores.", par[0] if par else "")
confere("no lugar da primeira (antes da Pleura)",
        linhas.index(par[0]) < linhas.index("Pleura:  sem derrames.") if par else False)
confere("CONCLUSÃO e TÉCNICA intactas", "CONCLUSÃO:\nEnfisema centrolobular." in saida
        and "TÉCNICA:  aquisição volumétrica sem contraste." in saida)

confere("frase repetida não duplica",
        roteador.juntar_rotulos_repetidos("Parênquima pulmonar:  enfisema.\nParênquima pulmonar:  enfisema.")
        == "Parênquima pulmonar:  enfisema.")
confere("sem ANÁLISE (frases soltas): junta também",
        roteador.juntar_rotulos_repetidos("Parênquima pulmonar:  bandas basais.\nParênquima pulmonar:  enfisema.")
        == "Parênquima pulmonar:  bandas basais. Enfisema.")
# 27/09 (2): a normalidade que vem com o achado novo sai quando NEGA o que já está na linha
j = roteador.juntar_rotulos_repetidos("Parênquima pulmonar:  consolidação no lobo inferior esquerdo.\n"
                                      "Parênquima pulmonar:  atelectasias laminares. Não há consolidações ou nódulos suspeitos.")
confere("sem contradição: 'Não há consolidações' sai quando há consolidação na linha",
        j == "Parênquima pulmonar:  consolidação no lobo inferior esquerdo. Atelectasias laminares.", j)
j = roteador.juntar_rotulos_repetidos("Parênquima pulmonar:  enfisema centrolobular.\n"
                                      "Parênquima pulmonar:  atelectasias laminares. Não há consolidações ou nódulos suspeitos.")
confere("normalidade que não contradiz fica",
        j == "Parênquima pulmonar:  enfisema centrolobular. Atelectasias laminares. Não há consolidações ou nódulos suspeitos.", j)
sem_rotulo = "RADIOGRAFIA DO TÓRAX\n\nTÉCNICA:  PA e perfil.\n\nANÁLISE:\nOpacidades basais.\nSeios livres."
confere("máscara de frases diretas (sem rótulo) não muda", roteador.juntar_rotulos_repetidos(sem_rotulo) == sem_rotulo)
confere("laudo sem repetição volta idêntico", roteador.juntar_rotulos_repetidos(sem_rotulo + "\nPleura:  ok.")
        == sem_rotulo + "\nPleura:  ok.")

# 4. o que vai para a IA já chega junto
n = roteador.nuvem
visto = {}
orig = (n.config, n.chamar, roteador._aprender)
n.config = lambda: {"ativa": True, "provedor": "openai", "modelo": "gpt-5.6-terra"}
n.chamar = lambda pedido, c, **k: (visto.update(pedido=pedido) or ("ok", "nuvem"))
roteador._aprender = lambda *a, **k: None      # não grava aprendizado.json na pasta real
try:
    roteador.ia_no_texto(LAUDO)
finally:
    n.config, n.chamar, roteador._aprender = orig
confere("a IA recebe o parênquima numa linha só",
        visto.get("pedido", "").count("Parênquima pulmonar:") == 1, visto.get("pedido", "")[:300])

print()
print("juntar rótulos: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
