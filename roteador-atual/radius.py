# -*- coding: utf-8 -*-
"""
Fila do Radius: leitura LOCAL dos arquivos de estado do Radius.

Regras (LGPD, seção 17 da especificação):
- Só abre os arquivos de ESTADO pelo nome (state*.json, *-state.json,
  statistics.json). Nunca abre, lista para fora nem indexa DICOM ou pacotes.
- Do estudo, só saem Modality, StudyDescription, Status, IsReported e
  QueueEnteredAt. Nome, número de acesso e qualquer identificador nunca saem
  deste módulo; o estudo é identificado por um código embaralhado local.
- Nada daqui vai para a IA nem para log.

O diagnóstico (radius_estrutura.txt) descreve só a ESTRUTURA dos arquivos:
nomes de campos, tipos e contagens. Valores, só dos campos permitidos, e já
filtrados (sem pedaço de nome, sem números longos).
"""
import hashlib
import json
import os
import re
import secrets
import time
import unicodedata

PASTA_PADRAO = os.path.join(os.path.expanduser("~"), "Downloads", "Radius Downloads")
AQUI = os.path.dirname(os.path.abspath(__file__))
_ARQ_SAL = os.path.join(AQUI, "dados", ".radius_sal")

_NOME_ESTADO = re.compile(r"^(?:state[\w.-]*\.json|[\w.-]*-state\.json|statistics\.json)$", re.I)
_MAX_BYTES = 60 * 1024 * 1024
# campos do paciente: nunca saem; os VALORES servem só para apagar pedaços de
# nome que apareçam na descrição
_SENSIVEL = re.compile(r"name|nome|patient|paciente|birth|nasc|cpf|mother|mae|phone|telefone|"
                       r"address|endereco|email|referring|physician|solicitante", re.I)
_ID_ESTUDO = ("accessionnumber", "studyinstanceuid", "studyuid", "studyid", "id", "uid", "key")
_ABERTO = re.compile(r"abert|open|view|curr|ativo|active|progress|laudando|reading|em leitura", re.I)


def _n(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def _sal():
    try:
        with open(_ARQ_SAL, encoding="utf-8") as f:
            s = f.read().strip()
            if s:
                return s
    except OSError:
        pass
    s = secrets.token_hex(16)
    try:
        os.makedirs(os.path.dirname(_ARQ_SAL), exist_ok=True)
        with open(_ARQ_SAL, "w", encoding="utf-8") as f:
            f.write(s)
    except OSError:
        pass
    return s


def pasta_radius(config=None):
    p = (config or {}).get("radius_pasta") or PASTA_PADRAO
    return os.path.expandvars(os.path.expanduser(p))


def achar_arquivos(pasta, profundidade=2):
    """Arquivos de estado do Radius, só pelo NOME (nenhum outro arquivo é aberto)."""
    achados = []
    if not os.path.isdir(pasta):
        return achados
    base = pasta.rstrip("\\/").count(os.sep)
    for raiz, dirs, arqs in os.walk(pasta):
        if raiz.count(os.sep) - base >= profundidade:
            dirs[:] = []
        for a in arqs:
            if _NOME_ESTADO.match(a):
                achados.append(os.path.join(raiz, a))
    return sorted(achados)


def _carregar(caminho):
    try:
        if os.path.getsize(caminho) > _MAX_BYTES:
            return None
        with open(caminho, "rb") as f:
            bruto = f.read()
    except OSError:
        return None
    for cod in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return json.loads(bruto.decode(cod))
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def _chaves(d):
    return {str(k).lower(): k for k in d}


def _eh_estudo(d):
    k = _chaves(d)
    return "modality" in k and ("studydescription" in k or ("status" in k and "isreported" in k))


def _estudos(obj, profundidade=0):
    """Todos os dicionários que parecem um estudo, em qualquer nível."""
    if profundidade > 12:
        return
    if isinstance(obj, dict):
        if _eh_estudo(obj):
            yield obj
            return
        for v in obj.values():
            yield from _estudos(v, profundidade + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _estudos(v, profundidade + 1)


def _tokens_sensiveis(d, sensivel=False, prof=0):
    """Pedaços (3+ letras) dos valores de campos de paciente, também aninhados
    ("Patient": {"Name": ...})."""
    toks = set()
    if prof > 4:
        return toks
    if isinstance(d, dict):
        for k, v in d.items():
            s2 = sensivel or bool(_SENSIVEL.search(str(k)))
            if isinstance(v, str):
                if s2:
                    toks.update(w for w in _n(v).split() if len(w) >= 3)
            else:
                toks |= _tokens_sensiveis(v, s2, prof + 1)
    elif isinstance(d, list):
        for v in d:
            toks |= _tokens_sensiveis(v, sensivel, prof + 1)
    return toks


def _limpo(texto, sensiveis):
    """Texto de campo permitido, sem pedaço de nome e sem número longo."""
    if texto is None:
        return ""
    t = re.sub(r"\d{5,}", "•••", str(texto))
    if sensiveis:
        t = " ".join("•••" if _n(w) in sensiveis else w for w in t.split())
    return t.strip()[:80]


def _valor(d, nome):
    k = _chaves(d)
    return d.get(k[nome]) if nome in k else None


def _laudado(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return _n(v) in ("true", "sim", "yes", "1", "laudado", "reported")
    return None


def _codigo(d, sal):
    for nome in _ID_ESTUDO:
        v = _valor(d, nome)
        if v not in (None, ""):
            base = "%s:%s" % (nome, v)
            break
    else:
        base = json.dumps({k: d[k] for k in sorted(d, key=str) if not _SENSIVEL.search(str(k))},
                          sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256((sal + "|" + base).encode("utf-8")).hexdigest()[:12]


_CACHE = {"chave": None, "fila": [], "arqs": None, "t_arqs": 0.0, "pasta": None}


def _arquivos_cache(pasta):
    agora = time.time()
    if _CACHE["arqs"] is None or _CACHE["pasta"] != pasta or agora - _CACHE["t_arqs"] > 60:
        _CACHE.update(arqs=achar_arquivos(pasta), t_arqs=agora, pasta=pasta)
    return _CACHE["arqs"]


def ler_fila(pasta):
    """[{id, modalidade, descricao, status, laudado, entrou, fonte}] — só campos permitidos.
    Relê só quando algum arquivo de estado muda."""
    arqs = _arquivos_cache(pasta)
    chave = []
    for a in arqs:
        try:
            chave.append((a, os.path.getmtime(a), os.path.getsize(a)))
        except OSError:
            pass
    chave = tuple(chave)
    if chave == _CACHE["chave"]:
        return [dict(x) for x in _CACHE["fila"]]
    fila = _ler_fila(arqs)
    _CACHE.update(chave=chave, fila=fila)
    return [dict(x) for x in fila]


def _ler_fila(arqs):
    sal = _sal()
    itens = {}
    for arq in arqs:
        obj = _carregar(arq)
        if obj is None:
            continue
        fonte = os.path.basename(arq)
        for d in _estudos(obj):
            sens = _tokens_sensiveis(d)
            item = {
                "id": _codigo(d, sal),
                "modalidade": _limpo(_valor(d, "modality"), sens).upper(),
                "descricao": _limpo(_valor(d, "studydescription"), sens),
                "status": _limpo(_valor(d, "status"), sens),
                "laudado": _laudado(_valor(d, "isreported")),
                "entrou": _limpo(_valor(d, "queueenteredat"), set()),
                "fonte": fonte,
            }
            velho = itens.get(item["id"])
            if velho is None or (fonte.lower().startswith("state") and not velho["fonte"].lower().startswith("state")):
                itens[item["id"]] = item
            elif velho.get("laudado") is None and item["laudado"] is not None:
                velho["laudado"] = item["laudado"]
    fila = list(itens.values())
    fila.sort(key=lambda x: (bool(x["laudado"]), x["entrou"] or ""))
    return fila


def atual(fila):
    """O estudo aberto agora (status de aberto/em leitura e ainda não laudado)."""
    abertos = [x for x in fila if not x["laudado"] and _ABERTO.search(x["status"] or "")]
    if not abertos:
        return None
    return max(abertos, key=lambda x: x["entrou"] or "")


_MODALIDADE = {"CT": "tomografia", "CR": "raio x", "DX": "raio x", "DR": "raio x", "RX": "raio x",
               "XR": "raio x", "RF": "raio x", "MR": "ressonancia", "US": "ultrassom", "MG": "mamografia"}
_PREFIXO_DESC = re.compile(r"^(?:tc|tomografia(?: computadorizada)?|rx|raio x|radiografia|rm|ressonancia"
                           r"(?: magnetica)?|us|usg|ultrassom|ultrassonografia|mamografia|mg)\b\s*"
                           r"(?:de|do|da|dos|das)?\s*")


def cabecalho(item):
    """Abertura de ditado para o estudo: "raio x de torax pa e perfil"."""
    if not item:
        return ""
    mod = _MODALIDADE.get((item.get("modalidade") or "").split("\\")[0].strip())
    desc = _n(item.get("descricao"))
    if "•" in (item.get("descricao") or ""):
        desc = _n(item["descricao"].replace("•••", " "))
    if not mod:
        return ""
    desc = _PREFIXO_DESC.sub("", desc).strip()
    return (mod + " de " + desc).strip() if desc else mod


# ---------------------------------------------------------------------------
# Diagnóstico: só a estrutura (para ajustar a leitura sem ver dado de paciente)
# ---------------------------------------------------------------------------
_CHAVE_OK = re.compile(r"^[A-Za-z_][A-Za-z_]{0,40}$")


def _todos_tokens_sensiveis(obj, acc, prof=0):
    if prof > 12:
        return
    if isinstance(obj, dict):
        acc.update(_tokens_sensiveis(obj))
        for v in obj.values():
            _todos_tokens_sensiveis(v, acc, prof + 1)
    elif isinstance(obj, list):
        for v in obj:
            _todos_tokens_sensiveis(v, acc, prof + 1)


def _estrutura(obj, caminho, cont, sensiveis, prof=0):
    tipo = type(obj).__name__
    cont[(caminho or "(raiz)", tipo)] = cont.get((caminho or "(raiz)", tipo), 0) + 1
    if prof > 10:
        return
    if isinstance(obj, dict):
        muitas = len(obj) > 40
        for k, v in obj.items():
            ks = str(k)
            ok = not muitas and _CHAVE_OK.match(ks) and _n(ks) not in sensiveis
            _estrutura(v, "%s.%s" % (caminho, ks if ok else "{*}"), cont, sensiveis, prof + 1)
    elif isinstance(obj, list):
        for v in obj[:5000]:
            _estrutura(v, caminho + "[]", cont, sensiveis, prof + 1)


def _contagem(valores, n=40):
    c = {}
    for v in valores:
        c[v] = c.get(v, 0) + 1
    return " | ".join("%s: %d" % (k if k != "" else "(vazio)", q)
                      for k, q in sorted(c.items(), key=lambda x: -x[1])[:n])


def diagnostico(pasta):
    linhas = ["Radius: estrutura dos arquivos de estado (sem dados de paciente)",
              "gerado em: " + time.strftime("%Y-%m-%d %H:%M"),
              "pasta existe: " + ("sim" if os.path.isdir(pasta) else "NAO")]
    arqs = achar_arquivos(pasta)
    linhas.append("arquivos de estado encontrados: %d" % len(arqs))
    for a in arqs:
        rel = os.path.relpath(a, pasta)
        if os.path.dirname(rel):              # nome de subpasta pode ter nome de paciente
            rel = "(subpasta)" + os.sep + os.path.basename(a)
        try:
            tam = os.path.getsize(a) // 1024
        except OSError:
            tam = -1
        linhas.append("  - %s (%d KB)" % (rel, tam))
    for a in arqs:
        obj = _carregar(a)
        linhas.append("")
        linhas.append("== %s ==" % os.path.basename(a))
        if obj is None:
            linhas.append("  (não consegui ler como JSON)")
            continue
        sens = set()
        _todos_tokens_sensiveis(obj, sens)
        cont = {}
        _estrutura(obj, "", cont, sens)
        linhas.append("  campos (tipo, quantas vezes):")
        for (cam, tipo), q in sorted(cont.items())[:400]:
            linhas.append("    %s: %s (%d)" % (cam, tipo, q))
        est = list(_estudos(obj))
        linhas.append("  estudos reconhecidos: %d" % len(est))
        if est:
            fila = [{"modalidade": _limpo(_valor(d, "modality"), sens).upper(),
                     "descricao": _limpo(_valor(d, "studydescription"), sens),
                     "status": _limpo(_valor(d, "status"), sens),
                     "laudado": _laudado(_valor(d, "isreported")),
                     "entrou": re.sub(r"\d", "9", str(_valor(d, "queueenteredat") or ""))[:40]} for d in est]
            linhas.append("  Modality: " + _contagem([x["modalidade"] for x in fila]))
            linhas.append("  Status: " + _contagem([x["status"] for x in fila]))
            linhas.append("  IsReported: " + _contagem([str(x["laudado"]) for x in fila]))
            linhas.append("  QueueEnteredAt (formato): " + _contagem([x["entrou"] for x in fila], 3))
            linhas.append("  StudyDescription (40 mais comuns): " + _contagem([x["descricao"] for x in fila]))
            ids = [nome for nome in _ID_ESTUDO if any(_valor(d, nome) not in (None, "") for d in est)]
            linhas.append("  campo usado para o código do estudo: " + (ids[0] if ids else "(nenhum; usa os campos permitidos)"))
    return "\n".join(linhas) + "\n"


def gravar_diagnostico(pasta, destino):
    try:
        texto = diagnostico(pasta)
        tmp = destino + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, destino)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else PASTA_PADRAO
    sys.stdout.write(diagnostico(p))
