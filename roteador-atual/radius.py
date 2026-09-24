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

try:
    import dicom as _dicom          # leitura LOCAL do cabeçalho (nada sai daqui)
except Exception:                   # pragma: no cover - roteador sem o módulo
    _dicom = None

PASTA_PADRAO = os.path.join(os.path.expanduser("~"), "Downloads", "Radius Downloads")
AQUI = os.path.dirname(os.path.abspath(__file__))
_ARQ_SAL = os.path.join(AQUI, "dados", ".radius_sal")

_NOME_ESTADO = re.compile(r"^(?:state[\w.-]*\.json|[\w.-]*-state\.json|statistics\.json)$", re.I)
# cópia de segurança (state.beta-v3.backup.json): estudo antigo, não entra na fila
_COPIA = re.compile(r"backup|\.bak\b|\.old\b|\.tmp\b", re.I)
_MAX_BYTES = 60 * 1024 * 1024
# campos do paciente: nunca saem; os VALORES servem só para apagar pedaços de
# nome que apareçam na descrição
_SENSIVEL = re.compile(r"name|nome|patient|paciente|birth|nasc|cpf|mother|mae|phone|telefone|"
                       r"address|endereco|email|referring|physician|solicitante", re.I)
_ID_ESTUDO = ("accessionnumber", "studyinstanceuid", "studyuid", "studyid", "id", "uid", "key")
_ABERTO = re.compile(r"abert|open|view|curr|ativo|active|progress|laudando|reading|em leitura", re.I)
_FALHOU = re.compile(r"erro|error|fail|falh|cancel", re.I)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?")


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


def pastas_observadas(config=None):
    """Onde procurar exame: a pasta do Radius e a(s) pasta(s) extras.

    Por padrão entra também a pasta de downloads do navegador — é onde caem os
    exames que você baixa com o Radius fechado. Em `pastas_extras` (config.json)
    dá para trocar essa lista."""
    achadas, vistas = [], set()
    extras = (config or {}).get("pastas_extras")
    if extras is None:
        extras = [os.path.join(os.path.expanduser("~"), "Downloads")]
    for p in [pasta_radius(config)] + list(extras or []):
        if not p:
            continue
        c = os.path.abspath(os.path.expandvars(os.path.expanduser(str(p))))
        chave = os.path.normcase(c)
        if chave in vistas or not os.path.isdir(c):
            continue
        vistas.add(chave)
        achadas.append(c)
    return achadas


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


def eh_copia(caminho):
    return bool(_COPIA.search(os.path.basename(caminho)))


def eh_principal(caminho):
    """state*.json (não other-dicoms-state.json): o estado do estudo da vez."""
    b = os.path.basename(caminho).lower()
    return b.startswith("state") and not eh_copia(caminho)


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


_PALAVRA_FRACA = {"de", "da", "do", "dos", "das", "e", "di", "del", "van", "von"}


def iniciais(nome, maximo=3):
    """"FULANO BELTRANO DE TAL" -> "F.B.T." — o bastante para bater com a tela
    do RadiAnt, sem o nome. É a única coisa derivada do nome que sai daqui, e
    mesmo assim só para a tela do app: não entra em log nem vai para a IA."""
    bruto = str(nome or "").replace("^", " ")
    letras = []
    for palavra in _n(bruto).split():
        # número de acesso e data não são nome: "CICLANO SOUZA 555444333" -> "C.S."
        if palavra in _PALAVRA_FRACA or not palavra or palavra[0].isdigit():
            continue
        letras.append(palavra[0].upper())
        if len(letras) >= maximo:
            break
    return ".".join(letras) + "." if letras else ""


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


def ler_fila(pasta, extras=()):
    """[{id, modalidade, descricao, status, laudado, entrou, iniciais, origem, fonte}]
    — só campos permitidos. Junta o que o Radius registrou com o que apareceu
    na pasta por fora (baixado pelo navegador) e tira o que você já apagou.
    Relê só quando algum arquivo de estado ou a própria pasta muda."""
    arqs = _arquivos_cache(pasta)
    chave = []
    for a in arqs:
        try:
            chave.append((a, os.path.getmtime(a), os.path.getsize(a)))
        except OSError:
            pass
    for p in [pasta] + list(extras or []):
        try:
            chave.append((p, os.path.getmtime(p), 0))
        except OSError:
            pass
    chave = tuple(chave)
    if chave == _CACHE["chave"]:
        return [dict(x) for x in _CACHE["fila"]]
    fila = _ler_fila(arqs)
    try:
        fila = fila + soltos(pasta, fila)
        for extra in extras or ():
            # fora da pasta do Radius só entra o que tem cara de exame: a pasta
            # de downloads do navegador tem de tudo
            fila = fila + soltos(extra, fila, exigir_exame=True)
    except Exception:
        pass                      # a fila do Radius nunca cai por causa da varredura
    fora = apagados()
    if fora:
        # baixou de novo depois de apagar? volta para a lista
        fila = [x for x in fila
                if x["id"] not in fora or float(x.get("_mtime") or 0) > fora[x["id"]]]
    for x in fila:
        x.pop("_mtime", None)
    fila.sort(key=lambda x: (bool(x["laudado"]), x["entrou"] or ""))
    _CACHE.update(chave=chave, fila=fila)
    return [dict(x) for x in fila]


def _quando(v):
    """Hora de entrada na fila: só "AAAA-MM-DDTHH:MM:SS" (sem fração nem fuso)."""
    s = str(v or "").strip()
    m = _ISO.match(s)
    return m.group(0).replace(" ", "T") if m else _limpo(s, set())[:25]


# o que a leitura já viu no estudo da vez (só status e se veio descrição):
# vai para o diagnóstico, para ajustar sem ver dado de paciente
_VISTOS = {"status": {}, "com_descricao": 0, "sem_descricao": 0, "leituras": 0}


def _ler_fila(arqs, contar=True):
    sal = _sal()
    itens = {}
    for arq in arqs:
        if eh_copia(arq):
            continue
        obj = _carregar(arq)
        if obj is None:
            continue
        fonte = os.path.basename(arq)
        # estado da vez = state*.json com UM estudo na raiz; uma lista de
        # estudos é fila, e aí vale o status de aberto
        principal = eh_principal(arq) and isinstance(obj, dict) and _eh_estudo(obj)
        for d in _estudos(obj):
            sens = _tokens_sensiveis(d)
            item = {
                "id": _codigo(d, sal),
                "modalidade": _limpo(_valor(d, "modality"), sens).upper(),
                "descricao": _limpo(_valor(d, "studydescription"), sens),
                "status": _limpo(_valor(d, "status"), sens),
                "laudado": _laudado(_valor(d, "isreported")),
                "entrou": _quando(_valor(d, "queueenteredat")),
                "iniciais": iniciais(_valor(d, "patientname")),
                "origem": "radius",
                "principal": principal,
                "fonte": fonte,
            }
            if principal and contar:
                st = item["status"][:30]
                _VISTOS["status"][st] = _VISTOS["status"].get(st, 0) + 1
                _VISTOS["com_descricao" if item["descricao"] else "sem_descricao"] += 1
            velho = itens.get(item["id"])
            if velho is None:
                itens[item["id"]] = item
                continue
            # o mesmo estudo em dois arquivos: o estado da vez manda; o que
            # faltar num (descrição vazia, laudado desconhecido) vem do outro
            novo, outro = (item, velho) if principal and not velho["principal"] else (velho, item)
            for campo in ("modalidade", "descricao", "status", "entrou", "iniciais"):
                if not novo[campo] and outro[campo]:
                    novo[campo] = outro[campo]
            if novo["laudado"] is None:
                novo["laudado"] = outro["laudado"]
            elif outro["laudado"] is True:
                novo["laudado"] = True
            novo["principal"] = novo["principal"] or outro["principal"]
            itens[item["id"]] = novo
    if contar:
        _VISTOS["leituras"] += 1
    fila = list(itens.values())
    fila.sort(key=lambda x: (bool(x["laudado"]), x["entrou"] or ""))
    return fila


def atual(fila):
    """O estudo aberto agora.

    1) o estudo do estado da vez (state*.json), se não foi laudado nem deu erro;
    2) senão, o mais recente com status de aberto/em leitura e sem laudo."""
    da_vez = [x for x in fila if x.get("principal") and not x["laudado"]
              and not _FALHOU.search(x["status"] or "")]
    if da_vez:
        return max(da_vez, key=lambda x: x["entrou"] or "")
    abertos = [x for x in fila if not x["laudado"] and _ABERTO.search(x["status"] or "")]
    if not abertos:
        return None
    return max(abertos, key=lambda x: x["entrou"] or "")


_MODALIDADE = {"CT": "tomografia", "CR": "raio x", "DX": "raio x", "DR": "raio x", "RX": "raio x",
               "XR": "raio x", "RF": "raio x", "MR": "ressonancia", "US": "ultrassom", "MG": "mamografia"}
_PREFIXO_DESC = re.compile(r"^(?:tc|tomografia(?: computadorizada)?|rx|raio x|radiografia|rm|ressonancia"
                           r"(?: magnetica)?|us|usg|ultrassom|ultrassonografia|mamografia|mg)\b\s*"
                           r"(?:de|do|da|dos|das)?\s*")


# abreviações comuns nas descrições do Radius ("TORAX E ABD TOTAL")
_ABREV = [(re.compile(r"\babd\b|\babdom\b|\baabd\b"), "abdome"),
          (re.compile(r"\bmmii\b"), "membros inferiores"),
          (re.compile(r"\bmmss\b"), "membros superiores"),
          (re.compile(r"\bcol\b"), "coluna")]
# "e+2 Angio ...": marca de estudos juntados, não faz parte do nome do exame
_MARCA_COMBO = re.compile(r"^\s*(?:e\s*)?\+\s*\d+\s*", re.I)


def cabecalho(item):
    """Abertura de ditado para o estudo: "raio x de torax pa e perfil".
    Sem descrição, "" (só a modalidade não diz a região)."""
    if not item:
        return ""
    mod = _MODALIDADE.get((item.get("modalidade") or "").split("\\")[0].strip())
    bruto = (item.get("descricao") or "").replace("•••", " ")
    desc = _n(_MARCA_COMBO.sub("", bruto))
    if not mod or not desc:
        return ""
    for rx, troca in _ABREV:
        desc = rx.sub(troca, desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    if mod == "tomografia" and re.match(r"angio\b|angiotomografia\b", desc):
        mod, desc = "angiotomografia", re.sub(r"^(?:angio|angiotomografia)\s*(?:de|do|da|dos|das)?\s*", "", desc)
    desc = _PREFIXO_DESC.sub("", desc).strip()
    return (mod + " de " + desc).strip() if desc else ""


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
    agora = time.time()
    for a in arqs:
        rel = os.path.relpath(a, pasta)
        if os.path.dirname(rel):              # nome de subpasta pode ter nome de paciente
            rel = "(subpasta)" + os.sep + os.path.basename(a)
        try:
            tam = os.path.getsize(a) // 1024
            idade = int((agora - os.path.getmtime(a)) // 60)
        except OSError:
            tam, idade = -1, -1
        marca = " [cópia de segurança: fora da fila]" if eh_copia(a) else \
                (" [estado da vez]" if eh_principal(a) else "")
        linhas.append("  - %s (%d KB, mudou há %d min)%s" % (rel, tam, idade, marca))
    linhas.extend(_resumo_fila(arqs))
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
        else:
            # statistics.json: histórico (Modality, Source, datas); só contagens
            regs = [d for d in (obj if isinstance(obj, list) else []) if isinstance(d, dict)]
            if regs:
                linhas.append("  registros: %d" % len(regs))
                linhas.append("  Modality: " + _contagem([_rotulo(_valor(d, "modality")) for d in regs], 12))
                linhas.append("  Source: " + _contagem([_rotulo(_valor(d, "source")) for d in regs], 12))
                dias = [str(_valor(d, "queueenteredat") or "")[:10] for d in regs]
                dias = sorted(x for x in dias if re.match(r"^\d{4}-\d{2}-\d{2}$", x))
                if dias:
                    linhas.append("  período: %s a %s (%d dias)" % (dias[0], dias[-1], len(set(dias))))
    return "\n".join(linhas) + "\n"


def _rotulo(v):
    """Valor curto de campo técnico (modalidade, origem); o resto vira "(outro)"."""
    s = str(v if v is not None else "").strip()
    return s if re.fullmatch(r"[A-Za-z][A-Za-z _-]{0,24}", s) else ("(vazio)" if not s else "(outro)")


def _resumo_fila(arqs):
    """Como a fila foi montada: estudo da vez, estudos repetidos entre arquivos."""
    linhas = [""]
    if not arqs:
        return linhas + ["fila montada: 0 estudo(s)", "estudo da vez: nenhum"]
    fila = _ler_fila(arqs, contar=False)
    sal = _sal()
    por_arquivo = {}
    for a in arqs:
        if eh_copia(a):
            continue
        obj = _carregar(a)
        if obj is None:
            continue
        por_arquivo[os.path.basename(a)] = {_codigo(d, sal) for d in _estudos(obj)}
    vistos = {}
    for ids in por_arquivo.values():
        for i in ids:
            vistos[i] = vistos.get(i, 0) + 1
    linhas.append("fila montada: %d estudo(s); em mais de um arquivo: %d"
                  % (len(fila), sum(1 for q in vistos.values() if q > 1)))
    at = atual(fila)
    if at:
        cab = cabecalho(at)
        linhas.append("estudo da vez: %s, status %s, descrição %s, laudado %s, cabeçalho %s"
                      % (at["modalidade"] or "?", at["status"] or "(vazio)",
                         "preenchida" if at["descricao"] else "VAZIA", at["laudado"],
                         "ok" if cab else "(nenhum)"))
    else:
        linhas.append("estudo da vez: nenhum")
    if _VISTOS["leituras"]:
        linhas.append("desde que o roteador abriu: %d leitura(s); status do estudo da vez: %s; "
                      "com descrição %d, sem descrição %d"
                      % (_VISTOS["leituras"], _contagem(list(_expandir(_VISTOS["status"]))) or "-",
                         _VISTOS["com_descricao"], _VISTOS["sem_descricao"]))
    return linhas


def _expandir(cont):
    for k, q in cont.items():
        for _ in range(min(q, 1000)):
            yield k


_ULTIMO_DIAG = {"t": 0.0}


def gravar_diagnostico_se_velho(pasta, destino, minutos=15):
    """Reescreve o diagnóstico de tempos em tempos (a fila muda ao longo do dia)."""
    if time.time() - _ULTIMO_DIAG["t"] < minutos * 60:
        return False
    return gravar_diagnostico(pasta, destino)


def gravar_diagnostico(pasta, destino):
    _ULTIMO_DIAG["t"] = time.time()
    try:
        texto = diagnostico(pasta)
        tmp = destino + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, destino)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Abrir no RadiAnt (Rotrix v2)
#
# O app marca dois exames na fila e manda abrir juntos. Daqui só sai o CAMINHO
# da pasta do estudo — nome de paciente continua sem sair do módulo. Se o
# Radius não guardar caminho nenhum, a resposta diz isso e ninguém chuta.
# ---------------------------------------------------------------------------
_CHAVE_CAMINHO = re.compile(r"path|pasta|folder|dir|file|arquivo|local|destino", re.I)

_RADIANT_CANDIDATOS = (
    r"%ProgramFiles%\\RadiAntViewer64bit\\RadiAntViewer.exe",
    r"%ProgramFiles%\\RadiAntViewer\\RadiAntViewer.exe",
    r"%ProgramFiles(x86)%\\RadiAntViewer\\RadiAntViewer.exe",
    r"%LOCALAPPDATA%\\Programs\\RadiAntViewer64bit\\RadiAntViewer.exe",
    r"%LOCALAPPDATA%\\RadiAntViewer\\RadiAntViewer.exe",
)


def _caminhos_no_estudo(d):
    """Valores do estudo que parecem caminho de pasta/arquivo."""
    out = []
    for k, v in (d or {}).items():
        if isinstance(v, str) and len(v) > 3 and _CHAVE_CAMINHO.search(str(k)):
            out.append(v)
    return out


def caminhos(pasta, ids):
    """{codigo: caminho existente} para os estudos pedidos."""
    sal = _sal()
    alvo = set(ids or [])
    achados = {}
    if not alvo:
        return achados
    for arq in achar_arquivos(pasta):
        if eh_copia(arq):
            continue
        obj = _carregar(arq)
        if obj is None:
            continue
        for d in _estudos(obj):
            cod = _codigo(d, sal)
            if cod not in alvo or cod in achados:
                continue
            for bruto in _caminhos_no_estudo(d):
                c = os.path.expandvars(bruto.strip().strip('"'))
                if os.path.isdir(c) or os.path.isfile(c):
                    achados[cod] = c
                    break
    return achados


_ARQ_APAGADOS = os.path.join(AQUI, "dados", "apagados.json")
_EXT_PACOTE = (".zip", ".rar", ".7z", ".iso", ".tar", ".gz")


def apagados():
    """{id: quando foi apagado}. Some da lista mesmo que o Radius ainda registre
    o estudo — mas se o mesmo exame for baixado DE NOVO depois disso, ele volta."""
    try:
        with open(_ARQ_APAGADOS, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    itens = d.get("itens")
    if isinstance(itens, dict):
        return {k: float(v or 0) for k, v in itens.items()}
    return {i: 0.0 for i in (d.get("ids") or [])}     # formato antigo


def _marcar_apagados(ids):
    fora = apagados()
    agora = time.time()
    for i in ids or []:
        fora[i] = agora
    try:
        os.makedirs(os.path.dirname(_ARQ_APAGADOS), exist_ok=True)
        with open(_ARQ_APAGADOS, "w", encoding="utf-8") as f:
            json.dump({"itens": fora}, f)
    except OSError:
        pass
    return fora


def _tamanho(caminho, limite=4000):
    """Bytes e quantos arquivos — sem abrir nada, só o que o sistema já sabe."""
    if os.path.isfile(caminho):
        try:
            return os.path.getsize(caminho), 1, False
        except OSError:
            return 0, 0, False
    total, n, cortou = 0, 0, False
    for raiz, _pastas, arquivos in os.walk(caminho):
        for a in arquivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
            n += 1
            if n >= limite:
                cortou = True
                return total, n, cortou
    return total, n, cortou


def _conhecidos(pasta):
    """O que já pertence a um estudo registrado pelo Radius: caminhos (e as
    pastas até a raiz) e os números de acesso/UID que aparecem no nome das
    pastas baixadas. Fica só na memória; nada disso sai do módulo."""
    vistos, numeros = set(), set()
    for arq in _arquivos_cache(pasta):
        if eh_copia(arq):
            continue
        obj = _carregar(arq)
        if obj is None:
            continue
        for d in _estudos(obj):
            for nome in _ID_ESTUDO:
                v = str(_valor(d, nome) or "")
                for n in re.findall(r"\d{5,}", v):
                    numeros.add(n)
            for bruto in _caminhos_no_estudo(d):
                c = os.path.abspath(os.path.expandvars(str(bruto).strip().strip('"')))
                raiz = os.path.abspath(pasta)
                # o caminho e todas as pastas até a raiz: uma subpasta que só
                # existe para guardar o estudo não é "exame baixado por fora"
                while True:
                    vistos.add(os.path.normcase(c))
                    pai = os.path.dirname(c)
                    if pai == c or os.path.normcase(c) == os.path.normcase(raiz):
                        break
                    c = pai
    return vistos, numeros


def _id_de_caminho(caminho):
    return hashlib.sha256((_sal() + "|pasta:" + os.path.normcase(os.path.abspath(caminho)))
                          .encode("utf-8")).hexdigest()[:12]


_MARCA_DICOM = re.compile(r"\.dcm$|\.dicom$|^dicomdir$", re.I)
_NOME_EXAME = re.compile(r"dicom|estudo|exame|imagem|study|radius", re.I)


def _parece_exame(caminho, nome):
    """É exame? A pasta tem um .dcm/DICOMDIR dentro, ou o .zip tem DICOM dentro
    (aí o cabeçalho é lido para confirmar). Serve para a pasta de downloads do
    navegador não virar uma lista de instaladores e boletos."""
    if os.path.isfile(caminho):
        if caminho.lower().endswith(".zip"):
            try:
                cab = _cabecalho_dicom(caminho, os.path.getmtime(caminho))
            except OSError:
                cab = {}
            if cab.get("modalidade") or cab.get("uid"):
                return True      # é um estudo, mesmo que o nome não diga nada
        return bool(_NOME_EXAME.search(nome))
    try:
        with os.scandir(caminho) as it:
            for i, e in enumerate(it):
                if _MARCA_DICOM.search(e.name):
                    return True
                if e.is_dir() and i < 40:
                    with os.scandir(e.path) as it2:
                        for j, e2 in enumerate(it2):
                            if _MARCA_DICOM.search(e2.name):
                                return True
                            if j > 60:
                                break
                if i > 200:
                    break
    except OSError:
        return False
    return bool(_NOME_EXAME.search(nome))


def _soltos_brutos(pasta, fila_radius=(), exigir_exame=False):
    """[(id, caminho, mtime, nome)] do que está na pasta e o Radius não registrou.
    Uso interno: o caminho tem o nome do paciente e não sai daqui."""
    if not pasta or not os.path.isdir(pasta):
        return []
    conhecidos, numeros = _conhecidos(pasta)
    del fila_radius
    achados = []
    try:
        entradas = sorted(os.scandir(pasta), key=lambda e: e.name)
    except OSError:
        return []
    for e in entradas:
        try:
            if e.name.startswith((".", "_")):
                continue
            if e.is_file() and (not e.name.lower().endswith(_EXT_PACOTE)
                                or _NOME_ESTADO.match(e.name)):
                continue
            caminho = os.path.abspath(e.path)
            if os.path.normcase(caminho) in conhecidos:
                continue
            # a pasta pode ser de um estudo do Radius sem FilePath no estado:
            # se o número de acesso dele está no nome, não é "baixado por fora"
            if any(n in e.name for n in numeros):
                continue
            info = e.stat()
            if exigir_exame and not _parece_exame(caminho, e.name):
                continue
        except OSError:
            continue
        achados.append((_id_de_caminho(caminho), caminho, _baixado_em(caminho, info), e.name))
    return achados


def _baixado_em(caminho, info=None):
    """Quando o exame chegou NESTE computador.

    Não serve o mtime sozinho: ZIP extraído carrega a data que o arquivo tinha
    dentro do pacote, que costuma ser a do exame, e aí a fila fica ordenada pela
    hora da aquisição em vez da hora do download. No Windows, st_ctime é a data
    de criação do arquivo aqui — é essa que responde "chegou antes ou depois?".
    Fora do Windows, st_ctime é a última troca de metadados; ainda assim a mais
    próxima da chegada. Na dúvida, a MAIS RECENTE das duas: um arquivo não pode
    ter chegado antes de existir."""
    try:
        st = info or os.stat(caminho)
    except OSError:
        return 0.0
    return max(getattr(st, "st_ctime", 0) or 0, st.st_mtime or 0)


_CAB = {}          # (caminho, mtime) -> cabeçalho lido; evita reler a cada 20 s


def _cabecalho_dicom(caminho, mtime):
    """Modalidade, descrição, data e iniciais lidas do cabeçalho, no disco.
    Só o cabeçalho, e nada disso sai do computador."""
    if _dicom is None:
        return {}
    chave = (os.path.normcase(caminho), round(mtime, 3))
    if chave in _CAB:
        return _CAB[chave]
    try:
        d = _dicom.de(caminho)
    except Exception:
        d = {}
    if len(_CAB) > 500:
        _CAB.clear()
    _CAB[chave] = d
    return d


def soltos(pasta, fila_radius=(), exigir_exame=False):
    """Exames que estão na pasta mas o Radius não registrou — os que você baixa
    pelo navegador.

    Da pasta vêm nome, data e tamanho; do DICOM vem só o cabeçalho (modalidade,
    descrição, data do exame e as iniciais). A imagem nunca é lida e nada disso
    sai do computador."""
    achados = []
    for cod, caminho, mtime, nome in _soltos_brutos(pasta, fila_radius, exigir_exame):
        bytes_, n, cortou = _tamanho(caminho)
        cab = _cabecalho_dicom(caminho, mtime)
        achados.append({
            "id": cod,
            "modalidade": (cab.get("modalidade") or "").upper(),
            "descricao": cab.get("descricao") or "",
            "status": "baixado por fora",
            "laudado": None,
            # A FILA SEGUE A ORDEM DE DOWNLOAD, não a hora do exame. O cabeçalho
            # DICOM traz a hora da aquisição, que pode ser de semanas atrás — o
            # exame antigo baixado agora ia parar no fim da lista. "entrou" é a
            # hora em que o arquivo chegou aqui; a do exame vai à parte.
            "entrou": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)),
            "quando_exame": cab.get("entrou") or "",
            "iniciais": cab.get("iniciais") or iniciais(os.path.splitext(nome)[0]),
            "origem": "pasta",
            "principal": False,
            "fonte": "pasta",
            "arquivos": n,
            "bytes": bytes_,
            "bytes_aprox": cortou,
            "lido_do_dicom": bool(cab.get("modalidade") or cab.get("uid")),
            "_mtime": mtime,
        })
    return achados


def _para_lixeira(caminho):
    """Manda para a Lixeira do Windows (dá para restaurar). Fora do Windows,
    move para uma subpasta "_apagados" ao lado — nada some de vez."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_uint16),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", wintypes.LPCWSTR)]

        FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION = 3, 0x0040, 0x0010
        FOF_SILENT, FOF_NOERRORUI = 0x0004, 0x0400
        op = SHFILEOPSTRUCTW()
        op.wFunc = FO_DELETE
        op.pFrom = os.path.abspath(caminho) + "\0\0"
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if r != 0 or op.fAnyOperationsAborted:
            raise OSError("SHFileOperation=%s" % r)
        return "lixeira"
    destino = os.path.join(os.path.dirname(os.path.abspath(caminho)), "_apagados")
    os.makedirs(destino, exist_ok=True)
    alvo = os.path.join(destino, os.path.basename(caminho))
    n = 1
    while os.path.exists(alvo):
        alvo = os.path.join(destino, "%s (%d)" % (os.path.basename(caminho), n))
        n += 1
    os.rename(caminho, alvo)
    return "_apagados"


def apagar(pasta, ids, config=None, extras=()):
    """Manda para a Lixeira os exames marcados e some com eles da lista.

    A resposta só traz contagem e motivo: caminho de pasta tem nome de paciente
    dentro e não sai daqui."""
    ids = list(ids or [])
    if not ids:
        return {"ok": False, "motivo": "nenhum_marcado"}
    alvos = dict(caminhos(pasta, ids))
    for p in [pasta] + list(extras or []):
        for cod, caminho, _mtime, _nome in _soltos_brutos(p):
            if cod in ids and cod not in alvos:
                alvos[cod] = caminho
    apagadas, falhas, onde = [], [], ""
    for cod in ids:
        c = alvos.get(cod)
        if not c or not os.path.exists(c):
            continue                       # sem arquivo no disco: só sai da lista
        try:
            onde = _para_lixeira(c)
            apagadas.append(cod)
        except Exception as e:
            falhas.append(type(e).__name__)
    _marcar_apagados(ids)
    _CACHE["chave"] = None                 # a lista é relida na próxima consulta
    del config
    return {"ok": not falhas, "apagados": len(apagadas), "pedidos": len(ids),
            "fora_da_lista": len(ids), "onde": onde,
            "motivo": "" if not falhas else "falhou_apagar", "erros": sorted(set(falhas))}


def executavel_radiant(config=None):
    """Caminho do RadiAnt: o da configuração, um dos lugares de sempre, ou o
    que o Windows registrou para abrir DICOM."""
    escolhido = (config or {}).get("radiant_exe") if isinstance(config, dict) else None
    if escolhido and os.path.isfile(escolhido):
        return escolhido
    for cand in _RADIANT_CANDIDATOS:
        c = os.path.expandvars(cand)
        if os.path.isfile(c):
            return c
    try:
        import winreg  # só existe no Windows
        for raiz, chave in ((winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\RadiAntViewer.exe"),
                            (winreg.HKEY_CURRENT_USER,
                             r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\RadiAntViewer.exe")):
            try:
                with winreg.OpenKey(raiz, chave) as k:
                    v = winreg.QueryValue(k, None)
                    if v and os.path.isfile(v):
                        return v
            except OSError:
                pass
    except ImportError:
        pass
    return None


def montar_comando(exe, caminhos_abrir, fechar_outras=True, arvore=False):
    """Uma linha de comando só, para tudo abrir na MESMA janela do RadiAnt.

    O manual do RadiAnt é específico: `-f` recebe VÁRIOS arquivos de uma vez
    (`-f "a.dcm" "b.dcm"`) e `-d` recebe VÁRIAS pastas. Repetir `-f` a cada
    caminho, e mandar pasta como se fosse arquivo, é o que fazia dois exames
    marcados abrirem separados — ou um deles não abrir.

    `-cl` fecha as outras janelas do RadiAnt, para o estudo novo não ir parar
    numa janela velha que ficou aberta do laudo anterior.

    Estudos do mesmo paciente carregados juntos aparecem agrupados sozinhos na
    lista de séries: o agrupamento é por PatientID, o RadiAnt faz.
    """
    pastas = [c for c in caminhos_abrir if os.path.isdir(c)]
    arquivos = [c for c in caminhos_abrir if not os.path.isdir(c)]
    args = [exe]
    if fechar_outras:
        args.append("-cl")
    if arvore and pastas:
        args.append("-b")
    if pastas:
        args.append("-d")
        args += pastas
    if arquivos:
        args.append("-f")
        args += arquivos
    return args


def abrir(pasta, ids, config=None, extras=()):
    """Abre os estudos marcados no RadiAnt, todos na mesma janela."""
    achados = dict(caminhos(pasta, ids))
    for p in [pasta] + list(extras or []):
        for cod, caminho, _mtime, _nome in _soltos_brutos(p):
            if cod in (ids or []) and cod not in achados:
                achados[cod] = caminho  # exame baixado por fora também abre
    if not achados:
        return {"ok": False, "motivo": "sem_caminho", "pedidos": len(ids or [])}
    exe = executavel_radiant(config)
    if not exe:
        return {"ok": False, "motivo": "radiant_nao_encontrado", "achados": len(achados)}
    cfg = config if isinstance(config, dict) else {}
    lista = [achados[cod] for cod in (ids or []) if achados.get(cod)]
    args = montar_comando(exe, lista,
                          fechar_outras=cfg.get("radiant_fechar_outras", True),
                          arvore=cfg.get("radiant_arvore", False))
    try:
        import subprocess
        subprocess.Popen(args, close_fds=True)
    except Exception as e:
        # só o tipo do erro: a mensagem do Windows costuma trazer o caminho
        # inteiro, e o caminho tem o nome do paciente na pasta.
        return {"ok": False, "motivo": "falhou_abrir", "erro": type(e).__name__}
    return {"ok": True, "abertos": len(achados), "pedidos": len(ids or [])}


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else PASTA_PADRAO
    sys.stdout.write(diagnostico(p))
