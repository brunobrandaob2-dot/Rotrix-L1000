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
try:
    import rx_literal
except Exception:
    rx_literal = None
try:
    import radius
except Exception:
    radius = None
try:
    import perfil as perfil_mod
except Exception:
    perfil_mod = None
try:
    import correcao as correcao_mod
except Exception:
    correcao_mod = None

BASE = os.environ.get("LAUDO_BASE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "base.sqlite")
HOST, PORT = "127.0.0.1", 8123
VERSAO = "2026-09-22.11"
LIMIAR = 0.74          # similaridade mínima para aceitar um gatilho
ORCAMENTO_S = 8.0      # teto de tempo; acima disso devolve o texto cru

COMANDOS = {
    "mascara": "mascara", "máscara": "mascara", "modelo": "mascara",
    "frase": "frase", "achado": "frase",
    "adendo": "adendo",
}

def _normalizar_bruto(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# normalizar() roda milhões de vezes ao varrer o banco (vocabulário, grafia
# s/z, rótulos da TC). Guardar o resultado das PALAVRAS - as frases longas
# passam direto - derruba o preparo de ~13 s para ~2 s.
_NORM = {}


def normalizar(s):
    if not s or len(s) > 48:
        return _normalizar_bruto(s)
    v = _NORM.get(s)
    if v is None:
        if len(_NORM) > 300000:
            _NORM.clear()
        v = _NORM[s] = _normalizar_bruto(s)
    return v


class Banco:
    def __init__(self, caminho):
        self.caminho = caminho
        self.lock = threading.Lock()
        self.itens = []          # (tipo, gatilho_norm, titulo, texto)
        self.meta = {}
        self.carregar()
    def carregar(self):
        """Lê a base. Se a leitura falhar (arquivo sendo refeito, vazio, corrompido),
        mantém o que já estava carregado: o ditado nunca fica sem banco."""
        with self.lock:
            if not os.path.exists(self.caminho):
                print("AVISO: base.sqlite nao encontrado. Rode construir_base.py", file=sys.stderr)
                return
            try:
                mtime = os.path.getmtime(self.caminho)
                con = sqlite3.connect("file:%s?mode=ro" % self.caminho.replace("\\", "/"), uri=True)
                try:
                    try:
                        rows = con.execute("SELECT tipo, gatilho_norm, titulo, texto, secao, conclusao, "
                                           "categoria, modalidade, regiao, subtipo FROM entradas").fetchall()
                    except sqlite3.OperationalError:     # base antiga, sem metadados
                        rows = [tuple(r) + ("", "", "", "") for r in con.execute(
                            "SELECT tipo, gatilho_norm, titulo, texto, secao, conclusao FROM entradas")]
                finally:
                    con.close()
            except (sqlite3.Error, OSError) as e:
                print("AVISO: base.sqlite ilegível (%s); mantendo a base anterior" % e, file=sys.stderr)
                return
            if not rows and self.itens:
                print("AVISO: base.sqlite vazia; mantendo a base anterior", file=sys.stderr)
                return
            itens, meta = [], {}     # titulo -> (categoria, modalidade, regiao, subtipo)
            prio = {"mascara": 0, "achado": 1, "adendo": 2, "bloco": 3, "frase": 4}
            rows.sort(key=lambda r: prio.get(r[0], 5))      # sort estavel
            textos = {}
            for r in rows:
                if r[3]:
                    textos.setdefault(r[2], r[3])
            for r in rows:
                if not r[3]:            # forma curta gerada: o texto é o da máscara
                    r = (r[0], r[1], r[2], textos.get(r[2], "")) + tuple(r[4:])
                itens.append(tuple(r[:6]))
                meta.setdefault(r[2], tuple(x or "" for x in r[6:10]))
            self.itens, self.meta, self.mtime = itens, meta, mtime
            print(f"base carregada: {len(self.itens)} gatilhos", flush=True)
    def atualizada(self):
        """Recarrega sozinho se a base.sqlite foi trocada no disco."""
        try:
            if os.path.getmtime(self.caminho) != getattr(self, "mtime", None):
                self.carregar()
        except Exception:
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
        # palavra de anatomia do gatilho so casa com palavra de anatomia do ditado:
        # "cranio" nao pode casar com "raio" (de "raio x") -> "raio x de femur" nao
        # vira radiografia do cranio
        alvo_anat = alvo - _GENERICAS
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
                elif len(w) >= 4 and difflib.get_close_matches(w, alvo_anat, 1, 0.8):
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
                   and not difflib.get_close_matches(w, alvo_set - _GENERICAS, 1, 0.8)
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

# ---------- modalidade dita x modalidade da mascara ----------
# "ressonancia de joelho normal" nao pode virar RADIOGRAFIA DO JOELHO so porque
# o banco nao tem ressonancia de joelho: sem mascara da modalidade dita, o
# ditado passa como texto.
_ANTES_MOD = r"^(?:\w+ ){0,2}?"
_MOD_DITA = [
    ("angiotc", re.compile(_ANTES_MOD + r"(?:angio ?tomografia|angio ?tc|angiotc|angio tomo)\b")),
    ("rm", re.compile(_ANTES_MOD + r"(?:angio ?ressonancia|ressonancia|rm|rnm)\b")),
    ("tc", re.compile(_ANTES_MOD + r"(?:tomografia|tc|tomo|urotomografia|uro tc)\b")),
    ("rx", re.compile(_ANTES_MOD + r"(?:raio x|raios x|raiox|rx|radiografia)\b")),
    ("us", re.compile(_ANTES_MOD + r"(?:ultrassom|ultrassonografia|ultrasonografia|usg|ecografia|"
                                   r"doppler|ecodoppler)\b")),
    ("mg", re.compile(_ANTES_MOD + r"mamografia\b")),
]
_MOD_ACEITA = {"tc": {"tc", "angiotc"}, "angiotc": {"angiotc", "tc"}, "rm": {"rm"},
               "rx": {"rx"}, "us": set(), "mg": set()}


def _modalidade_dita(n):
    for mod, rx in _MOD_DITA:
        if rx.match(n or ""):
            return mod
    return None


def _modalidade_confere(n, tit):
    """False quando o ditado comeca nomeando um exame e o item achado e de outro."""
    mod = _modalidade_dita(n)
    meta = BANCO.meta.get(tit) if tit else None
    if mod is None or not meta or not meta[1]:
        return True
    return meta[1] in _MOD_ACEITA.get(mod, {meta[1]})

# ---------- motor de slots ----------
# {nome|op1/op2}  -> se o ditado resolver, substitui; senao mantem [op1/op2]
# {nome}          -> se o ditado resolver, substitui; senao ___

def _lado(n):
    if re.search(r"\bbilatera", n): return "bilateral"
    d, e = re.search(r"\bdireit", n), re.search(r"\besquerd", n)
    if d and e:
        return None          # os dois lados no mesmo trecho: lacuna visível, nunca chute
    if d: return "direito"
    if e: return "esquerdo"
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

def _opcao_aproximada(opcoes, n0):
    """Opção da lacuna dita de outro jeito (só no "descrever X" da radiografia):
    "discreto" ~ "discreta"; "compartimento medial" -> "femorotibial medial"
    (a única opção com a palavra "medial")."""
    for o in opcoes:
        on = normalizar(o)
        if " " not in on and len(on) >= 5 and on[-1] in "oa" and \
                re.search(r"\b%s[oa]s?\b" % re.escape(on[:-1]), n0):
            return o
    toks = [set(w for w in normalizar(o).split() if len(w) >= 4) for o in opcoes]
    ditas = set(n0.split())
    hits = []
    for i, t in enumerate(toks):
        outras = set().union(*(toks[:i] + toks[i + 1:])) if len(toks) > 1 else set()
        if (t - outras) & ditas:
            hits.append(opcoes[i])
    return hits[0] if len(hits) == 1 else None

def preencher(texto, ditado, contexto=None, aproximar=False):
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
            if not valor and aproximar:
                valor = _opcao_aproximada(opcoes.split("/"), n0)
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
            _CFG["dados"] = json.load(open(p, encoding="utf-8-sig"))
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
        return _com_ponto_final(revisor.revisar(texto, pontuacao=pont))
    except Exception:
        return texto


def _com_ponto_final(t):
    """Ditado livre: comeca com maiuscula e termina com ponto (pedido do Bruno)."""
    if not t or not t.strip():
        return t
    fim = len(t.rstrip())
    corpo, cauda = t[:fim], t[fim:]
    if corpo[-1] == ",":
        corpo = corpo[:-1]
    if corpo and (corpo[-1].isalnum() or corpo[-1] in ")%°]"):
        corpo += "."
    i = next((k for k, ch in enumerate(corpo) if ch.isalpha()), None)
    if i is not None and corpo[i].islower() and not corpo[:i].strip("\"'([-— "):
        corpo = corpo[:i] + corpo[i].upper() + corpo[i + 1:]
    return corpo + cauda



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

# ---------- s / z / c / ss: o reconhecimento de voz troca ("risartrose",
# "esparca") ----------
# Palavra FORA do vocabulario do banco que, com UMA troca s<->z, c<->s, ss<->c
# ou s<->ss, vira palavra do banco: sai a do banco, com os acentos do banco.
_GRAFIA = {"n": None, "forma": {}}
_PAL_TXT = re.compile(r"[A-Za-zÀ-ÿ]+")


def _formas_do_banco():
    if _GRAFIA["n"] != len(BANCO.itens):
        cont = collections.defaultdict(collections.Counter)
        for t, g, tit, txt, sec, con in BANCO.itens:
            for w in _PAL_TXT.findall(txt or ""):
                if len(w) >= 5:
                    cont[normalizar(w)][w.lower()] += 1
        _GRAFIA.update(n=len(BANCO.itens), forma={k: c.most_common(1)[0][0] for k, c in cont.items()})
    return _GRAFIA["forma"]


def _trocas_sz(w):
    out = set()
    for i, ch in enumerate(w):
        seg = w[i + 1:i + 2]
        if ch == "s":
            out.add(w[:i] + "z" + w[i + 1:])
            if seg in ("a", "o", "u"):
                out.add(w[:i] + "c" + w[i + 1:])            # s -> c (ç)
            if w[i + 1:i + 2] == "s":
                out.add(w[:i] + "c" + w[i + 2:])            # ss -> c (ç)
                out.add(w[:i] + w[i + 1:])                  # ss -> s
            elif 0 < i < len(w) - 1 and w[i - 1] in "aeiou" and seg in tuple("aeiou"):
                out.add(w[:i] + "ss" + w[i + 1:])           # s -> ss
        elif ch == "z":
            out.add(w[:i] + "s" + w[i + 1:])
        elif ch == "c" and seg in ("a", "o", "u"):
            out.add(w[:i] + "s" + w[i + 1:])                # c (ç) -> s
            out.add(w[:i] + "ss" + w[i + 1:])               # c (ç) -> ss
    out.discard(w)
    return out


def grafia_sz(texto):
    """Corrige so a troca de s/z/c/ss contra o vocabulario do banco."""
    v = _vocab()
    if not v["set"] or not texto:
        return texto
    forma = _formas_do_banco()

    def troca(m):
        w = m.group(0)
        wn = normalizar(w)
        if len(wn) < 5 or wn in v["set"] or wn in _CURTAS_OK or " " in wn:
            return w
        cands = [c for c in _trocas_sz(wn) if c in v["set"]]
        if len(cands) != 1:
            return w
        novo = forma.get(cands[0], cands[0])
        if w[:1].isupper():
            novo = novo[:1].upper() + novo[1:]
        return novo
    return _PAL_TXT.sub(troca, texto)


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


# "formar laudo" (no fim ou no começo do ditado contínuo): monta o laudo com o
# banco local. "formar laudo com IA" monta local e depois manda o laudo montado
# para a IA do exame (config ia_por_exame: RX na Luna só formatando, etc.).
_FORMAR_NUCLEO = (r"(?:formar|forma|forme|formas|formando|montar|monta|monte|montando)\s+"
                  r"(?:o\s+|um\s+|meu\s+)?laudo"
                  r"(?P<ia>\s+(?:com|pela|pelo|na|no|por|via|usando)\s+(?:a\s+|o\s+)?"
                  r"(?:ia|i\.?\s?a\.?|intelig[eê]ncia\s+artificial|nuvem|claude|gpt|chat\s?gpt))?")
_FORMAR_FIM = re.compile(r"(?:^|[\s,.;:!?-])" + _FORMAR_NUCLEO + r"[\s,.;:!?-]*$", re.I)
_FORMAR_INICIO = re.compile(r"^[\s,.;:!?-]*" + _FORMAR_NUCLEO + r"(?:[\s,.;:!?-]+|$)", re.I)


def comando_formar(bruto):
    """(resto_do_ditado, com_ia) se o ditado tem o comando "formar laudo"; senão None."""
    t = (bruto or "").strip()
    m = _FORMAR_FIM.search(t)
    if m:
        return t[:m.start()].strip(" ,.;:-"), bool(m.group("ia"))
    m = _FORMAR_INICIO.match(t)
    if m:
        return t[m.end():].strip(" ,.;:-"), bool(m.group("ia"))
    return None


def formar_laudo(resto, com_ia):
    """Monta o laudo com o banco; com IA, manda o laudo montado para a rota do exame.
    Se a IA falhar, devolve o laudo local (o ditado nunca se perde)."""
    ativa = nuvem is not None and nuvem.config().get("ativa")
    if not resto.strip():
        # só o comando: vale para o laudo que já está na tela
        if com_ia and ativa and os.name == "nt":
            try:
                import atalho_win
                sel = atalho_win.copiar_selecao()
            except Exception:
                sel = ""
            if sel:
                novo, origem = revisar_laudo_inteiro(sel)
                if novo and origem == "nuvem":
                    return formato.padronizar(novo), "nuvem_formar_tela"
                return sel, "nuvem_formar_tela_falhou:" + str(origem)
        return "", "formar_vazio"
    texto, origem = rotear(resto)
    if not com_ia:
        return texto, "formar:" + origem
    if not ativa:
        return texto, "formar:" + origem + "+ia_desligada"
    try:
        c = nuvem.config()
        pedido = "LAUDO NA TELA:\n" + texto.replace("**", "")
        novo, o2 = nuvem.chamar(pedido, c, modo="laudo", marcar=False, max_tokens=4000)
    except Exception as e:
        return texto, "nuvem_indisponivel_local:erro_%s" % type(e).__name__
    if novo and o2 == "nuvem":
        return formato.padronizar(novo), "nuvem_formar"
    if novo and o2 in ("nuvem_bloqueada", "nuvem_teto"):
        return novo.split("\n", 1)[0] + "\n" + texto, o2     # aviso + laudo local
    # "nuvem..." no começo: o teto de tempo do ditado local não se aplica aqui
    return texto, "nuvem_indisponivel_local:" + str(o2)


def rotear(ditado, _auto=False):
    """Devolve (texto_final, origem). Nunca levanta excecao."""
    bruto = (ditado or "").strip()
    if not bruto:
        return "", "vazio"
    cmd = comando_formar(bruto)
    if cmd is not None:
        return formar_laudo(*cmd)
    original = bruto
    bruto = grafia_sz(ouvido_fixo(_sem_preambulo(bruto)))
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
    bruto_fixo = grafia_sz(ouvido_fixo(original))   # tsv: vale tambem para texto livre
    bruto_lit = bruto                        # palavras do medico (RX literal)
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
        if rx_literal is not None and _config().get("rx_literal", True) and \
                (txt is None or BANCO.meta.get(tit, ("",) * 4)[1] == "rx"):
            # radiografia: abertura depois de "proximo,", "mostrando ...", e
            # "raio x de torax com alteracoes cronicas, cardiomegalia"
            r_cab = _cabecalho_rx(bruto, bruto_lit)
            if r_cab is not None and (txt is None or len(r_cab[3]) > len(cab_norm)):
                bruto, bruto_lit, cab_raw, cab_norm, tit, txt = r_cab
        if txt is None and tipo is None and not _auto:
            cab_auto = _cabecalho_automatico()
            if cab_auto and _cabecalho_rx(cab_auto, cab_auto) is not None:
                t_auto, o_auto = rotear(cab_auto + ", " + original, _auto=True)
                if o_auto.startswith(("rx_literal", "mascara")):
                    return t_auto, o_auto + "+radius"
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
            if txt is not None and not _modalidade_confere(cab_norm, tit):
                tit, txt = None, None
            if txt is not None:
                cab_norm = g
        if txt is not None and rx_literal is not None and _config().get("rx_literal", True):
            try:
                r = _compor_rx_literal(bruto_lit, bruto, cab_raw, cab_norm, tit, txt)
            except Exception as e:
                print("AVISO: rx literal falhou (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
                r = None
            if r is not None:
                return r
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
            base = preencher(txt, bruto, ctx)
            if blocos or orfaos:
                texto = montar(base, blocos, ctx)
                postos = 0
                literal = {o: _palavras_do_medico(o, bruto, bruto_lit) for o in orfaos}
                if orfaos and _config().get("tc_literal", True):
                    try:
                        texto, sobra = _orfaos_no_lugar(texto, orfaos, tit, restantes, blocos, literal,
                                                        bruto, bruto_lit)
                        postos, orfaos = len(orfaos) - len(sobra), sobra
                    except Exception as e:
                        print("AVISO: achado no lugar falhou (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
                if orfaos:
                    texto = _anexar_orfaos(texto, [literal.get(o, o) for o in orfaos])
                texto = _alteradas_primeiro(texto, tit, bruto, ctx)
                return texto, f"composto:{tit}+{len(blocos)} bloco(s)" + \
                              (f"+{postos} com as suas palavras" if postos else "") + \
                              (f"+{len(orfaos)} nao reconhecido(s)" if orfaos else "")
            return _alteradas_primeiro(base, tit, bruto, ctx), f"mascara:{tit}"

    tit, txt, score = BANCO.buscar(resto, tipo)
    if txt is not None and not _modalidade_confere(resto, tit):
        tit, txt = None, None
    if txt is not None:
        return _alteradas_primeiro(preencher(txt, bruto), tit, bruto), f"{tipo or 'auto'}:{tit} ({score:.2f})"
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
# radiografia: "raio x de torax SEM sinais de pneumotorax", "... evidenciando ..."
_FRONTEIRA_RX = re.compile(r"^\s*(?:$|[,;.:]|(?:com|e|mais|apresentando|associad[oa]s?|sem|"
                           r"evidenciando|mostrando|demonstrando|onde|que)\b)", re.I)

def _cabecalho_do_exame(bruto, resto_norm, fronteira=None, so_rx=False):
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
        if so_rx and BANCO.meta.get(tit, ("",) * 4)[1] != "rx":
            continue
        if resto_norm == g or resto_norm.startswith(g + " "):
            cands.setdefault(g, (tit, txt))
    for g in sorted(cands, key=len, reverse=True):
        cru = _trecho_cru(bruto, g)
        if cru is None:
            continue
        if so_rx:
            cru = cru.rstrip(",.;:!?")     # a virgula depois do exame e fronteira
        sobra = bruto[len(cru):]
        if (fronteira or _FRONTEIRA).match(sobra) or not _relevante(sobra):
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


# ---------------------------------------------------------------------------
# TC: achado ditado que o banco nao tem entra COM AS PALAVRAS DO MEDICO no
# rotulo da estrutura ("Parenquima pulmonar:", "Figado:") e a frase de
# normalidade daquela estrutura sai (regra do Bruno: alteracao e normalidade
# da mesma estrutura nunca juntas). Sem estrutura certa, fica marcado no fim.
# config.json: "tc_literal": false volta a so marcar no fim.
# ---------------------------------------------------------------------------
_ROT_LINHA = re.compile(r"^(\s*-?\s*[^\W\d_][^:.;]{0,70}):\s+(.*)$")
_GENERICO_TC = set("""alteracoes alteracao significativas significativos significativa particularidades
anormalidades evidentes evidente caracterizaveis caracterizavel metodo limites normal normais habitual
habituais preservado preservada preservados preservadas regular regulares dimensoes contornos morfologia
densidade aspecto discreto discreta discretos discretas acentuado acentuada moderado moderada leve leves
direito direita esquerdo esquerda bilateral bilaterais medindo medida cerca inferior superior anterior
posterior lateral medial proximal distal terco regiao nivel niveis pequeno pequena grande volume
compativel sugestivo sugestiva achado achados estudo exame imagem imagens presenca ausencia sinais sinal
aumento reducao difuso difusa focal focais segmento segmentos demais outros outras protocolo utilizado
considerando incluidos incluidas incluido incluida para como mais pela pelo pelos pelas cada esta este
estes estas sobre entre apos ante onde numa nesse nessa desse dessa todo toda todos todas area areas
cerca aproximadamente associado associada associados associadas""".split())
_NEG_TC = re.compile(r"^(?:nao ha|nao se \w+|nao sao \w+|ausencia de|ausentes?|sem)\b")
_VOC_ROT = {"n": None, "por": {}}
# palavra que liga o achado ao anterior ("densificacao da gordura ADJACENTE")
_RELACAO = re.compile(r"\b(?:adjacente|adjacentes|associad[oa]s?|perilesiona(?:l|is)|de permeio|"
                      r"ao redor|circunjacente|circunjacentes|contigu[oa]s?|no mesmo|na mesma|"
                      r"deste|desta|dele|dela)\b")


def _rad_tc(texto, minimo=4):
    return {w[:6] for w in normalizar(texto).split()
            if len(w) >= minimo and w not in _GENERICO_TC and not w.isdigit()}


def _vocab_rotulos(reg):
    """{rotulo_norm: Counter(radicais)} dos blocos do banco da regiao."""
    if _VOC_ROT["n"] != len(BANCO.itens):
        por = {}
        for t, g, tit, txt, sec, con in BANCO.itens:
            if t != "bloco" or not sec:
                continue
            m = BANCO.meta.get(tit)
            if not m:
                continue
            d = por.setdefault(tuple(m[:3]), {})
            c = d.setdefault(normalizar(sec), collections.Counter())
            c.update(_rad_tc(g) | _rad_tc(txt or ""))
        _VOC_ROT.update(n=len(BANCO.itens), por=por)
    return _VOC_ROT["por"].get(tuple(reg), {})


def _rotulo_para(orfao, reg, presentes):
    """Rotulo (normalizado) do laudo onde o achado entra; None se nao ha um claro.
    Cada palavra do achado vota nos rotulos pela fracao dos blocos do banco
    daquele rotulo que a usam; o nome da estrutura dito conta mais."""
    rad = _rad_tc(orfao)
    if not rad:
        return None
    voc = _vocab_rotulos(reg)
    total = collections.Counter()
    for rot in presentes:
        for r in rad:
            total[r] += voc.get(rot, collections.Counter())[r]
    notas = []
    for rot in presentes:
        c = voc.get(rot, collections.Counter())
        nota = sum(c[r] / total[r] for r in rad if total[r])
        nota += 2.0 * len(rad & _rad_tc(rot))            # "... do figado" -> Figado
        notas.append((nota, rot))
    notas.sort(reverse=True)
    if not notas or notas[0][0] < 0.5:
        return None
    if len(notas) > 1 and notas[0][0] < 1.5 * notas[1][0]:
        return None
    return notas[0][1]


def _frases_normais_regiao(reg):
    out = set()
    for _g, _tit, txt in _normais_da_regiao(reg):
        for l in txt.split("\n"):
            m = _ROT_LINHA.match(l.replace("**", ""))
            corpo = m.group(2) if m else l
            for f in re.split(r"(?<=[.;])\s+", corpo):
                if f.strip():
                    out.add(normalizar(f))
    return out


def _cap(t):
    return t[:1].upper() + t[1:] if t else t


def _min(t):
    # "Nodulo..." -> "nodulo..." depois do rotulo; sigla fica ("TC", "L4-L5")
    return t[:1].lower() + t[1:] if len(t) > 1 and t[1:2].islower() else t


def _palavras_do_medico(trecho, bruto, bruto_lit):
    """O trecho saiu do texto ja aproximado ao vocabulario do banco (so para
    achar); devolve o mesmo trecho com as palavras ditas."""
    i = bruto.find(trecho)
    tb = list(re.finditer(r"[^\W\d_]+", bruto))
    tl = list(re.finditer(r"[^\W\d_]+", bruto_lit))
    if i < 0 or len(tb) != len(tl):
        return trecho
    k0 = sum(1 for m in tb if m.end() <= i)
    out, j = [], 0
    for m in re.finditer(r"[^\W\d_]+", trecho):
        if k0 + j >= len(tl):
            return trecho
        out.append((m.start(), m.end(), tl[k0 + j].group(0)))
        j += 1
    r, ult = [], 0
    for a, b, w in out:
        r.append(trecho[ult:a]); r.append(w); ult = b
    r.append(trecho[ult:])
    return "".join(r)


def _grupos_de_orfaos(orfaos, restantes, bruto):
    """Achados sem bloco ditos juntos com "com"/"e" ("pancreas com atrofia difusa
    e calcificacoes") formam UMA frase: [(trecho_do_bruto, [orfaos])]."""
    pos, ini = {}, 0
    for k, x in enumerate(restantes):
        i = bruto.find(x, ini) if bruto else -1
        if i >= 0:
            pos[k] = (i, i + len(x))
            ini = i + len(x)
    grupos = []
    for o in orfaos:
        k = restantes.index(o) if o in restantes else -1
        if grupos and k > 0 and (k - 1) in pos and k in pos:
            g_trecho, g_orf, g_k = grupos[-1]
            entre = bruto[pos[k - 1][1]:pos[k][0]]
            if g_k == k - 1 and re.fullmatch(r"\s*(?:com|e|associad[oa]s? a)\s*", entre, re.I):
                k0 = restantes.index(g_orf[0])
                grupos[-1] = (bruto[pos[k0][0]:pos[k][1]], g_orf + [o], k)
                continue
        grupos.append((o, [o], k))
    return [(t, g) for t, g, _k in grupos]


def _orfaos_no_lugar(texto, orfaos, tit, restantes, blocos, literal=None, bruto="", bruto_lit=""):
    """Poe cada achado sem bloco no rotulo da sua estrutura. Devolve (texto, sobra)."""
    literal = literal or {}
    meta = BANCO.meta.get(tit)
    if not meta:
        return texto, list(orfaos)
    reg = tuple(meta[:3])
    linhas = texto.split("\n")
    a = _idx(linhas, {"ANALISE", "RELATORIO", "ACHADOS"})
    if a is None:
        return texto, list(orfaos)
    fim = _fim_secao(linhas, a)
    onde = {}
    for i in range(a + 1, fim):
        m = _ROT_LINHA.match(linhas[i])
        if m and not _cab(linhas[i]):
            onde.setdefault(normalizar(m.group(1)), i)
    if not onde:
        return texto, list(orfaos)
    normais = _frases_normais_regiao(reg)
    rot_do_bloco = {b[4]: normalizar(b[2]) for b in blocos if b[2]}
    sobra, conclusao = [], []
    anterior_rot = {}
    for k, x in enumerate(restantes):
        nx = normalizar(x)
        for seg_b, rot_b in rot_do_bloco.items():
            # o bloco pode ter juntado trechos seguidos ("apendice" + "diametro aumentado")
            if x == seg_b or (nx and nx in normalizar(seg_b)):
                anterior_rot[k] = rot_b
                break

    def lugar(trecho, primeiro):
        k_o = restantes.index(primeiro) if primeiro in restantes else -1
        antes = anterior_rot.get(k_o - 1) if k_o > 0 else None
        if antes in onde and _RELACAO.search(normalizar(trecho)):
            return antes, True
        rot = _rotulo_para(trecho, reg, list(onde))
        if rot is not None:
            return rot, False
        if antes in onde:
            # sem estrutura clara logo depois de um achado do banco: detalhe dele
            return antes, True
        return None, False

    def colocar(rot, dito, voto, continuacao):
        i = onde[rot]
        m = _ROT_LINHA.match(linhas[i])
        rotulo, corpo = m.group(1), m.group(2)
        frase = revisar_local(dito).strip().rstrip(".;, ") + "."
        rad_o = _rad_tc(voto)
        ficam = []
        for n_f, f in enumerate([f for f in re.split(r"(?<=[.;])\s+", corpo) if f.strip()]):
            nf = normalizar(f)
            if n_f == 0 and _frase_normal_tc(f, normais):
                continue                                    # a descricao normal da estrutura ("sem colecoes")
            if nf.startswith(("demais", "restante")):
                continue                                    # "Demais segmentos sem alteracoes"
            if _NEG_TC.match(nf):
                cont = _rad_tc(re.sub(r"^(?:nao ha|nao se \w+|nao sao \w+|ausencia de|ausentes?|sem)\s*", "", nf))
                if not cont or cont & rad_o:
                    continue                                # "sem alteracoes" / o que o achado desmente
                ficam.append(("neg", f))
            elif nf in normais:
                continue                                    # a descricao normal da estrutura
            else:
                ficam.append(("alt", f))
        alteradas = [f for tp, f in ficam if tp == "alt"]
        negativas = [f for tp, f in ficam if tp == "neg"]
        partes = alteradas + [frase] + negativas
        partes = [_min(partes[0])] + [_cap(p) for p in partes[1:]]
        sep = re.search(r":(\s+)", linhas[i]).group(1)
        linhas[i] = rotulo + ":" + sep + " ".join(partes)
        if not continuacao:
            conclusao.append(_cap(frase))

    for trecho, grupo in _grupos_de_orfaos(orfaos, restantes, bruto):
        if len(grupo) > 1:
            # junta quando abre com o nome da estrutura ("pancreas com atrofia e
            # calcificacoes") ou quando cada pedaco, sozinho, iria para o mesmo lugar
            r0 = _rad_tc(grupo[0])
            nome = bool(r0) and any(r0 <= _rad_tc(rot, 4) for rot in onde)
            votos = [_rotulo_para(o, reg, list(onde)) for o in grupo]
            # (o pedaco sem estrutura, "espessura de 8 mm", e detalhe do anterior)
            grupo_ok = nome or (votos[0] is not None and len({v for v in votos if v}) == 1)
        if len(grupo) > 1 and grupo_ok:
            rot, cont = lugar(trecho, grupo[0])
            if rot is not None:
                colocar(rot, _palavras_do_medico(trecho, bruto, bruto_lit), trecho, cont)
                continue
        for o in grupo:
            if _ja_no_texto(o, linhas):
                continue
            rot, cont = lugar(o, o)
            if rot is None:
                sobra.append(o)
                continue
            colocar(rot, literal.get(o, o), o, cont)
    if conclusao:
        c = _idx(linhas, {"CONCLUSAO", "IMPRESSAO", "OPINIAO"})
        if c is not None:
            f = _fim_secao(linhas, c)
            corpo = [l for l in linhas[c + 1:f] if l.strip() and not NORMAL.search(l.strip())]
            ja = {normalizar(l) for l in corpo}
            novos = [x for x in conclusao if normalizar(x) not in ja]
            cauda = linhas[f:]
            linhas = linhas[:c + 1] + corpo + novos + ([""] + cauda if cauda else [])
    return "\n".join(linhas), sobra


# ---------------------------------------------------------------------------
# ALTERACOES PRIMEIRO (regra do Bruno): na analise, as estruturas com achado
# abrem o laudo; as normais vem abaixo, na ordem da mascara.
# config.json: "alteradas_primeiro": false mantem a ordem da mascara.
# ---------------------------------------------------------------------------
def _normais_preenchidas(meta, bruto, ctx):
    out = set()
    for _g, _t, txt_n in _normais_da_regiao(meta):
        for fonte in (txt_n, preencher(txt_n, bruto, ctx)):
            for l in fonte.split("\n"):
                m = _ROT_LINHA.match(l.replace("**", ""))
                corpo = m.group(2) if m else l
                for f in re.split(r"(?<=[.;])\s+", corpo):
                    if f.strip():
                        out.add(normalizar(f))
    return out


_PAL_NORMAL_TC = re.compile(r"preservad|\bnormais?\b|habitua(?:l|is)|dentro dos limites|sem particularidades|"
                            r"sem alteracoes|\bregulares?\b|centrad|normopneumat|normodistend|topic|integr|"
                            r"simetric|\blivres?\b|homogene|mantid|conservad")
_MARCA_TC = re.compile(r"compativ|sugestiv|aument|reduc|reduz|espessa|calcul|cisto|nodul|massa|derrame|"
                       r"atelect|consolid|opacid|fratur|hernia|protrus|abaulament|estenos|dilatad|ectasi|"
                       r"aneurism|trombo|colecao|liquido livre|densifica|hipodens|hiperdens|hipoatenu|"
                       r"hiperatenu|realce|lesao|osteofit|ateromat|placa|esteatose|litiase|edema|enfisema|"
                       r"bronquiectas|fibros|cicatri|gliose|encefalomal|isquemi|hemorrag|atrofi|calcifica|"
                       r"espondil|artros|escolio|listese|desvio|sequela|pos operatori|protese|material")


def _frase_normal_tc(f, normais):
    nf = normalizar(f)
    if not nf or nf in normais or _NEG_TC.match(nf) or nf.startswith(("demais", "restante")):
        return True
    return bool(_PAL_NORMAL_TC.search(nf)) and not _MARCA_TC.search(nf)


def _alteradas_primeiro(texto, tit, bruto="", ctx=""):
    if not _config().get("alteradas_primeiro", True):
        return texto
    meta = BANCO.meta.get(tit)
    if not meta or meta[1] == "rx":
        return texto                    # radiografia: rx_literal.compor ja ordena
    linhas = texto.split("\n")
    a = _idx(linhas, {"ANALISE", "RELATORIO", "ACHADOS"})
    if a is None:
        return texto
    fim = _fim_secao(linhas, a)
    while fim - 1 > a and not linhas[fim - 1].strip():
        fim -= 1
    corpo = linhas[a + 1:fim]
    # unidades: linha com rotulo + as linhas seguintes sem rotulo (continuacao)
    unidades, marcas = [], []
    for l in corpo:
        if l.startswith("[não encontrado"):
            marcas.append(l)
        elif _ROT_LINHA.match(l) or not unidades:
            unidades.append([l])
        else:
            unidades[-1].append(l)
    if sum(1 for u in unidades if _ROT_LINHA.match(u[0])) < 3:
        return texto                    # mascara sem rotulos: fica como esta
    normais = _normais_preenchidas(meta, bruto, ctx)

    def alterada(u):
        for l in u:
            if not l.strip():
                continue
            m = _ROT_LINHA.match(l)
            c = m.group(2) if m else l
            if any(not _frase_normal_tc(f, normais) for f in re.split(r"(?<=[.;])\s+", c) if f.strip()):
                return True
        return False
    alt = [u for u in unidades if alterada(u)]
    if not alt:
        return texto
    nor = [u for u in unidades if not alterada(u)]
    novo = [l for u in alt + nor for l in u] + marcas
    return "\n".join(linhas[:a + 1] + novo + linhas[fim:])


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


# ---------------------------------------------------------------------------
# RX LITERAL: a abertura do ditado acha a mascara; cada achado entra com as
# PALAVRAS DO MEDICO na linha certa (rx_literal.py). Sem conclusao, sem grau
# que nao foi dito. "descrever X" pede a frase pronta do banco.
# config.json: "rx_literal": false volta ao modo antigo (blocos do banco).
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"[^\W_]+")
_NORMAIS = {"n": None, "por_regiao": {}}
_TROCA_TECNICA = ("leito", "portatil", "uti", "dinamicas", "dinamica")
_LADO_W = set("direito direita esquerdo esquerda bilateral bilaterais ambos lados".split())


def _normais_da_regiao(meta):
    """Gatilhos das mascaras NORMAIS da mesma regiao: [(gatilho, titulo, texto)]."""
    if _NORMAIS["n"] != len(BANCO.itens):
        por = {}
        for t, g, tit, txt, sec, con in BANCO.itens:
            m = BANCO.meta.get(tit, ("",) * 4)
            if t == "mascara" and g and txt and m[3] == "normal":
                por.setdefault(m[:3], []).append((g, tit, txt))
        for k in por:
            por[k].sort(key=lambda x: -len(x[0]))
        _NORMAIS.update(n=len(BANCO.itens), por_regiao=por)
    return _NORMAIS["por_regiao"].get(tuple(meta[:3]), [])


def _fim_token(texto, k):
    """Posicao logo depois do k-esimo token (palavra ou numero) do texto."""
    if k <= 0:
        return 0
    for i, m in enumerate(_TOKEN.finditer(texto), 1):
        if i == k:
            return m.end()
    return None


def _fim_cabecalho(toks, g):
    """Quantos tokens do ditado formam o cabecalho que casou com o gatilho g:
    o menor prefixo que contem as palavras do gatilho, mais o lado e a tecnica
    logo depois ("raio x de joelho esquerdo artrose..." -> 5)."""
    nt = [normalizar(t) for t in toks]
    alvo = [w for w in g.split() if len(w) > 2 and w not in _GENERICAS]
    for k in range(1, len(toks) + 1):
        pref = set(" ".join(nt[:k]).split())
        if all(w in pref or difflib.get_close_matches(w, pref, 1, 0.8) for w in alvo):
            j = k
            while j < len(nt):
                w = nt[j]
                if w in _LADO_W or w in rx_literal.TECNICA:
                    j += 1
                    continue
                if w in rx_literal.STOP:
                    prox = next((x for x in nt[j + 1:] if x not in rx_literal.STOP), None)
                    if prox and (prox in _LADO_W or prox in rx_literal.TECNICA):
                        j += 1
                        continue
                break
            return j
    return None


def _coberto_todo(seg, cobertos):
    """O trecho so repete o cabecalho ("joelho direito" depois de "raio x de
    joelho direito"). Qualquer palavra nova (lado, achado) mantem o trecho."""
    cont = [w for w in normalizar(seg).split() if w not in rx_literal.STOP]
    return bool(cont) and all(w in cobertos for w in cont)


_SO_NORMAL = {"sem alteracoes", "sem alteracoes significativas", "normal", "normais", "exame normal",
              "dentro da normalidade", "dentro dos limites da normalidade", "sem anormalidades",
              "nada digno de nota", "sem achados", "sem achados significativos", "estudo normal"}
_RX_ABRE = re.compile(r"\b(?:raio x|rx|radiografia|rotina de abdome)\b")


def _cabecalho_rx(bruto, bruto_lit):
    """Radiografia cuja abertura nao casou do jeito comum: "proximo, raio x de
    ...", "agora raio x ...", "raio x do joelho direito mostrando ...". Procura o
    exame nas primeiras palavras. Devolve (bruto, bruto_lit, cab_raw, cab_norm,
    titulo, texto) ja sem o que vinha antes do exame, ou None."""
    n = normalizar(bruto)
    m = _RX_ABRE.search(n)
    if not m:
        return None
    k0 = len(n[:m.start()].split())
    if k0 > 4:
        return None
    if k0:
        c1, c2 = _fim_token(bruto, k0), _fim_token(bruto_lit, k0)
        if c1 is None or c2 is None:
            return None
        bruto = re.sub(r"^[\s,.;:!?-]+", "", bruto[c1:])
        bruto_lit = re.sub(r"^[\s,.;:!?-]+", "", bruto_lit[c2:])
        n = normalizar(bruto)
    cab_raw, cab_norm, tit, txt = _cabecalho_do_exame(bruto, n, _FRONTEIRA_RX, so_rx=True)
    if txt is None:
        seg0 = segmentar(bruto)[0]
        t2, x2, _sc, g = BANCO.buscar2(normalizar(seg0), "mascara")
        if x2 is None or BANCO.meta.get(t2, ("",) * 4)[1] != "rx" or not bruto.startswith(seg0):
            return None
        cab_raw, cab_norm, tit, txt = seg0, g, t2, x2
    return bruto, bruto_lit, cab_raw, cab_norm, tit, txt


_CONECTOR = re.compile(r"^[\s,.;:]*(?:(?:com|e|mostrando|evidenciando|demonstrando|apresentando|"
                       r"onde se (?:observa|nota|v[eê])|observa-se|observando-se|nota-se|notando-se|"
                       r"identifica-se|identificando-se|que (?:mostra|evidencia|demonstra))\b[\s,.;:]*)+", re.I)
_VIRGULA_FALADA = [(re.compile(r"\s+ponto e v[ií]rgula\b", re.I), ";"),
                   (re.compile(r"\s+v[ií]rgula\b", re.I), ","),
                   (re.compile(r"\s+ponto final\b", re.I), ".")]


def _compor_rx_literal(bruto_lit, bruto, cab_raw, cab_norm, tit, txt):
    """(texto, origem) ou None (entao segue o modo antigo)."""
    meta = BANCO.meta.get(tit, ("",) * 4)
    if meta[1] != "rx" or not rx_literal.aplicavel(txt):
        return None
    if not cab_raw or not bruto.startswith(cab_raw):
        return None
    toks = _TOKEN.findall(cab_raw)
    fim = len(toks)
    if normalizar(cab_raw) != cab_norm:
        # cabecalho achado por aproximacao: corta onde o gatilho termina
        k = _fim_cabecalho(toks, cab_norm)
        if k is not None:
            fim = k
    trocou = False
    if meta[3] != "normal":
        # mascara ALTERADA pelo gatilho ("raio x da bacia com coxartrose"):
        # rotulo generico ("com alteracoes cronicas", "no leito") mantem a mascara;
        # achado vira a mascara NORMAL + o achado com as palavras ditadas
        g0 = next(((g, t0, x0) for g, t0, x0 in _normais_da_regiao(meta)
                   if cab_norm == g or cab_norm.startswith(g + " ")), None)
        if g0 is not None and not rx_literal.eh_rotulo(cab_norm[len(g0[0]):].strip()):
            k = _fim_cabecalho(toks, g0[0])
            if k is not None and k < len(toks):
                tit, txt = g0[1], g0[2]
                fim, trocou = k, True
    corte = _fim_token(bruto_lit, fim)
    if corte is None:
        return None
    resto = bruto_lit[corte:]
    for rx_v, sub_v in _VIRGULA_FALADA:
        resto = rx_v.sub(sub_v, resto)
    lado_ini = re.match(r"^[\s,]*((?:(?:direit|esquerd)[oa]s?|bilaterai?s?|ambos|ambas)\b[\s,]*)+", resto, re.I)
    lead = []
    if lado_ini:                                # "raio x do joelho direito mostrando ..."
        lead.append(lado_ini.group(0).strip(" ,"))
        resto = resto[lado_ini.end():]
    resto = _CONECTOR.sub("", resto)
    partes = rx_literal.partir(resto) if resto.strip() else []
    while partes and not _relevante(partes[0][1]) and not rx_literal.tem_achado(normalizar(partes[0][1])):
        lead.append(partes.pop(0)[1])           # "rx de joelho, direito, com ..."
    ctx = " ".join([cab_raw] + lead)
    # o que o CABECALHO ja disse (so a parte usada como cabecalho: em "raio x da
    # bacia com coxartrose" a coxartrose e achado, nao cabecalho)
    cobertos = set(normalizar(" ".join(toks[:fim])).split())
    if not trocou:
        cobertos |= set(cab_norm.split())
    tecnicas, filtradas = [x for x in lead if rx_literal.eh_tecnica(x)], []
    for sep, seg in partes:
        if rx_literal.eh_tecnica(seg):
            tecnicas.append(seg)
        elif not _coberto_todo(seg, cobertos):
            filtradas.append((sep, seg))
    meta = BANCO.meta.get(tit, ("",) * 4)
    # "raio x de torax, no leito, com ...": a variante de tecnica da mesma regiao
    if tecnicas and meta[3] == "normal":
        base_g = next((g for g, t0, x0 in _normais_da_regiao(meta) if t0 == tit and
                       (cab_norm == g or cab_norm.startswith(g + " "))), cab_norm)
        feito = False
        for seg in tecnicas:
            for w in normalizar(seg).split():
                if w not in _TROCA_TECNICA or feito:
                    continue
                for alvo in (base_g + " no " + w, base_g + " " + w, base_g + " com " + w):
                    t2, x2, sc2, g2 = BANCO.buscar2(alvo, "mascara")
                    if x2 is not None and sc2 >= 0.95 and t2 != tit and \
                            BANCO.meta.get(t2, ("",) * 4)[:3] == meta[:3] and \
                            rx_literal.aplicavel(x2) and rx_literal.eh_rotulo(g2[len(base_g):].strip()
                                                                             if g2.startswith(base_g) else w):
                        tit, txt, feito = t2, x2, True
                        break
    achados = []
    for ach in rx_literal.juntar(filtradas):
        a = ach["texto"]
        m = re.match(r"^\s*(?:descrev\w*|descreva)\s+(.+)$", a, re.I)
        if m:
            x = m.group(1)
            nx = normalizar(ouvido_bruto(x))
            meta = BANCO.meta.get(tit, ("",) * 4)
            # 1) a mascara pronta do achado ("descrever pneumonia")
            if meta[3] == "normal":
                base_g = next((g for g, t0, x0 in _normais_da_regiao(meta) if t0 == tit), cab_norm)
                t2, x2, sc2, _g2 = BANCO.buscar2(base_g + " com " + nx, "mascara")
                if x2 is not None and sc2 >= 1.0 and t2 != tit and \
                        BANCO.meta.get(t2, ("",) * 4)[:3] == meta[:3] and rx_literal.aplicavel(x2):
                    tit, txt = t2, x2
                    continue
            # 2) a frase do banco para o achado ("descrever gonartrose do compartimento medial")
            bl = achar_blocos([ouvido_bruto(x)], BANCO.meta.get(tit))
            if bl:
                _bt, btxt, bsec, _bc, _bs = bl[0]
                corpo = preencher(btxt, x, ctx, aproximar=True)
                for linha in corpo.split("\n"):
                    if linha.strip():
                        achados.append({"texto": _sem_hifen(linha).strip(), "secao": bsec})
                continue
            a = x                                   # 3) sem frase no banco: literal
        if not m and normalizar(a) in _SO_NORMAL:
            continue                            # "sem alteracoes": a mascara ja e normal
        t = rx_literal.limpar(a, revisar_local)
        if t:
            if m:
                achados.append({"texto": t})
            else:
                achados.append({"texto": t, "cabeca": ach["cabeca"], "extras": ach["extras"]})
    if "dispositiv" not in cab_norm:
        txt = rx_literal.sem_dispositivos_do_molde(txt)
    # "raio x dos joelhos", "de ambos os pes": exame dos dois lados
    if re.search(r"\b(?:ambos|ambas|bilateral|bilaterais)\b|\b(?:dos|das) \w+s\b",
                 normalizar(bruto_lit[:corte])) and not re.search(r"\b(?:direit|esquerd)", normalizar(ctx)):
        ctx = ctx + " bilateral"
    # lacunas da mascara: so pelo CABECALHO. O nivel/lobo/medida de um achado nao
    # pode ir para outra frase ("anterolistese de L4" nao vira "osteofitos em L4").
    # O lado do titulo pode vir do ditado, se so um lado foi dito.
    lado_dit = _lado(normalizar(bruto))
    fonte = ctx if (_lado(normalizar(ctx)) or not lado_dit) else ctx + " " + lado_dit
    base = preencher(txt, fonte, ctx)
    normais = set()
    for _g, _t, txt_n in _normais_da_regiao(meta):
        normais.update(rx_literal._n(l) for l in txt_n.split("\n") if l.strip())
    texto = rx_literal.compor(base, achados, normais=normais,
                              alteradas_primeiro=_config().get("alteradas_primeiro", True))
    if texto is None:
        return None
    if achados:
        return texto, "rx_literal:%s+%d achado(s)" % (tit, len(achados))
    return texto, "mascara:%s" % tit


# ---------------------------------------------------------------------------
# FILA DO RADIUS (radius.py): le so os arquivos de estado, so os campos
# permitidos. Nome e numero de acesso nunca saem de radius.py.
# "perfil_automatico": true no config.json -> ditado de RX sem o nome do exame
# usa o exame ABERTO no Radius ("opacidade na base direita" vira "raio x de
# torax, opacidade na base direita"). Desligado ate a leitura ser conferida.
# ---------------------------------------------------------------------------
_MASC_ESTUDO = {}


def _mascara_do_estudo(cab):
    if not cab:
        return None
    if cab not in _MASC_ESTUDO:
        if len(_MASC_ESTUDO) > 500:
            _MASC_ESTUDO.clear()
        n = normalizar(ouvido_bruto(cab))
        _c, _g, tit, _t = _cabecalho_do_exame(cab, n)
        if tit is None:
            t2, x2, sc, _g2 = BANCO.buscar2(n, "mascara")
            tit = t2 if (x2 is not None and sc >= 0.9) else None
        if tit is not None and not _modalidade_confere(n, tit):
            tit = None
        _MASC_ESTUDO[cab] = tit
    return _MASC_ESTUDO[cab]


def fila_radius():
    c = _config()
    if radius is None:
        return {"disponivel": False, "itens": [], "atual": None, "perfil_automatico": False}
    pasta = radius.pasta_radius(c)
    fila = radius.ler_fila(pasta)
    at = radius.atual(fila)
    for x in fila:
        x["cabecalho"] = radius.cabecalho(x)
        x["mascara"] = _mascara_do_estudo(x["cabecalho"])
        x.pop("fonte", None)
        x.pop("principal", None)
    try:
        # o diagnostico (sem dado de paciente) acompanha a fila ao longo do dia
        radius.gravar_diagnostico_se_velho(pasta, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                               "radius_estrutura.txt"))
    except Exception:
        pass
    d = _estacao_ler()
    feitos = set(d.get("feitos") or [])
    for x in fila:
        x["feito"] = x["id"] in feitos
    vez = estacao_atual(fila)
    return {"disponivel": True, "pasta_existe": os.path.isdir(pasta), "itens": fila,
            "atual": at["id"] if at else None,
            "vez": vez["id"] if vez else None,
            "escolhido": d.get("escolhido"),
            "perfil_automatico": bool(c.get("perfil_automatico", False))}


# ---------------------------------------------------------------------------
# MODO ESTACAO: o exame da vez (Ctrl+Alt+N no app passa para o proximo).
# Guarda so codigos embaralhados (nada de nome nem numero de acesso).
# ---------------------------------------------------------------------------
_ESTACAO_ARQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "estacao.json")


def _estacao_ler():
    try:
        with open(_ESTACAO_ARQ, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("escolhido", None)
            d.setdefault("feitos", [])
            return d
    except (OSError, ValueError):
        pass
    return {"escolhido": None, "feitos": []}


def _estacao_gravar(d, ids_da_fila=None):
    if ids_da_fila is not None:                 # so guarda o que ainda esta na fila
        d["feitos"] = [i for i in d.get("feitos", []) if i in ids_da_fila][-500:]
    try:
        os.makedirs(os.path.dirname(_ESTACAO_ARQ), exist_ok=True)
        tmp = _ESTACAO_ARQ + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _ESTACAO_ARQ)
    except OSError:
        pass


def _pendente(x, feitos):
    return not x.get("laudado") and x.get("id") not in feitos


def estacao_atual(fila):
    """O exame da vez: o escolhido na estacao, senao o aberto no Radius."""
    d = _estacao_ler()
    feitos = set(d.get("feitos") or [])
    esc = next((x for x in fila if x.get("id") == d.get("escolhido")), None)
    if esc is not None and _pendente(esc, feitos):
        return esc
    at = radius.atual(fila) if radius is not None else None
    if at is not None and _pendente(at, feitos):
        return at
    return next((x for x in fila if _pendente(x, feitos)), None)


def estacao_escolher(id_estudo):
    fila = fila_radius()
    d = _estacao_ler()
    d["escolhido"] = id_estudo
    _estacao_gravar(d, {x["id"] for x in fila.get("itens", [])})
    item = next((x for x in fila.get("itens", []) if x["id"] == id_estudo), None)
    return {"ok": item is not None, "item": item}


def estacao_feito(id_estudo, feito=True):
    fila = fila_radius()
    d = _estacao_ler()
    feitos = [i for i in d.get("feitos", []) if i != id_estudo]
    if feito:
        feitos.append(id_estudo)
    d["feitos"] = feitos
    if feito and d.get("escolhido") == id_estudo:
        d["escolhido"] = None
    _estacao_gravar(d, {x["id"] for x in fila.get("itens", [])})
    return {"ok": True}


def estacao_proximo():
    """Marca o exame da vez como laudado aqui e passa para o proximo pendente."""
    if radius is None:
        return {"ok": False, "motivo": "sem_radius"}
    fila = fila_radius()
    itens = fila.get("itens", [])
    d = _estacao_ler()
    feitos = list(d.get("feitos") or [])
    atual = estacao_atual(itens)
    if atual is not None and atual["id"] not in feitos:
        feitos.append(atual["id"])
    pendentes = [x for x in itens if _pendente(x, set(feitos))]
    prox = pendentes[0] if pendentes else None
    d["feitos"] = feitos
    d["escolhido"] = prox["id"] if prox else None
    _estacao_gravar(d, {x["id"] for x in itens})
    return {"ok": True, "item": prox, "restam": len(pendentes)}


# ---------------------------------------------------------------------------
# CORRECOES DO MEDICO (correcao.py): a caixa de texto do app ("saiu risartrose,
# e com z"; "nao escrever tal frase no rx de punho") vira regra na hora.
# ---------------------------------------------------------------------------
def _regiao_do_exame(nome_exame):
    """"raio x de punho" -> "msk/rx/punho" (para a regra valer so nesse exame)."""
    tit = _mascara_do_estudo(normalizar(ouvido_bruto(nome_exame or "")))
    if not tit:
        return ""
    m = BANCO.meta.get(tit)
    return "/".join(m[:3]) if m else ""


def correcao_aplicar(texto, laudo="", usar_ia=False):
    if correcao_mod is None:
        return {"ok": False, "motivo": "correcao_indisponivel"}
    return correcao_mod.aplicar(texto, laudo, usar_ia, nuvem,
                                nuvem.config() if nuvem is not None else None,
                                _regiao_do_exame)


def correcao_listar():
    if correcao_mod is None:
        return {"ok": False, "motivo": "correcao_indisponivel"}
    return correcao_mod.listar()


def correcao_desfazer(id_regra):
    if correcao_mod is None:
        return {"ok": False, "motivo": "correcao_indisponivel"}
    return correcao_mod.desfazer(id_regra)


def perfil_exportar(destino=None, incluir_estilo=False):
    if perfil_mod is None:
        return {"ok": False, "motivo": "perfil_indisponivel"}
    return perfil_mod.exportar(destino, incluir_estilo)


def perfil_importar(arquivo, modo="juntar"):
    if perfil_mod is None:
        return {"ok": False, "motivo": "perfil_indisponivel"}
    r = perfil_mod.importar(arquivo, modo)
    try:
        BANCO.carregar()
    except Exception:
        pass
    return r


def _cabecalho_automatico():
    """Abertura do exame aberto no Radius, se o perfil automatico estiver ligado
    e o exame for radiografia. Senao, ""."""
    if radius is None or not _config().get("perfil_automatico", False):
        return ""
    try:
        fila = radius.ler_fila(radius.pasta_radius(_config()))
        for x in fila:
            x["cabecalho"] = radius.cabecalho(x)
        at = estacao_atual(fila)
    except Exception:
        return ""
    cab = radius.cabecalho(at) if at else ""
    # so com a regiao ("raio x de torax"); "raio x" sozinho nao diz a mascara
    return cab if cab.startswith("raio x de ") else ""


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
            # "pasta": o app (Rotrix) grava a configuração na pasta do roteador que está rodando
            return self._json(200, {"versao": VERSAO, "gatilhos": len(BANCO.itens),
                                    "pasta": os.path.dirname(os.path.abspath(__file__))})
        if self.path.rstrip("/") in ("/ia", "/v1/ia"):
            # botão de IA e contador de gasto (nunca devolve chave)
            if nuvem is None:
                return self._json(200, {"ativa": False})
            try:
                return self._json(200, nuvem.estado())
            except Exception as e:
                return self._json(500, {"error": type(e).__name__})
        if self.path.rstrip("/") in ("/fila", "/v1/fila"):
            # fila do Radius: so modalidade, descricao, status e laudado (nunca nome)
            try:
                return self._json(200, fila_radius())
            except Exception as e:
                return self._json(500, {"error": type(e).__name__})
        if self.path.rstrip("/") in ("/correcao", "/v1/correcao"):
            return self._json(200, correcao_listar())
        if self.path.rstrip("/") in ("/recarregar", "/v1/recarregar"):
            BANCO.carregar()
            return self._json(200, {"ok": True, "gatilhos": len(BANCO.itens)})
        self._json(404, {"error": "not found"})

    def _corpo(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_POST(self):
        rota = self.path.rstrip("/")
        if rota.endswith(("/fila/proximo", "/fila/escolher", "/fila/feito",
                          "/perfil/exportar", "/perfil/importar",
                          "/correcao", "/correcao/desfazer")):
            corpo = self._corpo()
            try:
                if rota.endswith("/fila/proximo"):
                    return self._json(200, estacao_proximo())
                if rota.endswith("/fila/escolher"):
                    return self._json(200, estacao_escolher(corpo.get("id")))
                if rota.endswith("/fila/feito"):
                    return self._json(200, estacao_feito(corpo.get("id"), bool(corpo.get("feito", True))))
                if rota.endswith("/correcao"):
                    return self._json(200, correcao_aplicar(corpo.get("texto") or "",
                                                            corpo.get("laudo") or "",
                                                            bool(corpo.get("usar_ia"))))
                if rota.endswith("/correcao/desfazer"):
                    return self._json(200, correcao_desfazer(corpo.get("id")))
                if rota.endswith("/perfil/exportar"):
                    return self._json(200, perfil_exportar(corpo.get("destino"),
                                                           bool(corpo.get("incluir_estilo"))))
                return self._json(200, perfil_importar(corpo.get("arquivo"), corpo.get("modo") or "juntar"))
            except Exception as e:
                print("AVISO: %s falhou (%s: %s)" % (rota, type(e).__name__, e), file=sys.stderr)
                return self._json(500, {"ok": False, "error": type(e).__name__, "detalhe": str(e)[:200]})
        t0 = time.time()
        ditado = ""
        try:
            BANCO.atualizada()
        except Exception as e:
            print("base: falha ao recarregar:", e, flush=True)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            ditado = extrair_ditado(body)
            texto, origem = rotear(ditado)
            if (not origem.startswith("nuvem")) and (time.time() - t0 > ORCAMENTO_S):
                texto, origem = ditado, "estouro_de_tempo"
            if correcao_mod is not None:
                try:
                    texto = correcao_mod.aplicar_regras(texto, origem)
                except Exception as e:
                    print("AVISO: regras do medico falharam (%s)" % type(e).__name__, file=sys.stderr)
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


def _base_em_dia():
    """A base foi gerada com as máscaras do usuário e a fonte atuais? (importar_usuario)"""
    if not os.path.exists(BASE) or os.path.getsize(BASE) == 0:
        return False                      # sem base: refaz
    try:
        import importar_usuario
        esperado = importar_usuario.assinatura_usuario()
        con = sqlite3.connect("file:%s?mode=ro" % BASE.replace("\\", "/"), uri=True)
        try:
            v = con.execute("SELECT valor FROM meta WHERE chave='assinatura_usuario'").fetchone()
        except sqlite3.OperationalError:
            v = None                      # base antiga, sem assinatura
        con.close()
        return (v[0] if v else "rotrix|0|0|0") == esperado
    except Exception:
        return True


if __name__ == "__main__":
    # atualização trocou a base (sem as máscaras do usuário) ou a fonte mudou: refaz
    if not _base_em_dia():
        try:
            import importar_usuario
            ok, msg = importar_usuario.refazer_base()
            print("base refeita com as máscaras do usuário:", msg, flush=True)
            BANCO.carregar()
        except Exception as e:
            print("não consegui refazer a base:", e, flush=True)
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
    if radius is not None:
        # estrutura dos arquivos do Radius, SEM dado de paciente (radius_estrutura.txt)
        def _diag_radius():
            try:
                p = radius.pasta_radius(_config())
                if os.path.isdir(p):
                    radius.gravar_diagnostico(p, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                              "radius_estrutura.txt"))
            except Exception:
                pass
        threading.Thread(target=_diag_radius, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"roteador em http://{HOST}:{PORT}/v1  (Ctrl+C para sair)", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nencerrado")
