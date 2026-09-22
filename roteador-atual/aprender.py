# -*- coding: utf-8 -*-
"""Revisa as correções que a nuvem fez e o local deixou passar.
Cada par aprovado vira uma regra MAP do processador de colagem — vale nos dois
atalhos, sem internet e sem custo, a partir da próxima colagem."""
import json, os, sys, io, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.join(AQUI, "aprendizado.json")
MAPA = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "handy_radiology_map.tsv")

if not os.path.exists(ARQ):
    print("\n  Nada para revisar ainda. As sugestões aparecem depois que você usar")
    print("  \"revisar ...\" e a nuvem corrigir alguma palavra.\n"); sys.exit(0)
d = json.load(open(ARQ, encoding="utf-8"))
pend = sorted(d.get("pendentes", {}).items(), key=lambda kv: -kv[1])
if not pend:
    print("\n  Nenhuma sugestão pendente.\n"); sys.exit(0)

print("\n  %d correção(ões) sugerida(s), da mais frequente para a menos.\n" % len(pend))
print("  s = aprovar   n = rejeitar (não pergunta mais)   Enter = decidir depois   q = sair\n")
novas = []
for k, n in pend:
    errado, certo = k.split("\t")
    r = input("   %3dx   %-28s ->  %-28s  [s/n/Enter/q] " % (n, errado, certo)).strip().lower()
    if r == "q":
        break
    if r == "s":
        novas.append((errado, certo)); d["aprovados"].append(k); del d["pendentes"][k]
    elif r == "n":
        d["rejeitados"].append(k); del d["pendentes"][k]

if novas:
    existe = os.path.exists(MAPA)
    with io.open(MAPA, "a", encoding="utf-8") as f:
        f.write("\n# aprendidas em %s\n" % datetime.date.today().isoformat())
        for e, c in novas:
            f.write("MAP\t%s\t%s\n" % (e, c))
    print("\n  %d regra(s) acrescentada(s) ao processador de colagem." % len(novas))
    if not existe:
        print("  (arquivo de regras criado em %s)" % MAPA)
json.dump(d, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  Pendentes restantes: %d\n" % len(d["pendentes"]))
