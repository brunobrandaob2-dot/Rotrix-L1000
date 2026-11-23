# -*- coding: utf-8 -*-
"""Fase 5: a IA pelo plano (Claude Code / Codex instalados), sem chave
(python testar_ia_local.py). Sem internet e sem os programas: a chamada ao
programa é simulada; confere o que seria enviado e o que volta."""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import ia_local  # noqa: E402
import nuvem  # noqa: E402

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp
nuvem.CONFIG = os.path.join(tmp, "config.json")
nuvem.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(v, None)

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("   (%r)" % (extra,)) if (extra != "" and not ok) else ""))
    if not ok:
        falhas.append(nome)


CHAMADAS = []
RESPOSTA = {"saida": "", "rc": 0, "arquivo": ""}


def _rodar_falso(args, entrada, pasta, timeout):
    CHAMADAS.append({"args": list(args), "entrada": entrada.decode("utf-8"), "pasta": pasta,
                     "sistema": open(args[args.index("--system-prompt-file") + 1], encoding="utf-8").read()
                     if "--system-prompt-file" in args else ""})
    if "--output-last-message" in args and RESPOSTA["arquivo"]:
        with open(args[args.index("--output-last-message") + 1], "w", encoding="utf-8") as f:
            f.write(RESPOSTA["arquivo"])
    return subprocess.CompletedProcess(args, RESPOSTA["rc"], RESPOSTA["saida"].encode("utf-8"), b"")


def resultado(texto, erro=False, inp=900, out=120):
    linhas = [{"type": "system", "subtype": "init", "model": "claude-sonnet-5", "tools": []},
              {"type": "result", "subtype": "success", "is_error": erro, "result": texto,
               "usage": {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": 0}}]
    return "\n".join(json.dumps(x) for x in linhas)


ia_local._rodar = _rodar_falso
ia_local.achar = lambda qual, c=None: "C:\\fake\\%s.exe" % qual if qual == "claude" else ""

# --- linha de comando: só pergunta e resposta ---
a = ia_local.args_claude("claude.exe", "sonnet", "s.txt", "low")
confere("sem ferramentas, sem MCP, sem ajustes do usuário, sem guardar sessão",
        a[a.index("--tools") + 1] == "" and "--strict-mcp-config" in a and a[a.index("--setting-sources") + 1] == ""
        and "--no-session-persistence" in a, a)
confere("modelo e esforço vão na linha", a[a.index("--model") + 1] == "sonnet" and a[a.index("--effort") + 1] == "low", a)
confere("--dangerously-skip-permissions nunca", not any("dangerously" in x for x in a))
m = json.loads(ia_local.mensagem_claude("laudo", [("image/png", "QUJD")]))
confere("imagem vai antes do texto, em base64", m["message"]["content"][0]["type"] == "image"
        and m["message"]["content"][-1] == {"type": "text", "text": "laudo"}, m)

# --- resposta ---
t, u = ia_local.ler_resultado_claude(resultado("TEXTO PRONTO"))
confere("lê o texto e os tokens do resultado", t == "TEXTO PRONTO" and u["in"] == 900 and u["out"] == 120, (t, u))
try:
    ia_local.ler_resultado_claude(resultado("Claude AI usage limit reached", erro=True))
    confere("limite do plano vira erro claro", False)
except ia_local.ErroLocal as e:
    confere("limite do plano vira erro claro", e.motivo == "limite_do_plano", e.motivo)
try:
    ia_local.ler_resultado_claude("lixo")
    confere("sem resultado vira erro", False)
except ia_local.ErroLocal as e:
    confere("sem resultado vira erro", e.motivo == "sem_resposta", e.motivo)

# --- dentro do roteador (nuvem.chamar) ---
c = {"ativa": True, "provedor": "claude_local", "modelo": "sonnet", "timeout_s": 40, "max_tokens": 1500,
     "limite_mes_usd": 5, "marcar_saida": False}
confere("aparece na lista quando o Claude Code está instalado", "claude_local" in nuvem.provedores_com_chave(c),
        nuvem.provedores_com_chave(c))
confere("o Codex não instalado não aparece", "codex_local" not in nuvem.provedores_com_chave(c))
lst = nuvem.modelos(c, "claude_local")
confere("modelos pelo plano: Sonnet, Opus, Haiku", [x["id"] for x in lst["modelos"]] == ["sonnet", "opus", "haiku"], lst)

PEDIDO = "TOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênquima pulmonar sem opacidades."
RESPOSTA["saida"] = resultado("TOMOGRAFIA DO TÓRAX\nANÁLISE:\nParênquima pulmonar sem opacidades.")
del CHAMADAS[:]
texto, origem = nuvem.chamar(PEDIDO, dict(c), modo="laudo", marcar=False, max_tokens=4000)
confere("o laudo volta pela IA do plano", origem == "nuvem" and "Parênquima" in (texto or ""), (texto, origem))
ch = CHAMADAS[-1] if CHAMADAS else {}
enviado = json.loads(ch["entrada"])["message"]["content"][-1]["text"] if ch else ""
confere("o pedido vai pela entrada, não pela linha de comando",
        "Parênquima pulmonar sem opacidades" in enviado and not any("Parênquima" in x for x in ch["args"]), enviado[:200])
confere("o texto de sistema é o mesmo da API (arquivo temporário)", ch and len(ch["sistema"]) > 200)
confere("sem raciocínio pedido -> esforço low (o mais rápido)", ch and ch["args"][ch["args"].index("--effort") + 1] == "low")
confere("a pasta temporária é apagada", ch and not os.path.exists(ch["pasta"]))
rec = nuvem.ultima_desta_chamada() or nuvem.ULTIMA
confere("custo zero (é do plano) e o recibo diz qual IA", rec.get("usd") == 0 and "claude_local" in rec.get("modelo", ""), rec)
confere("o gasto do mês não sobe", nuvem.gasto_ler()["usd"] == 0, nuvem.gasto_ler())

# a triagem de dados do paciente vale igual
del CHAMADAS[:]
texto, origem = nuvem.chamar("Paciente: JOSE DA SILVA SANTOS\nCPF 123.456.789-00\nTC de tórax normal.", dict(c),
                             modo="laudo", marcar=False)
confere("com nome/CPF do paciente: não chama o programa", origem == "nuvem_bloqueada" and not CHAMADAS, origem)

# erro do plano chega como erro, sem derrubar nada
RESPOSTA["saida"] = resultado("usage limit reached", erro=True)
texto, origem = nuvem.chamar(PEDIDO, dict(c), modo="laudo", marcar=False)
confere("limite do plano: volta erro, não texto", texto is None and origem == "nuvem_erro_local_limite_do_plano", origem)

# Codex (simulado)
ia_local.achar = lambda qual, c=None: "C:\\fake\\%s.exe" % qual
RESPOSTA["arquivo"] = "LAUDO DO CODEX"
del CHAMADAS[:]
texto, origem = nuvem.chamar(PEDIDO, dict(c, provedor="codex_local", modelo="padrao"), modo="laudo", marcar=False)
ch = CHAMADAS[-1] if CHAMADAS else {}
confere("Codex: resposta do --output-last-message", texto == "LAUDO DO CODEX" and origem == "nuvem", (texto, origem))
confere("Codex: somente leitura e pedido pela entrada", ch and "read-only" in ch["args"] and ch["args"][-1] == "-"
        and PEDIDO in ch["entrada"], ch.get("args"))

print("\nia local: %s" % ("tudo certo" if not falhas else "%d falha(s)" % len(falhas)))
sys.exit(1 if falhas else 0)
