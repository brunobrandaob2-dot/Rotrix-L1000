# -*- coding: utf-8 -*-
"""Auditoria de gatilhos que ENTRAM ONDE NÃO DEVEM (02/10).

    python auditar_cruzamentos.py              -> resumo na tela
    python auditar_cruzamentos.py relatorio.md -> tabela completa em arquivo

Pedido dele: "os gatilhos das máscaras do roteador estão atrapalhando ... tem que haver
uma auditoria completa para avaliar todos aqueles que estão entrando de forma inadequada
nas descrições". Exemplo dele: "derrame pleural bilateral, pequeno à direita" no botão
forte e entrava "ateromas calcificados".

Roda sobre o banco que o roteador carregar (LAUDO_BASE): no PC dele, o banco dele, com
as máscaras dele. Só LÊ: não muda máscara, gatilho nem frase. Seis provas:

 1. ACHADO PUXANDO BLOCO SEM RELAÇÃO (a principal): cada achado do banco (~3 mil) é
    ditado no exame de cada região; o bloco que entra tem de ter o achado no gatilho.
    Antes das trancas de 02/10 (roteador._bloco_do_segmento), 1.460 ditados entravam em
    bloco sem relação no banco dele ("avulsão da placa volar na mão" -> "ateromas
    calcificados", "artrodese cervical" -> coxartrose).
 2. TRECHO SÓ DE QUALIFICADOR: "pequeno à direita", "bilateral", "medindo 5 mm"...
    não nomeia achado e não pode puxar bloco nenhum.
 3. PALAVRAS QUE SE CONFUNDIAM: pares do banco parecidos (>= 0,85) que NÃO são a mesma
    palavra (artrose x artrodese, apêndice x apendicite). Desde 02/10 a palavra que o
    banco conhece só casa igual ou pela flexão; a lista fica para conferência.
 4. VARIANTE DE MÁSCARA COM ACHADO NO NOME: "<exame> com <achado>" troca a máscara pela
    variante; desde 02/10 só troca se os achados do NOME da variante foram ditados
    ("tc de tórax com derrame" não abre mais a variante derrame + ATELECTASIA).
 5. FRASE DE BLOCO QUE ACRESCENTA ACHADO: "derrame pleural ..., com atelectasia passiva"
    — o achado acrescentado é nome de outro bloco da mesma região e não está no gatilho.
    É redação do banco: fica para ele decidir, frase por frase.
 6. FRASE COM OPÇÃO SOLTA: "pequeno/moderado" no texto; o grau ditado não escolhe.

O ditado do botão de raciocínio com o switch "roteador" desligado (o padrão) não passa
por nada disto: vai cru para a IA.
"""
import collections
import difflib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import roteador as R  # noqa: E402

QUALIFICADORES = [
    "pequeno à direita", "pequeno à esquerda", "moderado à direita", "moderado à esquerda",
    "bilateral", "bilaterais", "à direita", "à esquerda", "discreto", "discreta", "leve",
    "moderado", "moderada", "acentuado", "acentuada", "pequeno", "pequena", "volumoso",
    "de pequeno volume", "de moderado volume", "de grande volume", "maior à direita",
    "maior à esquerda", "predominando nas bases", "nas bases", "nos ápices", "difuso",
    "difusa", "esparsos", "múltiplos", "medindo 5 mm", "medindo 1,2 cm", "cerca de 8 mm",
    "no lobo inferior direito", "no lobo superior esquerdo", "no terço médio",
    "sem complicações", "sem sinais de complicação", "associado", "e também", "residual",
    "inespecífico", "a esclarecer", "recomendando correlação", "agudo", "crônico",
    "simples", "pequenas dimensões", "em ambos os lados", "mais à direita",
]

GENERICAS = set("""direito direita esquerdo esquerda bilateral bilaterais pequeno pequena pequenos
pequenas moderado moderada acentuado acentuada discreto discreta leve leves volume volumoso
maior menor medindo cerca ambos lados lado difuso difusa esparsos multiplos multiplas
residual agudo aguda cronico cronica simples superior inferior medio media terco lobo
lobos bases base apices apice predominando associado associada tambem complicacoes
complicacao sinais sem com mais""".split())

_SLUG = re.compile(r"[a-z]+")
_PREFIXOS_VAR = {"aguda", "agudo", "cronica", "cronico", "normal", "pos", "com", "sem", "e", "de",
                 "do", "da", "variante", "frases", "blk", "achado", "achados"}
_OPCAO_SOLTA = re.compile(r"\b([a-záéíóúâêôãõç]{4,})/([a-záéíóúâêôãõç]{4,})\b", re.I)


def _conteudo(n):
    return [w for w in n.split() if len(w) >= 4 and w not in GENERICAS
            and w not in R._MODIFICADORES and w not in R._LOCAIS]


def prova_cruzada():
    """Cada achado do banco ditado no exame de cada região (com e sem "pequeno à direita"):
    o bloco que entra tem de ter no gatilho alguma palavra de conteúdo do achado."""
    regioes = {}
    for t, g, tit, txt, _s, _c in R.BANCO.itens:
        meta = R.BANCO.meta.get(tit) or ()
        if t == "bloco" and len(meta) >= 3:
            regioes.setdefault((meta[1], meta[2]), meta)
    achados = sorted({g for t, g, tit, *_ in R.BANCO.itens if t in ("bloco", "frase") and _conteudo(g)})
    gat_de = collections.defaultdict(set)
    for t, g, tit, *_ in R.BANCO.itens:
        if t == "bloco":
            gat_de[tit].add(g)
    ruins, n = [], 0
    for (mod, reg), _meta in sorted(regioes.items()):
        filtro = (lambda m, mod=mod, reg=reg: m[1] == mod and m[2] == reg)
        for a in achados:
            for seg in (a, a + " pequeno à direita"):
                n += 1
                b = R._bloco_do_segmento(seg, filtro)
                if not b:
                    continue
                cont = {w[:6] for w in _conteudo(R.normalizar(seg))}
                if not any({w[:6] for w in _conteudo(g)} & cont for g in gat_de[b[0]]):
                    ruins.append((mod + "/" + reg, seg, b[0], (b[1] or "")[:80]))
    return ruins, n


def prova_qualificadores():
    achados = []
    for q in QUALIFICADORES:
        b = R._bloco_do_segmento(q, lambda _m: True)
        if b:
            achados.append((q, b[0], (b[1] or "")[:90]))
    return achados


def prova_parecidas():
    """Pares de palavras DO BANCO parecidas (>= 0,85) que não são a mesma palavra."""
    v = collections.Counter()
    for t, g, tit, txt, _s, _c in R.BANCO.itens:
        for w in (g or "").split():
            if len(w) >= 5:
                v[w] += 1
    palavras = sorted(w for w in v if not w.isdigit() and w not in GENERICAS)
    por_inicio = collections.defaultdict(list)
    for w in palavras:
        por_inicio[w[:3]].append(w)
    pares = []
    for grupo in por_inicio.values():
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 and not R._mesma_familia(a, b):
                    pares.append((a, b, v[a], v[b]))
    return pares


def prova_variantes():
    """Variante de máscara aberta por '<exame> com <achado>' com achado no nome que o
    gatilho não diz."""
    saida, vistos = [], set()
    for t, g, tit, txt, _s, _c in R.BANCO.itens:
        meta = R.BANCO.meta.get(tit) or ()
        if t != "mascara" or len(meta) < 4 or str(meta[3]).startswith("normal") or " com " not in g:
            continue
        slug = [w for w in _SLUG.findall(tit.rsplit("/", 1)[-1].lower()) if w not in _PREFIXOS_VAR and len(w) >= 4]
        gat = set(w[:6] for w in g.split())
        falta = [w for w in slug if w[:6] not in gat]
        if falta and (tit, " ".join(falta)) not in vistos:
            vistos.add((tit, " ".join(falta)))
            saida.append((tit, g, ", ".join(falta)))
    return saida


def prova_frase_a_mais():
    """Bloco cujo texto acrescenta ("com", "associado a") um achado que é o nome de outro
    bloco da mesma região e não está em gatilho nenhum dele."""
    cabeca_reg = collections.defaultdict(set)
    gatilhos_do = collections.defaultdict(set)
    texto_do, reg_do = {}, {}
    for t, g, tit, txt, _s, _c in R.BANCO.itens:
        meta = R.BANCO.meta.get(tit) or ()
        if t != "bloco" or len(meta) < 3:
            continue
        cont = _conteudo(g)
        if cont:
            cabeca_reg[(meta[1], meta[2])].add(cont[0][:7])
        gatilhos_do[tit].update(w[:7] for w in g.split())
        texto_do[tit], reg_do[tit] = txt or "", (meta[1], meta[2])
    saida = []
    for tit, txt in texto_do.items():
        nt = R.normalizar(re.sub(r"\{[^}]*\}", " ", txt))
        slug = {w[:7] for w in _SLUG.findall(tit.rsplit("/", 1)[-1].lower())}
        acresc = set()
        for m in re.finditer(r"\b(?:com|associad[oa]s?\s+a)\s+((?:\w+\s+){0,2}\w+)", nt):
            for w in m.group(1).split():
                if len(w) >= 7 and w[:7] in cabeca_reg[reg_do[tit]] and w[:7] not in gatilhos_do[tit] \
                        and w[:7] not in slug and w not in GENERICAS:
                    acresc.add(w)
        if acresc:
            saida.append((tit, ", ".join(sorted(acresc)), txt[:110]))
    return saida


def prova_opcao_solta():
    saida, vistos = [], set()
    for t, g, tit, txt, _s, _c in R.BANCO.itens:
        if t not in ("bloco", "frase") or not txt or tit in vistos:
            continue
        m = _OPCAO_SOLTA.search(re.sub(r"\{[^}]*\}|\[[^\]]*\]", " ", txt))
        if m and m.group(0).lower() != "e/ou":
            vistos.add(tit)
            saida.append((tit, m.group(0), txt[:110]))
    return saida


def main(destino=None):
    R.BANCO.atualizada()
    c, n_c = prova_cruzada()
    q = prova_qualificadores()
    p = prova_parecidas()
    v = prova_variantes()
    f = prova_frase_a_mais()
    o = prova_opcao_solta()
    L = ["# Auditoria de gatilhos que entram onde não devem", "",
         "Banco: %d itens (%s)." % (len(R.BANCO.itens), os.path.basename(os.environ.get("LAUDO_BASE", "base.sqlite"))), "",
         "| prova | resultado |", "|---|---|",
         "| 1. achado ditado puxando bloco sem relação | %d de %d ditados |" % (len(c), n_c),
         "| 2. trecho só de qualificador puxando bloco | %d |" % len(q),
         "| 3. pares de palavras parecidas que não são a mesma (não casam mais) | %d |" % len(p),
         "| 4. variantes de máscara com achado no nome (só abrem com o achado dito) | %d |" % len(v),
         "| 5. frase de bloco que acrescenta achado (decisão dele) | %d |" % len(f),
         "| 6. frase com opção solta x/y (decisão dele) | %d |" % len(o), ""]
    L += ["## 1. Achado ditado puxando bloco sem relação", "",
          "| região | ditado | bloco que entrou | texto |", "|---|---|---|---|"]
    L += ["| %s | %s | %s | %s |" % x for x in c] or ["| (nenhum) | | | |"]
    L += ["", "## 2. Trecho só de qualificador puxando bloco", "", "| trecho | bloco | texto |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in q] or ["| (nenhum) | | |"]
    L += ["", "## 3. Palavras parecidas que não são a mesma (não casam mais por semelhança)", "",
          "| palavra | parecida com | usos | usos |", "|---|---|---|---|"]
    L += ["| %s | %s | %d | %d |" % x for x in p]
    L += ["", "## 4. Variantes de máscara com achado no nome", "",
          "| variante | gatilho | achado do nome que o gatilho não diz |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in v]
    L += ["", "## 5. Frase de bloco que acrescenta achado", "",
          "| bloco | achado acrescentado | texto |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in f]
    L += ["", "## 6. Frase com opção solta", "", "| bloco/frase | opção | texto |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % x for x in o]
    relatorio = "\n".join(L) + "\n"
    if destino:
        with io.open(destino, "w", encoding="utf-8") as fh:
            fh.write(relatorio)
    print("\n".join(L[:13]))
    return {"cruzada": c, "n_cruzada": n_c, "qualificadores": q, "parecidas": p, "variantes": v,
            "a_mais": f, "opcao": o}


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
