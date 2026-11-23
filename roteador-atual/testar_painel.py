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
dup = painel.normalizar({"versao": 4, "paginas": [{"nome": "A", "teclas": [
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

# --- migração da versão 1 (22/11): Ditar = IA; Máscara por voz; transcrição crua ---
v1 = {"versao": 1, "paginas": [{"nome": "Laudo", "teclas": [
    {"id": "l_proximo", "nome": "Próximo", "acao": "rotrix", "grupo": "laudo", "comando": "proximo"},
    {"id": "l_ditar", "nome": "Ditar", "acao": "rotrix", "grupo": "laudo", "comando": "ditar"},
    {"id": "minha", "nome": "Minha tecla", "acao": "sistema", "grupo": "sis", "comando": "mudo"}]},
    {"nome": "Expediente", "teclas": [{"id": "mascaras", "nome": "Máscaras", "acao": "rotrix", "grupo": "texto",
                                       "comando": "mascaras"}]}],
    "aparelhos": {"akp03e": {"paginas": [{"nome": "Laudo", "m": {"k1": "l_ditar", "k4": "mascaras"}}]}}}
mg = painel.normalizar(v1)
ts = {t["id"]: t for t in painel.todas_as_teclas(mg)}
confere("migração: Ditar vira o ditado com IA", ts["l_ditar"]["comando"] == "ditar_ia" and ts["l_ditar"]["nome"] == "Ditar (IA)",
        ts["l_ditar"])
confere("migração: entra Máscara por voz logo depois do Próximo",
        [t["id"] for t in mg["paginas"][0]["teclas"]][:3] == ["l_proximo", "l_mascara_voz", "l_ditar"],
        [t["id"] for t in mg["paginas"][0]["teclas"]])
confere("migração: transcrição crua vira tecla à parte", ts.get("l_cru", {}).get("comando") == "ditar")
confere("migração: a tecla dele fica", "minha" in ts)
mapa = mg["aparelhos"]["akp03e"]["perfis"][0]["paginas"][0]["m"]
confere("migração: no aparelho, a tecla de Máscaras chama a máscara por voz",
        mapa == {"k1": "l_ditar", "k4": "l_mascara_voz"}, mapa)
confere("migração: grava como versão 4", mg["versao"] == 4)
confere("migração 4: entra a tecla Apagar o laudo", (ts.get("l_apagar") or {}).get("comando") == "apagar",
        sorted(ts))
confere("migração 4: rodar de novo não duplica",
        sum(1 for t in painel.todas_as_teclas(painel.normalizar(mg)) if t["id"] == "l_apagar") == 1)

# --- versão 3: perfis no aparelho ---
v2 = {"versao": 2, "paginas": painel.padrao()["paginas"][:2] + [{"nome": "Sistema", "teclas": [
    {"id": "s_mudo", "nome": "Mudo", "acao": "sistema", "grupo": "sis", "comando": "mudo"}]}],
      "aparelhos": {"akp03e": {"brilho": 60, "auto": False, "paginas": [
          {"nome": "Minha", "app": "radiant", "m": {"k0": "mesa", "b2": "s_mudo"}},
          {"nome": "Outra", "app": "", "m": {"k1": "radiant"}}]}}}
m3 = painel.normalizar(v2)
ap = m3["aparelhos"]["akp03e"]
ts3 = {t["id"]: t for t in painel.todas_as_teclas(m3)}
confere("perfis: as páginas dele viram o perfil Principal",
        [p["nome"] for p in ap["perfis"][0]["paginas"]] == ["Minha", "Outra"] and ap["perfis"][0]["nome"] == "Principal",
        ap["perfis"][0])
confere("perfis: brilho e auto dele ficam", ap["brilho"] == 60 and ap["auto"] is False)
confere("perfis: entra um perfil Sistema", [p["nome"] for p in ap["perfis"]] == ["Principal", "Sistema"])
confere("perfis: o botão C (Mudo) passa a trocar o perfil", ap["perfis"][0]["paginas"][0]["m"]["b2"] == "d_perfil")
confere("perfis: entram as teclas de trocar perfil/página e de música",
        all(i in ts3 for i in ("d_perfil", "d_pagina", "d_pagina_ant", "s_ant", "s_prox")), sorted(ts3))
confere("perfis: o perfil Sistema só aponta para teclas que existem",
        all(v in ts3 for k, v in ap["perfis"][1]["paginas"][0]["m"].items() if k[0] != "g"))
confere("perfis: normalizar de novo não muda nada", painel.normalizar(m3) == m3)

# tela antiga (sem perfis) com o roteador novo
import tempfile
arq = os.path.join(tempfile.mkdtemp(), "painel.json")
painel.salvar(m3, arq)
tela = painel.para_tela(painel.carregar(arq))
confere("tela antiga recebe as páginas do 1º perfil", tela["aparelhos"]["akp03e"]["paginas"][0]["nome"] == "Minha")
velha = {k: v for k, v in tela.items()}
velha["aparelhos"] = {"akp03e": {"brilho": 70, "auto": True, "paginas": [{"nome": "Mudou", "app": "", "m": {"k0": "mesa"}}]}}
salvo = painel.salvar(velha, arq)["aparelhos"]["akp03e"]
confere("tela antiga salva: troca só o 1º perfil, o perfil Sistema fica",
        [p["nome"] for p in salvo["perfis"]] == ["Principal", "Sistema"] and salvo["perfis"][0]["paginas"][0]["nome"] == "Mudou"
        and salvo["brilho"] == 70, salvo)
confere("o arquivo não guarda o apelido 'paginas'", "paginas" not in painel.carregar(arq)["aparelhos"]["akp03e"])

# teclas novas
t = painel.tecla_valida({"id": "x", "nome": "X", "acao": "aparelho", "comando": "perfil_ir", "destino": "Sistema"})
confere("tecla aparelho: ir para o perfil pelo nome", t and t["destino"] == "Sistema")
confere("tecla aparelho: comando inventado sai",
        painel.tecla_valida({"id": "x", "acao": "aparelho", "comando": "explodir"}) is None)
base = painel.padrao()
base["paginas"][0]["teclas"] += [
    {"id": "mx", "nome": "Abrir tudo", "acao": "multi", "passos": ["mesa", "nao_existe", "mx", "radiant"], "espera_ms": 99999},
    {"id": "my", "nome": "Outra", "acao": "multi", "passos": ["mx", "mesa"]}]
mm = {t["id"]: t for t in painel.todas_as_teclas(painel.normalizar(base))}
confere("multiação: passo que não existe ou que é outra multiação sai",
        mm["mx"]["passos"] == ["mesa", "radiant"] and mm["my"]["passos"] == ["mesa"], (mm["mx"], mm["my"]))
confere("multiação: espera vai até 5 s", mm["mx"]["espera_ms"] == 5000)

# perfil automático (o Smart Profile)
a = {"perfis": [{"nome": "P", "app": "", "paginas": [{"nome": "1", "app": "", "m": {}}, {"nome": "W", "app": "whatsapp", "m": {}}]},
                {"nome": "RadiAnt", "app": "radiant", "paginas": [{"nome": "a", "app": "", "m": {}}, {"nome": "b", "app": "", "m": {}}]}]}
confere("automático: programa com perfil -> perfil dele, página 1",
        painel.alvo_automatico(a, (0, 0), "radiantviewer.exe") == (1, 0))
confere("automático: já no perfil, noutra página -> fica",
        painel.alvo_automatico(a, (1, 1), "radiantviewer.exe") == (1, 1))
confere("automático: página com programa dentro do perfil atual",
        painel.alvo_automatico(a, (0, 0), "whatsapp.exe") == (0, 1))
confere("automático: programa nenhum -> não mexe", painel.alvo_automatico(a, (0, 0), "notepad.exe") is None)

print("\npainel: %s" % ("tudo certo" if not falhas else "%d falha(s)" % falhas))
sys.exit(1 if falhas else 0)
