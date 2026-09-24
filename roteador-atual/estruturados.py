# -*- coding: utf-8 -*-
"""Estruturados por níveis — coluna cervical, torácica e lombar.

A grade: uma linha por nível discal, botões por achado. Marcar e a frase sai
montada. O motor é este arquivo; a tela só liga e desliga botões.

Três decisões que mandam no resto:

1. **A frase é montada por regra, não pela IA.** Combinação de botões sempre dá
   o mesmo texto. Isso é o que permite ele assinar sem reler: se "abaulamento +
   protrusão" saiu certo uma vez, sai certo sempre.

2. **Achado difuso é dito uma vez, acima da grade.** Desidratação e osteofitose
   não se repetem nível a nível; redução de altura, sim, porque é de cada disco.

3. **O que não é do disco não entra na linha do nível.** Anterolistese é de
   alinhamento, Modic é de corpo vertebral. Cada um na sua seção — senão a
   linha do nível vira um parágrafo e ninguém acha nada.
"""
import re

# ---------------------------------------------------------------------------
# níveis e zonas
# ---------------------------------------------------------------------------

NIVEIS = {
    "cervical": ["C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1"],
    "toracica": ["T1-T2", "T2-T3", "T3-T4", "T4-T5", "T5-T6", "T6-T7", "T7-T8",
                 "T8-T9", "T9-T10", "T10-T11", "T11-T12", "T12-L1"],
    "lombar": ["L1-L2", "L2-L3", "L3-L4", "L4-L5", "L5-S1"],
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

# ---------------------------------------------------------------------------
# achados difusos — ditos uma vez, antes dos níveis
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


def campos(segmento="lombar", modalidade="rm"):
    """Tudo o que a tela precisa para desenhar a grade daquele exame."""
    seg = segmento if segmento in NIVEIS else "lombar"
    mod = modalidade if modalidade in DIFUSOS else "rm"
    botoes = []
    for b in BOTOES:
        if "so" in b and mod not in b["so"]:
            continue
        if "so_segmento" in b and seg not in b["so_segmento"]:
            continue
        botoes.append({k: v for k, v in b.items() if k not in ("so", "so_segmento")})
    return {
        "ok": True,
        "segmento": seg,
        "modalidade": mod,
        "niveis": NIVEIS[seg],
        "zonas": ZONAS[seg],
        "lados": LADOS,
        "difusos": [{"id": i, "rotulo": r} for i, r, _f in DIFUSOS[mod]],
        "botoes": botoes,
        "forame": FORAME,
    }


# ---------------------------------------------------------------------------
# montagem da frase
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
        return "%s: sem alterações." % nivel
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
    if "osteofito_post" in m:
        pedacos.append("osteófito posterior")
    if "uncoartrose" in m:
        pedacos.append("uncoartrose")
    if "schmorl" in m:
        plato = (dados.get("plato") or "superior").strip()
        pedacos.append("hérnia intraesponjosa no platô %s" % plato)

    if len(pedacos) == 1:
        corpo = pedacos[0]
    else:
        corpo = pedacos[0] + ", com " + ", ".join(pedacos[1:]) if tem_altura and len(pedacos) > 1 \
            else ", ".join(pedacos[:-1]) + " e " + pedacos[-1]
    return "%s: %s." % (nivel, corpo)


def frase_difusa(marcados, modalidade="rm"):
    """A faixa de cima: dita uma vez, sem graduação — tem ou não tem."""
    mod = modalidade if modalidade in DIFUSOS else "rm"
    textos = [f for i, _r, f in DIFUSOS[mod] if i in (marcados or [])]
    if not textos:
        return ""
    if len(textos) == 1:
        frase = textos[0]
    else:
        frase = textos[0] + ", associada a " + ", ".join(textos[1:-1] + [""]).strip(", ")
        frase = (textos[0] + ", associada a " + textos[1] if len(textos) == 2
                 else textos[0] + ", associada a " + ", ".join(textos[1:-1]) + " e a " + textos[-1])
    return frase[0].upper() + frase[1:] + "."


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
    if len(niveis) == 1:
        partes.append("em " + niveis[0])
    else:
        partes.append("em " + ", ".join(niveis[:-1]) + " e " + niveis[-1])
    grau = (dados.get("grau") or "").strip()
    if grau:
        partes.append("de grau " + grau)
    rep = (dados.get("repercussao") or "").strip()
    if rep:
        partes.append(rep)
    return "Forames neurais: " + ", ".join(partes) + "."


def conclusao_foraminal(dados):
    dados = dados or {}
    niveis = [n for n in (dados.get("niveis") or []) if n]
    grau = (dados.get("grau") or "").strip()
    rep = (dados.get("repercussao") or "").strip()
    if not niveis or not grau:
        return ""
    onde = niveis[0] if len(niveis) == 1 else ", ".join(niveis[:-1]) + " e " + niveis[-1]
    lado = ""
    if (dados.get("simetria") or "") == "assimétrico" and dados.get("lado"):
        lado = " " + dados["lado"]
    fim = ""
    if rep and "sem repercussão" not in rep:
        fim = ", " + rep
    return "Estreitamento foraminal %s%s em %s%s." % (grau, lado, onde, fim)


def montar(pedido):
    """Tudo junto: difuso, uma linha por nível, forames e a conclusão."""
    if not isinstance(pedido, dict):
        return {"ok": False, "motivo": "pedido_invalido"}
    segmento = pedido.get("segmento") or "lombar"
    modalidade = pedido.get("modalidade") or "rm"
    if segmento not in NIVEIS:
        return {"ok": False, "motivo": "segmento_desconhecido", "aceitos": sorted(NIVEIS)}

    linhas, usados = [], []
    difusa = frase_difusa(pedido.get("difusos") or [], modalidade)
    if difusa:
        linhas.append(difusa)

    niveis = pedido.get("niveis") or {}
    for nivel in NIVEIS[segmento]:
        d = niveis.get(nivel) or {}
        marcados = d.get("marcados") or []
        f = frase_do_nivel(nivel, marcados, d)
        if f:
            linhas.append(f)
            usados.append(nivel)

    forame = frase_foraminal(pedido.get("forame") or {})
    if forame:
        linhas.append(forame)

    conclusoes = [c for c in (conclusao_foraminal(pedido.get("forame") or {}),) if c]
    return {"ok": True, "segmento": segmento, "modalidade": modalidade,
            "niveis_usados": usados, "texto": "\n".join(linhas),
            "conclusao": "\n".join(conclusoes)}
