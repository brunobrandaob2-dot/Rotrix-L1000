# -*- coding: utf-8 -*-
"""
RX literal: a radiografia com as PALAVRAS DO MÉDICO.

O ditado de RX é uma lista de achados em sequência:
    "raio x de tórax no leito, com tubo orotraqueal, sonda enteral,
     cateter venoso central à direita, opacidades pulmonares bilaterais"

O roteador acha a máscara pela abertura do ditado ("raio x de tórax no leito")
e este módulo põe cada achado, com as palavras ditadas, na linha certa da
ANÁLISE:
  - troca a frase normal da mesma estrutura ("Campos pulmonares sem
    opacidades focais." -> "Opacidades pulmonares bilaterais.");
  - dispositivos (tubo, sonda, cateter, dreno, prótese...) abrem a análise,
    um por linha;
  - o que não tem lugar certo entra antes de "Partes moles" (ou no fim).

Nunca acrescenta diagnóstico, grau ou conclusão que não foi ditado.
Módulo puro: não depende do banco (o roteador faz a escolha da máscara).
"""
import re
import unicodedata


def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _n(s):
    """Normalizado para comparar estruturas ("coluna de ar" = "coluna aérea")."""
    n = normalizar(s)
    n = re.sub(r"\bcoluna de ar\b", "coluna aerea", n)
    return n


# ---------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------

STOP = set("""de do da dos das no na nos nas em com e a o as os ao aos um uma uns umas
sob pelo pela pelos pelas por para entre sobre ate que se""".split())

# técnica: o trecho só diz COMO o exame foi feito (não é achado)
TECNICA = set("""realizado realizada realizados realizadas feito feita exame estudo leito beira
portatil aparelho incidencia incidencias ap pa perfil perfis frente obliqua obliquas obliquo
ortostase ortostatica ortostatico decubito supino supina sentado sentada inspiracao expiracao
carga apoio dinamica dinamicas flexao extensao axial mortise penetracao tecnica uti rotina
tres duas transoral lauenstein comparativo comparativa comparativas panoramica panoramico
controle paciente acamado acamada internado internada restrito restrita""".split())

# rótulo genérico de máscara alterada: MANTÉM a máscara pronta
ROTULO = set("""alteracoes alteracao cronicas cronica cronicos cronico degenerativas degenerativa
degenerativos involutivas involutiva idade idoso idosa idosos senis senil dispositivos
dispositivo pos operatorio operatoria operatorios apos queda trauma traumatismo normal
normais habituais""".split())

# qualificador: sozinho, o trecho só qualifica o achado anterior
QUALIF = set("""direito direita direitos direitas esquerdo esquerda esquerdos esquerdas bilateral
bilaterais bilateralmente ambos ambas lados lado discreto discreta discretos discretas leve leves
moderado moderada moderados moderadas acentuado acentuada acentuados acentuadas importante
importantes incipiente incipientes proeminente proeminentes pequeno pequena pequenos pequenas
grande grandes extenso extensa extensos extensas difuso difusa difusos difusas esparso esparsa
esparsos esparsas focal focais multiplo multipla multiplos multiplas inferior inferiores
superior superiores medial mediais lateral laterais anterior anteriores posterior posteriores
proximal proximais distal distais basal basais apical apicais medio media medios medias
predominio predominantemente grau graus mais menos evidente evidentes cm mm i ii iii iv
""".split()) | STOP

# o trecho que começa assim continua o achado anterior
PREPOS = set("da do das dos de no na nos nas em ao aos a para entre sobre ate".split())
CONTINUA = set("""convexidade concavidade predominio predominando predominante predominantemente
medindo mede medida extremidade extremidades ponta pontas desvio deslocamento angulacao
cavalgamento afastamento diastase sendo principalmente notadamente sobretudo especialmente
associado associada associados associadas determinando causando cujo cuja mais
posicionado posicionada posicionados posicionadas projetado projetada projetados projetadas
localizado localizada localizados localizadas pior melhor maior menor""".split())

# ", sem desvio": qualifica a fratura anterior
SEM_QUALIF = set("""desvio desvios deslocamento deslocamentos angulacao cavalgamento afastamento
diastase complicacao complicacoes extensao acometimento sinais""".split())

# achado genérico que precisa do lugar do próximo: "redução e irregularidade do espaço medial"
GENERICO_SEM_LUGAR = set("""reducao aumento esclerose irregularidade irregularidades espessamento
alargamento estreitamento calcificacao calcificacoes cisto cistos erosao erosoes osteofitos
pincamento deformidade apagamento velamento opacidade opacidades opacificacao""".split())
_LADO_W = set("direito direita esquerdo esquerda direitos direitas esquerdos esquerdas".split())

_NIVEL_W = re.compile(r"^[ctls]\d{1,2}$")

# ---------------------------------------------------------------------------
# Categorias: (nome, radicais do achado, [(âncora na linha da máscara, ação)])
# Ordem = prioridade. Só vale a categoria cuja âncora existe NESTA máscara;
# senão tenta a próxima. Ações: troca | depois | antes_demais
# ---------------------------------------------------------------------------

DISP = re.compile(r"\b(?:tubos?|sondas?|cateter|cateteres|drenos?|marca ?passo|cardiodesfibrilador|"
                  r"desfibrilador|eletrodos?|canulas?|traqueostomia|clipes?|grampos?|fios? de|"
                  r"cerclagem|esternorrafia|proteses?|endoproteses?|artroplastia|placas?(?! pleura)|"
                  r"parafusos?|hastes?|material de sintese|osteossintese|fixador(?:es)?|kirschner|"
                  r"diu|stents?|port a cath|portocath|derivacao|balao|monitorizacao|"
                  r"artrodese|cimento|ancoras?|arames?|espacador(?:es)?|cages?|banda de tensao|"
                  r"pinos?|tela cirurgica|tot|sng|sne|snd|sog|cvc|picc|dvp|cdi|tqt)\b")

def _c(nome, radicais, ancoras, tambem=None):
    return (nome, re.compile(radicais), [(re.compile(a), acao) for a, acao in ancoras], tambem or [])

_FRATURA_ANC = [(r"fratur|luxa", "troca"), (r"corpos vertebrais", "depois"), (r"arcabouc", "troca"),
                (r"calota", "troca")]
_OSSO_ANC = [(r"arcabouc", "troca")]

CATEGORIAS = [
    # --- cavum / seios da face / crânio ---
    _c("adenoide", r"adenoid|vegetac|tecido linfoide|amigdala faringea",
       [(r"adenoid", "troca"), (r"rinofaring", "troca")],
       tambem=[(re.compile(r"\bcoluna\b"), re.compile(r"coluna aerea da rinofaringe|rinofaringe com coluna aerea"))]),
    _c("orofaringe", r"amigdal|tonsil|orofaring|palatin", [(r"orofaring", "troca")]),
    _c("palato", r"\bpalato", [(r"palato", "troca")]),
    _c("prevertebral", r"pre vertebr|prevertebr|retrofaring", [(r"pre vertebr|prevertebr", "troca")]),
    _c("coluna_aerea", r"coluna aerea|via aerea",
       [(r"coluna aerea da rinofaringe|rinofaringe com coluna aerea", "troca"), (r"coluna aerea", "troca")]),
    _c("maxilar", r"maxilar", [(r"maxilar", "troca"), (r"seios paranasais", "troca")]),
    _c("frontal", r"\bseios? frontai?s?\b|\bfrontais\b", [(r"seios? frontai?s?", "troca"), (r"seios paranasais", "troca")]),
    _c("etmoide", r"etmoid|esfenoid", [(r"etmoid|esfenoid", "troca"), (r"seios paranasais", "troca")]),
    _c("nasal", r"\bnasa(?:l|is)\b|\bsepto\b|concha|corneto", [(r"nasal", "troca")]),
    _c("seios", r"\bseios? paranasa|sinusopatia|sinusite", [(r"seios paranasais", "troca"), (r"maxilar", "troca")]),
    _c("sutura", r"\bsutura", [(r"sutura", "troca")]),
    _c("sela", r"\bsela\b|selar", [(r"\bsela\b", "troca")]),
    # --- tórax ---
    _c("pleura", r"costofren|pleur|pneumotorax|hidrotorax|hemotorax", [(r"costofren|pleur", "troca")]),
    _c("coracao", r"cardiac|cardiomegal|coracao|pericard|cardiotoracic", [(r"cardiac", "troca")]),
    _c("aorta", r"\baort|ateromat|botao", [(r"mediastin", "depois"), (r"partes moles", "antes_demais")]),
    _c("mediastino", r"mediastin|traqueia|\btimo\b|bocio", [(r"mediastin", "troca")]),
    _c("hilo", r"\bhilos?\b|hilar", [(r"\bhilos?\b|hilar", "troca")]),
    _c("diafragma", r"cupula|diafragm", [(r"cupula|diafragm", "troca")]),
    _c("subcutaneo", r"subcutane|enfisema de partes moles", [(r"partes moles", "antes_demais"), (r"arcabouc", "depois")]),
    _c("pulmao", r"opacid|opacific|consolid|infiltr|atelect|nodul|\bmassas?\b|transparen|enfisema|"
                 r"\btrama\b|reticul|intersticial|congest|cavita|\bbolhas?\b|pneumon|broncogram|"
                 r"bronqu|\bestrias?\b|fibro|granulom|vidro fosco|pulmo|parenquima|\blobos?\b|lingula|"
                 r"\bapice|\bbases? pulmon|cissur|edema pulmonar|hiperinsufl",
       [(r"campos? pulmon|parenquima pulmon", "troca")]),
    # --- abdome ---
    _c("pneumoperitonio", r"pneumoperit|gas livre|ar livre", [(r"pneumoperit", "troca")]),
    _c("gases", r"gasosa|\bgas\b|\bgases\b|meteoris|aerocolia|ampola retal", [(r"gasosa", "troca")]),
    _c("alcas", r"\balcas?\b|hidroaere|distens|obstru|volvo|suboclus|empilhament|\bcalibre\b",
       [(r"\balcas\b", "troca")]),
    _c("fezes", r"fecal|fezes|fecaloma|coprost|residuos?", [(r"fecal", "troca")]),
    _c("calculo", r"calcul|litiase|lojas? rena|ureter|imagens? calcica|flebolit", [(r"calcica", "troca")]),
    _c("corpo_estranho", r"corpos? estranhos?", [(r"corpos? estranhos?", "troca"), (r"partes moles", "antes_demais")]),
    # --- ossos e articulações ---
    _c("calota", r"calota|litica|esclerotica|hiperostose|diploe|osteolit",
       [(r"calota", "troca"), (r"lesoes osseas|lesao ossea", "troca")]),
    _c("pinca", r"\bpinca\b|espaco claro", [(r"\bpinca\b", "troca")]),
    _c("sindesmose", r"sindesmose|tibiofibular", [(r"sindesmose", "troca")]),
    _c("coxins", r"\bcoxi|sinal da vela|derrame articular", [(r"\bcoxi", "troca"), (r"partes moles", "antes_demais")]),
    _c("acromioumeral", r"acromioumeral|subacromial|ascensao da cabeca umeral", [(r"acromioumeral", "troca")]),
    _c("cam", r"\bcam\b|\bgiba\b|cabeca colo|transicao", [(r"transicao cabeca", "troca")]),
    _c("acetabulo", r"\bacetabul|cobertura|displasia|pincer", [(r"acetabul", "troca")]),
    _c("arco_pe", r"pes? plan|pes? cav|planovalg|cavovar|\barcos? (?:longitudinal|plantar)|\barco\b",
       [(r"arco longitudinal", "troca")]),
    _c("cortical", r"cortica|periost", [(r"cortica", "troca")]),
    _c("altura_vertebral", r"\baltura\b|achatament|acunhament|colapso",
       [(r"corpos vertebrais", "troca"), (r"fratur", "troca")]),
    _c("fratura", r"fratur|luxa|avuls|fragmento osseo|calo osseo|consolidacao viciosa|pseudoartrose",
       _FRATURA_ANC, tambem=[(re.compile(r"fratur"), re.compile(r"contornos corticais regulares"))]),
    _c("lesao_ossea", r"lesao ossea|lesoes osseas|osteocondroma|exostose|enostose|ilhota",
       [(r"lesoes osseas|lesao ossea", "troca")]),
    _c("densidade", r"osteopen|rarefa|osteopor|desmineraliz|densidade", [(r"densidade", "troca")] + _OSSO_ANC),
    _c("sacroiliaca", r"sacroil", [(r"sacroil", "troca")]),
    _c("posterior", r"interapof|facet|uncoart|uncovert|elementos posteriores|espinhos|baastrup|"
                    r"\bistm|espondilolise|\blise\b",
       [(r"elementos posteriores|interapof|uncovert", "troca")]),
    _c("discos", r"discal|discais|\bdiscos?\b|discite|discopat|intervertebra|vacuo",
       [(r"discais|discal|intervertebra", "troca")]),
    _c("curvaturas", r"lordose|cifose|retific", [(r"curvatura", "troca")]),
    _c("alinhamento", r"alinhament|escoliose|escoliotic|retific|lordose|cifose|listese|desvio|"
                      r"desalinh|\bvaro\b|\bvalgo\b|\bvara\b|\bvalga\b|rotac|convexidade|halux|hallux|joanete",
       [(r"alinhament", "troca")] + _OSSO_ANC),
    _c("corpos", r"osteofit|espondil|corpos? vertebra|plataforma|schmorl|hemangioma|\bbicos?\b|"
                 r"sindesmofit|\bdish\b|hiperostose",
       [(r"corpos vertebrais", "depois")] + _OSSO_ANC),
    _c("rizartrose", r"rizartr|trapeziometacarp", [(r"trapeziometacarp", "troca")]),
    _c("erosao", r"\beros", [(r"erosoes", "troca"), (r"superficies articulares", "troca"),
                             (r"espacos? articular", "troca")]),
    _c("articular", r"artros|artrose|gonartr|coxartr|omartr|rizartr|artropat|espacos? articular|"
                    r"pincament|osteofit|subcondra|geod|compartiment|condrocalc|tricompartiment|"
                    r"femorotibial|femoropatelar|patelofemoral|tibiotalar|glenoumeral|acromioclavicular|"
                    r"radiocarpa|trapeziometacarp|interfalang|metatarsofalang|sinovi|incongruen|"
                    r"superficies articulares",
       [(r"espacos? articular", "troca"), (r"superficies articulares", "troca"),
        (r"articulac(?!\w* sacroil)", "troca")]),
    _c("partes_moles", r"partes moles|edema|tumefa|aumento de volume|entesop|entesof|esporao|calcific|"
                       r"tendinopat|tendinite|bursit|\bgas\b|lipoma|\bmassas?\b|ossificac|abaulament|"
                       r"espessament|haglund",
       [(r"partes moles", "antes_demais")]),
]

# sistema de cada categoria: "cardiomegalia com espondilose" são dois achados
_GRUPO = {"adenoide": "cavum", "orofaringe": "cavum", "palato": "cavum", "prevertebral": "cavum",
          "coluna_aerea": "cavum", "maxilar": "seios", "frontal": "seios", "etmoide": "seios",
          "nasal": "seios", "seios": "seios", "sutura": "cranio", "sela": "cranio",
          "pleura": "pulmao", "pulmao": "pulmao", "coracao": "coracao", "aorta": "mediastino",
          "mediastino": "mediastino", "hilo": "mediastino", "diafragma": "diafragma",
          "subcutaneo": "partes_moles", "partes_moles": "partes_moles", "corpo_estranho": "partes_moles",
          "pneumoperitonio": "intestino", "gases": "intestino", "alcas": "intestino", "fezes": "intestino",
          "calculo": "calculo"}


def grupo(n):
    """Sistema do achado (pela primeira categoria que casa); osso é o padrão."""
    for nome, rx, _a, _t in CATEGORIAS:
        if rx.search(n):
            return _GRUPO.get(nome, "osso")
    return None


_ACHADO_GERAL = re.compile(r"aument|reduc|diminu|alarg|espessa|calcific|lesa|lesoe|imagem|imagens|"
                           r"sinal|sinais|irregular|escler|deform|alterac|dilat|abaulam|afilam|apagam|"
                           r"velam|obliter|borrament|estreit|redu|hipertrof|hipotrof|atrofi|cisto|"
                           r"fratura|ausencia|presenca|nivel|diastase|luxa|subluxa")

_NORMAL_LINHA = re.compile(r"preservad|norma(?:l|is)\b|normalidade|habitua(?:l|is)\b|\blivres?\b|regular|\bsem\b|\bnao ha\b|"
                           r"normotranspar|congruente|centrad|dentro dos limites|de espessura")

_LACUNA = re.compile(r"___|\[[^\]\n]*/[^\]\n]*\]")

_NEGATIVO = re.compile(r"^(?:sem|nao|ausencia|ausentes?)\b")

_PALAVRA_NORMAL = set("""preservado preservada preservados preservadas normal normais habitual habituais
livre livres regular regulares alteracoes alteracao aspecto dimensoes espessura contornos contorno
posicao dentro limites normalidade evidente evidentes sinais centrado centrada congruente congruentes
normotransparente normotransparentes altura incidencia avaliacao limitada pela pelo nesta focais focal
significativas evidencia""".split())

_AFIN_GENERICA = set("""articular articulares articulacao articulacoes alteracoes aspecto habitual normal
normais dimensoes espessura contornos regulares direita direito esquerda esquerdo bilateral bilaterais
discreto discreta aumento reducao presenca regiao inferior superior anterior posterior lateral medial
partes preservado preservada preservados preservadas sinais evidente evidentes incipiente
incipientes proeminente proeminentes moderado moderada acentuado acentuada""".split())


def _radical(w, k=6):
    return w[:k] if len(w) > k else w


def _palavras_afinidade(n, minimo=6):
    return {_radical(w) for w in n.split() if len(w) >= minimo and w not in _AFIN_GENERICA}


def _afinidade(nf, nl):
    a = _palavras_afinidade(nf)
    if not a:
        return 0
    b = {_radical(w) for w in nl.split() if len(w) >= 6}
    return len(a & b)


def _estrutura(nl):
    """Palavras de estrutura de uma linha da máscara (sem as de normalidade)."""
    return {w for w in nl.split() if len(w) >= 4 and w not in _PALAVRA_NORMAL and w not in STOP}


def _coberta(estr, nf):
    """Todas as palavras de estrutura aparecem no achado (pela raiz)?"""
    raizes = {_radical(w, 5) for w in nf.split()}
    return bool(estr) and all(_radical(w, 5) in raizes for w in estr)


def eh_tecnica(seg):
    pal = normalizar(seg).split()
    return bool(pal) and any(w in TECNICA for w in pal) and all(w in TECNICA or w in STOP for w in pal)


def eh_rotulo(extra_norm):
    """O resto do gatilho da máscara alterada é só rótulo/técnica ("com alterações
    crônicas", "do idoso", "no leito", "após queda", "trauma sem fratura")?"""
    pal = extra_norm.split()
    if not pal:
        return True
    if "sem" in pal:
        return True
    return all(w in ROTULO or w in TECNICA or w in STOP for w in pal)


def tem_achado(n):
    if DISP.search(n) or _ACHADO_GERAL.search(n):
        return True
    return any(rx.search(n) for _nm, rx, _a, _t in CATEGORIAS)


def eh_dispositivo(n):
    return bool(DISP.search(n)) and not re.search(r"\bplacas? pleura", n)


def so_qualifica(n):
    pal = n.split()
    return bool(pal) and all(w in QUALIF or _NIVEL_W.match(w) or w.isdigit() for w in pal)


# ---------------------------------------------------------------------------
# Partir o ditado em achados
# ---------------------------------------------------------------------------

_SEP = re.compile(r"\s*[,;]\s*(?:(?:e|com)\b\s*)?|\s*\.(?:\s+|$)|\s+(?:e|com)\s+", re.I)


def partir(texto):
    """[(separador, trecho)] preservando o separador, sem partir "1,5 cm"."""
    prot = re.sub(r"(\d)\s*([,.])\s*(\d)",
                  lambda m: m.group(1) + ("\x00" if m.group(2) == "," else "\x01") + m.group(3), texto)
    partes, ult, sep = [], 0, ""
    for m in _SEP.finditer(prot):
        seg = prot[ult:m.start()]
        if seg.strip():
            partes.append((sep, seg))
            sep = m.group(0)
        else:
            sep = (sep + m.group(0)) if partes else ""
        ult = m.end()
    if prot[ult:].strip():
        partes.append((sep, prot[ult:]))
    return [(s, seg.replace("\x00", ",").replace("\x01", ".").strip()) for s, seg in partes]


def _tipo_sep(sep):
    s = sep.lower()
    if re.search(r"\bcom\b", s):
        return "com"
    if re.search(r"\be\b", s):
        return "e"
    if "," in s or ";" in s:
        return "virg"
    if "." in s:
        return "ponto"
    return ""


def _continua(tipo, seg, anterior=""):
    """O trecho continua o achado anterior?
    False = achado novo; "cabeca" = qualifica o achado (lado, grau, lugar, "com
    desvio"); "extra" = outro achado dito junto ("opacidade com derrame pleural",
    "..., reduzindo a coluna aérea"): fica na mesma frase, e a frase normal que
    ele desmente também sai."""
    n = normalizar(seg)
    pal = n.split()
    if not pal:
        return "cabeca"
    if so_qualifica(n):
        return "cabeca"
    if pal[0] in PREPOS:
        return "cabeca"
    if len(pal[0]) > 4 and pal[0].endswith("ndo"):
        return "extra"                   # "..., reduzindo a coluna aérea"
    if pal[0] == "sem" and len(pal) > 1 and pal[1] in SEM_QUALIF:
        return "cabeca"                  # "fratura do rádio, sem desvio"
    na = normalizar(anterior)
    if tipo == "e":
        pa = [w for w in na.split() if w not in QUALIF]
        if len(pa) == 1 and pa[0] in GENERICO_SEM_LUGAR:
            return "cabeca"              # "redução e irregularidade do espaço medial"
        return False if tem_achado(n) else "cabeca"   # "tíbia e fíbula"
    if pal[0] in CONTINUA:
        return "cabeca"                  # ", com desvio", ", com extremidade na cava"
    if tipo == "com":
        if eh_dispositivo(na):
            return "cabeca"              # "marcapasso com eletrodos"
        if eh_dispositivo(n):
            return False
        g1, g2 = grupo(na), grupo(n)
        if g1 and g2 and g1 != g2:
            return False                 # "cardiomegalia com espondilose": dois achados
        return "extra"                   # "opacidade com broncograma", "fratura com
                                         # redução do ângulo de Böhler"
    return False


def _junta(anterior, tipo, sep, seg):
    n = normalizar(seg)
    if tipo == "e":
        return anterior + " e " + seg
    if tipo == "com":
        return anterior + (", com " if "," in sep else " com ") + seg
    so_lado = bool(n.split()) and all(w in QUALIF for w in n.split())
    lado = so_lado or re.fullmatch(r"(?:a|ao|aos|as)\s+(?:direit|esquerd)\w*", n)
    return anterior + (" " if lado else ", ") + seg


def juntar(partes):
    """Agrupa os trechos em achados: [{"texto", "cabeca", "extras"}].
    "cabeca" é o achado principal (decide a linha); "extras" são os outros
    achados ditos na mesma frase."""
    achados = []
    for sep, seg in partes:
        tipo = _tipo_sep(sep)
        modo = _continua(tipo, seg, achados[-1]["texto"]) if achados else False
        if modo:
            a = achados[-1]
            a["texto"] = _junta(a["texto"], tipo, sep, seg)
            if modo == "extra":
                a["extras"].append(seg)
            elif a["extras"]:
                a["extras"][-1] = _junta(a["extras"][-1], tipo, sep, seg)
            else:
                a["cabeca"] = _junta(a["cabeca"], tipo, sep, seg)
        else:
            achados.append({"texto": seg, "cabeca": seg, "extras": []})
    return achados


# ---------------------------------------------------------------------------
# Limpar o texto do achado (sem mudar o que foi dito)
# ---------------------------------------------------------------------------

_NIVEL2 = re.compile(r"\b([ctls])\s?(\d{1,2})\s*[-–]?\s*([ctls])\s?(\d{1,2})\b", re.I)
_NIVEL1 = re.compile(r"\b([ctls])\s?(\d{1,2})\b", re.I)
_PRE_NIVEL = set("em de do da no na nos nas entre a e ate sobre nivel niveis ao aos".split())


def _niveis(t):
    t = _NIVEL2.sub(lambda m: "%s%s-%s%s" % (m.group(1).upper(), m.group(2), m.group(3).upper(), m.group(4)), t)
    t = re.sub(r"\b([ctls])(\d{1,2})\b", lambda m: m.group(1).upper() + m.group(2), t)
    # "artrose interapofisária L5-S1" -> "... em L5-S1"
    def em(m):
        antes = normalizar(m.group(1))
        return m.group(0) if antes in _PRE_NIVEL else m.group(1) + " em " + m.group(2)
    return re.sub(r"([^\W\d_]+)\s+((?:[CTLS]\d{1,2})(?:-[CTLS]\d{1,2})?)\b", em, t)


def limpar(texto, revisar=None):
    t = re.sub(r"^\s*(?:(?:com|e|mais)\s+)+", "", texto.strip(), flags=re.I)
    if revisar is not None:
        try:
            t = revisar(t) or t
        except Exception:
            pass
    t = _niveis(t)
    t = re.sub(r"\s+", " ", t).strip(" ,;:")
    t = re.sub(r"[.]+$", "", t).strip()
    if not t:
        return ""
    return t[0].upper() + t[1:] + "."


# ---------------------------------------------------------------------------
# Compor
# ---------------------------------------------------------------------------

CABECALHOS = {"TECNICA", "INDICACAO CLINICA", "INDICACAO", "ANALISE", "RELATORIO",
              "ACHADOS", "COMPARACAO", "CONCLUSAO", "IMPRESSAO", "OPINIAO"}
_CAB_RX = re.compile(r"^\s*\**\s*([^\W\d_][^:*]{1,40}?)\s*:\s*\**")
_ROTULO_LINHA = re.compile(r"^\s*-?\s*[^\W\d_][^:.;]{0,70}:\s")


def _cab(linha):
    s = (linha or "").strip()
    if not s or s.startswith("-"):
        return None
    m = _CAB_RX.match(s)
    if not m:
        return None
    n = normalizar(m.group(1)).upper()
    return n if n in CABECALHOS else None


def secao_analise(linhas):
    a = next((i for i, l in enumerate(linhas) if _cab(l) in {"ANALISE", "RELATORIO", "ACHADOS"}), None)
    if a is None:
        return None, None
    f = next((j for j in range(a + 1, len(linhas)) if _cab(linhas[j])), len(linhas))
    return a, f


_SLOT = re.compile(r"\{[^{}\n]*\}")


def sem_dispositivos_do_molde(texto):
    """Tira da ANÁLISE do molde as linhas de dispositivo com lacuna (máscara do
    leito): os dispositivos ditos entram com as palavras do médico."""
    linhas = texto.split("\n")
    a, f = secao_analise(linhas)
    if a is None:
        return texto
    corpo = [l for l in linhas[a + 1:f] if not (_SLOT.search(l) and eh_dispositivo(normalizar(_SLOT.sub(" ", l))))]
    return "\n".join(linhas[:a + 1] + corpo + linhas[f:])


def aplicavel(texto):
    """Máscara de RX em frases diretas (uma por linha, sem "Rótulo:")."""
    linhas = (texto or "").split("\n")
    a, f = secao_analise(linhas)
    if a is None:
        return False
    corpo = [l for l in linhas[a + 1:f] if l.strip()]
    return bool(corpo) and not any(_ROTULO_LINHA.match(l) for l in corpo)


def _escolher(nf, itens):
    """(id da linha, ação) para o achado; None se não tem lugar certo."""
    originais = [it for it in itens if it["orig_id"] is not None and it["ancoravel"]]
    vistos = {}
    for it in originais:
        vistos.setdefault(it["orig_id"], it)
    base = list(vistos.values())
    for nome, rx, ancoras, _t in CATEGORIAS:
        if not rx.search(nf):
            continue
        cands = []
        for r, (arx, acao) in enumerate(ancoras):
            for it in base:
                if arx.search(it["n0"]):
                    cands.append((_afinidade(nf, it["n0"]), -r, it, acao))
        if cands:
            cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
            _af, _r, it, acao = cands[0]
            return it["orig_id"], acao, nome
    # sem categoria: a linha normal que cita a mesma estrutura ("sínfise púbica")
    pal = {_radical(w) for w in nf.split() if len(w) >= 7 and w not in _AFIN_GENERICA}
    if pal:
        cands = []
        for it in base:
            if not it["normal0"]:
                continue
            k = len(pal & {_radical(w) for w in it["n0"].split() if len(w) >= 7})
            if k:
                cands.append((k, it))
        cands.sort(key=lambda c: -c[0])
        if cands and (len(cands) == 1 or cands[0][0] > cands[1][0]):
            return cands[0][1]["orig_id"], "troca", "afinidade"
    return None


_POS_OP = re.compile(r"^(?:pos operatori|status pos|pos cirurgic|pos op\b|controle pos)")
_PROTESE = re.compile(r"\b(?:proteses?|endoproteses?|artroplastia)\b")


def _escolher_protese(nf, itens):
    """Prótese articular entra na linha dos espaços articulares, se houver."""
    for nome, _rx, ancoras, _t in CATEGORIAS:
        if nome == "articular":
            cands = [it for it in itens if it["orig_id"] is not None and it["ancoravel"]
                     and any(arx.search(it["n0"]) for arx, _a in ancoras)]
            if cands:
                return cands[0]["orig_id"], "troca", nome
    return None


def _desmentidas(nx, itens, oid_principal):
    """Frases normais que um achado dito junto desmente ("opacidade com DERRAME
    PLEURAL" -> sai "Seios costofrênicos livres.")."""
    if not nx or _NEGATIVO.match(nx):
        return set()
    esc = _escolher(nx, itens)
    if esc is not None:
        oid, acao, _nome = esc
        if acao == "troca" and oid != oid_principal:
            return {it["orig_id"] for it in itens if it["orig_id"] == oid and it["orig"] and it["normal0"]}
        return set()
    # sem categoria: a frase normal que nomeia a mesma estrutura ("ângulo de Böhler")
    pal = {_radical(w, 5) for w in nx.split() if len(w) >= 5 and w not in _AFIN_GENERICA}
    alvo = [it for it in itens if it["orig"] and it["normal0"] and it["orig_id"] != oid_principal
            and pal & {_radical(w, 5) for w in _estrutura(it["n0"]) if len(w) >= 5}]
    return {alvo[0]["orig_id"]} if len(alvo) == 1 else set()


def compor(base, achados, revisar=None, tirar_dispositivos_lacuna=False):
    """base: máscara já preenchida. achados: lista de dicts
         {"texto": str}                      achado ditado (literal)
         {"texto": str, "secao": str}        frase do banco ("descrever X")
    Devolve o texto final, ou None se a máscara não serve para o modo literal."""
    linhas = base.split("\n")
    a, f = secao_analise(linhas)
    if a is None:
        return None
    corpo = linhas[a + 1:f]
    itens = []
    for k, l in enumerate(corpo):
        n0 = _n(l)
        vazio = not l.strip()
        itens.append({"t": l, "orig_id": None if vazio else k, "orig": not vazio, "n0": n0,
                      "normal0": bool(not vazio and _NORMAL_LINHA.search(n0)),
                      "lacuna": bool(_LACUNA.search(l)),
                      "ancoravel": not vazio and not n0.startswith("a radiografia")})
    if tirar_dispositivos_lacuna:
        itens = [it for it in itens if not (it["lacuna"] and eh_dispositivo(it["n0"]))]

    def pos_ultimo(oid):
        return max(i for i, it in enumerate(itens) if it["orig_id"] == oid)

    def novo(t, oid):
        return {"t": t, "orig_id": oid, "orig": False, "n0": _n(t), "normal0": False,
                "lacuna": False, "ancoravel": False}

    def trocar(oid, t):
        i = next((i for i, it in enumerate(itens) if it["orig_id"] == oid and it["orig"]), None)
        orig = itens[i] if i is not None else None
        if orig is not None and (orig["normal0"] or orig["lacuna"]):
            orig.update(t=t, orig=False)
            orig["ancoravel"] = True          # outras estruturas ainda podem mirar esta linha
            return orig
        n_it = novo(t, oid)
        itens.insert(pos_ultimo(oid) + 1, n_it)
        return n_it

    removidas = set()
    topo, sem_lugar = [], []
    ultimo = None                               # item do último achado colocado
    for ac in achados:
        t = (ac.get("texto") or "").strip()
        if not t:
            continue
        nf = _n(t)
        if any(it["n0"] == nf for it in itens):
            continue                            # a máscara já diz exatamente isso
        if ac.get("secao"):
            alvo = normalizar(ac["secao"])
            oid = next((it["orig_id"] for it in itens if it["orig_id"] is not None
                        and (it["n0"] == alvo or it["n0"].startswith(alvo + " "))), None)
            if oid is None:
                sem_lugar.append(t)
            else:
                ultimo = trocar(oid, t)
            continue
        nc = _n(ac.get("cabeca") or t)
        if _POS_OP.match(nf):
            topo.append(t)                      # "pós-operatório de ..." abre a análise
            continue
        if eh_dispositivo(nf):
            esc = _escolher_protese(nf, itens) if _PROTESE.search(nf) else None
            if esc is None:
                topo.append(t)
                continue
        else:
            esc = _escolher(nc, itens)
            if esc is None:
                # "joelho direito com gonartrose": o achado está no que veio junto
                for extra in (ac.get("extras") or []) + [t]:
                    esc = _escolher(_n(extra), itens)
                    if esc is not None:
                        break
        if esc is None:
            j = next((i for i, it in enumerate(itens) if it is ultimo), None)
            if j is not None:
                # sem lugar próprio: segue o achado ditado antes ("velamento do seio
                # maxilar e nível hidroaéreo")
                n_it = novo(t, ultimo["orig_id"])
                itens.insert(j + 1, n_it)
                ultimo = n_it
            else:
                sem_lugar.append(t)
            continue
        oid, acao, nome = esc
        for extra in ac.get("extras") or []:
            removidas.update(_desmentidas(_n(extra), itens, oid))
        if re.search(r"luxa", nf) and not _NEGATIVO.match(nc):
            # luxação desmente a articulação normal que ela cita ("luxação glenoumeral"
            # tira "Espaço articular glenoumeral preservado.") e a congruência
            pal = {_radical(w, 9) for w in nf.split() if len(w) >= 8 and w not in _AFIN_GENERICA}
            for it in itens:
                if it["orig"] and it["normal0"] and it["orig_id"] != oid and (
                        "congruente" in it["n0"].split() or
                        pal & {_radical(w, 9) for w in it["n0"].split() if len(w) >= 8}):
                    removidas.add(it["orig_id"])
        if _NEGATIVO.match(nc) and acao == "troca":
            linha0 = next(it["n0"] for it in itens if it["orig_id"] == oid)
            estr = {w for w in nc.split() if len(w) >= 3 and w not in STOP} - {"sem", "nao", "sinais", "sinal"}
            if not any(_radical(w, 4) in {_radical(x, 4) for x in linha0.split()} for w in estr):
                acao = "depois"                 # "sem pneumotórax" não apaga "seios livres";
                                                # "sem gás no reto" troca "... gás até a ampola retal"
        if acao == "troca":
            ultimo = trocar(oid, t)
        elif acao == "depois":
            ultimo = novo(t, oid)
            itens.insert(pos_ultimo(oid) + 1, ultimo)
        else:                                   # antes_demais
            orig = next((it for it in itens if it["orig_id"] == oid and it["orig"]), None)
            ultimo = novo(t, oid)
            if orig is None:                    # a linha já foi trocada: entra depois dela
                itens.insert(pos_ultimo(oid) + 1, ultimo)
            else:
                if orig["n0"] == "partes moles sem alteracoes":
                    orig["t"] = re.sub(r"^\s*Partes moles", "Demais partes moles", orig["t"])
                itens.insert(next(i for i, it in enumerate(itens) if it is orig), ultimo)
        # explicitamente: "aumento da adenoide ... coluna de ar" apaga a coluna aérea normal
        for nm, _rx, _an, tambem in CATEGORIAS:
            if nm != nome:
                continue
            for gat, linha_rx in tambem:
                if gat.search(nf):
                    removidas.update(it["orig_id"] for it in itens
                                     if it["orig"] and it["normal0"] and linha_rx.search(it["n0"]))
        # a frase normal cuja estrutura inteira (3+ palavras) o achado cita
        # ("Sindesmose tibiofibular sem alargamento." / "alargamento da sindesmose
        # tibiofibular"); com 2 palavras não ("Corpos vertebrais com altura
        # preservada." continua valendo ao lado de "osteófitos nos corpos vertebrais")
        for it in itens:
            if it["orig"] and it["normal0"] and it["orig_id"] != oid:
                estr = _estrutura(it["n0"])
                if len(estr) >= 3 and _coberta(estr, nf):
                    removidas.add(it["orig_id"])

    itens = [it for it in itens if not (it["orig"] and it["orig_id"] in removidas)]
    if topo:
        k = next((i for i, it in enumerate(itens) if it["t"].strip()), len(itens))
        itens[k:k] = [novo(t, None) for t in topo]
    if sem_lugar:
        k = next((i for i, it in enumerate(itens) if it["orig"] and re.match(
            r"(?:demais )?partes moles|a radiografia", it["n0"])), None)
        if k is None:
            k = len(itens)
            while k > 0 and not itens[k - 1]["t"].strip():
                k -= 1
        itens[k:k] = [novo(t, None) for t in sem_lugar]
    return "\n".join(linhas[:a + 1] + [it["t"] for it in itens] + linhas[f:])
