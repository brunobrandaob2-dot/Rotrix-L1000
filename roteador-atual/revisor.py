# -*- coding: utf-8 -*-
"""Revisor local de transcrição radiológica.

Aplica, sem sair da máquina e em milissegundos, a parte DETERMINÍSTICA das
regras de revisão: números e unidades, comandos de pontuação falados,
hesitações, capitalização e vocabulário radiológico mal reconhecido.

Doutrina: só mexe no que é mecanicamente seguro. Nunca troca palavra duvidosa
por outra "clinicamente mais provável", nunca altera valor de medida, nunca
mexe em lateralidade, nível vertebral, segmento ou nome próprio. O que exige
julgamento fica para a camada de nuvem, que só entra por gatilho explícito.
"""
import re, unicodedata

# ══════════════════════════════════════════════════════════════════
#  1. NÚMEROS POR EXTENSO
# ══════════════════════════════════════════════════════════════════
UNID = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19,
}
DEZ = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
       "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90}
CEM = {"cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300,
       "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
       "setecentos": 700, "oitocentos": 800, "novecentos": 900}
TODOS = {}
TODOS.update(UNID); TODOS.update(DEZ); TODOS.update(CEM)

_PAL = sorted(TODOS, key=len, reverse=True)
_NUM_RX = re.compile(
    r"\b(?:(?:%s)(?:\s+e\s+(?:%s))*)\b" % ("|".join(_PAL), "|".join(_PAL)),
    re.IGNORECASE)


def _valor(frase):
    """'cento e vinte e três' -> 123. Devolve None se não fizer sentido."""
    toks = [t for t in re.split(r"\s+|\s+e\s+", frase.lower()) if t and t != "e"]
    if not toks:
        return None
    total = 0
    for t in toks:
        v = TODOS.get(t)
        if v is None:
            return None
        total += v
    # 'cento e vinte e três' = 123; 'dois e três' (2+3=5) não é número ditado
    if len(toks) > 1 and all(TODOS[t] < 20 for t in toks):
        return None
    return total


# "um"/"uma" sozinhos quase sempre são artigo ("um nódulo", "uma discreta
# quantidade"): só viram 1 quando vem medida logo depois
_UM_MEDIDA = re.compile(
    r"\s*(?:v[íi]rgula|ponto|por\b|x\b|e\s+meio|[,.]\s*(?:\d|%s)\b|cent[íi]metro|mil[íi]metro|metro|"
    r"mil[íi]litro|litro|grau|unidade|hounsfield|cm\b|mm\b|ml\b|%%)" % "|".join(_PAL), re.IGNORECASE)


def _numeros_por_extenso(t):
    def rep(m):
        if m.group(0).lower() in ("um", "uma") and not _UM_MEDIDA.match(m.string, m.end()):
            return m.group(0)
        v = _valor(m.group(0))
        return str(v) if v is not None else m.group(0)
    return _NUM_RX.sub(rep, t)


# ══════════════════════════════════════════════════════════════════
#  2. DECIMAIS, DIMENSÕES E UNIDADES
# ══════════════════════════════════════════════════════════════════
UNIDADES = [
    (r"cent[íi]metros?\b",          "cm"),
    (r"mil[íi]metros?\b",           "mm"),
    (r"metros?\b",                  "m"),
    (r"mil[íi]litros?\b",           "mL"),
    (r"litros?\b",                  "L"),
    (r"gramas?\b",                  "g"),
    (r"miligramas?\b",              "mg"),
    (r"quilogramas?\b",             "kg"),
    (r"segundos?\b",                "s"),
    (r"unidades?\s+hounsfield\b",   "UH"),
    (r"hounsfield\b",               "UH"),
    (r"cent[íi]metros?\s+c[úu]bicos?\b", "cm³"),
]
UNIDADES_RX = [(re.compile(r"(?<=[\d\s])" + p, re.IGNORECASE), s) for p, s in UNIDADES]


_EXT = "|".join(_PAL)


def _percentuais_falados(t):
    """Resolve 'setenta por cento' antes que 'cento' vire 100."""
    t = re.sub(r"\b((?:%s)(?:\s+e\s+(?:%s))*)\s+por\s+cento\b" % (_EXT, _EXT),
               lambda m: (str(_valor(m.group(1))) + "%") if _valor(m.group(1)) is not None
                         else m.group(0), t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\d+(?:,\d+)?)\s+por\s+cento\b", r"\1%", t, flags=re.IGNORECASE)
    return t


def _decimais(t):
    # 1 vírgula 2  ->  1,2
    t = re.sub(r"\b(\d+)\s*(?:v[íi]rgula|ponto)\s*(\d+)\b", r"\1,\2", t, flags=re.I)
    t = re.sub(r"(\d),\s+(\d)", r"\1,\2", t)
    # 3 por 4  ->  3 x 4     (só entre números)
    for _ in range(3):
        t = re.sub(r"\b(\d+(?:,\d+)?)\s+por\s+(\d+(?:,\d+)?)\b", r"\1 x \2", t, flags=re.I)
    return t


def _unidades(t):
    t = re.sub(r"\b(\d+(?:,\d+)?)\s*por\s+cento\b", r"\1%", t, flags=re.I)
    t = re.sub(r"\b(\d+(?:,\d+)?)\s*graus?\b", r"\1°", t, flags=re.I)
    for rx, sub in UNIDADES_RX:
        t = rx.sub(sub, t)
    # une a unidade ao último número da sequência: "3 x 4 mm" fica como está,
    # mas "3 mm x 4 mm" vira "3 x 4 mm"
    t = re.sub(r"\b(\d+(?:,\d+)?)\s*(mm|cm|m|mL|L)\s*x\s*(\d+(?:,\d+)?)\s*\2\b",
               r"\1 x \3 \2", t)
    t = re.sub(r"\b(\d+(?:,\d+)?)\s*(mm|cm)\s*x\s*(\d+(?:,\d+)?)\s*x\s*(\d+(?:,\d+)?)\s*\2\b",
               r"\1 x \3 x \4 \2", t)
    t = re.sub(r"(\d)\s+(mm|cm|mL|UH|%|°)\b", r"\1 \2", t)
    return t


# ══════════════════════════════════════════════════════════════════
#  3. COMANDOS DE PONTUAÇÃO FALADOS
# ══════════════════════════════════════════════════════════════════
# "ponto" sozinho é ambíguo ("pontos de maior carga"), então só converte
# quando vier claramente como comando. Na dúvida, preserva. (regra 6)
PONTUACAO = [
    (r"\babre\s+par[êe]nteses\b",       "("),
    (r"\bfecha\s+par[êe]nteses\b",      ")"),
    (r"\babre\s+aspas\b",               '"'),
    (r"\bfecha\s+aspas\b",              '"'),
    (r"\bdois\s+pontos\b",              ":"),
    (r"\bponto\s+e\s+v[íi]rgula\b",     ";"),
    (r"\bponto\s+final\b",              "."),
    (r"\bponto\s+par[áa]grafo\b",       ".\n"),
    (r"\bnovo\s+par[áa]grafo\b",        "\n"),
    (r"\bnova\s+linha\b",               "\n"),
    (r"\bpar[áa]grafo\b(?=\s*$)",       "\n"),
    (r"\binterroga[çc][ãa]o\b",         "?"),
    (r"\bexclama[çc][ãa]o\b",           "!"),
    # "vírgula" isolada, cercada de espaço, sem número dos dois lados
    (r"(?<![\d,])\s+v[íi]rgula\s+(?![\d])", ", "),
    # "ponto" isolado no fim do ditado ou antes de palavra capitalizada
    (r"\s+ponto\s*$",                   "."),
    (r"\s+ponto\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", ". "),
]
PONTUACAO_RX = [(re.compile(p, re.IGNORECASE), s) for p, s in PONTUACAO]

HESITACOES = re.compile(
    r"(?:(?<=^)|(?<=[\s,;:]))(?:é+|ã+h+|a+h+n+|hu+m+|é+h+|ehh+|hmm+)\s*\.{2,}\s*"
    r"|(?:(?<=^)|(?<=[\s,.;:]))(?:ã+h+|a+h+n+|hu+m+|ehh+|hmm+|tipo assim|"
    r"quer dizer)(?=[\s,.;:]|$)", re.IGNORECASE)


# "dois ponto cinco milímetros" é número decimal, não fim de frase
_PONTO_DECIMAL = re.compile(
    r"\b(%s|\d+)\s+ponto\s+(?=(?:%s|\d+)\b)" % ("|".join(_PAL), "|".join(_PAL)), re.IGNORECASE)


def _pontuacao(t):
    t = _PONTO_DECIMAL.sub(r"\1 vírgula ", t)
    for rx, sub in PONTUACAO_RX:
        t = rx.sub(sub, t)
    return t


# ══════════════════════════════════════════════════════════════════
#  4. VOCABULÁRIO RADIOLÓGICO
# ══════════════════════════════════════════════════════════════════
# Só entram erros FONÉTICOS evidentes e grafias objetivamente erradas.
# Nunca um termo clínico trocado por outro clinicamente parecido.
VOCABULARIO = [
    # --- palavras que o STT costuma separar ---
    (r"\blinfo\s+nodo(s?)\b",            r"linfonodo\1"),
    (r"\blinfo\s+nodomegalia(s?)\b",     r"linfonodomegalia\1"),
    (r"\bhemi\s+t[óo]rax\b",             "hemitórax"),
    (r"\bhemi\s+abd[oô]men\b",           "hemiabdome"),
    (r"\bseios?\s+costo\s+fr[êe]nicos?\b", "seios costofrênicos"),
    (r"\bcosto\s+fr[êe]nico(s?)\b",      r"costofrênico\1"),
    (r"\bfibro\s+atelect[áa]sic(a|o)(s?)\b", r"fibroatelectásic\1\2"),
    (r"\bbronco\s+vascular(es)?\b",      r"broncovascular\1"),
    (r"\bvidro\s+fosco\b",               "vidro fosco"),
    (r"\bporta\s+hepatis\b",             "porta hepatis"),
    (r"\bhepato\s+esplenomegalia\b",     "hepatoesplenomegalia"),
    (r"\bespleno\s+megalia\b",           "esplenomegalia"),
    (r"\bhidro\s+nefrose\b",             "hidronefrose"),
    (r"\bpielo\s+calicial\b",            "pielocalicial"),
    (r"\bureter\s+o\s+hidronefrose\b",   "ureterohidronefrose"),
    (r"\bretro\s+peritonial\b",          "retroperitoneal"),
    (r"\bretro\s+peritoneal\b",          "retroperitoneal"),
    (r"\bintra\s+hep[áa]tic(a|o)(s?)\b", r"intra-hepátic\1\2"),
    (r"\bextra\s+hep[áa]tic(a|o)(s?)\b", r"extra-hepátic\1\2"),
    (r"\bperi\s+hep[áa]tic(a|o)(s?)\b",  r"peri-hepátic\1\2"),
    (r"\bsub\s+diafragm[áa]tic(a|o)(s?)\b", r"subdiafragmátic\1\2"),
    (r"\bsupra\s+renal(is|es)?\b",       r"suprarrenal\1"),
    (r"\bsupra\s+renais\b",              "suprarrenais"),
    (r"\bmeso\s+ap[êe]ndice\b",          "mesoapêndice"),
    (r"\bperi\s+apendicular\b",          "periapendicular"),
    (r"\bdiver\s+ticulite\b",            "diverticulite"),
    (r"\bosteo\s+f[íi]tos?\b",           "osteófitos"),
    (r"\bespondilo\s+artrose\b",         "espondiloartrose"),
    (r"\bdisco\s+part[íi]a\b",           "discopatia"),
    (r"\bsacro\s+il[íi]ac(a|o)(s?)\b",   r"sacroilíac\1\2"),
    (r"\bsub\s+aracn[óo]ide(o|a)?\b",    "subaracnóideo"),
    (r"\bleuco\s+araiose\b",             "leucoaraiose"),
    (r"\bmicro\s+angiopat(ia|ias)\b",    r"microangiopat\1"),
    (r"\bgangli[oa]\s+basais\b",         "gânglios da base"),
    (r"\bfossa\s+posterior\b",           "fossa posterior"),
    (r"\bsupra\s+espinhal\b",            "supraespinhal"),
    (r"\binfra\s+espinhal\b",            "infraespinhal"),
    (r"\bsub\s+escapular\b",             "subescapular"),
    (r"\bintra\s+substancial\b",         "intrassubstancial"),

    # --- erros fonéticos clássicos ---
    (r"\bcanola\b",                      "cânula"),
    (r"\bcanula\b",                      "cânula"),
    (r"\bparenquima(s?)\b",              r"parênquima\1"),
    (r"\bparenquimatos(a|o)(s?)\b",      r"parenquimatos\1\2"),
    (r"\besteatos[ei]\b",                "esteatose"),
    (r"\batelectasi(a|as)\b",            r"atelectasi\1"),
    (r"\bdiver?t[íi]culos?\b",           lambda m: m.group(0)),
    (r"\bhipoatenuante\b",               "hipoatenuante"),
    (r"\bhiper\s+atenuante\b",           "hiperatenuante"),
    (r"\bhipo\s+atenuante\b",            "hipoatenuante"),
    (r"\bhiper\s+sinal\b",               "hipersinal"),
    (r"\bhipo\s+sinal\b",                "hipossinal"),
    (r"\bhiposinal\b",                   "hipossinal"),
    (r"\bhipo\s+densid(ade|ades)\b",     r"hipodensid\1"),
    (r"\bhiper\s+densid(ade|ades)\b",    r"hiperdensid\1"),
    (r"\bhipo\s+capt(ante|ação)\b",      r"hipocapt\1"),

    # --- acentuação que o STT come ---
    (r"\bt[óo]rax\b",                    "tórax"),
    (r"\babdomen\b",                     "abdome"),
    (r"\babdominal\b",                   "abdominal"),
    (r"\bcr[âa]nio\b",                   "crânio"),
    (r"\bp[âa]ncreas\b",                 "pâncreas"),
    (r"\bduoden(o|al)\b",                r"duoden\1"),
    (r"\bves[íi]cula\b",                 "vesícula"),
    (r"\bbil[íi]ar(es)?\b",              lambda m: m.group(0).replace("bilíar", "biliar").replace("biliar", "biliar")),
    (r"\bcol[ée]doco\b",                 "colédoco"),
    (r"\bap[êe]ndice\b",                 "apêndice"),
    (r"\bapendic[ií]te\b",               "apendicite"),
    (r"\bm[ée]dula\b",                   "medula"),
    (r"\bvertebr(a|as)\b",               r"vértebr\1"),
    (r"\barteri(a|as)\b",                r"artéri\1"),
    (r"\bven(o|osa|osas|osos)\b",        r"ven\1"),
    (r"\btraqu[ée]ia\b",                 "traqueia"),
    (r"\bbr[ôo]nquic(o|a)(s?)\b",        r"brônquic\1\2"),
    (r"\bbronquiectasi(a|as)\b",         r"bronquiectasi\1"),
    (r"\benfisem(a|atos[oa])\b",         r"enfisem\1"),
    (r"\bn[óo]dul(o|os|ar|ares)\b",      r"nódul\1"),
    (r"\bm[íi]crondulos?\b",             "micronódulos"),
    (r"\bmicro\s+n[óo]dul(o|os)\b",      r"micronódul\1"),
    (r"\bcalcifica[çc][ãa]o\b",          "calcificação"),
    (r"\bateroma\s+tose\b",              "ateromatose"),
]
VOCAB_RX = [(re.compile(p, re.IGNORECASE), s) for p, s in VOCABULARIO]


def _preserva_caixa(original, novo):
    if isinstance(novo, str) and original[:1].isupper() and novo[:1].islower():
        return novo[:1].upper() + novo[1:]
    return novo


# --- restauração de acento em termos que o STT costuma entregar sem ---
ACENTOS = {
 "carotida":"carótida","caroticas":"caróticas","carotidas":"carótidas",
 "aortico":"aórtico","aortica":"aórtica","aorticos":"aórticos","aorticas":"aórticas",
 "toracica":"torácica","toracico":"torácico","toracicas":"torácicas","toracicos":"torácicos",
 "hepatica":"hepática","hepatico":"hepático","hepaticas":"hepáticas","hepaticos":"hepáticos",
 "pancreatica":"pancreática","pancreatico":"pancreático",
 "esplenica":"esplênica","esplenico":"esplênico",
 "renais":"renais","suprarenal":"suprarrenal","suprarenais":"suprarrenais",
 "ureter":"ureter","uretra":"uretra","vesical":"vesical",
 "cranio":"crânio","craniana":"craniana","encefalico":"encefálico","encefalica":"encefálica",
 "ventriculos":"ventrículos","ventricular":"ventricular","ventriculo":"ventrículo",
 "cisternas":"cisternas","sulcos":"sulcos","talamo":"tálamo","talamico":"talâmico",
 "cerebelo":"cerebelo","cerebral":"cerebral","hemisferio":"hemisfério","hemisferios":"hemisférios",
 "occipital":"occipital","parietal":"parietal","insula":"ínsula",
 "musculo":"músculo","musculos":"músculos","tendineo":"tendíneo","tendinea":"tendínea",
 "osseo":"ósseo","ossea":"óssea","osseos":"ósseos","osseas":"ósseas",
 "vertebra":"vértebra","vertebras":"vértebras","vertebral":"vertebral",
 "lombossacra":"lombossacra","sacroiliaca":"sacroilíaca","coccix":"cóccix",
 "torax":"tórax","abdomen":"abdome","pelvico":"pélvico","pelvica":"pélvica",
 "vesicula":"vesícula","coledoco":"colédoco","duodeno":"duodeno","ileo":"íleo",
 "ceco":"ceco","apendice":"apêndice","colon":"cólon","reto":"reto",
 "linfonodo":"linfonodo","linfonodos":"linfonodos","mediastino":"mediastino",
 "traqueia":"traqueia","bronquio":"brônquio","bronquios":"brônquios",
 "pleural":"pleural","diafragma":"diafragma","diafragmatica":"diafragmática",
 "cardiaco":"cardíaco","cardiaca":"cardíaca","pericardio":"pericárdio",
 "arteria":"artéria","arterias":"artérias","arterial":"arterial","venoso":"venoso",
 "calculo":"cálculo","calculos":"cálculos","litiase":"litíase",
 "cistico":"cístico","cistica":"cística","solido":"sólido","solida":"sólida",
 "nodulo":"nódulo","nodulos":"nódulos","nodular":"nodular",
 "area":"área","areas":"áreas","regiao":"região","regioes":"regiões",
 "alteracao":"alteração","alteracoes":"alterações","calcificacao":"calcificação",
 "calcificacoes":"calcificações","dimensoes":"dimensões","contornos":"contornos",
 "atenuacao":"atenuação","opacificacao":"opacificação","distensao":"distensão",
 "obstrucao":"obstrução","compressao":"compressão","reducao":"redução",
 "espessura":"espessura","espessamento":"espessamento","conclusao":"conclusão",
 "indicacao":"indicação","tecnica":"técnica","analise":"análise",
 "correlacao":"correlação","investigacao":"investigação","avaliacao":"avaliação",
 "posterior":"posterior","anterior":"anterior","inferior":"inferior","superior":"superior",
 "medio":"médio","basica":"básica","cronico":"crônico","cronica":"crônica",
 "agudo":"agudo","aguda":"aguda","simetrico":"simétrico","simetrica":"simétrica",
 "multiplos":"múltiplos","multiplas":"múltiplas","unico":"único","unica":"única",
 "proximo":"próximo","proxima":"próxima","adjacente":"adjacente",
 "orgao":"órgão","orgaos":"órgãos","liquido":"líquido","gasoso":"gasoso",
}
ACENTOS.update({
 "adelgacamento":"adelgaçamento","ausencia":"ausência","presenca":"presença",
 "evidencia":"evidência","evidencias":"evidências","referencia":"referência",
 "consequencia":"consequência","insuficiencia":"insuficiência",
 "transicao":"transição","insercao":"inserção","extensao":"extensão",
 "lesao":"lesão","lesoes":"lesões","implantacao":"implantação",
 "protese":"prótese","proteses":"próteses","utero":"útero","ovario":"ovário",
 "prostata":"próstata","tireoide":"tireoide","adrenal":"adrenal",
 "baco":"baço","estomago":"estômago","intestinal":"intestinal",
 "periferico":"periférico","periferica":"periférica","central":"central",
 "difuso":"difuso","difusa":"difusa","focal":"focal","segmentar":"segmentar",
 "bilateral":"bilateral","ipsilateral":"ipsilateral","contralateral":"contralateral",
 "anatomico":"anatômico","anatomica":"anatômica","morfologia":"morfologia",
 "densidade":"densidade","hipodenso":"hipodenso","hiperdenso":"hiperdenso",
 "isodenso":"isodenso","heterogeneo":"heterogêneo","homogeneo":"homogêneo",
 "realce":"realce","contraste":"contraste","fase":"fase","sequencia":"sequência",
 "milimetrico":"milimétrico","centimetrico":"centimétrico","volumetrico":"volumétrico",
 "diametro":"diâmetro","perimetro":"perímetro","eixo":"eixo",
 "ampola":"ampola","bexiga":"bexiga","ureteres":"ureteres",
 "peritonio":"peritônio","peritoneal":"peritoneal","retroperitonio":"retroperitônio",
 "mesenterio":"mesentério","mesenterica":"mesentérica","omento":"omento",
 "parenquimatoso":"parenquimatoso","parenquimatosa":"parenquimatosa",
})
# plurais automáticos, sem sobrescrever o que já foi definido à mão
for _k, _v in list(ACENTOS.items()):
    if _k[-1:] in "oae" and _k + "s" not in ACENTOS:
        ACENTOS[_k + "s"] = _v + "s"

_ACENTO_RX = re.compile(r"\b(%s)\b" % "|".join(sorted(ACENTOS, key=len, reverse=True)),
                        re.IGNORECASE)


def _acentos(t):
    def rep(m):
        novo = ACENTOS[m.group(0).lower()]
        return _preserva_caixa(m.group(0), novo)
    return _ACENTO_RX.sub(rep, t)


def _vocabulario(t):
    for rx, sub in VOCAB_RX:
        if callable(sub):
            t = rx.sub(sub, t)
        else:
            t = rx.sub(lambda m: _preserva_caixa(m.group(0), rx.sub(sub, m.group(0))), t)
    return t


# ══════════════════════════════════════════════════════════════════
#  5. ESPAÇAMENTO E CAPITALIZAÇÃO
# ══════════════════════════════════════════════════════════════════
def _espacos(t):
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s+([,.;:!?%°])", r"\1", t)
    t = re.sub(r"(?<!\d)([,;:])(?=\S)", r"\1 ", t)
    t = re.sub(r"([,;:])(?=[^\s\d])", r"\1 ", t)
    t = re.sub(r"\.(?=[A-Za-zÀ-ÿ])", ". ", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"([.,;:])\1+", r"\1", t)
    return t.strip()


_SIGLAS = {"mm", "cm", "ml", "mL", "uh", "UH", "tc", "rm", "ap", "dp", "t1",
           "t2", "stir", "adc", "dwi", "flair", "hu"}


def _capitalizar(t):
    """Maiúscula no início do texto, de cada linha e depois de ponto final."""
    def sobe(m):
        return m.group(1) + m.group(2).upper()
    t = re.sub(r"(^|[.!?]\s+|\n)\s*([a-zà-ÿ])", sobe, t)
    return t


# ══════════════════════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════════════════════
def revisar(texto, numeros=True, vocabulario=True, pontuacao=True,
            capitalizar=True):
    """Aplica a revisão determinística. Devolve o texto revisado."""
    if not texto or not texto.strip():
        return texto
    t = texto
    t = HESITACOES.sub("", t)
    if pontuacao:
        t = _pontuacao(t)
    if numeros:
        t = _percentuais_falados(t)
        t = _numeros_por_extenso(t)
        t = _decimais(t)
        t = _unidades(t)
    if vocabulario:
        t = _vocabulario(t)
        t = _acentos(t)
    t = _espacos(t)
    if capitalizar:
        t = _capitalizar(t)
    return t


if __name__ == "__main__":
    testes = [
        "nódulo sólido medindo um vírgula dois centímetros no lobo superior direito",
        "lesão hepática de dois vírgula sete por um vírgula nove centímetros",
        "cisto renal medindo três por quatro milímetros",
        "estenose de setenta por cento da carótida interna direita",
        "atenuação de quarenta e cinco unidades hounsfield",
        "linfo nodo mediastinal com eixo curto de oito milímetros",
        "derrame pleural bilateral seios costo frenicos livres",
        "é... o parenquima pulmonar apresenta ahn... opacidades em vidro fosco",
        "hemi torax direito com hiper sinal ponto final",
        "abre parenteses sem alteracoes fecha parenteses",
        "massa de cinco por quatro por tres centimetros no rim esquerdo",
        "angulo de quinze graus dois pontos alinhamento preservado",
        "supra espinhal com intra substancial aumento de sinal",
    ]
    print()
    for x in testes:
        print("  in : " + x)
        print("  out: " + revisar(x))
        print()
