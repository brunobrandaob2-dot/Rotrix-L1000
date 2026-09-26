# -*- coding: utf-8 -*-
"""Correções ditas pelo próprio radiologista, dentro do app.

Você escreve o que saiu errado ("risartrose é com z", "não escrever 'Partes
moles sem alterações' no raio x de punho") e o roteador aplica na hora:

  ouvido        troca fixa do reconhecimento de voz  -> dados/ouvido.tsv
  tirar         frase que não deve sair no laudo     -> dados/minhas_regras.json
  acrescentar   frase que deve sair sempre            -> dados/minhas_regras.json
  nota          o que não dá para aplicar sozinho     -> dados/correcoes.jsonl

Tudo é reversível (cada regra tem um código e um "desfazer") e nada é enviado
para fora do computador, a não ser que você peça a ajuda da IA — e aí vai só o
seu texto de correção, nunca o laudo do paciente.
"""
import json
import os
import random
import re
import time
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")
ARQ_REGRAS = os.path.join(DADOS, "minhas_regras.json")
ARQ_LOG = os.path.join(DADOS, "correcoes.jsonl")
ARQ_OUVIDO = os.path.join(DADOS, "ouvido.tsv")

_PALAVRA = r"[0-9A-Za-zÀ-ÿ][0-9A-Za-zÀ-ÿ\-']*(?:\s+[0-9A-Za-zÀ-ÿ\-']+){0,3}"

# "troque X por Y", "X, o certo é Y", "escreveu X, era Y"
_GRAFIA = [
    re.compile(r"\b(?:troq(?:ue|ar)|substitu(?:a|ir)|corrig(?:e|ir|a))\s+(?P<errado>%s)\s+por\s+(?P<certo>%s)" % (_PALAVRA, _PALAVRA), re.I),
    re.compile(r"\b(?P<errado>%s)[,;]?\s*(?:o\s+)?(?:certo|correto)\s+(?:é|e)\s+(?P<certo>%s)" % (_PALAVRA, _PALAVRA), re.I),
    re.compile(r"\b(?:escreve(?:u|ndo)?|saiu|apareceu|veio)\s+(?P<errado>%s)[,;]\s*(?:mas\s+)?(?:é|e|era|deveria ser|tem que ser)\s+(?P<certo>%s)" % (_PALAVRA, _PALAVRA), re.I),
    re.compile(r"\b(?P<errado>%s)\s+(?:deveria ser|tem que ser|era para ser)\s+(?P<certo>%s)" % (_PALAVRA, _PALAVRA), re.I),
]
_TIRAR = re.compile(r"\b(?:n[ãa]o\s+(?:escrev\w+|colocar?|por|p[õo]r|dizer|usar|sair)|tir(?:e|ar)|remov\w+|apag\w+|sum(?:a|ir) com)\s+"
                    r"(?:a\s+frase\s+|o\s+trecho\s+|essa\s+frase\s+|isso:?\s*)?['\"]?(?P<frase>[^'\"\n]{4,160})", re.I)
_ACRESCENTAR = re.compile(r"\b(?:sempre\s+)?(?:escrev\w+|coloc\w+|acrescent\w+|inclu\w+|p[õo]r|adicion\w+)\s+"
                          r"(?:a\s+frase\s+|isso:?\s*)?['\"]?(?P<frase>[^'\"\n]{4,160})", re.I)
_ESCOPO = re.compile(r"\b(?:n[oa]s?|em|para o|para a|do|da|de)\s+(?P<exame>(?:raio ?x|rx|radiografia|tomografia|tc|resson[âa]ncia|rm)\b[^,.;\n]{0,40})", re.I)
_CORTA_FIM = re.compile(r"\s*(?:\bno\b|\bna\b|\bnos\b|\bnas\b|\bem\b|\bpara\b|\bquando\b|\bporque\b|\bpois\b)\s+(?:raio ?x|rx|radiografia|tomografia|tc|resson[âa]ncia|rm)\b.*$", re.I)


def _n(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def _ler_regras():
    try:
        with open(ARQ_REGRAS, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("regras"), list):
            return d
    except (OSError, ValueError):
        pass
    return {"regras": []}


def _gravar_regras(d):
    os.makedirs(DADOS, exist_ok=True)
    tmp = ARQ_REGRAS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARQ_REGRAS)


def _registrar(item):
    try:
        os.makedirs(DADOS, exist_ok=True)
        with open(ARQ_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _novo_id(usados=()):
    """Identificador único da regra.

    Duas regras gravadas no mesmo milissegundo ganhavam o mesmo id, e aí o
    desfazer mexia na regra errada (tirava a linha do ouvido.tsv de outra, ou
    de nenhuma). Agora o id leva um sufixo sorteado e é conferido contra os
    que já existem."""
    usados = set(usados)
    base = "%s-%03d" % (time.strftime("%Y%m%d%H%M%S"), int(time.time() * 1000) % 1000)
    for _ in range(50):
        novo = "%s-%s" % (base, "%04x" % random.randrange(0x10000))
        if novo not in usados:
            return novo
    return "%s-%s" % (base, os.urandom(4).hex())


_PREFIXO = re.compile(r"^(?:a\s+palavra|a\s+express[ãa]o|o\s+termo|a\s+frase|o\s+trecho|a\s+sigla)\s+", re.I)


def _limpar_frase(t):
    t = _CORTA_FIM.sub("", (t or "").strip())
    t = _PREFIXO.sub("", t)
    return t.strip(" .;,\t").strip()


def _regra_ouvido(errado, certo):
    """Grava a troca no dados/ouvido.tsv. Devolve True se entrou."""
    errado, certo = _limpar_frase(errado), _limpar_frase(certo)
    if not errado or not certo or _n(errado) == _n(certo):
        return False
    try:
        atual = open(ARQ_OUVIDO, encoding="utf-8").read() if os.path.exists(ARQ_OUVIDO) else ""
    except OSError:
        atual = ""
    if any(l.split("\t")[0].strip().lower() == errado.lower()
           for l in atual.splitlines() if "\t" in l and not l.startswith("#")):
        return False
    os.makedirs(DADOS, exist_ok=True)
    with open(ARQ_OUVIDO, "a", encoding="utf-8") as f:
        if atual and not atual.endswith("\n"):
            f.write("\n")
        f.write("%s\t%s\n" % (errado.lower(), certo))
    return True


def _aplicar_acao(a, texto_original):
    """Grava uma ação. Devolve a regra gravada (dict) ou None."""
    tipo = (a.get("tipo") or "").strip().lower()
    d = _ler_regras()
    regra = {"id": _novo_id(r.get("id") for r in d["regras"]), "tipo": tipo,
             "quando": time.strftime("%Y-%m-%d %H:%M"), "pedido": texto_original[:300]}
    if tipo == "ouvido":
        if not _regra_ouvido(a.get("errado"), a.get("certo")):
            return None
        regra.update(errado=_limpar_frase(a.get("errado")).lower(), certo=_limpar_frase(a.get("certo")))
    elif tipo in ("tirar", "acrescentar"):
        frase = _limpar_frase(a.get("frase"))
        if len(frase) < 4:
            return None
        regra.update(frase=frase, escopo=(a.get("escopo") or "").strip())
    else:
        regra.update(tipo="nota", texto=texto_original[:600])
    d["regras"].append(regra)
    _gravar_regras(d)
    _registrar(regra)
    return regra


# ---------------------------------------------------------------------------
# Ler o pedido do médico
# ---------------------------------------------------------------------------
def _escopo_do_texto(texto, achar_regiao):
    m = _ESCOPO.search(texto or "")
    if not m or achar_regiao is None:
        return ""
    try:
        return achar_regiao(m.group("exame")) or ""
    except Exception:
        return ""


def entender(texto, achar_regiao=None):
    """Lê o pedido e devolve as ações que dá para aplicar sozinho."""
    t = (texto or "").strip()
    if not t:
        return []
    acoes = []
    for rx in _GRAFIA:
        m = rx.search(t)
        if m:
            acoes.append({"tipo": "ouvido", "errado": _limpar_frase(m.group("errado")),
                          "certo": _limpar_frase(m.group("certo"))})
            break
    if not acoes:
        m = _TIRAR.search(t)
        if m:
            acoes.append({"tipo": "tirar", "frase": _limpar_frase(m.group("frase")),
                          "escopo": _escopo_do_texto(t, achar_regiao)})
    if not acoes:
        m = _ACRESCENTAR.search(t)
        if m:
            acoes.append({"tipo": "acrescentar", "frase": _limpar_frase(m.group("frase")),
                          "escopo": _escopo_do_texto(t, achar_regiao)})
    return acoes


_PROMPT_IA = """Você ajuda um radiologista a corrigir o gerador de laudos dele.
Leia o pedido e devolva SOMENTE um JSON, sem explicação, no formato:
{"acoes":[{"tipo":"ouvido","errado":"...","certo":"..."}]}
Tipos possíveis:
- "ouvido": o reconhecimento de voz escreveu uma palavra errada ("errado" = o que saiu, "certo" = o que devia sair).
- "tirar": uma frase não deve aparecer no laudo ("frase" = a frase, "escopo" = o exame, se ele disse).
- "acrescentar": uma frase deve aparecer sempre ("frase", "escopo").
- "nota": qualquer outra coisa ("texto" = o pedido resumido).
Não invente. Se não estiver claro, use "nota". Pedido do radiologista:
"""


def _pela_ia(texto, nuvem, config):
    if nuvem is None:
        return []
    try:
        c = dict(config or {})
        resposta, origem = nuvem.chamar(_PROMPT_IA + texto.strip()[:800], c, modo="analise")
    except Exception:
        return []
    if not resposta or origem != "nuvem":
        return []
    m = re.search(r"\{.*\}", resposta, re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return []
    acoes = d.get("acoes") if isinstance(d, dict) else None
    return [a for a in (acoes or []) if isinstance(a, dict)][:5]


def aplicar(texto, laudo="", usar_ia=False, nuvem=None, config=None, achar_regiao=None):
    """Aplica o que der e devolve o que foi feito."""
    texto = (texto or "").strip()
    if len(texto) < 4:
        return {"ok": False, "motivo": "texto_curto"}
    acoes = entender(texto, achar_regiao)
    por_ia = False
    if not acoes and usar_ia:
        acoes = _pela_ia(texto, nuvem, config)
        por_ia = bool(acoes)
    if not acoes:
        acoes = [{"tipo": "nota"}]
    feitas = []
    for a in acoes:
        r = _aplicar_acao(a, texto)
        if r:
            r["por_ia"] = por_ia
            feitas.append(r)
    _registrar({"quando": time.strftime("%Y-%m-%d %H:%M"), "pedido": texto[:600],
                "laudo": bool(laudo), "acoes": len(feitas), "ia": por_ia})
    return {"ok": True, "acoes": feitas, "por_ia": por_ia}


def listar(n=20):
    d = _ler_regras()
    return {"ok": True, "regras": d["regras"][-n:][::-1]}


def desfazer(id_regra):
    d = _ler_regras()
    onde = [i for i, r in enumerate(d["regras"]) if r.get("id") == id_regra]
    if not onde:
        return {"ok": False, "motivo": "nao_encontrada"}
    # regras antigas podem ter id repetido (id só com o milissegundo): tira uma
    # só, a mais recente, e mexe no ouvido.tsv exatamente dessa.
    i = onde[-1]
    r = d["regras"][i]
    del d["regras"][i]
    _gravar_regras(d)
    if r.get("tipo") == "ouvido" and os.path.exists(ARQ_OUVIDO):
        try:
            linhas = open(ARQ_OUVIDO, encoding="utf-8").read().splitlines()
            novas = [l for l in linhas
                     if not (("\t" in l) and l.split("\t")[0].strip().lower() == (r.get("errado") or "").lower())]
            with open(ARQ_OUVIDO, "w", encoding="utf-8") as f:
                f.write("\n".join(novas) + "\n")
        except OSError:
            pass
    _registrar({"quando": time.strftime("%Y-%m-%d %H:%M"), "desfez": r.get("id"), "tipo": r.get("tipo")})
    return {"ok": True, "regra": r}


# ---------------------------------------------------------------------------
# Aplicar as regras no laudo montado
# ---------------------------------------------------------------------------
_CACHE = {"mtime": None, "tirar": [], "acrescentar": []}


def _regras_ativas():
    try:
        mt = os.path.getmtime(ARQ_REGRAS)
    except OSError:
        return [], []
    if mt != _CACHE["mtime"]:
        d = _ler_regras()
        _CACHE.update(mtime=mt,
                      tirar=[r for r in d["regras"] if r.get("tipo") == "tirar"],
                      acrescentar=[r for r in d["regras"] if r.get("tipo") == "acrescentar"])
    return _CACHE["tirar"], _CACHE["acrescentar"]


def _mod_reg(caminho, e_titulo):
    """(modalidade, regiao) de um escopo ("msk/rx/punho") ou de uma origem de
    laudo ("mascara:usuario/rx/torax/normal", "rx_literal:msk/rx/punho/normal+1 ...")."""
    c = (caminho or "").split(":", 1)[-1].split("+", 1)[0].strip().strip("/")
    p = [x for x in c.split("/") if x]
    if e_titulo:
        return (p[-3], p[-2]) if len(p) >= 3 else None
    return (p[-2], p[-1]) if len(p) >= 2 else None


def _vale(regra, origem):
    """A regra vale neste laudo? Compara MODALIDADE e REGIÃO, não a pasta.

    26/09: com as máscaras dele na frente, "no raio x de tórax" virava escopo
    "usuario/rx/torax" — e a regra deixava de valer no dia em que ele voltasse
    para a máscara do Rotrix (medicina_interna/rx/torax). E a comparação por
    pedaço de texto fazia a regra do PÉ ("msk/rx/pe") valer na PERNA
    ("msk/rx/perna"). Agora: mesma modalidade e mesma região, exatas."""
    esc = (regra.get("escopo") or "").strip()
    if not esc:
        return True
    a, b = _mod_reg(esc, False), _mod_reg(origem, True)
    if a and b:
        return _n(a[0]) == _n(b[0]) and _n(a[1]) == _n(b[1])
    return _n(esc) in _n(origem or "")


def aplicar_regras(texto, origem=""):
    """Tira as frases que o médico mandou tirar e põe as que ele mandou pôr."""
    tirar, acrescentar = _regras_ativas()
    if not tirar and not acrescentar:
        return texto
    linhas = texto.split("\n")
    fora = [_n(r["frase"]) for r in tirar if _vale(r, origem) and r.get("frase")]
    if fora:
        linhas = [l for l in linhas if not (l.strip() and _n(l) in fora)]
    for r in acrescentar:
        if not _vale(r, origem) or not r.get("frase"):
            continue
        frase = r["frase"].rstrip(".;, ") + "."
        if any(_n(l) == _n(frase) for l in linhas):
            continue
        fim = len(linhas)
        for i, l in enumerate(linhas):
            if re.match(r"^\s*\*\*(?:COMPARA|CONCLUS|IMPRESS|OPINI)", l, re.I):
                fim = i
                break
        while fim > 0 and not linhas[fim - 1].strip():
            fim -= 1
        linhas.insert(fim, frase)
    return "\n".join(linhas)
