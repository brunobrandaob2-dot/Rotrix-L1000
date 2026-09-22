# -*- coding: utf-8 -*-
"""Gera base.sqlite e CATALOGO.txt a partir de dados/.

Organização das máscaras (recursiva):

    dados/mascaras/<categoria>/<modalidade>/<regiao>/
        normal.txt              máscara normal
        cronica_<nome>.txt      máscara com alteração crônica / corriqueira
        aguda_<nome>.txt        máscara com alteração aguda
        blk_<nome>.txt          bloco encaixável na máscara da mesma região
        frases.txt              repertório de frases prontas da região
    dados/mascaras/_comum/      adendos, ressalvas e achados genéricos
    dados/mascaras/_legado/     ignorado na compilação

Cabeçalho dos arquivos (linhas iniciadas por #):
    # gatilhos: a | b | c
    # tipo: mascara | bloco | frases | adendo | achado   (padrão: mascara)
    # categoria / # modalidade / # regiao / # tipo_mascara
    # secao: (blocos)  # conclusao: (blocos)

Arquivo de frases:
    ## gatilhos: a | b
    Texto da frase.
    ## gatilhos: c | d
    Outra frase.
"""
import json, os, re, sqlite3, sys, unicodedata, collections

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)          # Python embutido (Rotrix) não põe a pasta do script no caminho
DADOS = os.path.join(AQUI, "dados")
BASE = os.environ.get("LAUDO_BASE") or os.path.join(AQUI, "base.sqlite")
CATALOGO = os.environ.get("LAUDO_CATALOGO") or os.path.join(AQUI, "CATALOGO.txt")

NOMES_CATEGORIA = {
    "medicina_interna": "MEDICINA INTERNA",
    "neuro": "NEURORRADIOLOGIA",
    "msk": "MUSCULOESQUELÉTICO",
    "angio": "ANGIOTOMOGRAFIA",
    "_comum": "COMUM (adendos e achados genéricos)",
    "usuario": "MINHAS MÁSCARAS",
}
NOMES_MODALIDADE = {"tc": "TOMOGRAFIA", "rx": "RADIOGRAFIA",
                    "angiotc": "ANGIOTOMOGRAFIA", "rm": "RESSONÂNCIA", "": "-"}


def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _meta_do_caminho(rel):
    """categoria/modalidade/regiao a partir da pasta, quando o arquivo não diz."""
    p = rel.replace("\\", "/").split("/")
    cat = p[0] if len(p) > 1 else ""
    mod = p[1] if len(p) > 2 else ""
    reg = p[2] if len(p) > 3 else ""
    return cat, mod, reg


def _subtipo_do_nome(nome):
    n = nome.lower()
    if n.startswith("normal"): return "normal"
    if n.startswith("cronica"): return "cronica"
    if n.startswith("aguda"): return "aguda"
    return ""


# Formas curtas do nome do exame, geradas sozinhas: "rx ombro", "tc cranio",
# "raio x do joelho"... Entram DEPOIS dos gatilhos escritos, então nunca
# tomam o lugar de um gatilho explícito de outra máscara.
_FORMAS = {"tc": ["tomografia computadorizada", "tomografia", "tc"],
           "rx": ["radiografia", "raio x", "rx"],
           "angiotc": ["angiotomografia computadorizada", "angiotomografia", "angio tc", "angio"]}
_ARTIGOS = ("de ", "do ", "da ", "dos ", "das ")

def _variantes(g, mod):
    formas = _FORMAS.get(mod)
    if not formas:
        return []
    for f in sorted(formas, key=len, reverse=True):
        if g.startswith(f + " "):
            resto = g[len(f) + 1:]
            break
    else:
        return []
    for a in _ARTIGOS:
        if resto.startswith(a):
            resto = resto[len(a):]
            break
    out = []
    for f in formas:
        for a in ("", "de ", "do ", "da "):
            v = f"{f} {a}{resto}"
            if v != g:
                out.append(v)
    return out

variantes = []

# (tipo, gatilho_norm, gatilho, titulo, texto, secao, conclusao,
#  categoria, modalidade, regiao, subtipo)
linhas = []
avisos = []

# --- fonte das máscaras (config.json -> fonte_mascaras) ---
#   rotrix: só dados/mascaras (padrão)   minhas: só dados/mascaras_usuario (+ _comum)
#   ambas:  as duas; as do usuário entram primeiro e vencem quando o comando é o mesmo
try:
    import importar_usuario as _iu
    FONTE = _iu.fonte_atual()
    ASSINATURA = _iu.assinatura_usuario()
except Exception as _e:
    print("AVISO: importar_usuario indisponível (%s); usando só as máscaras do Rotrix" % _e)
    FONTE, ASSINATURA = "rotrix", "rotrix|0|0|0"

dm = os.path.join(DADOS, "mascaras")
RAIZES = []
if FONTE in ("minhas", "ambas"):
    RAIZES.append((os.path.join(DADOS, "mascaras_usuario"), "usuario/", False))
RAIZES.append((dm, "", FONTE == "minhas"))
for dm_raiz, prefixo, so_comum in RAIZES:
    if not os.path.isdir(dm_raiz):
        continue
    for raiz, pastas, arquivos in os.walk(dm_raiz):
        pastas[:] = sorted(p for p in pastas if p != "_legado" and not p.startswith("."))
        if so_comum and raiz == dm_raiz:
            pastas[:] = [p for p in pastas if p == "_comum"]
            arquivos = []
        for nome in sorted(arquivos):
            if not nome.lower().endswith(".txt"):
                continue
            caminho = os.path.join(raiz, nome)
            rel = prefixo + os.path.relpath(caminho, dm_raiz).replace("\\", "/")
            bruto = open(caminho, encoding="utf-8").read().splitlines()

            meta = {"tipo": "", "categoria": "", "modalidade": "", "regiao": "",
                    "tipo_mascara": "", "secao": "", "conclusao": ""}
            gatilhos, inicio = [], len(bruto)
            for i, l in enumerate(bruto):
                s = l.strip()
                if s.startswith("## "):
                    inicio = i; break
                if s.startswith("#"):
                    m = re.match(r"#\s*([a-z_]+)\s*:(.*)$", s, re.I)
                    if m:
                        k, v = m.group(1).lower(), m.group(2).strip()
                        if k == "gatilhos":
                            gatilhos = [g.strip() for g in v.split("|") if g.strip()]
                        elif k in meta:
                            meta[k] = v
                    continue
                inicio = i; break

            cat0, mod0, reg0 = _meta_do_caminho(rel)
            cat = meta["categoria"] or cat0
            mod = meta["modalidade"] or mod0
            reg = meta["regiao"] or reg0
            tipo = (meta["tipo"] or ("bloco" if nome.startswith("blk_") else
                                     "frases" if nome.startswith("frases") else
                                     "adendo" if nome.startswith(("adendo", "ressalva")) else
                                     "achado" if nome.startswith("achado") else
                                     "mascara")).lower()
            sub = meta["tipo_mascara"] or _subtipo_do_nome(nome)
            titulo = rel[:-4]

            if tipo == "frases":
                atual_g, atual_t = None, []
                def _fecha():
                    if atual_g and "".join(atual_t).strip():
                        txt = "\n".join(atual_t).strip()
                        for g in atual_g:
                            linhas.append(("frase", normalizar(g), g, titulo + "#" + atual_g[0],
                                           txt, "", "", cat, mod, reg, ""))
                for l in bruto[inicio:]:
                    m = re.match(r"##\s*gatilhos?\s*:(.*)$", l.strip(), re.I)
                    if m:
                        _fecha()
                        atual_g = [g.strip() for g in m.group(1).split("|") if g.strip()]
                        atual_t = []
                    elif atual_g is not None:
                        atual_t.append(l)
                _fecha()
                continue

            texto = "\n".join(bruto[inicio:]).strip("\n")
            if not gatilhos:
                gatilhos = [os.path.splitext(nome)[0].replace("_", " ")]
                avisos.append("sem gatilhos: " + rel)
            for g in gatilhos:
                linhas.append((tipo, normalizar(g), g, titulo, texto, meta["secao"],
                               meta["conclusao"], cat, mod, reg, sub))
            if tipo == "mascara":
                for g in gatilhos:
                    for v in _variantes(normalizar(g), mod):
                        variantes.append((tipo, v, v, titulo, "", meta["secao"],
                                          meta["conclusao"], cat, mod, reg, sub))

# --- frases de RM musculoesquelética do banco original ---
fj = os.path.join(DADOS, "frases.json")
if os.path.exists(fj) and FONTE != "minhas":
    for r in json.load(open(fj, encoding="utf-8")):
        d = (r.get("descricao") or "").strip()
        if not d:
            continue
        tit = (r.get("titulo") or "").strip() or d[:60]
        reg = normalizar(r.get("regiao") or "").replace(" ", "_")
        for g in {tit}:
            if len(normalizar(g)) >= 5:
                linhas.append(("frase", normalizar(g), g, "msk/rm/" + reg + "#" + tit,
                               d, "", "", "msk", "rm", reg, ""))

# --- dedup ---
# máscaras, adendos e achados: gatilho único no banco inteiro
# blocos: únicos DENTRO da região (o mesmo "derrame articular" existe no joelho
#         e no quadril, e o roteador escolhe pelo exame ditado)
# frases: únicas no banco inteiro (são chamadas sem contexto de exame)
vistos, final, colisoes = set(), [], []
def _do_usuario(l):
    return l[3].startswith("usuario/")
ordem = ([(l, True) for l in linhas if _do_usuario(l)] +
         [(l, False) for l in variantes if _do_usuario(l)] +
         [(l, True) for l in linhas if not _do_usuario(l)] +
         [(l, False) for l in variantes if not _do_usuario(l)])
for l, explicito in ordem:
    tipo, gn = l[0], l[1]
    k = (tipo, gn, l[7], l[8], l[9]) if tipo == "bloco" else (tipo, gn)
    if not gn:
        continue
    if k in vistos:
        if explicito:
            colisoes.append((tipo, l[2], l[3]))
        continue
    vistos.add(k)
    final.append(l)

# grava num arquivo novo e troca no fim: o roteador que está rodando nunca lê a base pela metade
BASE_NOVA = BASE + ".nova"
if os.path.exists(BASE_NOVA):
    os.remove(BASE_NOVA)
con = sqlite3.connect(BASE_NOVA)
con.execute("""CREATE TABLE entradas(
    tipo TEXT, gatilho_norm TEXT, gatilho TEXT, titulo TEXT, texto TEXT,
    secao TEXT, conclusao TEXT,
    categoria TEXT, modalidade TEXT, regiao TEXT, subtipo TEXT)""")
con.executemany("INSERT INTO entradas VALUES (?,?,?,?,?,?,?,?,?,?,?)", final)
con.execute("CREATE INDEX ix ON entradas(tipo, gatilho_norm)")
con.execute("CREATE INDEX ix2 ON entradas(categoria, modalidade, regiao)")
con.execute("CREATE TABLE meta(chave TEXT, valor TEXT)")
con.execute("INSERT INTO meta VALUES (?, ?)", ("assinatura_usuario", ASSINATURA))
con.execute("INSERT INTO meta VALUES (?, ?)", ("fonte_mascaras", FONTE))
con.commit()
con.close()
import time as _time
for _tentativa in range(20):              # no Windows, a troca falha se alguém lê a base neste instante
    try:
        os.replace(BASE_NOVA, BASE)
        break
    except PermissionError:
        _time.sleep(0.25)
else:
    os.replace(BASE_NOVA, BASE)

# --- catálogo ---
arvore = collections.OrderedDict()
por_titulo = collections.OrderedDict()
for l in final:
    por_titulo.setdefault(l[3], l)
    if l[0] == "frase" and l[8] != "rm":
        por_titulo[l[3]] = l
ordem_cat = ["usuario", "medicina_interna", "neuro", "angio", "msk", "_comum"]
def _ordcat(c): return ordem_cat.index(c) if c in ordem_cat else 99
primeiro_gatilho = {}
for l in final:
    primeiro_gatilho.setdefault(l[3], l[2])

grupos = collections.defaultdict(lambda: collections.defaultdict(list))
for tit, l in por_titulo.items():
    tipo, cat, mod, reg, sub = l[0], l[7], l[8], l[9], l[10]
    if mod == "rm":
        continue
    grupos[(cat, mod, reg)][tipo if tipo != "mascara" else "mascara_" + (sub or "outra")].append(
        primeiro_gatilho.get(tit, l[2]))

out = ["CATÁLOGO DO ROTEADOR DE LAUDOS",
       "Gerado automaticamente por construir_base.py. Não edite à mão.",
       "", "Fale o que está entre aspas com Ctrl+Alt+Space.",
       "Blocos entram numa máscara: \"<exame> com <bloco>, <bloco>\".",
       "Frases saem soltas: \"frase <gatilho>\".", ""]
cat_atual = mod_atual = None
for (cat, mod, reg) in sorted(grupos, key=lambda k: (_ordcat(k[0]), k[1], k[2])):
    g = grupos[(cat, mod, reg)]
    if cat != cat_atual:
        out += ["", "═" * 64, " " + NOMES_CATEGORIA.get(cat, cat.upper()), "═" * 64]
        cat_atual, mod_atual = cat, None
    if mod != mod_atual:
        out += ["", "  ── " + NOMES_MODALIDADE.get(mod, mod.upper()) + " " + "─" * 40]
        mod_atual = mod
    out += ["", "   " + (reg.replace("_", " ").upper() or "GERAL")]
    for rot, chave in (("normal", "mascara_normal"), ("crônicas", "mascara_cronica"),
                       ("agudas", "mascara_aguda"), ("outras", "mascara_outra"),
                       ("blocos", "bloco"), ("adendos", "adendo"), ("achados", "achado")):
        if g.get(chave):
            out.append("     %-9s %s" % (rot, "  |  ".join('"%s"' % x for x in g[chave])))
    if g.get("frase"):
        out.append("     frases    %d prontas — veja abaixo" % len(g["frase"]))
        for x in g["frase"]:
            out.append("                 \"frase %s\"" % x)
io_txt = "\n".join(out) + "\n"
open(CATALOGO, "w", encoding="utf-8").write(io_txt)

c = collections.Counter(l[0] for l in final)
print(f"base.sqlite gerado: {len(final)} gatilhos  {dict(c)}  (fonte: {FONTE})")
print(f"CATALOGO.txt gerado: {len(grupos)} regiões")
if colisoes:
    print(f"AVISO: {len(colisoes)} gatilho(s) repetido(s) ignorado(s):")
    for t, g, tit in colisoes[:25]:
        print(f"   [{t}] \"{g}\"  em {tit}")
for a in avisos[:10]:
    print("AVISO:", a)
