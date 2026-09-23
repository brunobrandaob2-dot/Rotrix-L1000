# -*- coding: utf-8 -*-
"""Oficina de máscaras: mexer no banco pelo aplicativo, sem passar pelo chat.

O Bruno cola uma máscara corrigida (ou descreve o que quer) na aba Máscaras, e
daqui sai uma lista de PROPOSTAS. Ele aprova, e aí sim o arquivo é escrito e a
base é refeita. Nada é alterado sem aprovação e tudo é reversível.

Como funciona:
1. `propor()` escolhe sozinho as máscaras que interessam — pelo texto colado
   (que máscara é essa?), pela região, pelas palavras do pedido — e manda só
   essas para a IA, com o pedido. A IA responde em JSON com operações.
2. `aplicar()` grava as operações aprovadas SEMPRE em dados/mascaras_usuario,
   nunca por cima das máscaras que vêm com o Rotrix: quando o comando é o
   mesmo, a do usuário é a que vale. Antes de escrever, guarda uma cópia.
3. `desfazer()` devolve a cópia e refaz a base.
"""
import json
import os
import re
import shutil
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados")
PASTA_ROTRIX = os.path.join(DADOS, "mascaras")
PASTA_USUARIO = os.path.join(DADOS, "mascaras_usuario")
PASTA_COPIAS = os.path.join(DADOS, "oficina_copias")

_GENERICAS = {
    "de", "da", "do", "dos", "das", "e", "o", "a", "os", "as", "em", "no", "na",
    "para", "por", "com", "sem", "que", "uma", "um", "the", "mascara", "mascaras",
    "laudo", "laudos", "exame", "texto", "frase", "frases", "muda", "mudar",
    "arruma", "arrumar", "corrige", "corrigir", "troca", "trocar", "quero",
    "favor", "por favor", "essa", "esse", "este", "esta", "aqui", "esta",
}
_MAX_MASCARAS = 14          # quantas vão para a IA de uma vez
_MAX_TEXTO = 2500           # tamanho de cada máscara no pedido


def _n(s):
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def _palavras(texto, minimo=4):
    return {p for p in _n(texto).split() if len(p) >= minimo and p not in _GENERICAS}


def caminho_da_mascara(titulo):
    """Título do banco -> arquivo no disco. "usuario/..." é máscara sua."""
    t = (titulo or "").strip().replace("\\", "/")
    if not t or ".." in t:
        return None
    if t.startswith("usuario/"):
        return os.path.join(PASTA_USUARIO, *t[len("usuario/"):].split("/")) + ".txt"
    return os.path.join(PASTA_ROTRIX, *t.split("/")) + ".txt"


def _texto_da_mascara(caminho):
    """O conteúdo do arquivo, separando o cabeçalho (# gatilhos: ...) do corpo."""
    try:
        bruto = open(caminho, encoding="utf-8").read()
    except OSError:
        return "", ""
    linhas = bruto.splitlines()
    i = 0
    while i < len(linhas) and (linhas[i].startswith("#") or not linhas[i].strip()):
        i += 1
    return "\n".join(linhas[:i]), "\n".join(linhas[i:]).strip("\n")


def _gatilhos_do_cabecalho(cabecalho):
    m = re.search(r"^#\s*gatilhos:\s*(.+)$", cabecalho or "", re.M)
    if not m:
        return []
    return [g.strip() for g in re.split(r"[|;]", m.group(1)) if g.strip()]


def escolher(banco, instrucao, texto_colado="", busca="", limite=_MAX_MASCARAS):
    """Quais máscaras têm a ver com o pedido.

    Ordem: o que o texto colado parece ser (primeira linha vira comando), o que
    a busca da tela diz, e o quanto as palavras do pedido aparecem no título,
    nos gatilhos e no texto de cada máscara."""
    candidatas = {}
    for it in banco.itens:
        if it[0] != "mascara":
            continue
        tit = it[2]
        d = candidatas.get(tit)
        if d is None:
            cat, mod, reg, sub = banco.meta.get(tit, ("", "", "", ""))
            d = candidatas[tit] = {"titulo": tit, "regiao": reg, "modalidade": mod,
                                   "gatilhos": [], "texto": it[3] or "", "ponto": 0.0}
        if len(d["gatilhos"]) < 12:
            d["gatilhos"].append(it[1])
        if not d["texto"] and it[3]:
            d["texto"] = it[3]

    # 1) o texto colado é uma máscara? a primeira linha costuma ser o título
    primeira = ""
    for linha in (texto_colado or "").splitlines():
        if linha.strip():
            primeira = linha.strip()
            break
    alvo_direto = None
    if primeira and hasattr(banco, "buscar2"):
        try:
            tit, _txt, escore, _g = banco.buscar2(_n(primeira), "mascara")
            if tit and escore >= 0.8:
                alvo_direto = tit
        except Exception:
            alvo_direto = None

    chaves = _palavras(instrucao) | _palavras(primeira)
    chaves_texto = _palavras(texto_colado)
    busca_n = _n(busca)

    for d in candidatas.values():
        ponto = 0.0
        alvo = _n(d["titulo"] + " " + " ".join(d["gatilhos"]) + " " + d["regiao"])
        palavras_alvo = set(alvo.split())
        ponto += 4.0 * len(chaves & palavras_alvo)
        ponto += 1.0 * len(chaves_texto & palavras_alvo)
        if busca_n and (busca_n in alvo or busca_n in _n(d["regiao"])):
            ponto += 6.0
        if d["titulo"] == alvo_direto:
            ponto += 20.0
        if d["titulo"].startswith("usuario/"):
            ponto += 1.0          # as suas vêm primeiro em caso de empate
        d["ponto"] = ponto

    escolhidas = [d for d in candidatas.values() if d["ponto"] > 0]
    escolhidas.sort(key=lambda d: (-d["ponto"], d["titulo"]))
    if not escolhidas and busca_n:
        escolhidas = [d for d in candidatas.values() if busca_n in _n(d["titulo"])]
    return escolhidas[:limite]


_INSTRUCAO_JSON = """Você é o mantenedor do banco de máscaras de laudo de um radiologista.
Responda SÓ com JSON válido, sem texto em volta, neste formato:

{"operacoes": [
  {"acao": "substituir", "titulo": "<título exato de uma máscara da lista>",
   "texto": "<texto novo INTEIRO da máscara>", "porque": "<uma linha>"},
  {"acao": "criar", "nome": "<nome curto, ex.: rx joelho com prótese>",
   "modalidade": "<rx|tc|rm|us|outro>", "regiao": "<uma palavra, ex.: joelho>",
   "gatilhos": ["<comando de voz>", "..."],
   "texto": "<texto inteiro da máscara nova>", "porque": "<uma linha>"},
  {"acao": "trocar_frase", "titulo": "<título ou \\"todas\\">",
   "de": "<trecho exato que sai>", "para": "<trecho que entra>", "porque": "<uma linha>"}
]}

Regras:
- Se o radiologista colou uma máscara corrigida, a operação é "substituir" na
  máscara da lista que corresponde a ela; se nenhuma corresponder, é "criar".
- Mantenha o estilo do banco: títulos e rótulos em **negrito** com asteriscos,
  uma frase por linha, sem inventar achado clínico que não estava lá.
- Não invente medida, lado, idade nem conclusão que o texto não tenha.
- Lacunas ficam entre chaves, como {lado}.
- Se o pedido não der para atender, devolva {"operacoes": [], "recado": "<motivo>"}.
"""


def montar_pedido(instrucao, texto_colado, escolhidas):
    partes = [_INSTRUCAO_JSON, "", "PEDIDO DO RADIOLOGISTA:", (instrucao or "").strip()]
    if (texto_colado or "").strip():
        partes += ["", "TEXTO QUE ELE COLOU:", texto_colado.strip()[:8000]]
    partes += ["", "MÁSCARAS DO BANCO QUE PODEM SER AS CERTAS (%d):" % len(escolhidas)]
    for d in escolhidas:
        partes.append("--- título: %s | região: %s | comandos: %s ---\n%s"
                      % (d["titulo"], d["regiao"] or "?",
                         ", ".join(d["gatilhos"][:4]) or "?", d["texto"][:_MAX_TEXTO]))
    return "\n".join(partes)


def _so_json(resposta):
    """A resposta da IA pode vir com ```json em volta; tira e carrega."""
    t = (resposta or "").strip()
    t = re.sub(r"^```[a-z]*\s*|\s*```$", "", t, flags=re.I | re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except ValueError:
        return None


def validar(dados, escolhidas):
    """Operações que dá para aplicar, já com o antes/depois para a tela."""
    titulos = {d["titulo"]: d for d in escolhidas}
    propostas, recusadas = [], []
    for op in (dados or {}).get("operacoes") or []:
        acao = str(op.get("acao") or "").strip().lower()
        porque = str(op.get("porque") or "")[:200]
        if acao == "substituir":
            tit = str(op.get("titulo") or "").strip()
            novo = str(op.get("texto") or "").strip()
            d = titulos.get(tit)
            if not d:
                recusadas.append({"acao": acao, "motivo": "título fora da lista: %s" % tit[:60]})
                continue
            if len(novo) < 20:
                recusadas.append({"acao": acao, "motivo": "texto novo muito curto"})
                continue
            if novo.strip() == (d["texto"] or "").strip():
                recusadas.append({"acao": acao, "motivo": "o texto novo é igual ao atual"})
                continue
            propostas.append({"acao": "substituir", "titulo": tit, "porque": porque,
                              "antes": d["texto"], "depois": novo,
                              "regiao": d["regiao"], "gatilhos": d["gatilhos"][:6]})
        elif acao == "criar":
            nome = str(op.get("nome") or "").strip()
            novo = str(op.get("texto") or "").strip()
            gat = [str(g).strip() for g in (op.get("gatilhos") or []) if str(g).strip()]
            if len(novo) < 20 or not nome:
                recusadas.append({"acao": acao, "motivo": "máscara nova sem nome ou sem texto"})
                continue
            if not gat:
                recusadas.append({"acao": acao, "motivo": "máscara nova sem comando de voz"})
                continue
            propostas.append({"acao": "criar", "nome": nome, "porque": porque,
                              "modalidade": (str(op.get("modalidade") or "outro").strip().lower()),
                              "regiao": (str(op.get("regiao") or "").strip().lower() or "outros"),
                              "gatilhos": gat[:12], "antes": "", "depois": novo})
        elif acao == "trocar_frase":
            de = str(op.get("de") or "")
            para = str(op.get("para") or "")
            tit = str(op.get("titulo") or "todas").strip()
            if len(de.strip()) < 4:
                recusadas.append({"acao": acao, "motivo": "o trecho que sai é curto demais"})
                continue
            alvos = list(titulos) if tit.lower() in ("todas", "*") else [tit]
            atingidas = [t for t in alvos if de in (titulos.get(t, {}).get("texto") or "")]
            if not atingidas:
                recusadas.append({"acao": acao, "motivo": "o trecho %r não está em nenhuma das máscaras lidas" % de[:40]})
                continue
            propostas.append({"acao": "trocar_frase", "de": de, "para": para,
                              "porque": porque, "titulos": atingidas,
                              "antes": de, "depois": para})
        else:
            recusadas.append({"acao": acao or "?", "motivo": "ação desconhecida"})
    return propostas, recusadas


def _slug(s, n=40):
    s = _n(s).replace(" ", "_")
    return (s[:n] or "mascara").strip("_")


def _arquivo_do_usuario(modalidade, regiao, nome):
    pasta = os.path.join(PASTA_USUARIO, _slug(modalidade or "outro", 12), _slug(regiao or "outros", 24))
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, _slug(nome))
    arq, k = base + ".txt", 2
    while os.path.exists(arq):
        arq = "%s_%d.txt" % (base, k)
        k += 1
    return arq


def _gravar(arq, gatilhos, modalidade, regiao, texto, origem):
    cab = ["# gatilhos: " + " | ".join(gatilhos),
           "# categoria: usuario",
           "# modalidade: " + (modalidade or "outro"),
           "# regiao: " + _slug(regiao or "outros", 24),
           "# tipo_mascara: normal",
           "# origem: " + origem]
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    with open(arq, "w", encoding="utf-8") as f:
        f.write("\n".join(cab) + "\n" + texto.strip() + "\n")


def _copiar_antes(arq, destino):
    if os.path.exists(arq):
        alvo = os.path.join(destino, os.path.basename(arq))
        k = 2
        while os.path.exists(alvo):
            alvo = os.path.join(destino, "%d_%s" % (k, os.path.basename(arq)))
            k += 1
        shutil.copy2(arq, alvo)
        with open(alvo + ".de", "w", encoding="utf-8") as f:
            f.write(arq)


def aplicar(propostas, banco=None, refazer=None):
    """Grava as operações aprovadas e refaz a base. Sempre em mascaras_usuario."""
    propostas = [p for p in (propostas or []) if isinstance(p, dict)]
    if not propostas:
        return {"ok": False, "motivo": "nada_aprovado"}
    carimbo = time.strftime("%Y%m%d-%H%M%S")
    copias = os.path.join(PASTA_COPIAS, carimbo)
    os.makedirs(copias, exist_ok=True)
    feitas, erros = [], []

    for p in propostas:
        acao = p.get("acao")
        try:
            if acao == "substituir":
                tit = p["titulo"]
                origem = caminho_da_mascara(tit)
                cab, _corpo = _texto_da_mascara(origem) if origem else ("", "")
                gat = _gatilhos_do_cabecalho(cab) or [g for g in p.get("gatilhos") or []]
                if not gat:
                    erros.append("sem comando de voz para " + tit)
                    continue
                if tit.startswith("usuario/"):
                    arq = origem
                    _copiar_antes(arq, copias)
                else:
                    # a do Rotrix continua intacta; a sua entra por cima pelos
                    # mesmos comandos de voz
                    arq = _arquivo_do_usuario(_meta(cab, "modalidade"), _meta(cab, "regiao"),
                                              tit.rsplit("/", 1)[-1])
                _gravar(arq, gat, _meta(cab, "modalidade"), _meta(cab, "regiao"),
                        p["depois"], "oficina " + carimbo)
                feitas.append({"acao": acao, "titulo": tit,
                               "arquivo": os.path.relpath(arq, DADOS).replace("\\", "/")})
            elif acao == "criar":
                arq = _arquivo_do_usuario(p.get("modalidade"), p.get("regiao"), p.get("nome"))
                _gravar(arq, p.get("gatilhos") or [], p.get("modalidade"), p.get("regiao"),
                        p["depois"], "oficina " + carimbo)
                feitas.append({"acao": acao, "titulo": p.get("nome"),
                               "arquivo": os.path.relpath(arq, DADOS).replace("\\", "/")})
            elif acao == "trocar_frase":
                for tit in p.get("titulos") or []:
                    origem = caminho_da_mascara(tit)
                    if not origem or not os.path.exists(origem):
                        continue
                    cab, corpo = _texto_da_mascara(origem)
                    if p["de"] not in corpo:
                        continue
                    novo = corpo.replace(p["de"], p.get("para") or "")
                    gat = _gatilhos_do_cabecalho(cab)
                    if tit.startswith("usuario/"):
                        arq = origem
                        _copiar_antes(arq, copias)
                    else:
                        arq = _arquivo_do_usuario(_meta(cab, "modalidade"), _meta(cab, "regiao"),
                                                  tit.rsplit("/", 1)[-1])
                    _gravar(arq, gat, _meta(cab, "modalidade"), _meta(cab, "regiao"),
                            novo, "oficina " + carimbo)
                    feitas.append({"acao": acao, "titulo": tit,
                                   "arquivo": os.path.relpath(arq, DADOS).replace("\\", "/")})
            else:
                erros.append("ação desconhecida: %s" % acao)
        except Exception as e:
            erros.append("%s: %s" % (type(e).__name__, str(e)[:120]))

    # o que foi escrito agora fica anotado, para o desfazer saber o que apagar
    try:
        with open(os.path.join(copias, "escritos.json"), "w", encoding="utf-8") as f:
            json.dump([os.path.join(DADOS, x["arquivo"]) for x in feitas], f)
    except OSError:
        pass

    base_ok, base_msg = (True, "")
    if feitas and refazer is not None:
        base_ok, base_msg = refazer()
        if base_ok and banco is not None:
            try:
                banco.carregar()
            except Exception:
                pass
    return {"ok": bool(feitas) and base_ok, "aplicadas": len(feitas), "itens": feitas,
            "erros": erros, "desfazer": carimbo, "base": base_msg,
            "motivo": "" if feitas else "nada_gravado"}


def _meta(cabecalho, campo):
    m = re.search(r"^#\s*%s:\s*(.+)$" % campo, cabecalho or "", re.M)
    return (m.group(1).strip() if m else "")


def desfazer(carimbo, banco=None, refazer=None):
    """Volta tudo o que uma aplicação mudou."""
    copias = os.path.join(PASTA_COPIAS, re.sub(r"[^0-9\-]", "", carimbo or ""))
    if not carimbo or not os.path.isdir(copias):
        return {"ok": False, "motivo": "copia_nao_encontrada"}
    voltaram, apagados = 0, 0
    try:
        escritos = json.load(open(os.path.join(copias, "escritos.json"), encoding="utf-8"))
    except (OSError, ValueError):
        escritos = []
    for arq in escritos:
        try:
            if os.path.exists(arq):
                os.remove(arq)
                apagados += 1
        except OSError:
            pass
    for nome in sorted(os.listdir(copias)):
        if not nome.endswith(".de"):
            continue
        try:
            destino = open(os.path.join(copias, nome), encoding="utf-8").read().strip()
            shutil.copy2(os.path.join(copias, nome[:-3]), destino)
            voltaram += 1
        except OSError:
            pass
    base_msg = ""
    if refazer is not None:
        _ok, base_msg = refazer()
        if banco is not None:
            try:
                banco.carregar()
            except Exception:
                pass
    return {"ok": True, "voltaram": voltaram, "apagados": apagados, "base": base_msg}
