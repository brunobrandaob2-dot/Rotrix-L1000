# -*- coding: utf-8 -*-
"""Painel do Rotrix v2 (22/11/2026): a parte que não depende do Windows.

Layouts do Snap, posição -> retângulo, "usar a posição de agora", limpeza das
teclas, montagem dos comandos e gravação do painel.json. Não abre programa,
não mexe em janela e não escreve na pasta do roteador (usa pasta temporária).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import painel  # noqa: E402

falhas = 0


def confere(nome, ok, detalhe=""):
    global falhas
    print(("ok     " if ok else "FALHA  ") + nome + ("" if ok else "  -> %r" % (detalhe,)))
    if not ok:
        falhas += 1


MON = [{"device": r"\\.\DISPLAY1", "x": 0, "y": 0, "w": 3840, "h": 2160, "wx": 0, "wy": 0, "ww": 3840, "wh": 2088},
       {"device": r"\\.\DISPLAY2", "x": 3840, "y": 0, "w": 1920, "h": 1080, "wx": 3840, "wy": 0, "ww": 1920, "wh": 1032}]

# --- layout -----------------------------------------------------------------
r = painel.retangulo({"display": r"\\.\DISPLAY1|3840x2160", "layout": "quad", "zone": 3}, MON)
confere("canto inferior direito do 4K", r == {"x": 1920, "y": 1044, "w": 1920, "h": 1044}, r)
r = painel.retangulo({"display": r"\\.\DISPLAY9|1920x1080", "layout": "full", "zone": 0}, MON)
confere("monitor renomeado: acha pela resolução", r == {"x": 3840, "y": 0, "w": 1920, "h": 1032}, r)
confere("monitor que não existe -> None",
        painel.retangulo({"display": r"\\.\DISPLAY5|1280x720", "layout": "full", "zone": 0}, MON) is None)
confere("zona inválida -> None", painel.lugar_valido({"display": "x|1x1", "layout": "quad", "zone": 7}) is None)
confere("descrever", painel.descrever({"display": r"\\.\DISPLAY1|3840x2160", "layout": "thirds", "zone": 1}, MON)
        == "4K · terço do meio")
confere("nomes dos monitores", [painel.nome_do_monitor(m) for m in MON] == ["4K", "1080p"])
g = painel.adivinhar_lugar({"x": 1925, "y": 0, "w": 1910, "h": 1040, "max": False}, MON)
confere("posição de agora: canto superior direito", g and g["layout"] == "quad" and g["zone"] == 1, g)
g = painel.adivinhar_lugar({"x": 3830, "y": -8, "w": 1940, "h": 1050, "max": True}, MON)
confere("maximizada vira tela inteira do monitor dela", g == {"display": r"\\.\DISPLAY2|1920x1080", "layout": "full", "zone": 0}, g)
g = painel.adivinhar_lugar({"x": 100, "y": 100, "w": 300, "h": 200, "max": False}, MON)
confere("janela pequena solta não vira zona", g is None, g)

# --- teclas -----------------------------------------------------------------
cfg = painel.normalizar(None)
nomes = [p["nome"] for p in cfg["paginas"]]
confere("páginas padrão", nomes == ["Expediente", "Laudo", "Sistema"], nomes)
ids = [k["id"] for k in painel.todas_as_teclas(cfg)]
confere("ids únicos", len(ids) == len(set(ids)), ids)
confere("expediente traz os programas do Hub",
        {"mesa", "radiowant", "onelaudos", "claude"} <= {k["id"] for k in painel.todas_as_teclas(cfg) if k.get("expediente")})
confere("tecla sem ação conhecida é descartada", painel.tecla_valida({"id": "x", "acao": "formatar_hd"}) is None)
confere("programa sem alvo é descartado", painel.tecla_valida({"id": "x", "acao": "programa", "tipo": "exe"}) is None)
confere("atalho inválido é descartado", painel.tecla_valida({"id": "x", "acao": "atalho", "teclas": "Ctrl+Ç+rm -rf"}) is None)
confere("atalho válido passa", (painel.tecla_valida({"id": "x", "acao": "atalho", "teclas": "Ctrl+Shift+V"}) or {}).get("teclas") == "Ctrl+Shift+V")
k = painel.tecla_valida({"id": "s", "acao": "site", "sites": ["exemplo.com", " ", "http://a.b"]})
confere("site sem https ganha https; vazio sai", k and k["sites"] == ["https://exemplo.com", "http://a.b"], k)
dup = painel.normalizar({"paginas": [{"nome": "A", "teclas": [
    {"id": "a", "acao": "sistema", "comando": "mudo", "atalho_global": "F13"},
    {"id": "b", "acao": "sistema", "comando": "musica", "atalho_global": "F13"},
    {"id": "a", "acao": "sistema", "comando": "bloquear"}]}]})
t = dup["paginas"][0]["teclas"]
confere("id repetido sai; atalho global repetido fica só no primeiro",
        [x["id"] for x in t] == ["a", "b"] and t[0]["atalho_global"] == "F13" and t[1]["atalho_global"] == "", t)
confere("ajuste maluco volta ao padrão", painel.normalizar({"ajustes": {"navegador": "netscape", "atraso_s": 999}})["ajustes"]
        ["navegador"] == "padrao")

# --- comandos (montados, nunca executados aqui) --------------------------------
aj = cfg["ajustes"]
c = painel.montar_comando({"acao": "programa", "tipo": "powershell", "alvo": r"C:\x\Laudo.ps1", "args": ["-STA"]}, aj)
confere("script .ps1 roda escondido com -File", c["args"][-2:] == ["-File", r"C:\x\Laudo.ps1"] and c["oculto"]
        and c["args"][0] == "-STA", c)
c = painel.montar_comando({"acao": "programa", "tipo": "appx", "alvo": "Claude_x!Claude"}, aj)
confere("app da Loja pelo shell:AppsFolder", c["exe"] == "explorer.exe" and c["args"] == ["shell:AppsFolder\\Claude_x!Claude"], c)
c = painel.montar_comando({"acao": "site", "sites": ["https://a.b"], "navegador": "", "perfil": ""},
                          {"navegador": "padrao", "navegador_exe": "", "perfil": ""})
confere("site no navegador padrão do Windows", c == {"abrir_padrao": ["https://a.b"]}, c)

# --- gravar e ler (pasta temporária) -------------------------------------------
pasta = tempfile.mkdtemp(prefix="painel_")
arq = os.path.join(pasta, "painel.json")
cfg["paginas"][0]["teclas"][0]["nome"] = "Começar o dia"
salvo = painel.salvar(cfg, arq)
lido = painel.carregar(arq)
confere("grava e lê de volta (com acento)", lido["paginas"][0]["teclas"][0]["nome"] == "Começar o dia", lido["paginas"][0]["teclas"][0])
open(arq, "w", encoding="utf-8").write("{quebrado")
confere("arquivo quebrado -> painel padrão", painel.carregar(arq)["paginas"][0]["nome"] == "Expediente")
confere("nenhum .tmp sobrando", not [f for f in os.listdir(pasta) if f.endswith(".tmp")], os.listdir(pasta))

print("\npainel: %s" % ("tudo certo" if not falhas else "%d falha(s)" % falhas))
sys.exit(1 if falhas else 0)
