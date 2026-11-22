# -*- coding: utf-8 -*-
"""Painel do Rotrix v2 (22/11/2026): o Workflow Hub dentro do Rotrix.

"Eu acho que o Rotrix já abriria junto com o Windows e não precisaria ter mais
um aplicativo." Aqui mora o que o Hub fazia, agora a serviço da aba Painel:

  - as teclas (páginas, nome, cor, ação), gravadas em painel.json
  - abrir um programa / site / script / app da Loja, ou trazer para a frente
    a janela dele, se já estiver aberto
  - Iniciar expediente: abre os programas marcados e põe cada janela no seu
    lugar nos monitores (modelos do Snap do Windows)
  - Organizar janelas e "Usar a posição de agora"
  - ações de sistema: volume, mudo, música, bloquear a tela, atalho de
    teclado e texto pronto (colados na janela em que você estava)

A parte de janelas fala com o Windows pelo ctypes (user32/dwmapi/kernel32),
sem nada para instalar. Fora do Windows (o CI), só a parte pura funciona —
é ela que testar_painel.py confere.

Nada de paciente passa por aqui: só nomes de programas, títulos de janela e
posições.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

EH_WINDOWS = sys.platform == "win32"
# 2 (22/11): "Ditar" = o ditado com IA (3º botão da folha); "Máscara por voz" =
# o 2º botão; a transcrição crua (1º botão) vira tecla à parte.
VERSAO = 2

# ---------------------------------------------------------------------------
# Modelos de layout (os do Snap do Windows 11, iguais aos do Workflow Hub).
# Cada zona é uma fração da área útil do monitor: [x, y, largura, altura].
# ---------------------------------------------------------------------------
_T = 1.0 / 3
MODELOS = [
    ("full", "Tela inteira", [((0, 0, 1, 1), "tela inteira")]),
    ("halves", "Metades", [((0, 0, .5, 1), "metade esquerda"), ((.5, 0, .5, 1), "metade direita")]),
    ("wide-left", "2/3 + 1/3", [((0, 0, 2 * _T, 1), "2/3 à esquerda"), ((2 * _T, 0, _T, 1), "1/3 à direita")]),
    ("wide-right", "1/3 + 2/3", [((0, 0, _T, 1), "1/3 à esquerda"), ((_T, 0, 2 * _T, 1), "2/3 à direita")]),
    ("half-stack-right", "Metade + 2 empilhadas", [((0, 0, .5, 1), "metade esquerda"),
                                                   ((.5, 0, .5, .5), "quarto superior direito"),
                                                   ((.5, .5, .5, .5), "quarto inferior direito")]),
    ("stack-left-half", "2 empilhadas + metade", [((0, 0, .5, .5), "quarto superior esquerdo"),
                                                  ((0, .5, .5, .5), "quarto inferior esquerdo"),
                                                  ((.5, 0, .5, 1), "metade direita")]),
    ("quad", "Quatro cantos", [((0, 0, .5, .5), "canto superior esquerdo"), ((.5, 0, .5, .5), "canto superior direito"),
                               ((0, .5, .5, .5), "canto inferior esquerdo"), ((.5, .5, .5, .5), "canto inferior direito")]),
    ("thirds", "Terços", [((0, 0, _T, 1), "terço esquerdo"), ((_T, 0, _T, 1), "terço do meio"),
                          ((2 * _T, 0, _T, 1), "terço direito")]),
    ("center-wide", "1/4 + 1/2 + 1/4", [((0, 0, .25, 1), "faixa esquerda"), ((.25, 0, .5, 1), "centro"),
                                        ((.75, 0, .25, 1), "faixa direita")]),
    ("rows", "Em cima + embaixo", [((0, 0, 1, .5), "metade de cima"), ((0, .5, 1, .5), "metade de baixo")]),
    ("six", "Seis partes", [((0, 0, _T, .5), "superior esquerdo"), ((_T, 0, _T, .5), "superior do meio"),
                            ((2 * _T, 0, _T, .5), "superior direito"), ((0, .5, _T, .5), "inferior esquerdo"),
                            ((_T, .5, _T, .5), "inferior do meio"), ((2 * _T, .5, _T, .5), "inferior direito")]),
]
_MODELO = {m[0]: m for m in MODELOS}


def nome_do_monitor(m):
    w, h = max(m["w"], m["h"]), min(m["w"], m["h"])
    if w >= 3800:
        return "4K"
    if w >= 3400 and h <= 1600:
        return "Ultrawide"
    if w >= 2500:
        return "2.5K"
    if w >= 1900 and h >= 1060:
        return "1080p"
    if w >= 1600:
        return "900p"
    return "%dx%d" % (m["w"], m["h"])


def id_do_monitor(m):
    return "%s|%dx%d" % (m["device"], m["w"], m["h"])


def achar_monitor(display, monitores):
    if not display or not monitores:
        return None
    for m in monitores:
        if id_do_monitor(m) == display:
            return m
    device, _, res = str(display).partition("|")
    for m in monitores:
        if "%dx%d" % (m["w"], m["h"]) == res:
            return m
    for m in monitores:
        if m["device"] == device:
            return m
    return None


def lugar_valido(p):
    if not isinstance(p, dict):
        return None
    mod = _MODELO.get(str(p.get("layout")))
    try:
        zona = int(p.get("zone"))
    except (TypeError, ValueError):
        return None
    if not mod or not (0 <= zona < len(mod[2])) or not p.get("display"):
        return None
    return {"display": str(p["display"]), "layout": mod[0], "zone": zona}


def retangulo(lugar, monitores):
    """Retângulo em pixels reais (área útil, sem a barra de tarefas), ou None."""
    lugar = lugar_valido(lugar)
    if not lugar:
        return None
    m = achar_monitor(lugar["display"], monitores)
    if not m:
        return None
    fx, fy, fw, fh = _MODELO[lugar["layout"]][2][lugar["zone"]][0]
    x = round(m["wx"] + fx * m["ww"])
    y = round(m["wy"] + fy * m["wh"])
    return {"x": x, "y": y, "w": round(m["wx"] + (fx + fw) * m["ww"]) - x,
            "h": round(m["wy"] + (fy + fh) * m["wh"]) - y}


def descrever(lugar, monitores):
    lugar = lugar_valido(lugar)
    if not lugar:
        return ""
    m = achar_monitor(lugar["display"], monitores)
    tela = nome_do_monitor(m) if m else "monitor %s (desligado)" % lugar["display"].partition("|")[2]
    return "%s · %s" % (tela, _MODELO[lugar["layout"]][2][lugar["zone"]][1])


def adivinhar_lugar(win, monitores):
    """A zona mais parecida com onde a janela está agora (maior sobreposição)."""
    if not monitores:
        return None
    cx, cy = win["x"] + win["w"] / 2.0, win["y"] + win["h"] / 2.0
    m = next((mm for mm in monitores
              if mm["x"] <= cx < mm["x"] + mm["w"] and mm["y"] <= cy < mm["y"] + mm["h"]), None)
    if m is None:
        m = min(monitores, key=lambda mm: (cx - mm["x"] - mm["w"] / 2.0) ** 2 + (cy - mm["y"] - mm["h"] / 2.0) ** 2)
    display = id_do_monitor(m)
    if win.get("max"):
        return {"display": display, "layout": "full", "zone": 0}
    ordem = ["full", "halves", "quad", "wide-left", "wide-right", "thirds", "rows",
             "half-stack-right", "stack-left-half", "center-wide", "six"]
    melhor = None
    for mid in ordem:
        for zona in range(len(_MODELO[mid][2])):
            r = retangulo({"display": display, "layout": mid, "zone": zona}, [m])
            ix = max(0, min(r["x"] + r["w"], win["x"] + win["w"]) - max(r["x"], win["x"]))
            iy = max(0, min(r["y"] + r["h"], win["y"] + win["h"]) - max(r["y"], win["y"]))
            inter = ix * iy
            uniao = r["w"] * r["h"] + win["w"] * win["h"] - inter
            iou = inter / uniao if uniao > 0 else 0
            if melhor is None or iou > melhor[0] + 0.001:
                melhor = (iou, {"display": display, "layout": mid, "zone": zona})
    return melhor[1] if melhor and melhor[0] > 0.45 else None


# ---------------------------------------------------------------------------
# Teclas e o arquivo painel.json
# ---------------------------------------------------------------------------
# Cores por grupo (a tela desenha): laudo, ia, texto, app, jan, sis.
GRUPOS = ("laudo", "ia", "texto", "app", "jan", "sis")
# o que cada tecla faz
ACOES = ("programa", "site", "rotrix", "sistema", "atalho", "texto", "expediente", "organizar")
TIPOS_PROGRAMA = ("exe", "powershell", "appx")
COMANDOS_ROTRIX = ("proximo", "abrir_marcados", "fila", "colar", "ditar", "ditar_ia", "ditar_mascara",
                   "conferencia",
                   "revisar", "analisar_rx", "coronarias", "laudo", "fila_aba", "mascaras")
COMANDOS_SISTEMA = ("volume_mais", "volume_menos", "mudo", "musica", "proxima_musica",
                    "musica_anterior", "bloquear")
NAVEGADORES = ("padrao", "chrome", "edge", "brave", "firefox", "opera")

# Monitores deste PC quando o Hub foi montado (só para o layout inicial)
_4K, _25K, _1080 = "\\\\.\\DISPLAY1|3840x2160", "\\\\.\\DISPLAY3|2560x1600", "\\\\.\\DISPLAY2|1920x1080"


def _em(display, layout, zona):
    return {"display": display, "layout": layout, "zone": zona}


def _tecla(id_, nome, acao, grupo, icone, **extra):
    t = {"id": id_, "nome": nome, "acao": acao, "grupo": grupo, "icone": icone}
    t.update(extra)
    return t


def padrao():
    """As teclas iniciais: os programas e lugares do Workflow Hub + o Rotrix."""
    progs = [
        _tecla("mesa", "Mesa de Laudo", "programa", "app", "table", tipo="powershell",
               alvo=r"%USERPROFILE%\Documents\Mesa de Laudo\Laudo.ps1", args=["-STA"],
               titulo="Mesa de Laudo", expediente=True, lugar=_em(_4K, "quad", 2)),
        _tecla("radius", "Radius", "programa", "app", "download", tipo="powershell",
               alvo=r"%LOCALAPPDATA%\Radius Download Queue\RadiusQueue.ps1", titulo="Radius",
               expediente=True, lugar=_em(_4K, "quad", 0)),
        _tecla("radiowant", "RadioWant", "programa", "app", "image", tipo="exe",
               alvo=r"%LOCALAPPDATA%\Programs\RadioWant\RadioWant.exe", expediente=True,
               lugar=_em(_1080, "full", 0)),
        _tecla("radiant", "RadiAnt", "programa", "app", "sun", tipo="exe",
               alvo=r"%ProgramFiles%\RadiAntViewer64bit\RadiAntViewer.exe", expediente=False,
               lugar=_em(_1080, "full", 0)),
        _tecla("onelaudos", "OneLaudos", "site", "app", "globe",
               sites=["https://onelaudos.mobilemed.com.br/exames"], titulo="Telerradiologia",
               expediente=True, lugar=_em(_25K, "full", 0)),
        _tecla("claude", "Claude", "programa", "app", "bot", tipo="appx",
               alvo="Claude_pzs8sxrjxfjjc!Claude", detectar=r"WindowsApps\Claude_",
               expediente=True, lugar=_em(_4K, "quad", 1)),
        _tecla("whatsapp", "WhatsApp", "programa", "app", "chat", tipo="appx",
               alvo="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", detectar="WhatsApp", expediente=False),
        _tecla("rotrix", "Rotrix", "programa", "app", "rotrix", tipo="exe",
               alvo=r"%LOCALAPPDATA%\Rotrix L-1000\rotrix.exe", expediente=False,
               lugar=_em(_4K, "quad", 3)),
    ]
    # o RadioWant de desenvolvimento, se for o que existe neste PC
    rw_anotado = os.path.expandvars(r"%LOCALAPPDATA%\Radius Download Queue\radiowant-path.txt")
    try:
        if os.path.isfile(rw_anotado):
            c = open(rw_anotado, encoding="utf-8-sig").readline().strip()
            if c and os.path.isfile(c):
                progs[2]["alvo"] = c
    except OSError:
        pass
    expediente = [_tecla("expediente", "Iniciar expediente", "expediente", "jan", "play", larga=True),
                  _tecla("organizar", "Organizar janelas", "organizar", "jan", "grid"),
                  _tecla("mascaras", "Máscaras", "rotrix", "texto", "file", comando="mascaras")] + progs
    laudo = [
        _tecla("l_proximo", "Próximo da fila", "rotrix", "laudo", "next", comando="proximo"),
        _tecla("l_mascara_voz", "Máscara por voz", "rotrix", "texto", "file", comando="ditar_mascara"),
        _tecla("l_ditar", "Ditar (IA)", "rotrix", "ia", "mic", comando="ditar_ia"),
        _tecla("l_colar", "Colar no RIS", "rotrix", "laudo", "clip", comando="colar"),
        _tecla("l_cru", "Transcrição crua", "rotrix", "sis", "type", comando="ditar"),
        _tecla("l_conf", "Conferência", "rotrix", "laudo", "check", comando="conferencia"),
        _tecla("l_revisar", "Revisar", "rotrix", "ia", "spark", comando="revisar"),
        _tecla("l_rx", "Analisar RX", "rotrix", "ia", "scan", comando="analisar_rx"),
        _tecla("l_coro", "Coronárias", "rotrix", "laudo", "layers", comando="coronarias"),
        _tecla("l_fila", "Mostrar / esconder fila", "rotrix", "laudo", "list", comando="fila"),
    ]
    sistema = [
        _tecla("s_vmais", "Volume +", "sistema", "sis", "vol", comando="volume_mais"),
        _tecla("s_vmenos", "Volume −", "sistema", "sis", "vol", comando="volume_menos"),
        _tecla("s_mudo", "Mudo", "sistema", "sis", "mute", comando="mudo"),
        _tecla("s_musica", "Música ▶ ❚❚", "sistema", "sis", "media", comando="musica"),
        _tecla("s_bloq", "Bloquear a tela", "sistema", "sis", "lock", comando="bloquear"),
    ]
    return {
        "versao": VERSAO,
        "ajustes": {"navegador": "padrao", "navegador_exe": "", "perfil": "",
                    "iniciar_expediente": False, "atraso_s": 5, "organizar_ao_iniciar": True},
        "paginas": [{"nome": "Expediente", "teclas": expediente},
                    {"nome": "Laudo", "teclas": laudo},
                    {"nome": "Sistema", "teclas": sistema}],
        "aparelhos": aparelhos_padrao(),
    }


# ---------------------------------------------------------------------------
# Fase 3: o que cada tecla / botão / giratório do aparelho físico faz.
# aparelhos[modelo] = {"brilho", "auto", "paginas": [{"nome", "app", "m": {slot: ...}}]}
#   "kN" / "bN": id de uma tecla do Painel
#   "gN": {"girar": GIRO, "clique": id de tecla}
# "app": parte do nome do programa da frente (ex.: "radiant") -> a página troca sozinha
# ---------------------------------------------------------------------------
GIROS = ("volume", "pagina", "rolar", "zoom", "brilho")


def aparelhos_padrao():
    return {"akp03e": {"brilho": 80, "auto": True, "paginas": [
        {"nome": "Laudo", "app": "", "m": {
            "k0": "l_proximo", "k1": "l_mascara_voz", "k2": "l_ditar", "k3": "l_revisar", "k4": "l_colar",
            "k5": "mesa", "b0": "expediente", "b1": "organizar", "b2": "s_mudo",
            "g0": {"girar": "rolar", "clique": "l_proximo"}, "g1": {"girar": "pagina", "clique": "l_conf"},
            "g2": {"girar": "volume", "clique": "s_mudo"}}},
        {"nome": "Programas", "app": "", "m": {
            "k0": "radiowant", "k1": "radiant", "k2": "mesa", "k3": "onelaudos", "k4": "claude",
            "k5": "whatsapp", "b0": "expediente", "b1": "organizar", "b2": "s_mudo",
            "g0": {"girar": "rolar", "clique": "l_proximo"}, "g1": {"girar": "pagina", "clique": "l_conf"},
            "g2": {"girar": "volume", "clique": "s_mudo"}}},
    ]}}


def _aparelho_valido(a, ids):
    if not isinstance(a, dict):
        return None
    try:
        brilho = max(5, min(100, int(a.get("brilho", 80))))
    except (TypeError, ValueError):
        brilho = 80
    paginas = []
    for p in (a.get("paginas") or [])[:20]:
        if not isinstance(p, dict):
            continue
        m = {}
        for slot, v in (p.get("m") or {}).items():
            if not re.match(r"^[kb]\d{1,2}$|^g\d$", str(slot)):
                continue
            if slot.startswith("g"):
                if isinstance(v, dict):
                    g = {"girar": v.get("girar") if v.get("girar") in GIROS else "",
                         "clique": v.get("clique") if v.get("clique") in ids else ""}
                    if g["girar"] or g["clique"]:
                        m[slot] = g
            elif v in ids:
                m[slot] = v
        paginas.append({"nome": _texto(p.get("nome") or "Página", 24), "app": _texto(p.get("app"), 60).lower(),
                        "m": m})
    if not paginas:
        paginas = [{"nome": "Página 1", "app": "", "m": {}}]
    return {"brilho": brilho, "auto": bool(a.get("auto", True)), "paginas": paginas}


_ATALHO = re.compile(r"^((Ctrl|Alt|Shift|Win)\+)*([A-Z0-9]|F([1-9]|1[0-9]|2[0-4])|"
                     r"Enter|Tab|Esc|Espaço|Space|Home|End|PgUp|PgDn|Up|Down|Left|Right|Delete|Backspace)$")


def _texto(v, n=200):
    return str(v or "")[:n]


def tecla_valida(t):
    """Limpa uma tecla vinda da tela ou do disco. None = descartar."""
    if not isinstance(t, dict) or not t.get("id") or t.get("acao") not in ACOES:
        return None
    k = {"id": _texto(t["id"], 60), "nome": _texto(t.get("nome") or t["id"], 40),
         "acao": t["acao"], "grupo": t.get("grupo") if t.get("grupo") in GRUPOS else "sis",
         "icone": _texto(t.get("icone"), 30), "larga": bool(t.get("larga")),
         "atalho_global": _texto(t.get("atalho_global"), 40)}
    a = k["acao"]
    if a == "programa":
        if t.get("tipo") not in TIPOS_PROGRAMA or not t.get("alvo"):
            return None
        k.update(tipo=t["tipo"], alvo=_texto(t["alvo"], 400),
                 args=[_texto(x, 200) for x in (t.get("args") or []) if x][:10],
                 detectar=_texto(t.get("detectar"), 200), titulo=_texto(t.get("titulo"), 120),
                 expediente=bool(t.get("expediente")), lugar=lugar_valido(t.get("lugar")))
    elif a == "site":
        sites = [s.strip() for s in (t.get("sites") or []) if isinstance(s, str) and s.strip()][:12]
        sites = [s if re.match(r"^[a-z][a-z0-9+.-]*:", s, re.I) else "https://" + s for s in sites]
        if not sites:
            return None
        nav = t.get("navegador") if t.get("navegador") in NAVEGADORES else ""
        k.update(sites=sites, navegador=nav, perfil=_texto(t.get("perfil"), 60),
                 titulo=_texto(t.get("titulo"), 120), expediente=bool(t.get("expediente")),
                 lugar=lugar_valido(t.get("lugar")))
    elif a == "rotrix":
        if t.get("comando") not in COMANDOS_ROTRIX:
            return None
        k["comando"] = t["comando"]
    elif a == "sistema":
        if t.get("comando") not in COMANDOS_SISTEMA:
            return None
        k["comando"] = t["comando"]
    elif a == "atalho":
        tec = _texto(t.get("teclas"), 40).strip()
        if not _ATALHO.match(tec):
            return None
        k["teclas"] = tec
    elif a == "texto":
        k["texto"] = _texto(t.get("texto"), 4000)
        if not k["texto"].strip():
            return None
    return k


def _migrar_para_2(cru):
    """Painel salvo na versão 1: "Ditar" vira o ditado com IA, entram "Máscara por
    voz" e "Transcrição crua", e no aparelho a tecla que abria a aba Máscaras
    passa a chamar a máscara por voz. O resto do que ele montou fica igual."""
    import copy
    cru = copy.deepcopy(cru)
    paginas = cru.get("paginas") if isinstance(cru.get("paginas"), list) else []
    ids = {t.get("id") for p in paginas if isinstance(p, dict) for t in (p.get("teclas") or []) if isinstance(t, dict)}
    for p in paginas:
        if not isinstance(p, dict):
            continue
        teclas = p.get("teclas") or []
        for t in teclas:
            if isinstance(t, dict) and t.get("id") == "l_ditar" and t.get("comando") == "ditar":
                t.update(comando="ditar_ia", grupo="ia")
                if t.get("nome") in ("Ditar", "", None):
                    t["nome"] = "Ditar (IA)"
        if any(isinstance(t, dict) and t.get("id") == "l_proximo" for t in teclas):
            pos = next(i for i, t in enumerate(teclas) if isinstance(t, dict) and t.get("id") == "l_proximo") + 1
            if "l_mascara_voz" not in ids:
                teclas.insert(pos, _tecla("l_mascara_voz", "Máscara por voz", "rotrix", "texto", "file",
                                          comando="ditar_mascara"))
                ids.add("l_mascara_voz")
            if "l_cru" not in ids:
                teclas.append(_tecla("l_cru", "Transcrição crua", "rotrix", "sis", "type", comando="ditar"))
                ids.add("l_cru")
    ap = cru.get("aparelhos")
    if isinstance(ap, dict) and isinstance(ap.get("akp03e"), dict):
        for pg in ap["akp03e"].get("paginas") or []:
            m = pg.get("m") if isinstance(pg, dict) else None
            if isinstance(m, dict) and m.get("k4") == "mascaras" and "l_mascara_voz" in ids:
                m["k4"] = "l_mascara_voz"
    return cru


def normalizar(cru):
    base = padrao()
    if not isinstance(cru, dict):
        cru = {}
    elif cru.get("paginas"):
        try:
            versao = int(cru.get("versao") or 1)
        except (TypeError, ValueError):
            versao = 1
        if versao < 2:
            cru = _migrar_para_2(cru)
    aj = dict(base["ajustes"])
    if isinstance(cru.get("ajustes"), dict):
        aj.update({k: v for k, v in cru["ajustes"].items() if k in aj})
    aj["navegador"] = aj["navegador"] if aj["navegador"] in NAVEGADORES else "padrao"
    aj["navegador_exe"] = _texto(aj["navegador_exe"], 400)
    aj["perfil"] = _texto(aj["perfil"], 60)
    aj["iniciar_expediente"] = bool(aj["iniciar_expediente"])
    aj["organizar_ao_iniciar"] = bool(aj["organizar_ao_iniciar"])
    try:
        aj["atraso_s"] = max(0, min(60, int(aj["atraso_s"])))
    except (TypeError, ValueError):
        aj["atraso_s"] = 5
    paginas, vistos = [], set()
    for p in cru.get("paginas") or base["paginas"]:
        if not isinstance(p, dict):
            continue
        teclas = []
        for t in p.get("teclas") or []:
            k = tecla_valida(t)
            if k and k["id"] not in vistos:
                vistos.add(k["id"])
                teclas.append(k)
        paginas.append({"nome": _texto(p.get("nome") or "Página", 30), "teclas": teclas})
    if not paginas:
        return normalizar({"ajustes": aj})
    # um atalho global só pode ser de uma tecla
    usados = set()
    for p in paginas:
        for k in p["teclas"]:
            if k["atalho_global"] in usados:
                k["atalho_global"] = ""
            elif k["atalho_global"]:
                usados.add(k["atalho_global"])
    ids = {k["id"] for p in paginas for k in p["teclas"]}
    cru_ap = cru.get("aparelhos") if isinstance(cru.get("aparelhos"), dict) else base["aparelhos"]
    aparelhos = {}
    for mid, a in list(cru_ap.items())[:20]:
        v = _aparelho_valido(a, ids)
        if v and re.match(r"^[a-z0-9_]{2,20}$", str(mid)):
            aparelhos[mid] = v
    return {"versao": VERSAO, "ajustes": aj, "paginas": paginas, "aparelhos": aparelhos}


def caminho_padrao():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "painel.json")


def carregar(caminho=None):
    caminho = caminho or caminho_padrao()
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            return normalizar(json.load(f))
    except (OSError, ValueError):
        return normalizar(None)


def salvar(cfg, caminho=None):
    caminho = caminho or caminho_padrao()
    limpo = normalizar(cfg)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(limpo, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)
    return limpo


def todas_as_teclas(cfg):
    for p in cfg.get("paginas") or []:
        for k in p.get("teclas") or []:
            yield k


def tecla_por_id(cfg, id_):
    return next((k for k in todas_as_teclas(cfg) if k["id"] == id_), None)


# ---------------------------------------------------------------------------
# Montar o comando de um programa / site (sem executar) — testável no CI
# ---------------------------------------------------------------------------
_NAV_EXE = {
    "chrome": [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
               r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
               r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"],
    "edge": [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
             r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"],
    "brave": [r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
              r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"],
    "firefox": [r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
                r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"],
    "opera": [r"%LOCALAPPDATA%\Programs\Opera\opera.exe"],
}


def expandir(v):
    v = str(v or "").strip().strip('"')
    return os.path.expanduser(os.path.expandvars(v))


def navegador_exe(nome, exe_proprio=""):
    """Caminho do navegador escolhido, ou '' para o navegador padrão do Windows."""
    if exe_proprio and os.path.isfile(expandir(exe_proprio)):
        return expandir(exe_proprio)
    for c in _NAV_EXE.get(nome or "", []):
        if os.path.isfile(expandir(c)):
            return expandir(c)
    return ""


def montar_comando(tecla, ajustes):
    """{'exe', 'args', 'cwd', 'oculto', 'precisa'} ou {'abrir_padrao': [urls]}."""
    a = tecla["acao"]
    if a == "programa":
        alvo = expandir(tecla["alvo"])
        if tecla["tipo"] == "exe":
            return {"exe": alvo, "args": list(tecla.get("args") or []), "cwd": os.path.dirname(alvo),
                    "oculto": False, "precisa": alvo}
        if tecla["tipo"] == "powershell":
            ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                              "WindowsPowerShell", "v1.0", "powershell.exe")
            return {"exe": ps, "args": list(tecla.get("args") or []) +
                    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", alvo],
                    "cwd": os.path.dirname(alvo), "oculto": True, "precisa": alvo}
        return {"exe": "explorer.exe", "args": ["shell:AppsFolder\\" + tecla["alvo"]], "cwd": None,
                "oculto": False, "precisa": ""}
    if a == "site":
        nome = tecla.get("navegador") or ajustes.get("navegador") or "padrao"
        perfil = tecla.get("perfil") or ajustes.get("perfil") or ""
        exe = navegador_exe(nome, ajustes.get("navegador_exe") if not tecla.get("navegador") else "")
        if not exe:
            return {"abrir_padrao": list(tecla["sites"])}
        args = []
        if perfil and nome in ("chrome", "edge", "brave", "opera"):
            args.append("--profile-directory=" + perfil)
        if tecla.get("lugar"):
            args.append("--new-window")
        return {"exe": exe, "args": args + list(tecla["sites"]), "cwd": os.path.dirname(exe),
                "oculto": False, "precisa": exe}
    return None


# ---------------------------------------------------------------------------
# Windows: processos, janelas, monitores, foco, teclado (ctypes)
# ---------------------------------------------------------------------------
if EH_WINDOWS:
    import ctypes
    from ctypes import wintypes as W

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        _dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        _dwm = None
    try:
        _u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: pixels reais
    except Exception:
        pass

    class _RECT(ctypes.Structure):
        _fields_ = [("L", ctypes.c_long), ("T", ctypes.c_long), ("R", ctypes.c_long), ("B", ctypes.c_long)]

    class _MONINFO(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT),
                    ("dwFlags", W.DWORD), ("szDevice", W.WCHAR * 32)]

    class _PE32(ctypes.Structure):
        _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", W.DWORD),
                    ("cntThreads", W.DWORD), ("th32ParentProcessID", W.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", W.DWORD), ("szExeFile", W.WCHAR * 260)]

    _ENUMWIN = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    _ENUMMON = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(_RECT), W.LPARAM)
    _u32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    _u32.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    _u32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    _u32.GetWindowThreadProcessId.restype = W.DWORD
    _u32.GetWindow.restype = W.HWND
    _u32.GetForegroundWindow.restype = W.HWND
    _u32.GetWindowLongW.restype = ctypes.c_long
    _u32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
    _u32.GetMonitorInfoW.argtypes = [W.HMONITOR, ctypes.POINTER(_MONINFO)]
    _k32.OpenProcess.restype = W.HANDLE
    _k32.CreateToolhelp32Snapshot.restype = W.HANDLE
    _k32.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]

    def _caminho_do_processo(pid):
        h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = W.DWORD(1024)
            return buf.value if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
        finally:
            _k32.CloseHandle(h)

    def processos():
        """[{pid, nome, caminho}] direto da API do Windows."""
        out = []
        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return out
        try:
            e = _PE32()
            e.dwSize = ctypes.sizeof(_PE32)
            ok = _k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                out.append({"pid": e.th32ProcessID, "nome": e.szExeFile,
                            "caminho": _caminho_do_processo(e.th32ProcessID)})
                ok = _k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            _k32.CloseHandle(snap)
        return out

    def janelas(pids=None):
        """Janelas 'de verdade': visíveis, com título, sem dono, não escondidas pelo DWM."""
        quer = set(pids or [])
        out = []

        def cb(h, _l):
            if not _u32.IsWindowVisible(h) or _u32.GetWindow(h, 4):
                return True
            if _u32.GetWindowLongW(h, -20) & 0x80:  # WS_EX_TOOLWINDOW
                return True
            if _dwm is not None:
                cl = ctypes.c_int(0)
                _dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(cl), 4)
                if cl.value:
                    return True
            pid = W.DWORD()
            _u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if quer and pid.value not in quer:
                return True
            t = ctypes.create_unicode_buffer(512)
            _u32.GetWindowTextW(h, t, 512)
            if not t.value:
                return True
            r = _RECT()
            _u32.GetWindowRect(h, ctypes.byref(r))
            out.append({"hwnd": int(h), "pid": pid.value, "titulo": t.value,
                        "x": r.L, "y": r.T, "w": r.R - r.L, "h": r.B - r.T,
                        "min": bool(_u32.IsIconic(h)), "max": bool(_u32.IsZoomed(h))})
            return True

        _u32.EnumWindows(_ENUMWIN(cb), 0)
        return out

    def monitores():
        out = []

        def cb(hm, _dc, _r, _l):
            mi = _MONINFO()
            mi.cbSize = ctypes.sizeof(_MONINFO)
            if _u32.GetMonitorInfoW(hm, ctypes.byref(mi)):
                m, w = mi.rcMonitor, mi.rcWork
                out.append({"device": mi.szDevice, "x": m.L, "y": m.T, "w": m.R - m.L, "h": m.B - m.T,
                            "wx": w.L, "wy": w.T, "ww": w.R - w.L, "wh": w.B - w.T,
                            "principal": bool(mi.dwFlags & 1)})
            return True

        _u32.EnumDisplayMonitors(None, None, _ENUMMON(cb), 0)
        return out

    def janela_da_frente():
        return int(_u32.GetForegroundWindow() or 0)

    def ativar(hwnd):
        h = W.HWND(hwnd)
        if not _u32.IsWindow(h):
            return False
        if _u32.IsIconic(h):
            _u32.ShowWindow(h, 9)
        if _u32.GetForegroundWindow() == hwnd:
            return True
        pid = W.DWORD()
        fg = _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
        eu = _k32.GetCurrentThreadId()
        preso = bool(fg and fg != eu and _u32.AttachThreadInput(eu, fg, True))
        _u32.SetForegroundWindow(h)
        _u32.BringWindowToTop(h)
        if preso:
            _u32.AttachThreadInput(eu, fg, False)
        if _u32.GetForegroundWindow() != hwnd:
            _u32.keybd_event(0x12, 0, 0, 0)  # Alt solto destrava o SetForegroundWindow
            _u32.keybd_event(0x12, 0, 2, 0)
            _u32.SetForegroundWindow(h)
        for _ in range(20):
            if _u32.GetForegroundWindow() == hwnd:
                break
            time.sleep(0.015)
        return _u32.GetForegroundWindow() == hwnd

    def _mover(h, x, y, w, hh):
        wr, fr = _RECT(), _RECT()
        _u32.GetWindowRect(h, ctypes.byref(wr))
        l = t = r = b = 0
        if _dwm is not None and _dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(fr), 16) == 0:
            l, t, r, b = fr.L - wr.L, fr.T - wr.T, wr.R - fr.R, wr.B - fr.B  # borda invisível
        _u32.SetWindowPos(h, None, x - l, y - t, w + l + r, hh + t + b, 0x0004 | 0x0010)

    def posicionar(hwnd, ret, maximizar=False):
        h = W.HWND(hwnd)
        if not _u32.IsWindow(h):
            return False
        if _u32.IsIconic(h) or _u32.IsZoomed(h):
            _u32.ShowWindow(h, 9)
            time.sleep(0.06)
        _mover(h, ret["x"], ret["y"], ret["w"], ret["h"])
        time.sleep(0.12)  # a janela pode mudar de escala ao trocar de monitor
        _mover(h, ret["x"], ret["y"], ret["w"], ret["h"])
        if maximizar:
            _u32.ShowWindow(h, 3)
        return True

    _VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
           "espaço": 0x20, "space": 0x20, "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22,
           "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "delete": 0x2E, "backspace": 0x08}

    def _vk(nome):
        n = nome.lower()
        if n in _VK:
            return _VK[n]
        if re.match(r"^f([1-9]|1[0-9]|2[0-4])$", n):
            return 0x6F + int(n[1:])
        if len(nome) == 1:
            return ord(nome.upper())
        return None

    def _apertar(vks):
        for v in vks:
            _u32.keybd_event(v, 0, 0, 0)
        for v in reversed(vks):
            _u32.keybd_event(v, 0, 2, 0)

    def _soltar_modificadores(espera=1.5):
        fim = time.time() + espera
        while time.time() < fim:
            if not any(_u32.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
                return
            time.sleep(0.015)

    def mandar_atalho(texto):
        vks = [_vk(p) for p in texto.split("+")]
        if not vks or None in vks:
            return False
        _soltar_modificadores()
        _apertar(vks)
        return True

    def tecla_de_sistema(comando):
        vk = {"volume_mais": 0xAF, "volume_menos": 0xAE, "mudo": 0xAD, "musica": 0xB3,
              "proxima_musica": 0xB0, "musica_anterior": 0xB1}.get(comando)
        if comando == "bloquear":
            return bool(_u32.LockWorkStation())
        if vk is None:
            return False
        _apertar([vk])
        return True

    def _area_de_transferencia(texto):
        # o PowerShell faz o Set-Clipboard com Unicode certinho e sem janela
        p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                            "[Console]::InputEncoding=[Text.Encoding]::UTF8; Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
                           input=texto.encode("utf-8"), capture_output=True, timeout=10,
                           creationflags=0x08000000)
        return p.returncode == 0
else:  # fora do Windows: só a parte pura funciona
    def processos():
        return []

    def janelas(pids=None):
        return []

    def monitores():
        return []

    def janela_da_frente():
        return 0

    def ativar(hwnd):
        return False

    def posicionar(hwnd, ret, maximizar=False):
        return False

    def mandar_atalho(texto):
        return False

    def tecla_de_sistema(comando):
        return False

    def _area_de_transferencia(texto):
        return False


# ---------------------------------------------------------------------------
# A janela "de fora" em que você estava (para colar texto e mandar atalhos)
# ---------------------------------------------------------------------------
_FORA = {"hwnd": 0, "vigia": None}
_NOSSOS = ("rotrix.exe", "msedgewebview2.exe", "python.exe", "pythonw.exe")


def _vigiar():
    meus = {os.getpid()}
    while True:
        try:
            h = janela_da_frente()
            if h and EH_WINDOWS:
                pid = W.DWORD()
                _u32.GetWindowThreadProcessId(W.HWND(h), ctypes.byref(pid))
                if pid.value not in meus:
                    nome = os.path.basename(_caminho_do_processo(pid.value)).lower()
                    if nome not in _NOSSOS:
                        _FORA["hwnd"] = h
        except Exception:
            pass
        time.sleep(0.3)


def ligar_vigia():
    if EH_WINDOWS and _FORA["vigia"] is None:
        t = threading.Thread(target=_vigiar, name="painel-vigia", daemon=True)
        _FORA["vigia"] = t
        t.start()


# ---------------------------------------------------------------------------
# O que está aberto e qual janela é de cada tecla
# ---------------------------------------------------------------------------
def _baixo(v):
    return str(v or "").lower()


def processos_da_tecla(tecla, procs, wins, ajustes):
    """pids dos processos que são desta tecla."""
    a = tecla["acao"]
    if a == "site":
        nome = tecla.get("navegador") or ajustes.get("navegador") or "padrao"
        exe = _baixo(navegador_exe(nome, ajustes.get("navegador_exe", "")))
        if exe:
            return [p["pid"] for p in procs if _baixo(p["caminho"]) == exe]
        base = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"}
        return [p["pid"] for p in procs if _baixo(p["nome"]) in base]
    if a != "programa":
        return []
    if tecla["tipo"] == "exe":
        exe = _baixo(expandir(tecla["alvo"]))
        por_caminho = [p["pid"] for p in procs if _baixo(p["caminho"]) == exe]
        return por_caminho or [p["pid"] for p in procs if not p["caminho"] and _baixo(p["nome"]) == os.path.basename(exe)]
    if tecla["tipo"] == "powershell":
        # sem a linha de comando, reconhece pela janela: título com o nome do programa
        alvo = _baixo(tecla.get("titulo") or tecla["nome"])
        ps = {p["pid"] for p in procs if re.search(r"powershell|pwsh", _baixo(p["nome"]))}
        return sorted({w["pid"] for w in wins if w["pid"] in ps and alvo in _baixo(w["titulo"])})
    det = _baixo(tecla.get("detectar") or "")
    if not det:
        return []
    if "\\" in det:
        return [p["pid"] for p in procs if det in _baixo(p["caminho"])]
    return [p["pid"] for p in procs if _baixo(p["nome"]).startswith(det)]


def escolher_janela(tecla, wins, antes=None):
    lista = wins
    if tecla.get("titulo"):
        alvo = _baixo(tecla["titulo"])
        lista = [w for w in lista if alvo in _baixo(w["titulo"])]
    elif tecla["acao"] == "site":
        lista = [w for w in lista if antes is not None and w["hwnd"] not in antes]
    if not lista:
        return None
    return max(lista, key=lambda w: 0 if w["min"] else w["w"] * w["h"])


def _abertos_e_janelas(teclas, ajustes):
    procs = processos()
    wins = janelas()
    out = {}
    for t in teclas:
        if t["acao"] not in ("programa", "site"):
            continue
        pids = set(processos_da_tecla(t, procs, wins, ajustes))
        minhas = [w for w in wins if w["pid"] in pids]
        out[t["id"]] = {"aberto": bool(pids) and (t["acao"] != "site" or bool(escolher_janela(t, minhas))),
                        "janelas": minhas}
    return out


def estado(cfg):
    teclas = list(todas_as_teclas(cfg))
    mons = monitores()
    ab = _abertos_e_janelas(teclas, cfg["ajustes"])
    achados = {}
    for t in teclas:
        cmd = montar_comando(t, cfg["ajustes"]) if t["acao"] in ("programa", "site") else None
        if cmd and cmd.get("precisa"):
            achados[t["id"]] = os.path.exists(cmd["precisa"])
    return {
        "ok": True,
        "abertos": {k: v["aberto"] for k, v in ab.items()},
        "achados": achados,
        "lugares": {t["id"]: descrever(t.get("lugar"), mons) for t in teclas if t.get("lugar")},
        "monitores": [dict(m, id=id_do_monitor(m), nome=nome_do_monitor(m)) for m in mons],
        "modelos": [{"id": m[0], "nome": m[1], "zonas": [{"r": list(z[0]), "nome": z[1]} for z in m[2]]}
                    for m in MODELOS],
        "navegadores": {n: bool(navegador_exe(n)) for n in NAVEGADORES if n != "padrao"},
    }


# ---------------------------------------------------------------------------
# Executar
# ---------------------------------------------------------------------------
def _abrir(tecla, ajustes):
    cmd = montar_comando(tecla, ajustes)
    if cmd is None:
        return {"ok": False, "motivo": "nao_abre"}
    if "abrir_padrao" in cmd:
        for u in cmd["abrir_padrao"]:
            os.startfile(u)  # navegador padrão do Windows
        return {"ok": True, "frase": "abrindo %s no navegador padrão" % tecla["nome"]}
    if cmd["precisa"] and not os.path.exists(cmd["precisa"]):
        return {"ok": False, "motivo": "nao_achado", "frase": "não achei o arquivo de %s" % tecla["nome"]}
    try:
        subprocess.Popen([cmd["exe"]] + cmd["args"],
                         cwd=cmd["cwd"] if cmd["cwd"] and os.path.isdir(cmd["cwd"]) else None,
                         creationflags=(0x08000000 if cmd["oculto"] else 0) | 0x00000008,  # sem janela | destacado
                         close_fds=True)
    except OSError as e:
        return {"ok": False, "motivo": "falhou_abrir", "frase": "não consegui abrir %s (%s)" % (tecla["nome"], type(e).__name__)}
    return {"ok": True, "frase": "abrindo %s" % tecla["nome"]}


def _colar_texto(texto):
    alvo = _FORA["hwnd"]
    if not alvo or not ativar(alvo):
        return {"ok": False, "motivo": "sem_janela", "frase": "clique antes na janela onde o texto deve entrar"}
    if not _area_de_transferencia(texto):
        return {"ok": False, "motivo": "area_de_transferencia"}
    time.sleep(0.05)
    mandar_atalho("Ctrl+V")
    return {"ok": True, "frase": "texto colado"}


def executar(cfg, id_tecla):
    """Aperta uma tecla do painel. Rotrix (folha, fila, IA) a tela resolve sozinha."""
    t = tecla_por_id(cfg, id_tecla)
    if not t:
        return {"ok": False, "motivo": "tecla_desconhecida"}
    a = t["acao"]
    if a in ("programa", "site"):
        ab = _abertos_e_janelas([t], cfg["ajustes"]).get(t["id"]) or {}
        jan = escolher_janela(t, ab.get("janelas") or []) if ab.get("aberto") else None
        if jan and t["acao"] == "programa" or (jan and t.get("titulo")):
            ok = ativar(jan["hwnd"])
            return {"ok": True, "frase": "%s %s" % (t["nome"], "na frente" if ok else "já está aberto")}
        antes = {w["hwnd"] for w in janelas()} if t.get("lugar") else None
        r = _abrir(t, cfg["ajustes"])
        if r.get("ok") and t.get("lugar"):
            threading.Thread(target=_posicionar_quando_abrir, args=(t, cfg["ajustes"], antes, 25),
                             daemon=True).start()
        return r
    if a == "sistema":
        ok = tecla_de_sistema(t["comando"])
        return {"ok": ok, "frase": t["nome"] if ok else "não deu (%s)" % t["comando"]}
    if a == "atalho":
        alvo = _FORA["hwnd"]
        if alvo:
            ativar(alvo)
        ok = mandar_atalho(t["teclas"])
        return {"ok": ok, "frase": ("%s mandado" % t["teclas"]) if ok else "atalho inválido"}
    if a == "texto":
        return _colar_texto(t["texto"])
    if a == "expediente":
        return expediente(cfg)
    if a == "organizar":
        return organizar(cfg)
    return {"ok": True, "na_tela": True, "comando": t.get("comando")}


def _posicionar_quando_abrir(t, ajustes, antes, segundos):
    fim = time.time() + segundos
    mons = monitores()
    ret = retangulo(t["lugar"], mons)
    if not ret:
        return
    while time.time() < fim:
        procs, wins = processos(), janelas()
        pids = set(processos_da_tecla(t, procs, wins, ajustes))
        jan = escolher_janela(t, [w for w in wins if w["pid"] in pids], antes)
        if jan:
            posicionar(jan["hwnd"], ret, t["lugar"]["layout"] == "full")
            return
        time.sleep(0.7)


def organizar(cfg, espera_s=0, antes=None):
    """Põe a janela de cada tecla com lugar no lugar dela."""
    mons = monitores()
    pend, res = [], {}
    for t in todas_as_teclas(cfg):
        if t["acao"] not in ("programa", "site") or not t.get("lugar"):
            continue
        ret = retangulo(t["lugar"], mons)
        if ret:
            pend.append((t, ret))
        else:
            res[t["id"]] = "sem_monitor"
    fim = time.time() + espera_s
    while pend:
        procs, wins = processos(), janelas()
        for i in range(len(pend) - 1, -1, -1):
            t, ret = pend[i]
            pids = set(processos_da_tecla(t, procs, wins, cfg["ajustes"]))
            jan = escolher_janela(t, [w for w in wins if w["pid"] in pids], antes)
            if jan:
                res[t["id"]] = "posicionada" if posicionar(jan["hwnd"], ret, t["lugar"]["layout"] == "full") else "erro"
                pend.pop(i)
        if not pend or time.time() >= fim:
            break
        time.sleep(0.7)
    for t, _r in pend:
        res[t["id"]] = "fechada"
    n = sum(1 for v in res.values() if v == "posicionada")
    return {"ok": True, "resultado": res, "frase": "%d janela%s no lugar" % (n, "" if n == 1 else "s")}


def expediente(cfg):
    """Abre os programas do expediente que estão fechados e organiza as janelas."""
    teclas = [t for t in todas_as_teclas(cfg) if t.get("expediente") and t["acao"] in ("programa", "site")]
    ab = _abertos_e_janelas(teclas, cfg["ajustes"])
    antes = {w["hwnd"] for w in janelas()}
    abriu, falhou = [], []
    for t in teclas:
        if (ab.get(t["id"]) or {}).get("aberto"):
            continue
        r = _abrir(t, cfg["ajustes"])
        (abriu if r.get("ok") else falhou).append(t["nome"])
        time.sleep(0.45)
    org = organizar(cfg, espera_s=25 if abriu else 0, antes=antes) if cfg["ajustes"].get("organizar_ao_iniciar", True) else {}
    frase = ("abri " + ", ".join(abriu) if abriu else "tudo já estava aberto")
    if org:
        frase += " · " + org["frase"]
    if falhou:
        frase += " · não achei: " + ", ".join(falhou)
    return {"ok": not falhou, "abertos": abriu, "falhou": falhou, "frase": frase,
            "resultado": org.get("resultado") if org else {}}


def rodinha(passos, com_ctrl=False):
    """Gira a rodinha do mouse (vai para a janela sob o cursor: rola cortes,
    com Ctrl dá zoom no visualizador)."""
    if not EH_WINDOWS:
        return False
    if com_ctrl:
        _u32.keybd_event(0x11, 0, 0, 0)
    _u32.mouse_event(0x0800, 0, 0, int(120 * passos), 0)  # negativo = rolar para baixo
    if com_ctrl:
        _u32.keybd_event(0x11, 0, 2, 0)
    return True


# ---------------------------------------------------------------------------
# Fase 3: o aparelho físico (deck.py) ligado às teclas do Painel
# ---------------------------------------------------------------------------
_DECK = {"gerente": None, "fila": [], "ultimo": None, "trava": threading.Lock(), "voltar_para": {}}


def _cfg_aparelho(modelo_id):
    cfg = carregar()
    return cfg, (cfg.get("aparelhos") or {}).get(modelo_id)


def _ao_evento(ap, slot, tipo, apertado):
    """Um aperto/giro no aparelho -> a ação mapeada no Painel."""
    _DECK["ultimo"] = {"chave": ap.chave, "slot": slot, "tipo": tipo, "apertado": apertado, "em": time.time()}
    if not apertado:
        return
    cfg, a = _cfg_aparelho(ap.modelo["id"])
    if not a:
        return
    g = _DECK["gerente"]
    pag_i = g.pagina.get(ap.chave, 0) if g else 0
    paginas = a["paginas"]
    m = paginas[pag_i % len(paginas)]["m"] if paginas else {}
    ref = m.get(slot)
    if slot.startswith("g"):
        ref = ref or {}
        if tipo == "clique":
            _executar_ref(cfg, ref.get("clique"))
            return
        d = 1 if tipo == "girar+" else -1
        giro = ref.get("girar")
        if giro == "volume":
            tecla_de_sistema("volume_mais" if d > 0 else "volume_menos")
        elif giro == "pagina" and g:
            g.trocar_pagina(ap.chave, pag_i + d, len(paginas))
            _avisar_tela({"pagina_aparelho": ap.chave, "indice": (pag_i + d) % len(paginas)})
        elif giro == "rolar":
            rodinha(-d)
        elif giro == "zoom":
            rodinha(d, com_ctrl=True)
        elif giro == "brilho" and g:
            a["brilho"] = max(5, min(100, a["brilho"] + 5 * d))
            g.ajustar_brilho(ap.modelo["id"], a["brilho"])
        return
    _executar_ref(cfg, ref)


def _avisar_tela(item):
    with _DECK["trava"]:
        _DECK["fila"].append(item)
        del _DECK["fila"][:-50]


def _executar_ref(cfg, id_tecla):
    if not id_tecla:
        return
    t = tecla_por_id(cfg, id_tecla)
    if not t:
        return
    if t["acao"] == "rotrix":
        _avisar_tela({"comando": t["comando"]})  # a tela do Rotrix faz (folha, fila, abas)
        return
    threading.Thread(target=executar, args=(cfg, id_tecla), daemon=True).start()


def _pagina_pelo_programa():
    """Página que troca sozinha pelo programa da frente ("app" da página)."""
    while True:
        try:
            g = _DECK["gerente"]
            h = _FORA["hwnd"]
            if g and g.aparelhos and h and EH_WINDOWS:
                pid = W.DWORD()
                _u32.GetWindowThreadProcessId(W.HWND(h), ctypes.byref(pid))
                exe = os.path.basename(_caminho_do_processo(pid.value)).lower()
                cfg = carregar()
                for ap in list(g.aparelhos.values()):
                    a = (cfg.get("aparelhos") or {}).get(ap.modelo["id"])
                    if not a or not a.get("auto"):
                        continue
                    atual = g.pagina.get(ap.chave, 0)
                    alvo = next((i for i, p in enumerate(a["paginas"]) if p.get("app") and p["app"] in exe), None)
                    if alvo is not None and alvo != atual:
                        if not a["paginas"][atual % len(a["paginas"])].get("app"):
                            _DECK["voltar_para"][ap.chave] = atual
                        g.trocar_pagina(ap.chave, alvo, len(a["paginas"]))
                        _avisar_tela({"pagina_aparelho": ap.chave, "indice": alvo})
                    elif alvo is None and a["paginas"][atual % len(a["paginas"])].get("app"):
                        volta = _DECK["voltar_para"].pop(ap.chave, 0)
                        g.trocar_pagina(ap.chave, volta, len(a["paginas"]))
                        _avisar_tela({"pagina_aparelho": ap.chave, "indice": volta})
        except Exception:
            pass
        time.sleep(1.0)


def ligar_deck():
    if _DECK["gerente"] is not None:
        return _DECK["gerente"]
    try:
        import deck
    except Exception:
        return None
    g = deck.Gerente(_ao_evento)
    _DECK["gerente"] = g
    for mid, a in (carregar().get("aparelhos") or {}).items():
        g.brilhos[mid] = a.get("brilho", 80)
    g.iniciar()
    ligar_vigia()
    if EH_WINDOWS:
        threading.Thread(target=_pagina_pelo_programa, name="deck-pagina", daemon=True).start()
    return g


def deck_rota(acao, corpo):
    g = ligar_deck()
    if g is None:
        return {"ok": False, "motivo": "deck_ausente"}
    if acao == "deck_estado":
        e = g.estado()
        e["ok"] = True
        return e
    if acao == "deck_imagens":
        n = g.receber_imagens(str(corpo.get("modelo") or ""), corpo.get("paginas") or {})
        return {"ok": True, "imagens": n}
    if acao == "deck_eventos":
        with _DECK["trava"]:
            fila, _DECK["fila"] = _DECK["fila"], []
        return {"ok": True, "eventos": fila, "ultimo": _DECK["ultimo"]}
    if acao == "deck_pagina":
        _cfg, a = _cfg_aparelho(str(corpo.get("modelo") or ""))
        total = len(a["paginas"]) if a else 1
        for ap in list(g.aparelhos.values()):
            if ap.modelo["id"] == corpo.get("modelo"):
                g.trocar_pagina(ap.chave, int(corpo.get("indice") or 0), total)
        return {"ok": True}
    if acao == "deck_brilho":
        g.ajustar_brilho(str(corpo.get("modelo") or ""), max(5, min(100, int(corpo.get("brilho") or 80))))
        return {"ok": True}
    if acao == "deck_simular":
        # "Apertar (simular)" na tela: o mesmo caminho de um aperto de verdade
        class _Falso:
            chave = "simulado"
            modelo = {"id": str(corpo.get("modelo") or "")}
        _ao_evento(_Falso(), str(corpo.get("slot") or ""), str(corpo.get("tipo") or "tecla"), True)
        return {"ok": True}
    return {"ok": False, "motivo": "acao_desconhecida"}


def capturar(cfg):
    """'Usar a posição de agora': onde está a janela de cada tecla aberta."""
    mons = monitores()
    procs, wins = processos(), janelas()
    out = {}
    for t in todas_as_teclas(cfg):
        if t["acao"] not in ("programa", "site"):
            continue
        pids = set(processos_da_tecla(t, procs, wins, cfg["ajustes"]))
        jan = escolher_janela(t, [w for w in wins if w["pid"] in pids])
        if t["acao"] == "site" and not t.get("titulo"):
            jan = None  # sem título, não dá para saber qual janela do navegador é
        if jan and not jan["min"]:
            out[t["id"]] = adivinhar_lugar(jan, mons)
    return {"ok": True, "lugares": out, "descricao": {k: descrever(v, mons) for k, v in out.items() if v}}
