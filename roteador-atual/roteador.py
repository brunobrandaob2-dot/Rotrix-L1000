# -*- coding: utf-8 -*-
"""
Roteador de laudos — camada determinística sobre o Handy.

Fala o protocolo OpenAI (/v1/chat/completions) para que o Handy o use como
"provider custom" de pós-processamento. NÃO usa LLM: apenas busca no banco.

Regra de ouro: nunca trava e nunca inventa. Se não reconhecer o ditado,
devolve o texto exatamente como veio.
"""
import os as _os, sys as _sys
# Python embutido (Rotrix) nao poe a pasta do script no caminho: garante aqui
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import formato
import collections, json, re, sqlite3, sys, unicodedata, difflib, threading, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
try:
    import nuvem
except Exception:
    nuvem = None
try:
    import revisor
except Exception:
    revisor = None

BASE = os.environ.get("LAUDO_BASE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "base.sqlite")
HOST, PORT = "127.0.0.1", 8123
VERSAO = "2026-09-22.1"
LIMIAR = 0.74          # similaridade mínima para aceitar um gatilho
ORCAMENTO_S = 8.0      # teto de tempo; acima disso devolve o texto cru

COMANDOS = {
    "mascara": "mascara", "máscara": "mascara", "modelo": "mascara",
    "frase": "frase", "achado": "frase",
    "adendo": "adendo",
}

def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Banco:
    def __init__(self, caminho):
        self.caminho = caminho
        self.lock = threading.Lock()
        self.itens = []          # (tipo, gatilho_norm, titulo, texto)
        self.carregar()
    def carregar(self):
        with self.lock:
            self.itens = []
            self.meta = {}           # titulo -> (categoria, modalidade, regiao, subtipo)
            if not os.path.exists(self.caminho):
                print("AVISO: base.sqlite nao encontrado. Rode construir_base.py", file=sys.stderr)
                return
            self.mtime = os.path.getmtime(self.caminho)
            con = sqlite3.connect(self.caminho)
            try:
                rows = con.execute("SELECT tipo, gatilho_norm, titulo, texto, secao, conclusao, "
                                   "categoria, modalidade, regiao, subtipo FROM entradas").fetchall()
            except sqlite3.OperationalError:     # base antiga, sem metadados
                rows = [tuple(r) + ("", "", "", "") for r in con.execute(
                    "SELECT tipo, gatilho_norm, titulo, texto, secao, conclusao FROM entradas")]
            con.close()
            prio = {"mascara": 0, "achado": 1, "adendo": 2, "bloco": 3, "frase": 4}
            rows.sort(key=lambda r: prio.get(r[0], 5))      # sort estavel
            textos = {}
            for r in rows:
                if r[3]:
                    textos.setdefault(r[2], r[3])
            for r in rows:
                if not r[3]:            # forma curta gerada: o texto é o da máscara
                    r = (r[0], r[1], r[2], textos.get(r[2], "")) + tuple(r[4:])
                self.itens.append(tuple(r[:6]))
                self.meta.setdefault(r[2], tuple(x or "" for x in r[6:10]))
            print(f"base carregada: {len(self.itens)} gatilhos", flush=True)
    def atualizada(self):
        """Recarrega sozinho se a base.sqlite foi trocada no disco."""
        try:
            if os.path.getmtime(self.caminho) != getattr(self, "mtime", None):
                self.carregar()
        except OSError:
            pass
    def buscar(self, consulta_norm, tipo=None):
        tit, txt, score, _g = self.buscar2(consulta_norm, tipo)
        return tit, txt, score
    def buscar2(self, consulta_norm, tipo=None):
        """Como buscar(), mas devolve tambem o gatilho que casou."""
        cand = [i for i in self.itens if tipo is None or i[0] == tipo]
        # 1) exato
        for t, g, tit, txt, sec, con in cand:
            if g == consulta_norm:
                return tit, txt, 1.0, g
        # 2) prefixo/contido
        for t, g, tit, txt, sec, con in cand:
            if consulta_norm and (consulta_norm.startswith(g + " ") or g.startswith(consulta_norm + " ")):
                if abs(len(g) - len(consulta_norm)) <= 12:
                    return tit, txt, 0.95, g
        # 3) cobertura de tokens: o gatilho precisa estar quase todo dentro do ditado
        alvo = set(consulta_norm.split())
        melhor_cob, cob_score, cob_n = None, 0.0, 0
        for t, g, tit, txt, sec, con in cand:
            if t in ("frase", "bloco") and tipo is None:
                continue                      # frases so por comando explicito ou exato
            gt = g.split()
            if len(gt) < 2 and not (len(gt) == 1 and len(gt[0]) >= 6):
                continue
            achou, anatomia_ok = 0, True
            for w in gt:
                if w in alvo:
                    achou += 1
                elif len(w) >= 4 and difflib.get_close_matches(w, alvo, 1, 0.8):
                    achou += 1
                elif (len(w) >= 4 and w not in _GENERICAS) or len(w) <= 3 and w not in ("de", "do", "da", "e", "x"):
                    # palavra de anatomia/achado (ou curta, como "pe") faltando:
                    # o gatilho NAO serve, por mais que o resto coincida
                    anatomia_ok = False
                    break
            if not anatomia_ok:
                continue
            cob = achou / len(gt)
            if cob >= 0.8 and (len(gt) > cob_n or (len(gt) == cob_n and cob > cob_score)):
                melhor_cob, cob_score, cob_n = (tit, txt, g), cob, len(gt)
        if melhor_cob:
            return melhor_cob[0], melhor_cob[1], 0.90, melhor_cob[2]
        # 4) difuso
        melhor, score = None, 0.0
        alvo_set = set(consulta_norm.split())
        for t, g, tit, txt, sec, con in cand:
            if t == "bloco" and tipo is None:
                continue
            # palavra curta do gatilho ("pe", "mao", "tc") tem de estar EXATA no
            # ditado: "tc de pelve" nao pode virar "tc de pe" por semelhanca
            if any(len(w) <= 3 and w not in alvo_set for w in g.split()):
                continue
            # e toda palavra de ANATOMIA/achado do gatilho precisa de par no
            # ditado: "pelve" nao vira "perna", "pescoco" nao vira "pe"
            if any(len(w) >= 4 and w not in _GENERICAS and w not in alvo_set
                   and not difflib.get_close_matches(w, alvo_set, 1, 0.8)
                   for w in g.split()):
                continue
            r = difflib.SequenceMatcher(None, consulta_norm, g).ratio()
            if r > score:
                melhor, score = (tit, txt, g), r
        if melhor and score >= LIMIAR:
            return melhor[0], melhor[1], score, melhor[2]
        return None, None, score, ""

_GENERICAS = set("""tomografia tomografica computadorizada radiografia raio angio angiotomografia
normal normais sem com alteracoes alteracao significativas exame estudo contraste""".split())

BANCO = Banco(BASE)

# ---------- motor de slots ----------
# {nome|op1/op2}  -> se o ditado resolver, substitui; senao mantem [op1/op2]
# {nome}          -> se o ditado resolver, substitui; senao ___

def _lado(n):
    if re.search(r"\bbilatera", n): return "bilateral"
    if re.search(r"\bdireit", n):   return "direito"
    if re.search(r"\besquerd", n):  return "esquerdo"
    return None

def _lobo(n):
    if re.search(r"\blobo superior|\bapic", n): return "lobo superior"
    if re.search(r"\blingul", n):               return None   # lingula: lacuna visivel
    if re.search(r"\blobo medio", n):           return "lobo médio"
    if re.search(r"\blobo inferior|\bbasal", n): return "lobo inferior"
    return None

def _segmento(n):
    m = re.search(r"\bsegmento\s+([ivx]+|\d+)\b", n)
    return "segmento " + m.group(1).upper() if m else None

def _tamanho(texto):
    # "cinco milimetros", "dois virgula sete centimetros" -> digitos, via revisor
    if revisor is not None:
        try:
            texto = revisor.revisar(texto)
        except Exception:
            pass
    n = normalizar(texto)
    m2 = re.search(r"\b([a-z]+\s+virgula\s+[a-z]+)\s*(cent|mil|cm|mm)", n)
    if m2:
        v = _num_extenso(m2.group(1))
        if v:
            return v + (" cm" if m2.group(2).startswith(("cm","cent")) else " mm")
    # medida com 1, 2 ou 3 eixos: "0,6 cm", "2,5 x 2,6 cm", "3 x 4 x 5 mm"
    num = r"\d+(?:[.,]\d+)?"
    m = re.search(r"(%s(?:\s*(?:x|por)\s*%s){0,2})\s*(cm|mm|cent|mil)" % (num, num), texto, re.I)
    if not m: return None
    eixos = re.split(r"\s*(?:x|por)\s*", m.group(1), flags=re.I)
    v = " x ".join(e.replace(".", ",") for e in eixos)
    u = "cm" if m.group(2).lower().startswith(("cm", "cent")) else "mm"
    return v + " " + u

_UNI = {"zero":0,"um":1,"uma":1,"dois":2,"duas":2,"tres":3,"quatro":4,"cinco":5,
        "seis":6,"sete":7,"oito":8,"nove":9,"dez":10,"onze":11,"doze":12,"treze":13,
        "quatorze":14,"catorze":14,"quinze":15,"dezesseis":16,"dezessete":17,
        "dezoito":18,"dezenove":19,"vinte":20,"trinta":30}

def _num_extenso(n):
    """1,2 a partir de 'um virgula dois'. Devolve string ou None."""
    m = re.search(r"\b([a-z]+)\s+virgula\s+([a-z]+)\b", n)
    if m and m.group(1) in _UNI and m.group(2) in _UNI:
        return str(_UNI[m.group(1)]) + "," + str(_UNI[m.group(2)])
    return None

_LOBOS_CEREBRAIS = ["frontal","parietal","temporal","occipital","insular","cerebelar"]
def _lobo_cerebral(n):
    for l in _LOBOS_CEREBRAIS:
        if re.search(r"\b"+l, n): return l
    return None

def _lado_f(n):
    v = _lado(n)
    return {"direito": "direita", "esquerdo": "esquerda",
            "bilateral": "bilateral"}.get(v)

def _lado_a(n):
    v = _lado(n)
    return {"direito": "à direita", "esquerdo": "à esquerda",
            "bilateral": "bilateralmente"}.get(v)

def _contraste(n):
    if re.search(r"\bsem e com contraste|\bsem e com\b|\btrifasic|\bbifasic|\bmultifasic", n):
        return "sem e com"
    if re.search(r"\bsem contraste\b|\bsem injecao\b|\bsem uso de contraste", n):
        return "sem"
    if re.search(r"\bcom contraste\b|\bcontrastad|\bcom injecao\b", n):
        return "com"
    return None

def _nivel(n):
    """Nivel vertebral ditado: "l4", "l4 l5", "l4 sobre l5", "c5 c6" -> "L4", "L4-L5"."""
    m = re.search(r"\b([ctls])\s?(\d{1,2})(?:\s*(?:e|a|sobre|ate|)\s*([ctls])\s?(\d{1,2}))?\b", n)
    if not m:
        return None
    a = m.group(1).upper() + m.group(2)
    if m.group(3):
        return a + "-" + m.group(3).upper() + m.group(4)
    return a

_SO_GRAU = set("""leve leves discreta discreto discretas discretos moderada moderado moderadas
acentuada acentuado acentuadas importante importantes avancada avancado grave severa difusa difuso
a e direita direito esquerda esquerdo bilateral""".split())

def _nivel_listese(n):
    v = _nivel(n)
    if not v:
        return None
    if "-" in v:
        a, b = v.split("-")
        return "de %s sobre %s" % (a, b)
    return "de %s sobre o nível subjacente" % v

def _lobo_completo(n):
    """'lobo inferior esquerdo', 'lobo medio', 'lingula'. Sem lado -> None (fica ___)."""
    if re.search(r"\blobo medio\b", n):
        return "lobo médio"
    if re.search(r"\blingula\b", n):
        return "língula"
    l, lado = _lobo(n), _lado(n)
    if l and lado in ("direito", "esquerdo"):
        return "%s %s" % (l, lado)
    return None

EXTRATORES = {"lobo_completo": _lobo_completo, "nivel_listese": _nivel_listese, "nivel": _nivel, "lado": _lado, "lado_a": _lado_a, "lado_f": _lado_f, "lobo": _lobo,
              "contraste": _contraste,
              "segmento": _segmento, "lobo_cerebral": _lobo_cerebral}
PADRAO_SLOT = re.compile(r"\{(\??[A-Za-z_]+)(?::([^}|]*))?(?:\|([^}]*))?\}")

def preencher(texto, ditado, contexto=None):
    """Resolve os slots pelo ditado. Slot em MAIUSCULAS devolve em maiusculas.
    contexto = o cabecalho do exame ("rx de joelho direito"). Ele so e usado
    para LADO — nunca para medida, e nunca o lado de OUTRO achado do ditado.
    O que nao resolver fica VISIVEL: [op1/op2] ou ___."""
    def sub(m):
        nome, prefixo, opcoes = m.group(1), m.group(2), m.group(3)
        opcional = nome.startswith("?")
        nome = nome.lstrip("?")
        chave = nome.lower()
        fontes = [ditado]
        if contexto and contexto != ditado and chave.startswith("lado"):
            fontes.append(contexto)
        valor = None
        for f in fontes:
            if chave == "tamanho":
                valor = _tamanho(f)
            else:
                valor = (EXTRATORES.get(chave) or (lambda _: None))(normalizar(f))
            if valor:
                break
        if not valor and opcoes and not chave.startswith(("lado", "contraste")):
            # opcao dita com todas as letras ("acentuada", "grau 1", "medial")
            n0 = normalizar(ditado)
            def _dita(o):
                on = normalizar(o)
                if not on:
                    return False
                if re.fullmatch(r"[0-9ivx]+", on):     # "1", "II": so depois de "grau"
                    return re.search(r"\bgrau %s\b" % re.escape(on), n0) is not None
                return re.search(r"\b%s\b" % re.escape(on), n0) is not None
            achadas = [o for o in opcoes.split("/") if _dita(o)]
            if achadas:
                maior = max(achadas, key=len)
                if all(normalizar(o) in normalizar(maior) for o in achadas):
                    valor = maior
        if opcional:
            # {?nome:prefixo } ou {?nome|a/b}: some quando nao foi ditado
            return ((prefixo or "") + valor + " ") if valor else ""
        if valor:
            return valor.upper() if nome.isupper() else valor
        return "[" + opcoes + "]" if opcoes else "___"
    return PADRAO_SLOT.sub(sub, texto)

# ---------- composicao: mascara base + blocos ----------

SEPARADORES = re.compile(r"[,;]| com | e | mais |\.")
_DECIMAL = re.compile(r"(\d)\s*[,.]\s*(\d)")

def segmentar(texto):
    # protege "1,5 cm" e "1.5 cm" para o separador nao partir a medida ao meio
    protegido = _DECIMAL.sub(lambda m: m.group(1) + "\x00" + m.group(2), texto)
    partes = [p.replace("\x00", ",").strip()
              for p in SEPARADORES.split(protegido) if p and p.strip()]
    return partes or [texto]

def _bloco_do_segmento(seg, filtro):
    n = normalizar(seg)
    if len(n) < 4:
        return None
    alvo = set(n.split())
    melhor, melhor_chave = None, None
    for t, g, tit, txt, sec, con in BANCO.itens:
        if t != "bloco" or not filtro(BANCO.meta.get(tit, ("", "", "", ""))):
            continue
        gt = g.split()
        exatas = sum(1 for w in gt if w in alvo)
        parecidas = sum(1 for w in gt if w not in alvo and len(w) >= 5
                        and difflib.get_close_matches(w, alvo, 1, 0.85))
        if (exatas + parecidas) / len(gt) < 0.8:
            continue
        # criterio: mais palavras EXATAS, depois gatilho mais longo, depois menos
        # palavras so parecidas ("espondilolise" nao cai em "espondilolistese")
        chave = (exatas, len(gt), -parecidas)
        if melhor_chave is None or chave > melhor_chave:
            melhor, melhor_chave = (tit, txt, sec, con), chave
    return melhor

def achar_blocos(segmentos, meta=None):
    """Devolve [(titulo, texto, secao, conclusao, segmento)] sem repetir.
    Com meta (categoria, modalidade, regiao, _) da mascara base, procura
    primeiro os blocos da MESMA regiao e modalidade, depois da mesma
    modalidade, e so entao em qualquer lugar."""
    cat, mod, reg = (meta or ("", "", "", ""))[:3]
    # Bloco so da MESMA regiao e modalidade do exame. Buscar em outra regiao
    # colava "artrose" do ombro numa coluna. O que nao casar aparece VISIVEL
    # como "[nao encontrado no banco]" em vez de entrar no lugar errado.
    if reg:
        camadas = [lambda m: m[1] == mod and m[2] == reg]
    else:
        camadas = [lambda m: True]
    achados, vistos = [], set()
    for seg in segmentos:
        for filtro in camadas:
            melhor = _bloco_do_segmento(seg, filtro)
            if melhor:
                break
        if melhor and melhor[0] not in vistos:
            vistos.add(melhor[0])
            achados.append(melhor + (seg,))
    return achados

CABECALHOS = {"TECNICA", "INDICACAO CLINICA", "INDICACAO", "ANALISE", "RELATORIO",
              "ACHADOS", "COMPARACAO", "CONCLUSAO", "IMPRESSAO", "OPINIAO"}
_CAB_RX = re.compile(r"^\s*\**\s*([^\W\d_][^:*]{1,40}?)\s*:\s*\**")

def _cab(linha):
    """Nome normalizado do cabecalho de secao, ou None."""
    s = (linha or "").strip()
    if not s or s.startswith("-"):
        return None
    m = _CAB_RX.match(s)
    if not m:
        return None
    n = normalizar(m.group(1)).upper()
    return n if n in CABECALHOS else None

def _idx(linhas, nomes):
    return next((i for i, l in enumerate(linhas) if _cab(l) in nomes), None)

def _fim_secao(linhas, i):
    return next((j for j in range(i + 1, len(linhas)) if _cab(linhas[j])), len(linhas))

_NEGATIVA = re.compile(r"^(?:não há|não se|não são|ausência|sem |demais |restante)", re.I)

NORMAL = re.compile(r"sem altera\w+ significativ|sem anormalidades|dentro dos limites da normalidade$", re.I)

# linha de topico da analise: "Figado:  ..." / "Arterias carotidas comuns:  ..."
_ROTULO = re.compile(r"^\s*-?\s*[^\W\d_][^:.;]{0,70}:\s")

def dentro_analise(linhas, i):
    a = _idx(linhas, {"ANALISE", "RELATORIO", "ACHADOS"})
    return a is not None and a < i < _fim_secao(linhas, a)

def _sem_hifen(t):
    return re.sub(r"^\s*-\s+", "", t)

def montar(base_txt, blocos, ditado=None):
    linhas = base_txt.split("\n")
    extras_conclusao = []
    trocadas = {}          # rotulo normalizado -> indice da linha ja reescrita
    for tit, txt, secao, conclusao, seg in blocos:
        corpo = preencher(txt, seg, ditado)
        colocado = False
        if secao:
            alvo = normalizar(secao)
            if alvo in trocadas:
                # segundo achado na mesma estrutura: SOMA ao primeiro
                i = trocadas[alvo]
                if _ROTULO.match(linhas[i]):
                    resto = corpo.split(":", 1)[1].strip() if ":" in corpo else corpo.strip()
                    if resto:
                        resto = resto[0].upper() + resto[1:]
                        rot, _, atual = linhas[i].partition(":")
                        # a frase de normalidade do primeiro achado ("Não há nódulos...")
                        # sai, senão contradiz o segundo achado que entra agora
                        frases = re.split(r"(?<=[.])\s+", atual.strip())
                        frases = [f for f in frases if not _NEGATIVA.match(f)]
                        linhas[i] = rot + ":  " + " ".join(frases + [resto])
                else:
                    # mascara de frases diretas (radiografia): so acrescenta
                    linhas[i] = linhas[i].rstrip() + " " + _sem_hifen(corpo).strip()
                colocado = True
        if secao and not colocado:
            for i, l in enumerate(linhas):
                if _cab(l):
                    continue
                por_rotulo = ":" in l and normalizar(l.split(":", 1)[0]) == alvo
                nl = normalizar(l)
                por_frase = (not por_rotulo and dentro_analise(linhas, i)
                             and (nl == alvo or nl.startswith(alvo + " ")))
                if por_rotulo or por_frase:
                    trocadas[alvo] = i
                    linhas[i] = _sem_hifen(corpo)
                    # remove linhas de continuacao da linha substituida (as que nao
                    # abrem com "Rotulo:"), para o texto normal nao sobreviver ao
                    # lado do achado: "Nao ha sinais inflamatorios na regiao..."
                    # So no modo rotulo: na radiografia cada linha e uma frase propria.
                    j = i + 1
                    while (por_rotulo and j < len(linhas) and linhas[j].strip()
                           and not _ROTULO.match(linhas[j]) and not _cab(linhas[j])):
                        del linhas[j]
                    colocado = True
                    break
        if not colocado:
            # mascara ALTERADA ja traz a mesma frase (ex.: "Escoliose toracica de
            # convexidade ___" na mascara de escoliose): troca em vez de duplicar
            chave = normalizar(_sem_hifen(corpo).split(":", 1)[-1] if _ROTULO.match(corpo) else corpo).split()[:3]
            if len(chave) == 3:
                for i, l in enumerate(linhas):
                    if _cab(l) or not dentro_analise(linhas, i):
                        continue
                    nl = normalizar(l.split(":", 1)[-1] if _ROTULO.match(l) else l).split()[:3]
                    if nl == chave:
                        linhas[i] = _sem_hifen(corpo)
                        colocado = True
                        break
        if not colocado:
            a = _idx(linhas, {"ANALISE", "RELATORIO", "ACHADOS"})
            if a is not None:
                pos = _fim_secao(linhas, a)
                while pos - 1 > a and not linhas[pos - 1].strip():
                    pos -= 1
                linhas.insert(pos, _sem_hifen(corpo))
            else:
                c = _idx(linhas, {"CONCLUSAO", "IMPRESSAO", "OPINIAO"})
                linhas.insert(max((c if c is not None else len(linhas)) - 1, 0), corpo)
        if conclusao:
            c_txt = preencher(conclusao, seg, ditado).strip()
            c_txt = c_txt[:1].upper() + c_txt[1:]
            if normalizar(c_txt) not in {normalizar(x) for x in linhas + extras_conclusao}:
                extras_conclusao.append(c_txt)

    c = _idx(linhas, {"CONCLUSAO", "IMPRESSAO", "OPINIAO"})
    if extras_conclusao:
        if c is None:
            pass   # mascara sem conclusao (radiografia): o achado ja esta na analise
        else:
            f = _fim_secao(linhas, c)
            corpo = [l for l in linhas[c + 1:f] if l.strip() and not NORMAL.search(l.strip())]
            cauda = linhas[f:]
            linhas = linhas[:c + 1] + corpo + extras_conclusao + ([""] + cauda if cauda else [])

    # conclusao: um achado por linha, SEM numeracao (padrao do Bruno)
    c = _idx(linhas, {"CONCLUSAO", "IMPRESSAO", "OPINIAO"})
    if c is not None:
        f = _fim_secao(linhas, c)
        for j in range(c + 1, f):
            if linhas[j].strip():
                linhas[j] = re.sub(r"^\s*(?:\d+[.)]|-)\s*", "", linhas[j].strip())
    return "\n".join(linhas)

_CFG = {"mtime": None, "dados": {}}

def _config():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        mt = os.path.getmtime(p)
        if mt != _CFG["mtime"]:
            _CFG["dados"] = json.load(open(p, encoding="utf-8"))
            _CFG["mtime"] = mt
    except Exception:
        pass
    return _CFG["dados"]

def formatar_saida(texto):
    """Os cabecalhos vem marcados como **TECNICA:** no banco.
    formato_titulos = "texto"    -> tira as marcas (cola texto puro)
                      "rico"     -> mantem; o colar.exe converte em negrito
                      "markdown" -> mantem as marcas como estao"""
    modo = (_config().get("formato_titulos") or "texto").lower()
    if modo in ("rico", "markdown"):
        # rotulos da ANALISE ("Figado:") tambem em negrito
        return formato.negritar_rotulos(texto)
    return texto.replace("**", "")


# ---------- aprendizado: o que a nuvem corrigiu e o local deixou passar ----------
APRENDIZADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aprendizado.json")
_MAPA_HANDY = os.path.join(os.environ.get("APPDATA", ""), "com.pais.handy", "handy_radiology_map.tsv")
_mapa_cache = {"mtime": None, "fontes": set()}

def _fontes_do_mapa():
    try:
        mt = os.path.getmtime(_MAPA_HANDY)
        if mt != _mapa_cache["mtime"]:
            f = set()
            for l in open(_MAPA_HANDY, encoding="utf-8"):
                p = l.rstrip("\n").split("\t")
                if len(p) == 3 and not l.startswith("#"):
                    f.add(p[1].strip().lower())
            _mapa_cache.update(mtime=mt, fontes=f)
    except Exception:
        pass
    return _mapa_cache["fontes"]

def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# Palavras que NUNCA viram regra, mesmo que a nuvem as troque: lado, posicao,
# presenca/ausencia e grau. Uma regra dessas aplicada em silencio em todo ditado
# seria o pior defeito possivel do sistema.
_NUNCA_APRENDER = set("""direito direita esquerdo esquerda direitos direitas esquerdos esquerdas
bilateral bilaterais unilateral superior inferior medial lateral anterior posterior proximal
distal central periferico periferica cranial caudal ventral dorsal interno interna externo externa
maior menor leve moderado moderada acentuado acentuada discreto discreta aumento reducao
aumentado aumentada reduzido reduzida presenca ausencia presente ausente sem com nao ha
sinais normal normais anormal agudo aguda cronico cronica novo nova antigo antiga
primeiro segundo terceiro quarto quinto""".split())

def _aprender(antes, depois):
    """Guarda so PARES DE PALAVRAS (errado -> certo), nunca o laudo. Palavra que
    comeca com maiuscula no meio da frase e ignorada (pode ser nome)."""
    try:
        depois = "\n".join(l for l in depois.split("\n") if not l.startswith("[["))
        pa = re.findall(r"[^\W\d_]+", antes)
        pb = re.findall(r"[^\W\d_]+", depois)
        sm = difflib.SequenceMatcher(None, [w.lower() for w in pa], [w.lower() for w in pb], autojunk=False)
        conhecidas = _fontes_do_mapa()
        pares = []
        cand = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != "replace":
                continue
            if i2 - i1 == j2 - j1:                       # troca palavra a palavra
                cand += [(i, i + 1, j) for i, j in zip(range(i1, i2), range(j1, j2))]
            elif j2 - j1 == 1 and i2 - i1 == 2:          # "linfo nodo" -> "linfonodo"
                cand.append((i1, i2, j1))
        for i1, i2, j1 in cand:
            x = " ".join(pa[i1:i2]); y = pb[j1]
            if _sem_acento(y.lower()) in _NUNCA_APRENDER or any(
                    _sem_acento(w.lower()) in _NUNCA_APRENDER for w in pa[i1:i2]):
                continue
            if y[:1].isupper() and y[1:].islower() and x.islower():
                y = y.lower()          # a maiuscula era so do inicio da frase
            if len(y) < 4 or x.lower() == y.lower() or x.lower() in conhecidas:
                continue
            if any(w[0].isupper() for w in pa[i1:i2]) and i1 > 0:
                continue
            sim = difflib.SequenceMatcher(None, _sem_acento(x.lower().replace(" ", "")),
                                          _sem_acento(y.lower())).ratio()
            if sim >= (0.8 if i2 - i1 == 2 else 0.6):
                pares.append((x.lower(), y))
        if not pares:
            return
        try:
            d = json.load(open(APRENDIZADO, encoding="utf-8"))
        except Exception:
            d = {"pendentes": {}, "aprovados": [], "rejeitados": []}
        ja = set(d.get("aprovados", [])) | set(d.get("rejeitados", []))
        for x, y in pares:
            k = x + "\t" + y
            if k not in ja:
                d["pendentes"][k] = d["pendentes"].get(k, 0) + 1
        json.dump(d, open(APRENDIZADO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def revisar_local(texto):
    """Revisao deterministica do ditado livre. Nunca levanta excecao."""
    if revisor is None:
        return texto
    try:
        # com o processador de colagem ativo, os comandos falados ("parágrafo",
        # "nova linha", "vírgula"...) ficam com ELE, que vale para os dois atalhos
        # e tem a semantica que o Bruno refinou no v8
        pont = not _config().get("processador_colagem", False)
        return revisor.revisar(texto, pontuacao=pont)
    except Exception:
        return texto



# ---------------------------------------------------------------------------
# OUVIDO: corrige o que o reconhecimento de voz escreveu errado ANTES de
# procurar no banco. Duas camadas:
#  1. dados/ouvido.tsv — trocas fixas (editável: "na horta" -> "na aorta").
#  2. vocabulário do banco — palavra que não existe no banco é trocada pela
#     palavra do banco mais parecida ("antiromas" -> "ateromas"). Esta só vale
#     para ACHAR a máscara/bloco/frase; o texto que sai é sempre o do banco.
# ---------------------------------------------------------------------------
import difflib
_OUVIDO = {"mtime": None, "regras": []}
_ARQ_OUVIDO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "ouvido.tsv")

def _regras_ouvido():
    try:
        mt = os.path.getmtime(_ARQ_OUVIDO)
    except OSError:
        return []
    if mt != _OUVIDO["mtime"]:
        regras = []
        for l in open(_ARQ_OUVIDO, encoding="utf-8"):
            if l.startswith("#") or "\t" not in l:
                continue
            a, b = l.rstrip("\n").split("\t")[:2]
            a = normalizar(a)
            if a and b.strip():
                regras.append((re.compile(r"(?<![\w])" + r"\s+".join(map(re.escape, a.split())) + r"(?![\w])", re.I), b.strip()))
        regras.sort(key=lambda r: -len(r[0].pattern))
        _OUVIDO.update(mtime=mt, regras=regras)
    return _OUVIDO["regras"]

def ouvido_fixo(texto):
    """Aplica dados/ouvido.tsv. Compara sem acento, preserva o resto do texto."""
    regras = _regras_ouvido()
    if not regras:
        return texto
    # trabalha sobre uma versao sem acento alinhada caractere a caractere
    for rx, certo in regras:
        base = _sem_acento(texto).lower()
        partes, ult = [], 0
        for m in rx.finditer(base):
            partes.append(texto[ult:m.start()]); partes.append(certo); ult = m.end()
        if partes:
            partes.append(texto[ult:]); texto = "".join(partes)
    return texto

_VOCAB = {"n": None, "set": set(), "lista": []}
_CURTAS_OK = set("""com sem mais para pela pelo pelos pelas entre sobre apos ante como onde
frase frases achado achados adendo mascara modelo revisar revisao corrigir analise analisar
comparar recist direito direita esquerdo esquerda bilateral""".split())

def _vocab():
    if _VOCAB["n"] != len(BANCO.itens):
        c = collections.Counter()
        for t, g, tit, txt, sec, con in BANCO.itens:
            for w in (g + " " + normalizar(txt or "")).split():
                if len(w) >= 4 and not w.isdigit():
                    c[w] += 1
        _VOCAB.update(n=len(BANCO.itens), set=set(c), lista=[w for w, _ in c.most_common()])
    return _VOCAB

_PERTO = {}
def _mais_perto(w):
    v = _vocab()
    k = (v["n"], w)
    if k not in _PERTO:
        if len(_PERTO) > 20000:
            _PERTO.clear()
        c = difflib.get_close_matches(w, v["lista"], n=1, cutoff=0.78)
        _PERTO[k] = c[0] if c else w
    return _PERTO[k]

def ouvido_banco(n):
    """Troca, no texto NORMALIZADO, palavras fora do vocabulario do banco pela
    mais parecida do banco (>= 0,78). So para a busca."""
    v = _vocab()
    if not v["set"]:
        return n
    out = []
    for w in n.split():
        if len(w) < 5 or w in v["set"] or w.isdigit() or w in _CURTAS_OK:
            out.append(w); continue
        out.append(_mais_perto(w))
    return " ".join(out)

_VAZIAS = set("""de do da dos das no na nos nas em um uma o a os as e com sem por para ao aos
que se ou mais muito pouco pequeno pequena pequenos pequenas grande""".split())

def _raiz(w):
    return w[:5] if len(w) > 5 else w

def _frase_aproximada(consulta):
    """Frase que o ditado nao casou literalmente: procura frase e bloco cujo
    gatilho tenha TODAS as palavras de conteudo presentes no ditado, pela raiz
    (ateromas ~ ateromatose, aorta ~ aortica). Prefere o gatilho mais completo."""
    pal = [w for w in consulta.split() if w not in _VAZIAS]
    if not pal:
        return None
    raizes = {_raiz(w) for w in pal} | {w[:4] for w in pal if len(w) >= 4}
    melhor, chave_m = None, None
    for t, g, tit, txt, sec, con in BANCO.itens:
        if t not in ("frase", "bloco") or not txt:
            continue
        gp = [w for w in g.split() if w not in _VAZIAS]
        if not gp:
            continue
        ok = sum(1 for w in gp if _raiz(w) in raizes or w[:4] in raizes)
        if ok < len(gp):
            continue
        # quantas palavras do ditado o gatilho explica
        cob = sum(1 for w in pal if any(_raiz(w) == _raiz(x) or w[:4] == x[:4] for x in gp))
        chave = (cob, len(gp), t == "frase")
        if chave_m is None or chave > chave_m:
            melhor, chave_m = (tit, txt), chave
    if melhor is None or chave_m[0] < max(1, (len(pal) + 1) // 2):
        return None
    tit, txt = melhor
    # bloco de TC vem como "Rotulo:  texto": mantem o rotulo (entra na ANALISE)
    linha = next((l for l in txt.splitlines() if l.strip()), "")
    return tit, linha.strip()


def ouvido_bruto(bruto):
    """ouvido_banco aplicado palavra a palavra no texto cru (mantem pontuacao)."""
    v = _vocab()
    if not v["set"]:
        return bruto
    def troca(m):
        w = m.group(0)
        nw = normalizar(w)
        if " " in nw or len(nw) < 5 or nw in v["set"] or nw.isdigit() or nw in _CURTAS_OK:
            return w
        c = _mais_perto(nw)
        return c if c != nw else w
    return re.sub(r"[^\W\d_]+", troca, bruto)


_PREAMBULO = re.compile(r"^\s*(?:(?:e|é|eh|ah|ahn|hum|oi|olá|ola|ok|então|entao|bom|te|"
                        r"descreva|descreve|descriva|escreva|escreve|me\s+d[eê])[\s,.:;!?-]+)+", re.I)

_INSTRUCAO = re.compile(
    r"^\s*(?:(?:e|é|ok|então|entao|agora)[\s,.:;]+)*"
    r"(?:(?:revise|revisar|corrija|corrigir|revisa)\s*(?:o\s+laudo\s*)?[,.:;]?\s*(?:e\s+)?)?"
    r"(?P<verbo>fa[çc]a|melhore|descreva|reescreva|resuma|deixe|padronize|acrescente|inclua|"
    r"retire|tire|remova|organize|reorganize|transforme|ajuste|detalhe|simplifique|"
    r"refa[çc]a|complete|enxugue|reformule|substitua|troque|coloque|escreva|redija)\b", re.I)

def _sem_preambulo(t):
    """Tira do INICIO palavras que o Whisper acrescenta ou que nao sao comando
    ("e revisar laudo", "descreva tomografia de cranio"). So se sobrar texto."""
    r = _PREAMBULO.sub("", t)
    return r if r.strip() else t


def rotear(ditado):
    """Devolve (texto_final, origem). Nunca levanta excecao."""
    bruto = (ditado or "").strip()
    if not bruto:
        return "", "vazio"
    original = bruto
    bruto = ouvido_fixo(_sem_preambulo(bruto))
    n = normalizar(bruto)

    # --- instrucao sobre o laudo que esta na tela ---
    # "revise e faca uma melhor descricao do AVC", "melhore a conclusao"...
    # copia o campo do laudo, manda laudo + instrucao, cola o laudo inteiro de volta
    mi = _INSTRUCAO.match(original)
    if mi and mi.group("verbo").lower() in ("descreva", "escreva", "redija", "coloque"):
        # "descreva tomografia de cranio" e pedido de MASCARA, nao instrucao
        resto_v = original[mi.end("verbo"):].strip(" ,.:;")
        if resto_v and _cabecalho_do_exame(resto_v, normalizar(resto_v))[3] is not None:
            mi = None
    if mi and os.name == "nt" and nuvem is not None and nuvem.config().get("ativa"):
        instrucao = original[mi.start("verbo"):].strip()
        try:
            import atalho_win
            sel = atalho_win.copiar_selecao()
        except Exception:
            sel = ""
        if sel:
            novo, origem = instruir_laudo(sel, instrucao)
            if novo and origem == "nuvem":
                return formato.padronizar(novo), "nuvem_instrucao"
            return sel, origem

    # --- rota de nuvem: so por gatilho explicito ---
    if nuvem is not None:
        c = nuvem.config()
        if c.get("ativa"):
            # os gatilhos mais longos primeiro, para "revisar laudo" nao ser
            # capturado por "revisar"
            rotas = ([(g, "revisao") for g in c.get("gatilhos_revisao", [])] +
                     [(g, "analise") for g in c.get("gatilhos", [])])
            rotas.sort(key=lambda x: -len(normalizar(x[0])))
            for g, modo in rotas:
                gn = normalizar(g)
                if gn and (n == gn or n.startswith(gn + " ")):
                    pedido = bruto[len(g):].strip(" ,.:;-") or bruto
                    if modo == "revisao" and os.name == "nt" and \
                            normalizar(pedido) in ("", "laudo", "o laudo", "texto", "o texto", n):
                        try:
                            import atalho_win
                            sel = atalho_win.copiar_selecao()
                        except Exception:
                            sel = ""
                        if sel:
                            novo, origem = revisar_laudo_inteiro(sel)
                            if novo and origem == "nuvem":
                                return formato.padronizar(novo), "nuvem_laudo_inteiro"
                            return sel, origem
                    if modo == "revisao":
                        # manda para a nuvem o texto JA passado pela revisao
                        # local: o modelo so precisa resolver o que sobrou
                        pedido = revisar_local(pedido)
                    texto, origem = nuvem.chamar(pedido, c, modo=modo)
                    if texto is not None:
                        if modo == "revisao" and origem == "nuvem":
                            _aprender(pedido, texto)
                        return texto, origem
                    # nuvem indisponivel: cai na revisao local e segue
                    if modo == "revisao":
                        return revisar_local(pedido), "revisado_local_sem_nuvem"
                    break

    # OUVIDO: o que o reconhecimento de voz errou, antes de procurar
    bruto_fixo = ouvido_fixo(original)       # tsv: vale tambem para texto livre
    bruto = ouvido_bruto(bruto)              # vocabulario do banco: so para achar
    n = normalizar(bruto)

    primeira = n.split(" ")[0] if n else ""
    tipo, resto = None, n
    for palavra, t in COMANDOS.items():
        if primeira == normalizar(palavra):
            tipo, resto = t, n[len(primeira):].strip()
            break

    segmentos = segmentar(bruto)

    if tipo in (None, "mascara"):
        cab_raw, cab_norm, tit, txt = _cabecalho_do_exame(bruto, resto)
        if txt is None and len(segmentos) > 1:
            # sem gatilho no inicio: a base sai do primeiro segmento
            cab_raw = segmentos[0]
            cab_norm = normalizar(cab_raw)
            for palavra in COMANDOS:
                pn = normalizar(palavra)
                if cab_norm.startswith(pn + " "):
                    cab_norm = cab_norm[len(pn):].strip()
                    break
            tit, txt, _sc, g = BANCO.buscar2(cab_norm, "mascara")
            if txt is not None:
                cab_norm = g
        if txt is not None:
            resto_raw = bruto[len(cab_raw):] if bruto.startswith(cab_raw) else \
                        " ".join(segmentos[1:])
            resto_raw = re.sub(r"^[\s,.;:]*(?:com\b|e\b|mais\b)?[\s,.;:]*", "", resto_raw, flags=re.I)
            restantes = segmentar(resto_raw) if resto_raw.strip() else []
            # lado do ESTUDO = o que vem no cabecalho e nos trechos sem achado
            # logo depois dele ("rx de joelho, direito, com artrose")
            lead = []
            for x in restantes:
                if _relevante(x):
                    break
                lead.append(x)
            ctx = " ".join([cab_raw] + lead)
            cobertos = set(cab_norm.split())
            restantes = [x for x in restantes if not _coberto(x, cobertos)]
            # "tomografia de abdome SEM CONTRASTE com alteracoes cronicas": o trecho
            # pode ser uma mascara alterada da mesma regiao ("<exame> com <x>")
            nucleo = re.sub(r"\b(?:sem e com|sem|com)\s+contraste\b|\bcontraste\b|\bnormal\b", " ", cab_norm)
            nucleo = re.sub(r"\b(?:direit[oa]|esquerd[oa]|bilateral)\b", " ", nucleo)
            nucleo = re.sub(r"\s+", " ", nucleo).strip()
            reg = BANCO.meta.get(tit, ("", "", "", ""))[:3]
            trocou = False
            for x in list(restantes):
                pal = normalizar(x).split()
                for k in range(len(pal), 0, -1):       # "gonartrose tricompartimental acentuada"
                    if any(w not in _SO_GRAU for w in pal[k:]):
                        break                          # so descarta palavra de grau/lado
                    t2, x2, sc2, _g2 = BANCO.buscar2(normalizar(nucleo + " com " + " ".join(pal[:k])), "mascara")
                    if x2 is not None and sc2 >= 1.0 and t2 != tit and \
                            BANCO.meta.get(t2, ("",) * 4)[:3] == reg:
                        tit, txt = t2, x2
                        restantes.remove(x)
                        trocou = True
                        break
                if trocou:
                    break
            blocos = achar_blocos(restantes, BANCO.meta.get(tit))
            usados = {b[4] for b in blocos}
            orfaos = [x for x in restantes if x not in usados and _relevante(x)]
            # "desvio lateral da coluna, com convexidade para a esquerda": o trecho
            # que so qualifica o achado anterior (lado, medida, nivel) vai para ele
            blocos, orfaos = _juntar_qualificadores(restantes, blocos, orfaos)
            base = preencher(txt, bruto, None)
            if blocos or orfaos:
                texto = montar(base, blocos, ctx)
                if orfaos:
                    texto = _anexar_orfaos(texto, orfaos)
                return texto, f"composto:{tit}+{len(blocos)} bloco(s)" + \
                              (f"+{len(orfaos)} nao reconhecido(s)" if orfaos else "")
            return base, f"mascara:{tit}"

    tit, txt, score = BANCO.buscar(resto, tipo)
    if txt is not None:
        return preencher(txt, bruto), f"{tipo or 'auto'}:{tit} ({score:.2f})"
    if tipo == "frase":
        achado = _frase_aproximada(resto)
        if achado:
            tit, txt = achado
            return preencher(txt, bruto), f"frase~:{tit}"
    if tipo is not None:
        return (f"[não encontrei \"{resto}\" no banco de {tipo}s]\n{revisar_local(bruto_fixo)}",
                "nao_encontrado")
    # nada casou no banco: o ditado passa pela revisao local deterministica
    limpo = revisar_local(bruto_fixo)
    return limpo, ("revisado" if limpo != bruto else "passagem")


# palavras que aparecem no ditado do exame e nao sao achados
_MODIFICADORES = set("""contraste iodado endovenoso venoso intravenoso direito direita
esquerdo esquerda bilateral bilaterais normal normais alteracoes alteracao significativas
pelve abdome abdomen total superior inferior torax cranio fase fases arterial portal tardia
tardio sem com exame tomografia tc rx raio radiografia angio angiotomografia incidencias
incidencia perfil frente oblicua ap pa multislice helicoidal protocolo""".split())

def _trecho_cru(bruto, g):
    """Trecho do ditado CRU que corresponde ao gatilho normalizado g."""
    palavras = bruto.split()
    for k in range(1, len(palavras) + 1):
        pedaco = " ".join(palavras[:k])
        n = normalizar(pedaco)
        for cmd in COMANDOS:
            pn = normalizar(cmd)
            if n.startswith(pn + " ") and not g.startswith(pn + " "):
                n = n[len(pn):].strip()
                break
        if n == g:
            return pedaco
    return None

_FRONTEIRA = re.compile(r"^\s*(?:$|[,;.:]|(?:com|e|mais|apresentando|associad[oa]s?)\b)", re.I)

def _cabecalho_do_exame(bruto, resto_norm):
    """Maior gatilho de MASCARA que abre o ditado e termina numa FRONTEIRA de
    frase (virgula, "com", "e", fim) — ou cujo resto e so lado/medida/local.
    "raio x de joelho com artrose femoropatelar" NAO para em "...com artrose",
    porque "femoropatelar" continua o mesmo termo; cai para "raio x de joelho".
    Resolve tambem nomes com " e " ("cranio e pescoco", "abdome superior e pelve").
    Devolve (trecho_cru, gatilho, titulo, texto) ou ("", "", None, None)."""
    cands = {}
    for t, g, tit, txt, sec, con in BANCO.itens:
        if t != "mascara" or not g:
            continue
        if resto_norm == g or resto_norm.startswith(g + " "):
            cands.setdefault(g, (tit, txt))
    for g in sorted(cands, key=len, reverse=True):
        cru = _trecho_cru(bruto, g)
        if cru is None:
            continue
        sobra = bruto[len(cru):]
        if _FRONTEIRA.match(sobra) or not _relevante(sobra):
            tit, txt = cands[g]
            return cru, g, tit, txt
    return "", "", None, None

_LOCAIS = set("""ramo ramos principais lobo lobos lingula segmento segmentos terco tercos proximal distal medial
lateral anterior posterior superior inferior apical basal apice base regiao nivel niveis
porcao face margem polo corno cupula lado ambos""".split())

def _coberto(seg, cobertos):
    """O trecho ja esta dito pelo nome da mascara? (metade ou mais das palavras
    de conteudo ja aparecem no gatilho). Evita reaplicar o mesmo achado como bloco."""
    cont = [w for w in normalizar(seg).split()
            if len(w) >= 4 and w not in _MODIFICADORES and w not in _LOCAIS]
    if not cont:
        return True
    return sum(1 for w in cont if w in cobertos) / len(cont) >= 0.5

def _relevante(seg):
    """Segmento que parece um achado (e nao so lado, medida ou localizacao)."""
    tok = [w for w in normalizar(seg).split() if len(w) >= 4]
    return any(w not in _MODIFICADORES and w not in _LOCAIS for w in tok)

_QUALIFICA = set("""convexidade concavidade lateralidade predominio predominando predominante
medindo mede medida cerca maior menor eixo eixos localizado localizada situado situada
lado para de do da dos das no na nos nas em a o as os ao aos com e mais nivel niveis
direita direito esquerda esquerdo bilateral bilateralmente sobre ate grau""".split())

def _juntar_qualificadores(restantes, blocos, orfaos):
    seg_idx = {b[4]: k for k, b in enumerate(blocos)}
    juntado = {}          # orfao ja anexado -> bloco (encadeia "plantar", "e posterior")
    sobra = []
    for x in orfaos:
        i = restantes.index(x) if x in restantes else -1
        prev = restantes[i - 1] if i > 0 else None
        pal = [w for w in normalizar(x).split() if not w.isdigit()]
        k = seg_idx.get(prev, juntado.get(prev))
        # vocabulario aceito: qualificadores gerais + as OPCOES das lacunas do bloco
        # ("centrolobular e predominantemente parasseptal nos lobos superiores")
        opc = set()
        if k is not None:
            for m in PADRAO_SLOT.finditer((blocos[k][1] or "") + " " + (blocos[k][3] or "")):
                opc.update(normalizar((m.group(3) or "").replace("/", " ")).split())
            # e as palavras do proprio texto do bloco ("... no calcaneo")
            opc.update(w for w in normalizar(PADRAO_SLOT.sub(" ", blocos[k][1] or "")).split() if len(w) >= 4)
        so_qualifica = pal and all(w in _QUALIFICA or w in opc or re.fullmatch(r"[ctls]\d{1,2}|cm|mm", w)
                                   for w in pal)
        if k is not None and so_qualifica:
            b = blocos[k]
            blocos[k] = b[:4] + (b[4] + " e " + x,)
            seg_idx[blocos[k][4]] = k
            juntado[x] = k
        else:
            sobra.append(x)
    return blocos, sobra


_VAZIAS = set("para pelo pela pelos pelas com sem entre sobre mais cerca".split())
_NEGA = re.compile(r"\b(sem|nao|ausencia|ausentes?|inexiste)\b")

def _ja_no_texto(orfao, linhas):
    """Complemento que a mascara ja escreveu ("convexidade para a esquerda",
    "posterior no calcaneo"): todas as palavras de conteudo estao numa mesma
    linha AFIRMATIVA do laudo -> nao marca como faltando."""
    pal = [w for w in normalizar(orfao).split() if len(w) >= 4 and w not in _VAZIAS]
    if not pal:
        return False
    frases = [f for l in linhas for f in re.split(r"(?<=[.;])\s+", l.replace("**", ""))]
    for f in frases:
        n = normalizar(f)
        if _NEGA.search(n):
            continue
        if all(re.search(r"\b%s\b" % re.escape(w), n) for w in pal):
            return True
    return False


def _anexar_orfaos(texto, orfaos):
    """Achado ditado que nao casou com nenhum bloco: entra VISIVEL no fim da
    analise, marcado, em vez de sumir."""
    linhas = texto.split("\n")
    orfaos = [o for o in orfaos if not _ja_no_texto(o, linhas)]
    if not orfaos:
        return texto
    a = _idx(linhas, {"ANALISE", "RELATORIO", "ACHADOS"})
    marca = ["[não encontrado no banco — completar: " + revisar_local(o) + "]" for o in orfaos]
    if a is None:
        return texto + "\n" + "\n".join(marca)
    pos = _fim_secao(linhas, a)
    while pos - 1 > a and not linhas[pos - 1].strip():
        pos -= 1
    return "\n".join(linhas[:pos] + marca + linhas[pos:])


def extrair_ditado(body):
    msgs = body.get("messages") or []
    for m in reversed(msgs):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return msgs[-1].get("content", "") if msgs else ""

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _json(self, code, obj):
        d = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": "laudo-router", "object": "model", "owned_by": "local"}]})
        if self.path.rstrip("/") in ("/versao", "/v1/versao"):
            return self._json(200, {"versao": VERSAO, "gatilhos": len(BANCO.itens)})
        if self.path.rstrip("/") in ("/ia", "/v1/ia"):
            # botão de IA e contador de gasto (nunca devolve chave)
            if nuvem is None:
                return self._json(200, {"ativa": False})
            try:
                return self._json(200, nuvem.estado())
            except Exception as e:
                return self._json(500, {"error": type(e).__name__})
        if self.path.rstrip("/") in ("/recarregar", "/v1/recarregar"):
            BANCO.carregar()
            return self._json(200, {"ok": True, "gatilhos": len(BANCO.itens)})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        t0 = time.time()
        BANCO.atualizada()
        ditado = ""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            ditado = extrair_ditado(body)
            texto, origem = rotear(ditado)
            if (not origem.startswith("nuvem")) and (time.time() - t0 > ORCAMENTO_S):
                texto, origem = ditado, "estouro_de_tempo"
            texto = formatar_saida(texto)
        except Exception as e:
            texto, origem = (ditado or ""), f"erro:{type(e).__name__}"
        print(f"[{origem}] {ditado[:60]!r} -> {texto[:60]!r}", flush=True)
        self._json(200, {
            "id": "chatcmpl-local", "object": "chat.completion",
            "model": "laudo-router",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": texto}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

def revisar_laudo_inteiro(texto):
    """Laudo inteiro -> revisao da nuvem, sem marca, pronto para colar por cima."""
    if nuvem is None:
        return None, "nuvem_ausente"
    c = nuvem.config()
    if not c.get("ativa"):
        return None, "nuvem_desligada"
    novo, origem = nuvem.chamar("LAUDO NA TELA:\n" + texto, c, modo="laudo",
                                marcar=False, max_tokens=4000)
    if origem == "nuvem" and novo:
        _aprender(texto, novo)
    return novo, origem


def instruir_laudo(texto, instrucao):
    """Laudo inteiro + instrucao falada -> laudo modificado pela nuvem."""
    if nuvem is None:
        return None, "nuvem_ausente"
    c = nuvem.config()
    if not c.get("ativa"):
        return None, "nuvem_desligada"
    pedido = "INSTRUÇÃO FALADA: %s\n\nLAUDO NA TELA:\n%s" % (instrucao.strip(), texto)
    return nuvem.chamar(pedido, c, modo="laudo", marcar=False, max_tokens=4000)


if __name__ == "__main__":
    if os.name == "nt":
        try:
            import atalho_win
            atalho_win.iniciar(revisar_laudo_inteiro, tecla="A")
        except Exception as e:
            print("atalho Ctrl+Alt+A indisponivel:", e, flush=True)
    # aquece antes de atender: a 1a consulta (vocabulario, aproximacao) levava
    # ~5 s e estourava o tempo -> o Handy colava o ditado cru
    for _t in ("radiografia do tornozelo esquerdo com entesopatia calcificada plantar e posterior no calcanho",
               "tc de torax com enfisema centrolobular", "frase derrame pleural"):
        try:
            rotear(_t)
        except Exception:
            pass
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"roteador em http://{HOST}:{PORT}/v1  (Ctrl+C para sair)", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nencerrado")
