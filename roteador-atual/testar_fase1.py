# -*- coding: utf-8 -*-
"""Fase 1 da auditoria de 14/10 (versão 2026-10-16.1): velocidade e laudo certo.

    python testar_fase1.py

Cada bloco é um achado da AUDITORIA_ROTRIX_14-10.md que foi corrigido:
  A. textos errados no laudo (marca e aviso comidos, seção virando comando, nada
     selecionado, palavra de comando colada, estouro de tempo jogando fora a revisão,
     "acrescentar sempre" em frase solta)
  B. rotas da IA (o título decide o exame, tarefas fora da tabela, a barra vence a
     tabela, Luna sem raciocínio, piso de saída de quem raciocina)
  C. privacidade (atendimento de 7 dígitos, RG, telefone, "Paciente Nome Sobrenome")
     sem barrar NENHUMA máscara do banco
  D. perfil completo (as chaves que faltavam, as regras dele, nunca a chave de IA)
  E. gasto sem perder soma, recibo de cada chamada, log com o porquê do modelo,
     negrito por padrão quando o colador existe, caches pela geração do banco
  F. resposta por diferença (a IA devolve só as linhas que mudam)
Sem internet e sem chave de verdade (respostas simuladas). Nada é gravado na pasta.
"""
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import nuvem  # noqa: E402

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp
nuvem.CONFIG = os.path.join(tmp, "config.json")
nuvem.CACHE_MODELOS = os.path.join(tmp, "dados", "modelos_cache.json")
os.environ["OPENAI_API_KEY"] = "teste-openai"
os.environ["ANTHROPIC_API_KEY"] = "teste-anthropic"
os.environ.pop("ROTEADOR_COLADOR", None)

import roteador  # noqa: E402
import correcao  # noqa: E402
import perfil  # noqa: E402

roteador._aprender = lambda *a, **k: None      # nunca grava aprendizado.json na pasta real
correcao.ARQ_REGRAS = os.path.join(tmp, "minhas_regras.json")
correcao.ARQ_LOG = os.path.join(tmp, "correcoes.jsonl")
correcao.ARQ_OUVIDO = os.path.join(tmp, "ouvido.tsv")

falhas = []


def confere(nome, ok, extra=""):
    print("%-6s  %s%s" % ("ok" if ok else "FALHA", nome, ("\n        " + str(extra)[:600]) if (extra and not ok) else ""))
    if not ok:
        falhas.append(nome)


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


CHAMADAS = []                 # corpos enviados
RESPOSTAS = []                # fila de respostas; vazia = "LAUDO PRONTO"
ESPERA = {"s": 0.0}


def _falso(req, timeout=None, context=None):
    corpo = json.loads(req.data.decode("utf-8"))
    CHAMADAS.append(corpo)
    if ESPERA["s"]:
        time.sleep(ESPERA["s"])
    txt = RESPOSTAS.pop(0) if RESPOSTAS else "LAUDO PRONTO"
    if isinstance(txt, Exception):
        raise txt
    return _R(json.dumps({"choices": [{"message": {"content": txt}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 900, "completion_tokens": 50}}).encode())


urllib.request.urlopen = _falso

C_DELE = {"ativa": True, "provedor": "openai", "modelo": "gpt-6-sol", "limite_mes_usd": 0,
          "marcar_saida": True, "marca_inicio": "[[ análise assistida — revisar antes de assinar ]]",
          "marca_fim": "", "max_tokens": 1500, "timeout_s": 40,
          "gatilhos": ["analise avancada", "analise", "analisar"],
          "gatilhos_revisao": ["revisar", "revisao", "corrigir", "revisar laudo"],
          "ia_por_exame": {"rx": {"provedor": "openai", "modelo": "gpt-6-luna", "modo": "formatar"},
                           "tc": {"provedor": "openai", "modelo": "gpt-6-sol"}}}


def gravar_config(extra=None):
    c = dict(C_DELE)
    c.update(extra or {})
    with open(nuvem.CONFIG, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    return nuvem.config()


def zerar():
    del CHAMADAS[:]
    del RESPOSTAS[:]
    ESPERA["s"] = 0.0


def usuario(corpo):
    return next((m["content"] for m in corpo.get("messages", []) if m.get("role") == "user"), "")


def sistema(corpo):
    return next((m["content"] for m in corpo.get("messages", []) if m.get("role") == "system"), "")


gravar_config()

LAUDO_TC = """**TOMOGRAFIA COMPUTADORIZADA DO TÓRAX**

**TÉCNICA:**  exame realizado com técnica multislice, sem contraste.

**ANÁLISE:**
Parênquima pulmonar:  nodulo de 6 mm no lobo superior direito.
Traqueia e brônquios:  calibre e trajetos normais.
Mediastino:  sem alterações evidentes.
Derrames:  ausência de derrame pleural ou pericárdico.
Estruturas ósseas e partes moles:  sem particularidades.

**CONCLUSÃO:**
Nódulo pulmonar no lobo superior direito."""

# ============================================================== A. textos
print("--- A. textos errados no laudo")
marca = "[[ análise assistida — revisar antes de assinar ]]  (gpt-6-luna · US$ 0.0012 · mês US$ 1.20)"
aviso = "[não enviei para a nuvem: o texto contém CPF]"
g = roteador.generalizar(marca + "\nlinha com lacuna ___ no fim.\n" + aviso)
confere("A1 modo genérico não come a marca da IA", marca in g, g)
confere("A1 nem o aviso de recusa", aviso in g, g)
_orig = roteador._rotear
roteador._rotear = lambda d, _a=False: (marca + "\nfrase com ___ aqui", "nuvem")
t, o = roteador.rotear("qualquer")
roteador._rotear = _orig
confere("A1 resposta da nuvem não passa pelo modo genérico", t.startswith(marca) and "___" in t, t)

zerar()
t, o = roteador.rotear("Análise: fígado com esteatose difusa")
confere("A2 'Análise:' (nome da seção) não vai para a nuvem", not CHAMADAS and not o.startswith("nuvem"), (o, t))
zerar()
t, o = roteador.rotear("analisar nódulo pulmonar de 8 mm no lobo inferior esquerdo")
confere("A2 'analisar ...' (comando) vai para a nuvem", len(CHAMADAS) == 1, (o, len(CHAMADAS)))

# A3: sem nada selecionado, instrução e "revisar laudo" não colam nada
_os_nome = roteador.os.name
_aw = sys.modules.get("atalho_win")


class _AtalhoFalso:
    @staticmethod
    def copiar_selecao():
        return ""


sys.modules["atalho_win"] = _AtalhoFalso
try:
    roteador.os.name = "nt"
    zerar()
    t1, o1 = roteador.rotear("melhore a conclusão")
    zerar()
    t2, o2 = roteador.rotear("revisar laudo")
finally:
    roteador.os.name = _os_nome
    if _aw is None:
        sys.modules.pop("atalho_win", None)
    else:
        sys.modules["atalho_win"] = _aw
confere("A3 instrução sem seleção: nada é colado", (t1, o1) == ("", "instrucao_sem_selecao") and not CHAMADAS, (t1, o1))
confere("A3 'revisar laudo' sem seleção: nada é colado", (t2, o2) == ("", "revisar_sem_selecao"), (t2, o2))

# A4: nuvem fora do ar no "analisar": segue no local SEM a palavra de comando
zerar()
RESPOSTAS.append(OSError("sem rede"))
t, o = roteador.rotear("analisar derrame pleural pequeno à direita")
confere("A4 nuvem fora: o comando 'analisar' não vai para o laudo",
        not re.match(r"^\s*analis", t or "", re.I), (o, t))

# A5: o teto de 8 s é do roteamento local, não da nuvem
from http.server import ThreadingHTTPServer  # noqa: E402
_orc = roteador.ORCAMENTO_S
roteador.ORCAMENTO_S = 0.2


def _lento(origem):
    def f(d, _a=False):
        time.sleep(0.4)
        return "REVISADO PELO LOCAL.", origem
    return f


srv = ThreadingHTTPServer(("127.0.0.1", 0), roteador.Handler)
th = threading.Thread(target=srv.serve_forever, daemon=True)
th.start()


def _post(dit):
    req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % srv.server_address[1],
                                 data=json.dumps({"messages": [{"role": "user", "content": dit}]}).encode(),
                                 headers={"Content-Type": "application/json"})
    import http.client
    cx = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    cx.request("POST", "/v1/chat/completions", body=req.data, headers={"Content-Type": "application/json"})
    r = json.loads(cx.getresponse().read().decode("utf-8"))
    cx.close()
    return r["choices"][0]["message"]["content"]


_rot = roteador.rotear
try:
    roteador.rotear = _lento("revisado_local_sem_nuvem")
    a = _post("revisar o texto ditado")
    roteador.rotear = _lento("local:frase")
    b = _post("frase lenta")
finally:
    roteador.rotear = _rot
    roteador.ORCAMENTO_S = _orc
    srv.shutdown()
confere("A5 nuvem tentada e demorada: a revisão local volta (não o ditado cru)",
        a.startswith("REVISADO"), a)
confere("A5 roteamento local demorado: continua devolvendo o ditado", b == "frase lenta", b)

# A6: "sempre acrescentar a frase X" só entra em laudo inteiro
with open(correcao.ARQ_REGRAS, "w", encoding="utf-8") as f:
    json.dump({"regras": [{"id": "a1", "tipo": "acrescentar", "frase": "Correlacionar com dados clínicos",
                           "escopo": ""}]}, f, ensure_ascii=False)
correcao._CACHE["mtime"] = None
solta = correcao.aplicar_regras("Derrame pleural pequeno à direita.", "local:frase")
inteiro = correcao.aplicar_regras(LAUDO_TC, "mascara:medicina_interna/tc/torax/normal")
confere("A6 frase solta: 'acrescentar' não entra", "Correlacionar" not in solta, solta)
confere("A6 laudo inteiro: entra antes da conclusão",
        "Correlacionar com dados clínicos." in inteiro and
        inteiro.index("Correlacionar") < inteiro.index("**CONCLUSÃO:**"), inteiro)
os.remove(correcao.ARQ_REGRAS)
correcao._CACHE["mtime"] = None

# ============================================================== B. rotas
print("--- B. rotas da IA")
c = gravar_config()
confere("B1 o título decide: TC que cita radiografia prévia é TC",
        nuvem.tipo_exame("LAUDO NA TELA:\nTOMOGRAFIA DE TÓRAX\nComparado com radiografia de 2025.") == "tc")
confere("B1 escanometria é RX", nuvem.tipo_exame("LAUDO NA TELA:\nESCANOMETRIA DOS MEMBROS INFERIORES\nx") == "rx")
confere("B1 colangio-RM é RM", nuvem.tipo_exame("LAUDO NA TELA:\nCOLANGIORRESSONÂNCIA\nx") == "rm"
        or nuvem.tipo_exame("LAUDO NA TELA:\nCOLANGIO-RM\nx") == "rm")
r = nuvem.rota("RADIOGRAFIA DO JOELHO ... máscara da oficina", c, "instrucao", tarefa="oficina")
confere("B2 oficina fora da tabela (fica no Modelo padrão)",
        r["regra"] == "tarefa:oficina" and r["modelo"] == "gpt-6-sol" and r["modo"] == "instrucao", r)
r = nuvem.rota("LAUDO NA TELA:\n" + LAUDO_TC, nuvem.com_modelo(c, "openai:gpt-6-luna"), "laudo")
confere("B3 Luna escolhida na barra vence a linha da TC", r["modelo"] == "gpt-6-luna" and r["regra"] == "barra", r)
r = nuvem.rota("LAUDO NA TELA:\n" + LAUDO_TC, nuvem.com_modelo(c, "openai:gpt-6-sol"), "laudo")
confere("B3 o Modelo padrão repetido na barra deixa a tabela mandar", r["regra"] == "tc", r)
confere("B4 Luna/mini/nano são básicos; Sol não",
        all(nuvem._modelo_basico(m) for m in ("gpt-6-luna", "gpt-5-mini", "gpt-4.1-nano")) and
        not any(nuvem._modelo_basico(m) for m in ("gpt-6-sol", "claude-opus-5", "lunar-x")))
zerar()
nuvem.chamar("LAUDO NA TELA:\n" + LAUDO_TC, nuvem.com_modelo(c, "openai:gpt-6-luna"), modo="laudo",
             marcar=False, max_tokens=4000)
confere("B4 Luna no laudo de TC: raciocínio 'none'", CHAMADAS and CHAMADAS[-1].get("reasoning_effort") == "none",
        CHAMADAS[-1] if CHAMADAS else "")
zerar()
nuvem.chamar("LAUDO NA TELA:\n" + LAUDO_TC, c, modo="laudo", marcar=False, max_tokens=4000)
confere("B4 Sol no laudo: raciocínio no padrão do modelo (não desligado)",
        CHAMADAS and CHAMADAS[-1].get("reasoning_effort") in (None, "", "medium"), CHAMADAS[-1] if CHAMADAS else "")
zerar()
nuvem.chamar("analisar nódulo de 8 mm", c, modo="analise", marcar=False, max_tokens=300)
confere("B5 quem raciocina ganha piso de saída (300 -> 3000)",
        CHAMADAS and CHAMADAS[-1].get("max_completion_tokens", 0) >= 3000, CHAMADAS[-1] if CHAMADAS else "")
_ex = nuvem._exemplos_estilo
nuvem._exemplos_estilo = lambda c: "\n\nEXEMPLOS_DE_ESTILO_FALSOS"
zerar()
nuvem.chamar("pedido da oficina", c, modo="instrucao", marcar=False, max_tokens=4000, tarefa="oficina")
confere("B6 tarefa que responde JSON não leva exemplos de laudo",
        CHAMADAS and "EXEMPLOS_DE_ESTILO_FALSOS" not in sistema(CHAMADAS[-1]))
nuvem._exemplos_estilo = _ex

# ============================================================== C. privacidade
print("--- C. privacidade")
barra = ["Atendimento 1234567", "acesso nº 654321", "Atendimento: 98765432", "RG 12.345.678-9",
         "tel (41) 99876-5432", "contato 99876-5432", "Pac: Maria Souza", "PACIENTE - JOÃO SILVA",
         "Paciente João da Silva, 45 anos", "CPF 123.456.789-09"]
passa = ["Paciente com dor torácica.", "Paciente em decúbito dorsal.", "PACIENTE COM TOSSE",
         "Nódulo de 12 mm no exame de 2025.", "Comparado com exame de 12/03/2025.",
         "Escoliose com Cobb de 12 graus.", "L4-L5: abaulamento discal.", "Acesso venoso central à direita."]
erradas = [t for t in barra if not nuvem.triagem(t)]
confere("C1 identificadores barram", not erradas, erradas)
erradas = [(t, nuvem.triagem(t)) for t in passa if nuvem.triagem(t)]
confere("C1 texto de laudo passa", not erradas, erradas)
falsos = []
for raiz, _d, arqs in os.walk(os.path.join(AQUI, "dados", "mascaras")):
    for a in arqs:
        if a.endswith(".txt"):
            corpo = open(os.path.join(raiz, a), encoding="utf-8").read()
            corpo = "\n".join(l for l in corpo.split("\n") if not l.startswith("#"))
            if nuvem.triagem(corpo):
                falsos.append((a, nuvem.triagem(corpo)))
confere("C2 nenhuma máscara do banco é barrada (%d achados)" % len(falsos), not falsos, falsos[:5])
trechos = nuvem.triagem_trechos("Paciente João da Silva, 45 anos")
confere("C3 a tela mostra 'Paciente', nunca o nome", trechos and all("João" not in t for _n, t in trechos), trechos)

# ============================================================== D. perfil
print("--- D. perfil completo")
casa = os.path.join(tmp, "casa_a")
os.makedirs(os.path.join(casa, "dados"))
cfg_a = {"max_tokens": 1500, "formato_titulos": "rico", "modelo_leve": "gpt-6-luna", "fonte_mascaras": "ambas",
         "laudo_generico": True, "economizar": False, "api_key": "x", "token": "y",
         "prompt_perfil": "Seja breve. sk-ABCDEFGHIJKLMNOPQRSTUVWX123 fim",
         "ia_por_exame": {"tc": {"modelo": "gpt-6-sol", "chave": "zzz"}},
         "arquivo_da_chave": "chave_openai.txt"}
with open(os.path.join(casa, "config.json"), "w", encoding="utf-8-sig") as f:   # com BOM, como o Bloco de Notas
    json.dump(cfg_a, f, ensure_ascii=False)
with open(os.path.join(casa, "dados", "minhas_regras.json"), "w", encoding="utf-8") as f:
    json.dump({"regras": [
        {"id": "r1", "tipo": "tirar", "frase": "Partes moles sem alterações", "escopo": "msk/rx/punho",
         "pedido": "não escrever partes moles no rx do punho do paciente FULANO"},
        {"id": "r2", "tipo": "nota", "texto": "laudo do paciente FULANO estava errado"}]}, f, ensure_ascii=False)
with open(os.path.join(casa, "dados", "correcoes.jsonl"), "w", encoding="utf-8") as f:
    f.write('{"pedido": "texto com laudo FULANO"}\n')
perfil.AQUI, perfil.DADOS = casa, os.path.join(casa, "dados")
perfil.ARQ_REGRAS = os.path.join(perfil.DADOS, "minhas_regras.json")
z = perfil.exportar(os.path.join(tmp, "p.rotrix.zip"))
with zipfile.ZipFile(z["arquivo"]) as zz:
    nomes = zz.namelist()
    cfg_z = json.loads(zz.read("config.json").decode("utf-8"))
    regras_z = zz.read("dados/minhas_regras.json").decode("utf-8") if "dados/minhas_regras.json" in nomes else ""
confere("D1 max_tokens, formato_titulos, modelo_leve, fonte_mascaras vão",
        all(k in cfg_z for k in ("max_tokens", "formato_titulos", "modelo_leve", "fonte_mascaras", "economizar")), cfg_z)
confere("D1 chave nunca vai (nome nem valor)",
        "api_key" not in cfg_z and "token" not in cfg_z and "arquivo_da_chave" not in cfg_z and
        "sk-" not in json.dumps(cfg_z) and "chave" not in json.dumps(cfg_z.get("ia_por_exame")), cfg_z)
confere("D1 o resto do prompt continua", "Seja breve." in cfg_z.get("prompt_perfil", ""), cfg_z.get("prompt_perfil"))
confere("D2 as regras dele vão, sem o texto do pedido e sem as notas",
        '"r1"' in regras_z and "FULANO" not in regras_z and "nota" not in regras_z, regras_z)
confere("D2 correcoes.jsonl nunca vai", not any("correcoes" in n for n in nomes), nomes)
casa_b = os.path.join(tmp, "casa_b")
os.makedirs(os.path.join(casa_b, "dados"))
with open(os.path.join(casa_b, "config.json"), "w", encoding="utf-8-sig") as f:
    json.dump({"modelo": "gpt-6-sol", "provedor": "openai"}, f)
with open(os.path.join(casa_b, "dados", "minhas_regras.json"), "w", encoding="utf-8") as f:
    json.dump({"regras": [{"id": "r1", "tipo": "acrescentar", "frase": "outra", "escopo": ""}]}, f)
perfil.AQUI, perfil.DADOS = casa_b, os.path.join(casa_b, "dados")
perfil.ARQ_REGRAS = os.path.join(perfil.DADOS, "minhas_regras.json")
res = perfil.importar(z["arquivo"])
res2 = perfil.importar(z["arquivo"])
cfg_b = json.load(open(os.path.join(casa_b, "config.json"), encoding="utf-8-sig"))
reg_b = json.load(open(perfil.ARQ_REGRAS, encoding="utf-8"))["regras"]
confere("D3 importar: config junta (formato_titulos chega, modelo dele fica)",
        cfg_b.get("formato_titulos") == "rico" and cfg_b.get("provedor") == "openai", cfg_b)
confere("D3 importar: regra nova entra com outro id, a dele fica, e a 2a vez não duplica",
        res.get("regras") == 1 and res2.get("regras") == 0 and len(reg_b) == 2 and
        len({r["id"] for r in reg_b}) == 2, (res, res2, reg_b))
perfil.AQUI = AQUI
perfil.DADOS = os.path.join(AQUI, "dados")
perfil.ARQ_REGRAS = os.path.join(perfil.DADOS, "minhas_regras.json")

# ============================================================== E. gasto, recibo, log, negrito, cache
print("--- E. gasto, recibo, log, negrito, cache")
if os.path.exists(nuvem.GASTO):
    os.remove(nuvem.GASTO)
ths = [threading.Thread(target=nuvem.gasto_somar, args=("openai:gpt-6-sol", 100, 10, 0.01)) for _ in range(40)]
[t.start() for t in ths]
[t.join() for t in ths]
confere("E1 40 chamadas ao mesmo tempo: o gasto conta as 40", nuvem.gasto_ler()["chamadas"] == 40,
        nuvem.gasto_ler())

zerar()
ESPERA["s"] = 0.15
saida = {}


def _uma(nome, modelo):
    cc = nuvem.com_modelo(nuvem.config(), modelo)
    nuvem.chamar("revisar texto curto " + nome, cc, modo="revisao", marcar=False, max_tokens=200)
    time.sleep(0.05)
    saida[nome] = nuvem.ultima_desta_chamada().get("modelo")


t1 = threading.Thread(target=_uma, args=("a", "openai:gpt-6-luna"))
t2 = threading.Thread(target=_uma, args=("b", "openai:gpt-6-sol"))
t1.start()
time.sleep(0.05)
t2.start()
t1.join()
t2.join()
ESPERA["s"] = 0.0
confere("E2 cada tela recebe o recibo da SUA chamada",
        saida.get("a") == "openai:gpt-6-luna" and saida.get("b") == "openai:gpt-6-sol", saida)
zerar()
nuvem.chamar("LAUDO NA TELA:\n" + LAUDO_TC, c, modo="laudo", marcar=False, max_tokens=4000)
ult = open(nuvem.LOG, encoding="utf-8").read().strip().split("\n")[-1]
confere("E3 log diz regra, modo e exame (sem conteúdo)",
        "regra=tc" in ult and "modo=laudo" in ult and "exame=tc" in ult and "nódulo" not in ult.lower(), ult)

roteador._COLADOR["quando"] = 0.0
sem = roteador.formatar_saida("**TÉCNICA:** x")
falso_colador = os.path.join(tmp, "colador.exe")
open(falso_colador, "w").close()
os.environ["ROTEADOR_COLADOR"] = falso_colador
roteador._COLADOR["quando"] = 0.0
com = roteador.formatar_saida("**TÉCNICA:** x")
os.environ.pop("ROTEADOR_COLADOR", None)
roteador._COLADOR["quando"] = 0.0
cfg_pacote = roteador._config()
if "formato_titulos" not in cfg_pacote:
    confere("E4 sem formato_titulos e sem colador: texto puro", "**" not in sem, sem)
    confere("E4 sem formato_titulos e com colador: negrito (marcas mantidas)", "**TÉCNICA:**" in com, com)

g0 = roteador.BANCO.geracao
roteador._vocab()
confere("E5 cache do vocabulário marcado com a geração do banco", roteador._VOCAB["n"] == g0)
roteador.BANCO.geracao += 1
roteador._vocab()
confere("E5 nova geração do banco renova o cache", roteador._VOCAB["n"] == g0 + 1)
confere("E6 versão nova", roteador.VERSAO == "2026-10-16.1", roteador.VERSAO)

# ============================================================== F. resposta por diferença
print("--- F. resposta por diferença")
ped = "LAUDO NA TELA:\n" + LAUDO_TC
dif = nuvem.pedido_por_diferenca(ped)
confere("F1 linhas numeradas e a regra no pedido",
        dif and "#1: **TOMOGRAFIA" in dif and "RESPOSTA POR DIFERENÇA" in dif and "#10: Nódulo" in dif, dif)
confere("F1 laudo curto não é numerado", nuvem.pedido_por_diferenca("LAUDO NA TELA:\na\nb\nc") is None)
L = LAUDO_TC.split("\n")


def ap(resp):
    return nuvem.aplicar_diferenca(ped, resp)


novo, f = ap("#4: Parênquima pulmonar:  nódulo de 6 mm no lobo superior direito.")
esperado = LAUDO_TC.replace("nodulo de 6 mm", "nódulo de 6 mm")
confere("F2 troca de uma linha: o resto fica byte a byte", f == "dif" and novo == esperado, (f, novo))
novo, f = ap("#5+: Pleura:  sem alterações.\n#0+: LINHA DO TOPO")
confere("F2 linha nova depois da 5 e no começo",
        f == "dif" and novo.split("\n")[0] == "LINHA DO TOPO" and
        "calibre e trajetos normais.\nPleura:  sem alterações.\nMediastino" in novo, novo)
novo, f = ap("#6: (apagar)")
confere("F2 apagar uma linha", f == "dif" and "Mediastino" not in novo and novo.count("\n") == LAUDO_TC.count("\n") - 1,
        novo)
confere("F2 SEM MUDANÇAS devolve o laudo como está", ap("SEM MUDANÇAS") == (LAUDO_TC, "sem_mudancas"))
confere("F2 SEM MUDANÇAS. (com ponto)", ap("Sem mudanças.")[1] == "sem_mudancas")
novo, f = ap("```\n#4: Parênquima pulmonar:  nódulo.\n```")
confere("F2 bloco de código em volta é tolerado", f == "dif" and "nódulo." in novo, (f, novo))
inteiro = "TOMOGRAFIA\n\nlaudo todo reescrito"
confere("F3 a IA devolveu o laudo inteiro: vale o inteiro", ap(inteiro) == (inteiro, "inteiro"))
confere("F3 metade remendo, metade texto: inválida", ap("#4: x\ntexto solto")[0] is None)
confere("F3 linha fora do laudo: inválida", ap("#99: x")[0] is None)
confere("F3 a mesma linha trocada duas vezes: inválida", ap("#4: x\n#4: y")[0] is None)
confere("F3 linha trocada por nada: inválida", ap("#4:")[0] is None)
confere("F3 resposta cortada no teto: inválida",
        ap("[a IA parou no limite de tamanho (4000 tokens): ...]\n#4: x")[0] is None)
confere("F3 apagar mais da metade: inválida",
        ap("\n".join("#%d: (apagar)" % i for i in range(1, 8)))[0] is None)
ped_col = "LAUDO NA TELA:\nRM DA COLUNA LOMBAR\n\nANÁLISE:\nL1: sem alterações.\nL2: sem alterações.\n" \
          "L4-L5: abaulamento discal.\nL5-S1: sem alterações.\n\nCONCLUSÃO:\nAbaulamento em L4-L5."
novo, f = nuvem.aplicar_diferenca(ped_col, "#4: L2: discreta desidratação discal.")
confere("F3 coluna: 'L2:' do laudo não se confunde com o número da linha",
        f == "dif" and "L2: discreta desidratação discal." in novo and "L1: sem alterações." in novo, novo)

# integração: o botão de IA da folha
c = gravar_config()
zerar()
RESPOSTAS.append("#4: Parênquima pulmonar:  nódulo de 6 mm no lobo superior direito.")
r = roteador.ia_no_texto(LAUDO_TC)
corpo = CHAMADAS[-1] if CHAMADAS else {}
confere("F4 botão de IA: a folha volta com só a linha trocada",
        r.get("ok") and r.get("formato") == "dif" and r.get("texto") == esperado, r)
confere("F4 o pedido leva os números, o prompt de sistema não muda (cache)",
        "#1: **TOMOGRAFIA" in usuario(corpo) and "RESPOSTA POR DIFERENÇA" not in sistema(corpo))
zerar()
RESPOSTAS.extend(["#4: x\ntexto que não é remendo", "LAUDO INTEIRO NA 2a"])
r = roteador.ia_no_texto(LAUDO_TC)
confere("F5 remendo fora do formato: 2a chamada no modo antigo",
        r.get("texto") == "LAUDO INTEIRO NA 2a" and r.get("formato") == "inteiro_apos_dif" and len(CHAMADAS) == 2
        and "#1:" not in usuario(CHAMADAS[1]), (r, len(CHAMADAS)))
confere("F5 o recibo soma as duas chamadas", (r.get("custo_usd") or 0) > 0, r)
zerar()
r = roteador.ia_no_texto("Paciente: Fulano de Tal\n" + LAUDO_TC)
confere("F6 número na linha não esconde 'Paciente:' da triagem", not CHAMADAS and
        str(r.get("motivo", "")).startswith("nuvem_bloqueada"), r)
zerar()
r = roteador.ia_no_texto("TC DE TÓRAX\nNódulo de 6 mm.")
confere("F7 laudo curto vai inteiro, sem número", CHAMADAS and "#1:" not in usuario(CHAMADAS[-1]))
zerar()
gravar_config({"saida_por_diferenca": False})
r = roteador.ia_no_texto(LAUDO_TC)
confere("F7 desligada no config: sem número", CHAMADAS and "#1:" not in usuario(CHAMADAS[-1]))
gravar_config()
zerar()
r = roteador.ia_no_texto(LAUDO_TC, ditado="derrame pleural pequeno à direita")
confere("F7 botão de raciocínio (ditado): sem número", CHAMADAS and "#1:" not in usuario(CHAMADAS[-1]))
zerar()
LAUDO_RX = LAUDO_TC.replace("TOMOGRAFIA COMPUTADORIZADA DO TÓRAX", "RADIOGRAFIA DO TÓRAX")
r = roteador.ia_no_texto(LAUDO_RX)
confere("F7 RX na linha 'Só formatar' (trava de conferência): sem número",
        CHAMADAS and "#1:" not in usuario(CHAMADAS[-1]), usuario(CHAMADAS[-1])[:200] if CHAMADAS else "")
zerar()
RESPOSTAS.append("SEM MUDANÇAS")
novo, origem = roteador.revisar_laudo_inteiro(LAUDO_TC)
confere("F8 'revisar laudo' (Ctrl+Alt+A) também por diferença", origem == "nuvem" and novo == LAUDO_TC and
        CHAMADAS and "#1:" in usuario(CHAMADAS[-1]), (origem, novo))
zerar()
RESPOSTAS.append("#10: Nódulo pulmonar de 6 mm no lobo superior direito.")
novo, origem = roteador.instruir_laudo(LAUDO_TC, "ponha a medida na conclusão")
confere("F8 instrução sobre o laudo selecionado também", origem == "nuvem" and
        novo.endswith("Nódulo pulmonar de 6 mm no lobo superior direito."), novo)
ult = open(nuvem.LOG, encoding="utf-8").read().strip().split("\n")[-1]
confere("F9 log diz formato=dif", "formato=dif" in ult, ult)

print("")
print("fase 1: tudo certo" if not falhas else "fase 1: %d FALHA(S)" % len(falhas))
sys.exit(1 if falhas else 0)
