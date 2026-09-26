# -*- coding: utf-8 -*-
"""A lista de modelos diz QUANDO o provedor do config não respondeu.

    python testar_ia_modelos.py

26/09 (tarde): ele pôs a chave da OpenAI, trocou para OpenAI, e o laudo foi
para o Claude Opus. A lista da OpenAI não respondia e a tela não sabia: pegava
o mais forte que existisse, de outro provedor. A tela agora avisa e não troca de
provedor sozinha (modelos.ts) — e para isso o roteador tem de DIZER a falha:
  1. provedor sem resposta e sem lista guardada -> falhas[provedor] = motivo
  2. provedor sem resposta, mas com lista antiga guardada -> a lista aparece,
     e falhas[provedor] diz que é antiga (senão a falha fica escondida)
  3. os modelos dos outros provedores vêm prefixados ("anthropic:...")
Sem rede e sem tocar no config.json de verdade.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roteador  # noqa: E402

n = roteador.nuvem
falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (" + extra + ")") if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


CONFIG = {"provedor": "openai", "modelo": "gpt-5.6-terra", "modelos_vistos": {}}
guardado = {}


def falso_modelos(c=None, nome=None, timeout=12):
    if nome == "openai":
        return {"ok": False, "motivo": "http_401", "provedor": "openai", "modelos": []}
    return {"ok": True, "provedor": nome, "modelos": [
        {"id": "claude-opus-5-5", "nome": "Opus 5.5"}, {"id": "claude-haiku-4-5", "nome": "Haiku"}]}


orig = (n.config, n.provedores_com_chave, n.modelos, n.gravar_config)
n.config = lambda: dict(CONFIG)
n.provedores_com_chave = lambda c=None: ["openai", "anthropic"]
n.modelos = falso_modelos
n.gravar_config = lambda d: guardado.update(d)
try:
    r = roteador.ia_modelos()
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("OpenAI sem resposta e sem lista guardada: a falha vem no resultado",
            (r.get("falhas") or {}).get("openai") == "http_401", repr(r.get("falhas")))
    confere("os da Anthropic vêm prefixados (não se passam pelo provedor do config)",
            ids and all(i.startswith("anthropic:") for i in ids), repr(ids))
    confere("o provedor do config continua sendo a OpenAI", r.get("provedor") == "openai")

    CONFIG["modelos_vistos"] = {"openai": [{"id": "gpt-5.6-terra", "nome": "Terra"}]}
    r = roteador.ia_modelos()
    ids = [m["id"] for m in r.get("modelos", [])]
    confere("com lista antiga guardada, o modelo aparece...", "gpt-5.6-terra" in ids, repr(ids))
    confere("...mas a falha NÃO fica escondida",
            "lista antiga" in str((r.get("falhas") or {}).get("openai", "")), repr(r.get("falhas")))
finally:
    n.config, n.provedores_com_chave, n.modelos, n.gravar_config = orig

print()
print("lista de modelos: %s" % ("tudo certo" if not falhas else "%d FALHA(S)" % len(falhas)))
sys.exit(1 if falhas else 0)
