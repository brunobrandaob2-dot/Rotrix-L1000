# -*- coding: utf-8 -*-
"""Estruturados por níveis — coluna cervical, torácica e lombar.

A grade: uma linha por nível discal, botões por achado, mais as seções que não
são do disco (alinhamento, corpos, canal, facetas, musculatura, medula). Marcar
e o LAUDO INTEIRO sai montado — não só as alterações.

Quatro decisões que mandam no resto:

1. **A frase é montada por regra, não pela IA.** Combinação de botões sempre dá
   o mesmo texto. Isso é o que permite ele assinar sem reler: se "abaulamento +
   protrusão" saiu certo uma vez, sai certo sempre.

2. **A saída é a máscara completa.** O módulo não devolve um punhado de frases:
   ele parte do `normal.txt` da região e troca a seção correspondente, exatamente
   como um bloco do banco faz. Título, TÉCNICA, INDICAÇÃO, todas as seções da
   ANÁLISE e a CONCLUSÃO vêm juntos. Sem isso o estruturado é meio laudo.

3. **Achado difuso é dito uma vez, acima da grade.** Desidratação e osteofitose
   não se repetem nível a nível; redução de altura, sim, porque é de cada disco.

4. **O que não é do disco não entra na linha do nível.** Anterolistese é de
   alinhamento, Modic é de corpo vertebral, infiltração gordurosa é de
   musculatura. Cada um na sua seção — senão a linha do nível vira um parágrafo
   e ninguém acha nada.
"""

# ---------------------------------------------------------------------------
# níveis e zonas
# ---------------------------------------------------------------------------

NIVEIS = {
    "cervical": ["C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1"],
    "toracica": ["T1-T2", "T2-T3", "T3-T4", "T4-T5", "T5-T6", "T6-T7", "T7-T8",
                 "T8-T9", "T9-T10", "T10-T11", "T11-T12", "T12-L1"],
    "lombar": ["L1-L2", "L2-L3", "L3-L4", "L4-L5", "L5-S1"],
}

# corpos vertebrais (para listese, Modic, hemangioma): não são os espaços
VERTEBRAS = {
    "cervical": ["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
    "toracica": ["T%d" % i for i in range(1, 13)],
    "lombar": ["L1", "L2", "L3", "L4", "L5", "S1"],
}

# Na cervical o espaço lateral é da artéria vertebral: não há subarticular nem
# extraforaminal. Ele corrigiu isto — e é o tipo de detalhe que denuncia mapa
# copiado de outro segmento.
ZONAS = {
    "cervical": ["central", "centro-lateral", "foraminal"],
    "toracica": ["central", "centro-lateral", "subarticular", "foraminal", "extraforaminal"],
    "lombar": ["central", "centro-lateral", "subarticular", "foraminal", "extraforaminal"],
}

LADOS = ["à direita", "à esquerda", "bilateral"]

CURVA = {"cervical": "lordose cervical", "toracica": "cifose torácica",
         "lombar": "lordose lombar"}
NOME_SEG = {"cervical": "cervical", "toracica": "torácica", "lombar": "lombar"}

# ---------------------------------------------------------------------------
# como cada seção se chama na máscara daquele exame
# ---------------------------------------------------------------------------
# A troca é por rótulo: o nome aqui tem de bater com o da máscara, senão o
# achado cai no fim da ANÁLISE em vez de substituir a frase normal.
SECOES = {
    "alinhamento": {"*": "Alinhamento"},
    "corpos": {"*": "Corpos vertebrais"},
    "discos": {"*": "Discos intervertebrais"},
    "canal": {"*": "Canal vertebral"},
    "forames": {"*": "Forames neurais"},
    "facetas": {
        "rm/cervical": "Articulações uncovertebrais e interapofisárias",
        "rm/toracica": "Articulações interapofisárias e costovertebrais",
        "tc/cervical": "Articulações interapofisárias",
        "tc/toracica": "Articulações interapofisárias",
        "*": "Articulações interapofisárias",
    },
    "medula": {
        "rm/cervical": "Medula cervical",
        "rm/toracica": "Medula torácica",
        "rm/lombar": "Cone medular e cauda equina",
    },
    "sacroiliacas": {"tc/lombar": "Articulações sacroilíacas",
                     "rm/lombar": "Articulações sacroilíacas"},
    "musculatura": {"*": "Musculatura paravertebral"},
}


def secao_de(chave, segmento, modalidade):
    """Nome do rótulo daquela seção naquele exame, ou "" quando não existe."""
    t = SECOES.get(chave) or {}
    return t.get("%s/%s" % (modalidade, segmento)) or t.get("*") or ""


# ---------------------------------------------------------------------------
# achados difusos do disco — ditos uma vez, antes dos níveis
# ---------------------------------------------------------------------------
# Desidratação é sinal de T2: não existe em TC. Vácuo e esclerose são de TC —
# na RM a esclerose se descreve por Modic. Misturar os dois é erro de método,
# não de gosto.
DIFUSOS = {
    "tc": [
        ("altura_difusa", "redução difusa da altura discal",
         "redução difusa da altura dos discos intervertebrais"),
        ("osteofitose", "osteofitose marginal", "osteofitose marginal"),
        ("esclerose", "esclerose dos platôs", "esclerose dos platôs vertebrais"),
        ("vacuo", "fenômeno do vácuo", "fenômeno do vácuo discal"),
        ("schmorl", "Schmorl esparsos", "hérnias intraesponjosas esparsas"),
    ],
    "rm": [
        ("desidratacao", "desidratação difusa", "desidratação discal difusa"),
        ("osteofitose", "osteofitose marginal", "osteofitose marginal"),
        ("schmorl", "Schmorl esparsos", "hérnias intraesponjosas esparsas"),
    ],
}

# ---------------------------------------------------------------------------
# botões por nível
# ---------------------------------------------------------------------------
BOTOES = [
    {"id": "normal", "rotulo": "normal", "exclui": ["altura", "abaulamento", "protrusao",
                                                    "extrusao", "schmorl", "osteofito_post",
                                                    "uncoartrose"]},
    {"id": "altura", "rotulo": "redução de altura", "exclui": ["normal"]},
    {"id": "abaulamento", "rotulo": "abaulamento", "exclui": ["normal"]},
    {"id": "protrusao", "rotulo": "protrusão", "exclui": ["normal", "extrusao"]},
    {"id": "extrusao", "rotulo": "extrusão", "exclui": ["normal", "protrusao"]},
    {"id": "schmorl", "rotulo": "Schmorl", "exclui": ["normal"]},
    {"id": "osteofito_post", "rotulo": "osteófito posterior", "exclui": ["normal"],
     "so": ["tc"]},
    {"id": "uncoartrose", "rotulo": "uncoartrose", "exclui": ["normal"],
     "so_segmento": ["cervical"]},
]

ORDEM = ["altura", "abaulamento", "protrusao", "extrusao", "osteofito_post",
         "uncoartrose", "schmorl"]

# ---------------------------------------------------------------------------
# estreitamento foraminal — seção própria, fora da linha do nível
# ---------------------------------------------------------------------------
FORAME = {
    "simetria": ["simétrico", "assimétrico"],
    "lado": ["à direita", "à esquerda"],
    "grau": ["discreto", "moderado", "acentuado"],
    # Ele tirou o nome da raiz: "só de falar que tem conflito já tá bom".
    "repercussao": ["sem repercussão radicular significativa",
                    "com contato radicular", "com compressão radicular"],
}

GRAUS = ["discreta", "moderada", "acentuada"]
# "de grau discreto", não "de grau discreta": o substantivo é que manda
MASCULINO = {"discreta": "discreto", "moderada": "moderado", "acentuada": "acentuado"}


# ---------------------------------------------------------------------------
# utilitários de frase
# ---------------------------------------------------------------------------

def _lista(itens):
    """"L3-L4, L4-L5 e L5-S1"."""
    itens = [str(x).strip() for x in (itens or []) if str(x).strip()]
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _v(dados, chave, padrao=""):
    return str((dados or {}).get(chave) or padrao).strip()


def _lig(dados, chave):
    return bool((dados or {}).get(chave))


def _maiuscula(t):
    return t[:1].upper() + t[1:] if t else t


def _rotulada(rotulo, corpo):
    """Linha no padrão do banco: "Rótulo:  texto." (dois espaços).

    Minúscula depois dos dois pontos — é assim em todo o banco, e a frase difusa
    chega capitalizada de quando era linha solta."""
    corpo = corpo.strip().rstrip(".")
    if not corpo:
        return ""
    if len(corpo) > 1 and corpo[1].islower():
        corpo = corpo[0].lower() + corpo[1:]
    return "%s:  %s." % (rotulo, corpo)


# ---------------------------------------------------------------------------
# seções que não são do disco
# ---------------------------------------------------------------------------
# ATENÇÃO: o texto clínico destas seções foi escrito aqui, não veio de máscara
# aprovada por ele. Precisa de revisão antes de virar rotina.

def _alinhamento(d, seg, mod):
    partes, conc = [], []
    if _lig(d, "retificacao"):
        partes.append("retificação da %s" % CURVA[seg])
        conc.append("Retificação da %s." % CURVA[seg])
    if _lig(d, "escoliose"):
        f = "escoliose %s de convexidade %s" % (NOME_SEG[seg], _v(d, "escoliose_lado", "à direita"))
        ap = _v(d, "escoliose_apice")
        if ap:
            f += ", com ápice em %s" % ap
        partes.append(f)
        conc.append("Escoliose %s de convexidade %s." %
                    (NOME_SEG[seg], _v(d, "escoliose_lado", "à direita")))
    if _lig(d, "listese"):
        tipo = _v(d, "listese_tipo", "anterolistese")
        sup, inf = _v(d, "listese_sup"), _v(d, "listese_inf")
        grau = _v(d, "listese_grau", "1")
        etio = _v(d, "listese_etiologia", "degenerativo")
        onde = ("de %s sobre %s" % (sup, inf)) if sup and inf else ""
        f = ", ".join(x for x in [" ".join(y for y in [tipo, onde] if y),
                                  "grau %s de Meyerding" % grau] if x)
        if etio:
            f += ", de aspecto %s" % etio
        partes.append(f)
        conc.append(_maiuscula(f.split(", de aspecto")[0]) + ".")
    if not partes:
        return "", []
    return _lista(partes), conc


def _corpos(d, seg, mod):
    partes, conc = [], []
    if mod == "rm" and _lig(d, "modic"):
        niveis = _lista(d.get("modic_niveis") or [])
        tipo = _v(d, "modic_tipo", "II")
        f = "alterações de sinal dos platôs vertebrais do tipo Modic %s" % tipo
        if niveis:
            f += " em %s" % niveis
        f += ", de natureza degenerativa"
        partes.append(f)
        conc.append("Alterações degenerativas dos platôs vertebrais tipo Modic %s%s." %
                    (tipo, (" em %s" % niveis) if niveis else ""))
    if _lig(d, "hemangioma"):
        onde = _lista(d.get("hemangioma_niveis") or [])
        partes.append("imagem de aspecto hemangiomatoso%s, sem repercussão estrutural" %
                      ((" em %s" % onde) if onde else ""))
    if _lig(d, "perda_altura"):
        onde = _lista(d.get("perda_niveis") or [])
        grau = _v(d, "perda_grau", "discreta")
        fase = _v(d, "perda_fase", "sem edema ósseo associado, sugerindo cronicidade")
        f = "redução %s da altura do corpo vertebral%s" % (grau, (" de %s" % onde) if onde else "")
        if fase:
            f += ", %s" % fase
        partes.append(f)
        conc.append("Fratura por compressão%s, %s." %
                    ((" de %s" % onde) if onde else "",
                     "de aspecto antigo" if "cronicidade" in fase else "de aspecto recente"))
    if not partes:
        return "", []
    return _lista(partes), conc


def _canal(d, seg, mod):
    partes, conc = [], []
    if _lig(d, "estenose"):
        onde = _lista(d.get("estenose_niveis") or [])
        grau = _v(d, "estenose_grau", "discreta")
        causa = _v(d, "estenose_causa")
        efeito = _v(d, "estenose_efeito")
        f = "redução da amplitude do canal vertebral%s, de grau %s" % (
            (" em %s" % onde) if onde else "", MASCULINO.get(grau, grau))
        if causa:
            f += ", determinada por %s" % causa
        if efeito:
            f += ", %s" % efeito
        partes.append(f)
        conc.append("Estenose do canal vertebral %s%s." % (grau, (" em %s" % onde) if onde else ""))
    if _lig(d, "ligamento_amarelo"):
        partes.append("espessamento dos ligamentos amarelos")
    if not partes:
        return "", []
    return _lista(partes), conc


def _facetas(d, seg, mod):
    partes, conc = [], []
    if _lig(d, "artropatia"):
        onde = _lista(d.get("artropatia_niveis") or [])
        grau = _v(d, "artropatia_grau", "")
        f = "sinais de artropatia degenerativa interapofisária"
        if onde:
            f += " em %s" % onde
        if grau:
            f += ", de grau %s" % grau
        f += ", com redução do espaço articular, esclerose e hipertrofia dos processos articulares"
        if _lig(d, "derrame"):
            f += ", com discreto derrame articular"
        partes.append(f)
        conc.append("Artropatia degenerativa interapofisária%s." % ((" em %s" % onde) if onde else ""))
    if _lig(d, "cisto"):
        onde = _v(d, "cisto_nivel")
        lado = _v(d, "cisto_lado", "à direita")
        partes.append("cisto sinovial facetário %s%s" % (lado, (" em %s" % onde) if onde else ""))
        conc.append("Cisto sinovial facetário %s%s." % (lado, (" em %s" % onde) if onde else ""))
    if not partes:
        return "", []
    return _lista(partes), conc


def _musculatura(d, seg, mod):
    """A seção que faltava. Goutallier é da RM; na TC a leitura é por densidade."""
    partes, conc = [], []
    if _lig(d, "infiltracao"):
        musc = _v(d, "infiltracao_musculos", "musculatura paravertebral")
        grau = _v(d, "infiltracao_grau", "2")
        f = "infiltração gordurosa %s" % musc if musc.startswith("d") else \
            "infiltração gordurosa da %s" % musc
        if mod == "rm":
            f += ", grau %s de Goutallier" % grau
        sim = _v(d, "infiltracao_simetria", "simétrica")
        if sim:
            f += ", %s" % sim
        partes.append(f)
        if grau in ("2", "3", "4"):
            conc.append("Infiltração gordurosa da musculatura paravertebral%s." %
                        (", grau %s de Goutallier" % grau if mod == "rm" else ""))
    if _lig(d, "assimetria"):
        partes.append("redução volumétrica %s" % _v(d, "assimetria_lado", "à direita"))
    if mod == "rm" and _lig(d, "edema"):
        partes.append("áreas de hipersinal em T2 com supressão de gordura, "
                      "traduzindo edema muscular")
    if not partes:
        return "", []
    return _lista(partes), conc


def _medula(d, seg, mod):
    if mod != "rm":
        return "", []
    partes, conc = [], []
    if seg in ("cervical", "toracica"):
        if _lig(d, "mielopatia"):
            onde = _v(d, "mielopatia_nivel")
            f = "área de hipersinal em T2 intramedular%s, sem realce pelo meio de contraste" % (
                (" em nível de %s" % onde) if onde else "")
            partes.append(f)
            conc.append("Alteração de sinal intramedular%s, a correlacionar com o quadro clínico." %
                        ((" em %s" % onde) if onde else ""))
        if _lig(d, "compressao"):
            partes.append("impressão sobre a face ventral do saco dural, sem alteração de "
                          "sinal intramedular")
    else:
        if _lig(d, "cone_baixo"):
            onde = _v(d, "cone_nivel", "L2")
            partes.append("cone medular terminando em nível de %s" % onde)
            conc.append("Cone medular de terminação baixa, em %s." % onde)
        if _lig(d, "aracnoidite"):
            partes.append("agrupamento das raízes da cauda equina, a considerar aracnoidite")
    if not partes:
        return "", []
    return _lista(partes), conc


def _sacroiliacas(d, seg, mod):
    if seg != "lombar":
        return "", []
    partes, conc = [], []
    if _lig(d, "sacroileite"):
        lado = _v(d, "sacroileite_lado", "bilateral")
        fase = _v(d, "sacroileite_fase", "esclerose subcondral")
        partes.append("alterações %s, caracterizadas por %s" % (lado, fase))
        conc.append("Alterações sacroilíacas %s — %s." % (lado, fase))
    if not partes:
        return "", []
    return _lista(partes), conc


# id -> (chave da seção, construtor, campos que a tela desenha)
EXTRAS = [
    ("alinhamento", "alinhamento", _alinhamento, [
        {"id": "retificacao", "tipo": "botao", "rotulo": "retificação"},
        {"id": "escoliose", "tipo": "botao", "rotulo": "escoliose"},
        {"id": "escoliose_lado", "tipo": "opcao", "rotulo": "convexidade",
         "opcoes": ["à direita", "à esquerda"], "depende": "escoliose"},
        {"id": "escoliose_apice", "tipo": "vertebra", "rotulo": "ápice", "depende": "escoliose"},
        {"id": "listese", "tipo": "botao", "rotulo": "listese"},
        {"id": "listese_tipo", "tipo": "opcao", "rotulo": "tipo",
         "opcoes": ["anterolistese", "retrolistese"], "depende": "listese"},
        {"id": "listese_sup", "tipo": "vertebra", "rotulo": "de", "depende": "listese"},
        {"id": "listese_inf", "tipo": "vertebra", "rotulo": "sobre", "depende": "listese"},
        {"id": "listese_grau", "tipo": "opcao", "rotulo": "Meyerding",
         "opcoes": ["1", "2", "3", "4"], "depende": "listese"},
        {"id": "listese_etiologia", "tipo": "opcao", "rotulo": "aspecto",
         "opcoes": ["degenerativo, associada a artropatia facetária",
                    "ístmico, associada a defeito da pars interarticularis"],
         "depende": "listese"},
    ]),
    ("corpos", "corpos", _corpos, [
        {"id": "modic", "tipo": "botao", "rotulo": "Modic", "so": ["rm"]},
        {"id": "modic_tipo", "tipo": "opcao", "rotulo": "tipo", "opcoes": ["I", "II", "III"],
         "depende": "modic", "so": ["rm"]},
        {"id": "modic_niveis", "tipo": "niveis", "rotulo": "níveis", "depende": "modic",
         "so": ["rm"]},
        {"id": "hemangioma", "tipo": "botao", "rotulo": "hemangioma"},
        {"id": "hemangioma_niveis", "tipo": "vertebras", "rotulo": "vértebras",
         "depende": "hemangioma"},
        {"id": "perda_altura", "tipo": "botao", "rotulo": "perda de altura"},
        {"id": "perda_niveis", "tipo": "vertebras", "rotulo": "vértebras",
         "depende": "perda_altura"},
        {"id": "perda_grau", "tipo": "opcao", "rotulo": "grau", "opcoes": GRAUS,
         "depende": "perda_altura"},
        {"id": "perda_fase", "tipo": "opcao", "rotulo": "fase",
         "opcoes": ["sem edema ósseo associado, sugerindo cronicidade",
                    "com edema ósseo associado, sugerindo evento recente"],
         "depende": "perda_altura"},
    ]),
    ("canal", "canal", _canal, [
        {"id": "estenose", "tipo": "botao", "rotulo": "estenose de canal"},
        {"id": "estenose_niveis", "tipo": "niveis", "rotulo": "níveis", "depende": "estenose"},
        {"id": "estenose_grau", "tipo": "opcao", "rotulo": "grau", "opcoes": GRAUS,
         "depende": "estenose"},
        {"id": "estenose_causa", "tipo": "opcao", "rotulo": "causa",
         "opcoes": ["abaulamento discal, hipertrofia facetária e espessamento dos "
                    "ligamentos amarelos",
                    "protrusão discal",
                    "espondilolistese degenerativa"], "depende": "estenose"},
        {"id": "estenose_efeito", "tipo": "opcao", "rotulo": "efeito",
         "opcoes": ["com apinhamento das raízes da cauda equina",
                    "com redução do espaço liquórico anterior, sem apinhamento radicular"],
         "depende": "estenose", "so_segmento": ["lombar"]},
        {"id": "ligamento_amarelo", "tipo": "botao", "rotulo": "ligamento amarelo espessado"},
    ]),
    ("facetas", "facetas", _facetas, [
        {"id": "artropatia", "tipo": "botao", "rotulo": "artropatia facetária"},
        {"id": "artropatia_niveis", "tipo": "niveis", "rotulo": "níveis", "depende": "artropatia"},
        {"id": "artropatia_grau", "tipo": "opcao", "rotulo": "grau",
         "opcoes": ["discreto", "moderado", "acentuado"], "depende": "artropatia"},
        {"id": "derrame", "tipo": "botao", "rotulo": "derrame articular", "depende": "artropatia"},
        {"id": "cisto", "tipo": "botao", "rotulo": "cisto sinovial"},
        {"id": "cisto_nivel", "tipo": "niveis", "rotulo": "nível", "depende": "cisto"},
        {"id": "cisto_lado", "tipo": "opcao", "rotulo": "lado",
         "opcoes": ["à direita", "à esquerda"], "depende": "cisto"},
    ]),
    ("medula", "medula", _medula, [
        {"id": "mielopatia", "tipo": "botao", "rotulo": "hipersinal intramedular",
         "so": ["rm"], "so_segmento": ["cervical", "toracica"]},
        {"id": "mielopatia_nivel", "tipo": "niveis", "rotulo": "nível", "depende": "mielopatia",
         "so": ["rm"], "so_segmento": ["cervical", "toracica"]},
        {"id": "compressao", "tipo": "botao", "rotulo": "impressão sobre o saco dural",
         "so": ["rm"], "so_segmento": ["cervical", "toracica"]},
        {"id": "cone_baixo", "tipo": "botao", "rotulo": "cone baixo",
         "so": ["rm"], "so_segmento": ["lombar"]},
        {"id": "cone_nivel", "tipo": "vertebra", "rotulo": "termina em", "depende": "cone_baixo",
         "so": ["rm"], "so_segmento": ["lombar"]},
        {"id": "aracnoidite", "tipo": "botao", "rotulo": "agrupamento radicular",
         "so": ["rm"], "so_segmento": ["lombar"]},
    ]),
    ("sacroiliacas", "sacroiliacas", _sacroiliacas, [
        {"id": "sacroileite", "tipo": "botao", "rotulo": "alteração sacroilíaca",
         "so_segmento": ["lombar"]},
        {"id": "sacroileite_lado", "tipo": "opcao", "rotulo": "lado",
         "opcoes": ["à direita", "à esquerda", "bilateral"], "depende": "sacroileite",
         "so_segmento": ["lombar"]},
        {"id": "sacroileite_fase", "tipo": "opcao", "rotulo": "achado",
         "opcoes": ["esclerose subcondral", "edema ósseo subcondral",
                    "erosões e esclerose subcondral"], "depende": "sacroileite",
         "so_segmento": ["lombar"]},
    ]),
    ("musculatura", "musculatura", _musculatura, [
        {"id": "infiltracao", "tipo": "botao", "rotulo": "infiltração gordurosa"},
        {"id": "infiltracao_musculos", "tipo": "opcao", "rotulo": "músculos",
         "opcoes": ["dos músculos multífidos", "dos músculos eretores da espinha",
                    "dos multífidos e eretores da espinha", "do músculo psoas"],
         "depende": "infiltracao"},
        {"id": "infiltracao_grau", "tipo": "opcao", "rotulo": "Goutallier",
         "opcoes": ["1", "2", "3", "4"], "depende": "infiltracao", "so": ["rm"]},
        {"id": "infiltracao_simetria", "tipo": "opcao", "rotulo": "simetria",
         "opcoes": ["simétrica", "de predomínio à direita", "de predomínio à esquerda"],
         "depende": "infiltracao"},
        {"id": "assimetria", "tipo": "botao", "rotulo": "redução volumétrica"},
        {"id": "assimetria_lado", "tipo": "opcao", "rotulo": "lado",
         "opcoes": ["à direita", "à esquerda"], "depende": "assimetria"},
        {"id": "edema", "tipo": "botao", "rotulo": "edema muscular", "so": ["rm"]},
    ]),
]


PRIORIDADE = {"discos": 0, "canal": 1, "medula": 2, "forames": 3, "alinhamento": 4,
              "corpos": 5, "facetas": 6, "sacroiliacas": 7, "musculatura": 8}


def _cabe(item, seg, mod):
    if "so" in item and mod not in item["so"]:
        return False
    if "so_segmento" in item and seg not in item["so_segmento"]:
        return False
    return True


def campos(segmento="lombar", modalidade="rm"):
    """Tudo o que a tela precisa para desenhar a grade daquele exame."""
    seg = segmento if segmento in NIVEIS else "lombar"
    mod = modalidade if modalidade in DIFUSOS else "rm"
    botoes = []
    for b in BOTOES:
        if not _cabe(b, seg, mod):
            continue
        botoes.append({k: v for k, v in b.items() if k not in ("so", "so_segmento")})

    extras = []
    for eid, chave, _f, itens in EXTRAS:
        rot = secao_de(chave, seg, mod)
        if not rot:
            continue
        cps = [{k: v for k, v in c.items() if k not in ("so", "so_segmento")}
               for c in itens if _cabe(c, seg, mod)]
        if not cps:
            continue
        extras.append({"id": eid, "secao": rot, "rotulo": rot, "campos": cps})

    return {
        "ok": True,
        "segmento": seg,
        "modalidade": mod,
        "niveis": NIVEIS[seg],
        "vertebras": VERTEBRAS[seg],
        "zonas": ZONAS[seg],
        "lados": LADOS,
        "difusos": [{"id": i, "rotulo": r} for i, r, _f in DIFUSOS[mod]],
        "botoes": botoes,
        "forame": FORAME,
        "extras": extras,
    }


# ---------------------------------------------------------------------------
# montagem da frase do disco
# ---------------------------------------------------------------------------

def _componente(dados, tipo):
    """"protruso subarticular à esquerda, medindo 5 mm, em contato com a raiz"."""
    nome = "protruso" if tipo == "protrusao" else "extruso"
    partes = [nome]
    zona = (dados.get("zona") or "").strip()
    if zona:
        partes.append(zona)
    lado = (dados.get("lado") or "").strip()
    if lado:
        partes.append(lado)
    texto = " ".join(partes)
    medida = str(dados.get("medida") or "").strip().replace(".", ",")
    if medida:
        texto += ", medindo %s mm" % medida
    if tipo == "extrusao":
        mig = (dados.get("migracao") or "").strip()
        if mig:
            texto += ", com migração %s" % mig
    contato = (dados.get("contato") or "").strip()
    if contato:
        texto += ", %s" % contato
    return texto


def frase_do_nivel(nivel, marcados, dados=None):
    """A linha de um nível. Vazia quando nada foi marcado.

    As combinações que ele aprovou, na ordem em que aprovou:
      abaulamento              -> abaulamento discal difuso.
      abaulamento + protrusão  -> abaulamento discal difuso, associado a
                                  componente protruso ...
      altura + abaulamento + protrusão
                               -> redução da altura discal, com abaulamento
                                  difuso associado a componente protruso ...
    Com os três ligados, "abaulamento discal difuso" vira "abaulamento difuso":
    senão a frase diz *disco* duas vezes."""
    dados = dados or {}
    m = [x for x in ORDEM if x in (marcados or [])]
    if "normal" in (marcados or []) and not m:
        return "%s:  sem alterações." % nivel
    if not m:
        return ""

    tem_altura = "altura" in m
    tem_abaul = "abaulamento" in m
    hernia = "protrusao" if "protrusao" in m else ("extrusao" if "extrusao" in m else "")

    pedacos = []
    if tem_altura:
        pedacos.append("redução da altura discal")
    if tem_abaul:
        # sem nada antes, o disco precisa ser nomeado; com algo antes, não
        pedacos.append(("abaulamento difuso" if pedacos else "abaulamento discal difuso"))
    if hernia:
        comp = _componente(dados, hernia)
        if tem_abaul:
            # o abaulamento manda, a herniação entra como componente
            ligacao = "associado a componente " + comp
            pedacos[-1] = pedacos[-1] + (", " if not tem_altura else " ") + ligacao
        else:
            nome = "protrusão discal" if hernia == "protrusao" else "extrusão discal"
            resto = comp.split(" ", 1)[1] if " " in comp else ""
            pedacos.append((nome + " " + resto).strip())
    # Osteófito, uncoartrose e Schmorl não são do disco: viram frase própria.
    # Emendados na frase do disco por vírgula, ficavam pendurados no fim de uma
    # oração que já tinha três vírgulas ("...com contato radicular, uncoartrose").
    fora = []
    if "osteofito_post" in m:
        fora.append("osteofitose marginal posterior")
    if "uncoartrose" in m:
        fora.append("uncoartrose")
    if "schmorl" in m:
        plato = (dados.get("plato") or "superior").strip()
        fora.append("hérnia intraesponjosa no platô %s" % plato)

    if not pedacos:
        corpo = _lista(fora)
        fora = []
    elif len(pedacos) == 1:
        corpo = pedacos[0]
    elif tem_altura:
        corpo = pedacos[0] + ", com " + _lista(pedacos[1:])
    else:
        corpo = _lista(pedacos)
    frase = "%s:  %s." % (nivel, corpo)
    if fora:
        frase += " " + _maiuscula(_lista(fora)) + "."
    return frase


def conclusao_do_nivel(nivel, marcados, dados=None):
    """Só herniação vai para a conclusão. Abaulamento e altura entram na linha
    de discopatia, que é uma só para o exame inteiro."""
    dados = dados or {}
    m = marcados or []
    if "extrusao" in m:
        nome, tipo = "Extrusão discal", "extrusao"
    elif "protrusao" in m:
        nome, tipo = "Protrusão discal", "protrusao"
    else:
        return ""
    zona = (dados.get("zona") or "").strip()
    lado = (dados.get("lado") or "").strip()
    partes = [nome]
    if zona:
        partes.append(zona)
    if lado:
        partes.append(lado)
    frase = " ".join(partes) + " em %s" % nivel
    contato = (dados.get("contato") or "").strip()
    if contato and "sem" not in contato:
        frase += ", %s" % contato
    return frase + "."


def frase_difusa(marcados, modalidade="rm"):
    """A faixa de cima: dita uma vez, sem graduação — tem ou não tem."""
    mod = modalidade if modalidade in DIFUSOS else "rm"
    textos = [f for i, _r, f in DIFUSOS[mod] if i in (marcados or [])]
    if not textos:
        return ""
    if len(textos) == 1:
        frase = textos[0]
    elif len(textos) == 2:
        frase = textos[0] + ", associada a " + textos[1]
    else:
        frase = textos[0] + ", associada a " + ", ".join(textos[1:-1]) + " e a " + textos[-1]
    return _maiuscula(frase) + "."


def frase_foraminal(dados):
    """"estreitamento foraminal", como ele pediu — e sem dizer qual raiz."""
    dados = dados or {}
    niveis = [n for n in (dados.get("niveis") or []) if n]
    if not niveis:
        return ""
    simetria = (dados.get("simetria") or "simétrico").strip()
    partes = ["estreitamento foraminal " + simetria]
    if simetria == "assimétrico":
        lado = (dados.get("lado") or "").strip()
        if lado:
            partes.append("de predomínio " + lado)
    partes.append("em " + _lista(niveis))
    grau = (dados.get("grau") or "").strip()
    if grau:
        partes.append("de grau " + grau)
    rep = (dados.get("repercussao") or "").strip()
    if rep:
        partes.append(rep)
    return ", ".join(partes)


def conclusao_foraminal(dados):
    dados = dados or {}
    niveis = [n for n in (dados.get("niveis") or []) if n]
    grau = (dados.get("grau") or "").strip()
    rep = (dados.get("repercussao") or "").strip()
    if not niveis or not grau:
        return ""
    lado = ""
    if (dados.get("simetria") or "") == "assimétrico" and dados.get("lado"):
        lado = " " + dados["lado"]
    fim = ""
    if rep and "sem repercussão" not in rep:
        fim = ", " + rep
    return "Estreitamento foraminal %s%s em %s%s." % (grau, lado, _lista(niveis), fim)


def _conclusao_discopatia(pedido, segmento, modalidade):
    """Uma linha para o exame inteiro, não uma por nível."""
    difusos = pedido.get("difusos") or []
    niveis = pedido.get("niveis") or {}
    com_altura = [n for n, d in niveis.items() if "altura" in ((d or {}).get("marcados") or [])]
    if not difusos and not com_altura:
        return ""
    extensao = "multissegmentar" if (difusos or len(set(com_altura)) > 1) else "em nível isolado"
    return "Discopatia degenerativa %s %s." % (NOME_SEG[segmento], extensao)


# ---------------------------------------------------------------------------
# montagem do laudo
# ---------------------------------------------------------------------------

def blocos(pedido):
    """Traduz a grade em blocos no formato do banco:
    (titulo, texto, secao, conclusao, segmento_ditado).

    É esse formato que o motor do roteador já sabe encaixar numa máscara: cada
    bloco substitui a linha da sua seção e joga a conclusão no fim. Reaproveitar
    esse motor é o que garante que o estruturado saia com a mesma cara de um
    laudo ditado — e não com uma segunda gramática paralela."""
    segmento = pedido.get("segmento") or "lombar"
    modalidade = pedido.get("modalidade") or "rm"
    saida = []

    # --- discos: difusa + uma linha por nível ---------------------------------
    rot_disco = secao_de("discos", segmento, modalidade)
    difusa = frase_difusa(pedido.get("difusos") or [], modalidade)
    niveis_pedido = pedido.get("niveis") or {}
    listar_todos = bool(pedido.get("listar_todos"))
    linhas_nivel, usados, conc_niveis = [], [], []
    for nivel in NIVEIS[segmento]:
        d = niveis_pedido.get(nivel) or {}
        marcados = d.get("marcados") or []
        f = frase_do_nivel(nivel, marcados, d)
        if not f and listar_todos:
            f = "%s:  sem alterações." % nivel
        if f:
            linhas_nivel.append(f)
            if marcados:
                usados.append(nivel)
            c = conclusao_do_nivel(nivel, marcados, d)
            if c:
                conc_niveis.append(c)
    if difusa or linhas_nivel:
        corpo = [_rotulada(rot_disco, difusa) if difusa else rot_disco + ":"]
        corpo += linhas_nivel
        # As conclusões dos níveis viajam junto com o bloco do disco: um bloco
        # de texto vazio só para carregar conclusão entraria na ANÁLISE como
        # linha em branco.
        conc = [c for c in [_conclusao_discopatia(pedido, segmento, modalidade)] + conc_niveis if c]
        saida.append(("estruturado/discos", "\n".join(corpo), rot_disco,
                      "\n".join(conc), ""))

    # --- forames --------------------------------------------------------------
    forame = frase_foraminal(pedido.get("forame") or {})
    if forame:
        rot = secao_de("forames", segmento, modalidade)
        saida.append(("estruturado/forames", _rotulada(rot, forame), rot,
                      conclusao_foraminal(pedido.get("forame") or {}), ""))

    # --- demais seções --------------------------------------------------------
    extras_pedido = pedido.get("extras") or {}
    for eid, chave, func, _itens in EXTRAS:
        rot = secao_de(chave, segmento, modalidade)
        if not rot:
            continue
        d = extras_pedido.get(eid) or {}
        texto, conc = func(d, segmento, modalidade)
        if not texto:
            continue
        saida.append(("estruturado/" + eid, _rotulada(rot, texto), rot,
                      "\n".join(conc), ""))

    # A ordem dos blocos não muda a ANÁLISE (cada um troca a sua seção pelo
    # rótulo), mas manda na CONCLUSÃO — e lá a ordem é clínica: o que decide
    # conduta primeiro, o achado de acompanhamento por último.
    saida.sort(key=lambda b: PRIORIDADE.get(b[0].split("/", 1)[-1], 50))
    return saida


def montar(pedido, base=None, motor=None):
    """O laudo inteiro.

    base  = texto da máscara normal da região (sem as linhas de cabeçalho #).
    motor = a função montar(base, blocos, ditado) do roteador.

    Sem base/motor (teste isolado, chamada crua), devolve só as frases — mas
    quem chama pela API sempre recebe o laudo completo, que é o ponto."""
    if not isinstance(pedido, dict):
        return {"ok": False, "motivo": "pedido_invalido"}
    segmento = pedido.get("segmento") or "lombar"
    modalidade = pedido.get("modalidade") or "rm"
    if segmento not in NIVEIS:
        return {"ok": False, "motivo": "segmento_desconhecido", "aceitos": sorted(NIVEIS)}
    if modalidade not in DIFUSOS:
        return {"ok": False, "motivo": "modalidade_desconhecida", "aceitas": sorted(DIFUSOS)}

    bl = blocos(pedido)
    usados = [n for n in NIVEIS[segmento]
              if ((pedido.get("niveis") or {}).get(n) or {}).get("marcados")]

    achados = "\n".join(t for _tit, t, _s, _c, _g in bl if t)
    conclusoes = "\n".join(c for _tit, _t, _s, c, _g in bl if c)

    if base and motor:
        completo = motor(base, bl, "")
        return {"ok": True, "segmento": segmento, "modalidade": modalidade,
                "niveis_usados": usados, "texto": completo,
                "achados": achados, "conclusao": conclusoes, "completo": True}

    return {"ok": True, "segmento": segmento, "modalidade": modalidade,
            "niveis_usados": usados, "texto": achados,
            "achados": achados, "conclusao": conclusoes, "completo": False}
