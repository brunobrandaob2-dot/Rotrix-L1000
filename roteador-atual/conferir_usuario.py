# -*- coding: utf-8 -*-
"""Quais máscaras SUAS estão na frente das do Rotrix — e o que muda por causa disso.

    python conferir_usuario.py

Por que existe
--------------
26/09: o testar_tecnica_rx falhou na máquina dele em tórax, tornozelo e ombro.
Não era o banco: são as máscaras DELE (dados/mascaras_usuario) ganhando o
gatilho. Isso é o desenho certo — máscara dele manda — mas tem um efeito que
ninguém via: as incidências de TÉCNICA que ele ditou em 25/09 entraram nas
máscaras do Rotrix e NÃO chegam no laudo dele, porque a dele vem na frente.

Este relatório mostra, lado a lado, a TÉCNICA que ele usa hoje e a que o Rotrix
passou a ter. Não muda nada: quem decide é ele.

Correção de 26/09 (tarde)
-------------------------
A primeira versão procurava a disputa dentro do base.sqlite. Só que o
construir_base guarda UM dono por gatilho — o perdedor nem entra no banco —,
então a interseção era sempre vazia e o relatório dizia "nenhum gatilho seu
está na frente" justamente na máquina em que estava. Agora a disputa sai dos
ARQUIVOS (dados/mascaras e dados/mascaras_usuario), com a mesma normalização
do construir_base, e o banco só é usado para confirmar quem sai hoje.
"""

import io
import os
import re
import sys
import unicodedata

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AQUI = os.path.dirname(os.path.abspath(__file__))
RX = re.compile(r"^\*\*TÉCNICA:\*\*\s*(.*)$")


def normalizar(s):
    """Igual ao construir_base.normalizar (lá o módulo compila ao ser importado)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tecnica(texto):
    linhas = (texto or "").split("\n")
    for i, l in enumerate(linhas):
        m = RX.match(l)
        if m:
            fora = [m.group(1).strip()] if m.group(1).strip() else []
            # a TÉCNICA vai até a linha em branco ou a próxima seção — a segunda
            # linha nem sempre começa com "Exame realizado" (a dele de tórax é
            # "Incidência em anteroposterior.")
            j = i + 1
            while j < len(linhas) and linhas[j].strip() and not linhas[j].startswith("**"):
                fora.append(linhas[j].strip())
                j += 1
            return fora
    return []


_FORMAS = {"tc": ["tomografia computadorizada", "tomografia", "tc"],
           "rx": ["radiografia", "raio x", "rx"],
           "angiotc": ["angiotomografia computadorizada", "angiotomografia", "angio tc", "angio"]}
_ARTIGOS = ("de ", "do ", "da ", "dos ", "das ")


def _variantes(g, mod):
    """Igual ao construir_base._variantes: "rx de ombro" também vale "radiografia do ombro"."""
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


def ler_mascaras(raiz, prefixo=""):
    """Lê as MÁSCARAS de uma pasta exatamente como o construir_base lê:
    mesmo cabeçalho (# chave: valor, sem diferenciar maiúscula), mesmo tipo pelo
    nome do arquivo quando não há "# tipo:" (blk_ = bloco, frases, adendo,
    ressalva, achado), _legado fora, e as variantes geradas.
    Devolve {titulo: {"gat": [explícitos], "var": [variantes], "corpo": texto}}."""
    fora = {}
    if not os.path.isdir(raiz):
        return fora
    for r, pastas, arquivos in os.walk(raiz):
        pastas[:] = sorted(p for p in pastas if p != "_legado" and not p.startswith("."))
        for nome in sorted(arquivos):
            if not nome.lower().endswith(".txt"):
                continue
            caminho = os.path.join(r, nome)
            try:
                bruto = io.open(caminho, encoding="utf-8").read().splitlines()
            except Exception:
                continue
            rel = os.path.relpath(caminho, raiz).replace("\\", "/")
            meta, gatilhos, inicio = {}, [], len(bruto)
            for i, l in enumerate(bruto):
                s = l.strip()
                if s.startswith("## "):
                    inicio = i
                    break
                if s.startswith("#"):
                    m = re.match(r"#\s*([a-z_]+)\s*:(.*)$", s, re.I)
                    if m:
                        k, v = m.group(1).lower(), m.group(2).strip()
                        if k == "gatilhos":
                            gatilhos = [g.strip() for g in v.split("|") if g.strip()]
                        else:
                            meta[k] = v
                    continue
                inicio = i
                break
            tipo = (meta.get("tipo") or ("bloco" if nome.startswith("blk_") else
                                         "frases" if nome.startswith("frases") else
                                         "adendo" if nome.startswith(("adendo", "ressalva")) else
                                         "achado" if nome.startswith("achado") else
                                         "mascara")).lower()
            if tipo != "mascara":
                continue
            p = (prefixo + rel).split("/")          # como o _meta_do_caminho do construir_base
            mod = meta.get("modalidade") or (p[1] if len(p) > 2 else "")
            if not gatilhos:
                gatilhos = [os.path.splitext(nome)[0].replace("_", " ")]
            gat = [normalizar(g) for g in gatilhos]
            var = [v for g in gat for v in _variantes(g, mod)]
            fora[prefixo + rel[:-4]] = {"gat": [g for g in gat if g], "var": var,
                                        "corpo": "\n".join(bruto[inicio:]).strip()}
    return fora


def fonte_atual():
    try:
        import importar_usuario
        return importar_usuario.fonte_atual()
    except Exception:
        return "rotrix"


def disputas(dados, fonte=None):
    """Quem fica com cada gatilho, na MESMA ordem do construir_base:
    o lado que vence (suas, com a fonte "minhas" ou "ambas"; do Rotrix, com "rotrix")
    entra primeiro; dentro de cada lado, os gatilhos escritos antes das variantes.

    Devolve (pares, mortas, suas, rotrix, voce_vence):
      pares:  {(titulo_seu, titulo_rotrix): [gatilhos disputados]}
      mortas: {titulo_seu: titulo_seu_que_ganha} — sua máscara que nunca sai,
              porque outra SUA leva todos os gatilhos dela."""
    fonte = fonte or fonte_atual()
    voce_vence = fonte in ("minhas", "ambas")
    suas = ler_mascaras(os.path.join(dados, "mascaras_usuario"), "usuario/")
    rotrix = ler_mascaras(os.path.join(dados, "mascaras"))
    lados = [suas, rotrix] if voce_vence else [rotrix, suas]
    ordem = []
    for lado in lados:
        for tit in sorted(lado):
            ordem += [(g, tit) for g in lado[tit]["gat"]]
        for tit in sorted(lado):
            ordem += [(g, tit) for g in lado[tit]["var"]]
    dono, candidatos = {}, {}
    for g, tit in ordem:
        dono.setdefault(g, tit)
        candidatos.setdefault(g, [])
        if tit not in candidatos[g]:
            candidatos[g].append(tit)
    pares = {}
    for g, tits in candidatos.items():
        dele = [t for t in tits if t.startswith("usuario/")]
        rot = [t for t in tits if not t.startswith("usuario/")]
        if dele and rot:
            k = (dono[g] if dono[g].startswith("usuario/") else dele[0],
                 dono[g] if not dono[g].startswith("usuario/") else rot[0])
            pares.setdefault(k, []).append(g)
    mortas = {}
    for tit, d in suas.items():
        donos = {dono[g] for g in d["gat"] + d["var"]}
        if tit not in donos and donos and all(x.startswith("usuario/") for x in donos) and len(donos) == 1:
            mortas[tit] = donos.pop()
    pares = {k: sorted(v) for k, v in pares.items() if k[0] not in mortas}
    return pares, mortas, suas, rotrix, voce_vence


def main():
    dados = os.path.join(AQUI, "dados")
    pares, mortas, suas, rotrix, voce_vence = disputas(dados)
    print("máscaras suas: %d   |   do Rotrix: %d   |   pares em disputa: %d   |   fonte: %s"
          % (len(suas), len(rotrix), len(pares), fonte_atual()))
    print()

    rotear = None
    try:
        import roteador
        rotear = roteador.rotear
    except Exception as e:
        print("(banco não carregou: %s — mostro só os arquivos)" % type(e).__name__)
        print()

    if not pares:
        print("nenhum gatilho seu está na frente de máscara do Rotrix.")
    else:
        print("=" * 74)
        print("  ONDE A SUA MÁSCARA GANHA — e o que o Rotrix diria no lugar" if voce_vence else
              "  ONDE A SUA MÁSCARA PERDE — a fonte está em \"rotrix\": sai a do Rotrix")
        print("=" * 74)
    for (tit_u, tit_r), gatilhos in sorted(pares.items()):
        print()
        print("SUA:    %s" % tit_u)
        print("Rotrix: %s" % tit_r)
        print("gatilhos: %s%s" % (", ".join(gatilhos[:6]),
                                  "  (+%d)" % (len(gatilhos) - 6) if len(gatilhos) > 6 else ""))
        if rotear:
            try:
                _t, origem = rotear(gatilhos[0])
                print("   sai hoje: %s" % origem)
            except Exception as e:
                print("   (não consegui rotear: %s)" % type(e).__name__)
        tec_u = tecnica(suas[tit_u]["corpo"])
        tec_r = tecnica(rotrix[tit_r]["corpo"])
        if tec_u == tec_r:
            print("   TÉCNICA: igual nas duas.")
            continue
        print("   TÉCNICA da sua:")
        for l in (tec_u or ["(sem TÉCNICA)"]):
            print("      %s" % l)
        print("   TÉCNICA da máscara do Rotrix:")
        for l in (tec_r or ["(sem TÉCNICA)"]):
            print("      %s" % l)

    if mortas:
        print()
        print("=" * 74)
        print("  MÁSCARAS SUAS QUE NUNCA SAEM (outra sua tem os mesmos gatilhos)")
        print("=" * 74)
        for m, dono in sorted(mortas.items()):
            print("   %s   -> quem sai é %s" % (m, dono))

    print()
    print("=" * 74)
    print("  O QUE FAZER — nada é automático, a máscara é sua")
    print("=" * 74)
    print("  1. deixar como está  -> o laudo sai com a SUA técnica, como hoje")
    print("  2. ajustar a sua     -> abrir a máscara em Máscaras > Minhas e trocar")
    print("                          só a linha da TÉCNICA")
    print("  3. usar a do Rotrix  -> tirar a sua máscara daquela região da pasta")
    print()
    print("  As máscaras suas ficam em:")
    print("     %s" % os.path.join(dados, "mascaras_usuario"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
