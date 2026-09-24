# -*- coding: utf-8 -*-
"""Máscaras e laudos PRÓPRIOS do radiologista no Roteador de Laudos (Rotrix).

    python importar_usuario.py mascaras ARQUIVO [--substituir] [--json]
    python importar_usuario.py laudos   ARQUIVO [--substituir] [--json]
    python importar_usuario.py fonte    rotrix|minhas|ambas     [--json]
    python importar_usuario.py listar                            [--json]
    python importar_usuario.py remover  mascaras|laudos          [--json]

Arquivos aceitos: .txt, .md, .docx (Word) e .rtf.
Várias máscaras no mesmo arquivo: separe com uma linha "---", ou comece cada uma
com o título em CAIXA ALTA ("TOMOGRAFIA COMPUTADORIZADA DO TÓRAX").
Opcional, na primeira linha de cada máscara: "gatilhos: tc de torax | tomografia de torax".

Fonte das máscaras (config.json -> fonte_mascaras):
    rotrix  só as do Rotrix (padrão)
    minhas  só as suas
    ambas   as duas; quando o comando é o mesmo, vale a SUA

Segurança:
  - Lado escrito no título ("JOELHO DIREITO") vira lacuna que o ditado preenche. Um lado
    fixo colaria "direito" num exame do lado esquerdo.
  - Máscara com identificador (CPF, data completa, prontuário, e-mail, "Paciente:") não entra.
  - Laudo: as linhas de cabeçalho com dados do paciente são retiradas. Se ainda sobrar
    identificador, o laudo não entra. Nome de paciente no meio do texto não é detectável:
    retire antes de importar.
"""
import json, os, re, subprocess, sys, unicodedata, zipfile, hashlib, datetime
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
DADOS = os.path.join(AQUI, "dados")
PASTA_MASC = os.path.join(DADOS, "mascaras_usuario")
PASTA_ESTILO = os.path.join(DADOS, "estilo")
CONFIG = os.path.join(AQUI, "config.json")
FONTES = ("rotrix", "minhas", "ambas")
MAX_LAUDOS = 40                   # os exemplos de estilo têm teto de tamanho no prompt


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")

def normalizar(s):
    s = _sem_acento(s).lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _slug(s, n=40):
    return (normalizar(s).replace(" ", "_")[:n].strip("_")) or "geral"


# ---------- leitura dos arquivos ----------
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def _ler_docx(caminho):
    with zipfile.ZipFile(caminho) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
    linhas = []
    for p in raiz.iter(_W + "p"):
        partes = []
        for el in p.iter():
            if el.tag == _W + "t":
                partes.append(el.text or "")
            elif el.tag == _W + "tab":
                partes.append("\t")
            elif el.tag == _W + "br":
                if el.get(_W + "type") == "page":
                    partes.append("\n---\n")
                else:
                    partes.append("\n")
        linhas.append("".join(partes))
    return "\n".join(linhas)

def _ler_rtf(bruto):
    """RTF simples (exportação de editor de laudo) -> texto. Tabelas e imagens são ignoradas."""
    t = bruto
    # grupos que não são texto: {\*\...}, fontes, cores, estilos, informações, imagens
    for _ in range(3):
        t = re.sub(r"\{\\\*[^{}]*\}", " ", t)
        t = re.sub(r"\{\\(?:fonttbl|colortbl|stylesheet|info|pict|header|footer)[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", " ", t)
    t = re.sub(r"\\par[d]?\b ?", "\n", t)
    t = re.sub(r"\\line\b ?", "\n", t)
    t = re.sub(r"\\page\b ?", "\n---\n", t)
    t = re.sub(r"\\tab\b ?", "\t", t)
    # \uN vem seguido do caractere substituto (\'hh ou ?), que precisa sair junto
    t = re.sub(r"\\u(-?\d+) ?(?:\\'[0-9a-fA-F]{2}|\?)?", lambda m: chr(int(m.group(1)) % 65536), t)
    t = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
    t = t.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    return t.replace("{", "").replace("}", "")

def ler_arquivo(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".docx":
        return _ler_docx(caminho)
    raw = open(caminho, "rb").read()
    texto = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    if ext == ".rtf" or texto.lstrip().startswith("{\\rtf"):
        return _ler_rtf(texto)
    if ext in (".txt", ".md", ".text", ""):
        return texto
    raise ValueError("formato não aceito (%s): use .txt, .md, .docx ou .rtf" % ext)


# ---------- separar o arquivo em máscaras ----------
_SEP = re.compile(r"^\s*(?:-{3,}|={3,}|\*{3,}|_{3,}|#{3,})\s*$")
_EXAME = re.compile(r"\b(?:TOMOGRAFIA|RADIOGRAFIA|RESSONANCIA|ULTRASSONOGRAFIA|ULTRA SONOGRAFIA|"
                    r"ULTRASSOM|ECOGRAFIA|ANGIOTOMOGRAFIA|ANGIORRESSONANCIA|ANGIO|MAMOGRAFIA|"
                    r"DENSITOMETRIA|DOPPLER|RAIO X|RX|TC|RM|US|CINTILOGRAFIA|UROGRAFIA|"
                    r"ESOFAGOGRAMA|ENEMA|ARTROGRAFIA|ELASTOGRAFIA|COLANGIO\w*|ENTERO\w*)\b")
_GATILHOS = re.compile(r"^\s*#?\s*(?:gatilhos?|comandos?|atalhos?)\s*:\s*(.+)$", re.I)

def _titulo_limpo(l):
    return l.strip().strip("*#").strip()

def _eh_titulo(linha, estrito=True):
    t = _titulo_limpo(linha)
    if len(t) < 5 or len(t) > 140 or t.endswith(":"):
        return False
    alto = re.sub(r"[^A-Z0-9]+", " ", _sem_acento(t).upper())
    if not _EXAME.search(alto):
        return False
    letras = [c for c in t if c.isalpha()]
    if not letras:
        return False
    if estrito:
        return sum(1 for c in letras if c.isupper()) / len(letras) >= 0.85
    # título em caixa normal: curto, começa pelo nome do exame, sem ponto final
    return (len(t) <= 100 and not t.endswith(".") and
            bool(_EXAME.match(alto.strip())))

def _corpo(linhas):
    return [l for l in linhas if l.strip() and not _GATILHOS.match(l)]

def _separar_por_titulo(linhas, estrito):
    blocos, atual = [], []
    for i, l in enumerate(linhas):
        anterior_vazia = i == 0 or not linhas[i - 1].strip()
        if _eh_titulo(l, estrito) and (estrito or anterior_vazia) and len(_corpo(atual)) >= 2:
            # linhas "gatilhos:" logo antes do título pertencem à máscara nova
            leva = []
            while atual and (not atual[-1].strip() or _GATILHOS.match(atual[-1])):
                leva.insert(0, atual.pop())
            blocos.append(atual)
            atual = leva
        atual.append(l)
    if atual:
        blocos.append(atual)
    return blocos

def separar(texto):
    linhas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if any(_SEP.match(l) for l in linhas):
        blocos, atual = [], []
        for l in linhas:
            if _SEP.match(l):
                blocos.append(atual)
                atual = []
            else:
                atual.append(l)
        blocos.append(atual)
    else:
        blocos = _separar_por_titulo(linhas, True)
        if len(blocos) == 1:
            blocos = _separar_por_titulo(linhas, False)
    out = []
    for b in blocos:
        t = "\n".join(b).strip("\n")
        if t.strip():
            out.append(t)
    return out


# ---------- identificadores ----------
_CAMPO_PACIENTE = re.compile(
    r"^\s*(?:paciente|pac\.|nome do paciente|nome|data de nascimento|nascimento|d\.?\s?n\.?|idade|"
    r"sexo|prontu[aá]rio|atendimento|conv[eê]nio|pedido|accession|n[ºo°]\.?\s*(?:do\s+)?exame|"
    r"c[oó]digo|registro|m[eé]dico solicitante|solicitante|data do exame|data)\s*[:：]", re.I | re.M)

def identificadores(texto):
    """Motivos pelos quais o texto não pode entrar (vazio = liberado)."""
    motivos = []
    try:
        import nuvem
        motivos += nuvem.triagem(texto)
    except Exception:
        pass
    if _CAMPO_PACIENTE.search(texto or ""):
        motivos.append("campo de dados do paciente")
    return motivos

_ASSINATURA = re.compile(r"\b(?:dra?\.|doutora?|crm|m[eé]dic[oa] respons[aá]vel|assinado|"
                        r"laudado por|respons[aá]vel t[eé]cnico)\b", re.I)
_IDADE = re.compile(r"^\s*\d{1,3}\s*(?:anos|a)\b", re.I)

def tirar_cabecalho_paciente(texto):
    """Laudo -> só o corpo: sai tudo antes do título do exame (cabeçalho com nome,
    idade, médico, convênio, mesmo em linhas separadas), os campos de paciente e
    as linhas de assinatura/CRM."""
    linhas = texto.split("\n")
    for i, l in enumerate(linhas):
        if _eh_titulo(l, True) or _eh_titulo(l, False):
            linhas = linhas[i:]
            break
    return "\n".join(l for l in linhas
                     if not _CAMPO_PACIENTE.match(l) and not _ASSINATURA.search(l)
                     and not _IDADE.match(l))


# ---------- tipo de exame, região e comandos ----------
_MODS = {"rx": "rx", "tc": "tc", "rm": "rm", "angio": "angiotc", "us": "us", "mamo": "mamo"}
_FALA = {  # como se fala o exame (a região vai depois)
    "tc": ["tomografia de", "tc de", "tomografia computadorizada de"],
    "rx": ["radiografia de", "rx de", "raio x de"],
    "rm": ["ressonancia de", "rm de", "ressonancia magnetica de"],
    "angiotc": ["angiotomografia de", "angio de", "angio tc de"],
    "us": ["ultrassonografia de", "us de", "ultrassom de", "ecografia de"],
    "mamo": ["mamografia de", "mamografia"],
}
_TIRAR_EXAME = re.compile(
    r"^(?:angiotomografia computadorizada|angiotomografia|angiorressonancia magnetica|angiorressonancia|"
    r"angio tc|angio rm|angio|tomografia computadorizada|tomografia|tc|ressonancia magnetica|"
    r"ressonancia|rm|radiografia|raio x|rx|ultrassonografia|ultra sonografia|ultrassom|us|"
    r"ecografia|mamografia|densitometria ossea|densitometria|doppler colorido|doppler|"
    r"cintilografia|exame|estudo)\b\s*(?:(?:de|do|da|dos|das)\b\s*)?")
_TIRAR = re.compile(r"\b(?:sem e com contraste|com e sem contraste|sem contraste|com contraste|"
                    r"contrastad[ao]|com meio de contraste|endovenoso|iodado|normal|"
                    r"direit[oa]s?|esquerd[oa]s?|bilateral|bilaterais)\b")

def _regiao_e_complemento(titulo):
    n = normalizar(titulo)
    n = _TIRAR_EXAME.sub("", n).strip()
    n = _TIRAR.sub(" ", n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"^(?:de|do|da|dos|das)\s+", "", n)
    if " com " in (" " + n + " "):
        reg, comp = (" " + n + " ").split(" com ", 1)
        return reg.strip(), comp.strip()
    return n, ""

def _modalidade(titulo):
    try:
        import nuvem
        t = nuvem.tipo_exame(titulo)
    except Exception:
        t = ""
    return _MODS.get(t, "outros")

def comandos_automaticos(titulo, mod):
    reg, comp = _regiao_e_complemento(titulo)
    fim = (reg + (" com " + comp if comp else "")).strip()
    out = []
    for f in _FALA.get(mod, []):
        if f.endswith(" de") and not fim:
            continue
        out.append(normalizar((f + " " + fim).strip()))
    sem_lado = normalizar(_TIRAR.sub(" ", normalizar(titulo)))
    if sem_lado:
        out.append(sem_lado)
    vistos, res = set(), []
    for g in out:
        if g and len(g) >= 4 and g not in vistos:
            vistos.add(g)
            res.append(g)
    return res


# ---------- lado: nunca fixo ----------
_LADO_TIT = re.compile(r"\b(DIREITO|ESQUERDO|DIREITA|ESQUERDA)\b|\b(DIR|ESQ)\b\.?|\((D|E)\)", re.I)
# "à direita", "para a esquerda" (direção) ficam como estão; "mama esquerda" vira lacuna
_LADOS_CORPO = re.compile(r"(?<!à )(?<!para a )(?<!para )\b(direito|esquerdo|direita|esquerda)\b", re.I)
_FEMININOS = set("""mama mao perna coxa clavicula patela escapula axila orbita fossa face costela
articulacao regiao glandula parotida tibia fibula ulna falange hemiface hemipelve narina tuba
trompa suprarrenal adrenal carotida jugular femoral poplitea subclavia vertebral renal iliaca
cabeca coluna""".split())

def _feminino(anterior):
    return normalizar(anterior) in _FEMININOS

def _slot_lado(palavra, maiuscula, feminino):
    if maiuscula:
        return "{LADO_F|DIREITA/ESQUERDA}" if feminino else "{LADO|DIREITO/ESQUERDO}"
    return "{lado_f|direita/esquerda}" if feminino else "{lado|direito/esquerdo}"

def _lado_de(palavra):
    return "d" if palavra.lower().startswith(("d", "(d")) else "e"

def lado_em_lacuna(titulo, corpo):
    """Lado fixo vira lacuna que o ditado preenche; nunca fica um lado escrito.
    Título com lado (inclusive "DIR.", "(E)"): o título vira lacuna e, se o texto só
    cita esse mesmo lado, o texto também. Título sem lado: o lado do texto que vem
    logo depois da própria estrutura do título ("Joelho direito") vira lacuna.
    O que não der para trocar com segurança vira aviso para conferir."""
    avisos = []
    reg = set(normalizar(_regiao_e_complemento(titulo)[0]).split()) | set(normalizar(titulo).split())
    m_tit = _LADO_TIT.search(titulo)
    novo_tit = titulo
    if m_tit:
        def troca_tit(m):
            antes = titulo[:m.start()].split()
            fem = (m.group(1) or "").upper().endswith("A") or (
                not m.group(1) and bool(antes) and _feminino(antes[-1]))
            return _slot_lado(m.group(0), True, fem)
        novo_tit = _LADO_TIT.sub(troca_tit, titulo)
        avisos.append("lado do título virou lacuna (o ditado preenche)")
        if m_tit.group(2) or m_tit.group(3):
            avisos.append("título tinha o lado abreviado: confira o texto")
    ocorr = list(_LADOS_CORPO.finditer(corpo))
    lados = {_lado_de(m.group(1)) for m in ocorr}
    def slot_corpo(m):
        w = m.group(1)
        return _slot_lado(w, w.isupper(), w.lower().endswith("a"))
    if m_tit:
        if len(lados) == 1:
            corpo = _LADOS_CORPO.sub(slot_corpo, corpo)
            avisos.append("lado do texto virou lacuna")
        elif len(lados) == 2:
            avisos.append("o texto cita os dois lados: ficou como está — confira")
    elif ocorr:
        trocou, ficou = False, set()
        def talvez(m):
            nonlocal trocou
            antes = normalizar(corpo[max(0, m.start() - 40):m.start()]).split()
            if antes and antes[-1] in reg and len(lados) == 1:
                trocou = True
                return slot_corpo(m)
            ficou.add(m.group(1).lower())
            return m.group(0)
        corpo = _LADOS_CORPO.sub(talvez, corpo)
        if trocou:
            avisos.append("lado do texto virou lacuna")
        if ficou and len(lados) == 1:     # os dois lados descritos (rim direito e esquerdo) é normal
            avisos.append("o texto cita lado (%s) sem lado no título — confira" % ", ".join(sorted(ficou)))
    return novo_tit, corpo, avisos


# ---------- formato ----------
_CAB = re.compile(r"^\s*\**\s*([A-ZÀ-Ý][A-ZÀ-Ý /]{2,40}):\s*\**\s*(.*)$")

def negritar(titulo, corpo):
    """Título e cabeçalhos em CAIXA ALTA ("TÉCNICA:") entre ** — a colagem vira negrito."""
    linhas = []
    for l in corpo.split("\n"):
        m = _CAB.match(l)
        if m and m.group(1).upper() == m.group(1):
            resto = m.group(2).strip()
            linhas.append("**%s:**" % m.group(1).strip() + (("  " + resto) if resto else ""))
        else:
            linhas.append(l.rstrip())
    t = "\n".join(linhas).strip("\n")
    t = re.sub(r"\n{3,}", "\n\n", t)
    return "**%s**" % titulo.strip("* ").strip(), t


# ---------- config ----------
def _config(para_gravar=False):
    if not os.path.exists(CONFIG):
        return {}
    try:
        return json.load(open(CONFIG, encoding="utf-8-sig"))
    except Exception:
        if para_gravar:
            raise ValueError("config.json ilegível: corrija o arquivo antes (nada foi alterado)")
        return {}

def _gravar_config(c):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)

def fonte_atual():
    # LAUDO_FONTE existe para o teste de regressão poder compilar a base nas
    # três fontes sem mexer no config.json do médico.
    f = (os.environ.get("LAUDO_FONTE") or _config().get("fonte_mascaras") or "rotrix").lower()
    return f if f in FONTES else "rotrix"

def definir_fonte(f):
    f = (f or "").lower()
    if f not in FONTES:
        raise ValueError("fonte deve ser rotrix, minhas ou ambas")
    c = _config(para_gravar=True)
    c["fonte_mascaras"] = f
    _gravar_config(c)
    return f


def assinatura_usuario():
    """Resumo do que o usuário tem (fonte + arquivos). A base guarda esta assinatura:
    se mudar (atualização trocou a base, máscara nova), o roteador refaz a base ao subir."""
    f = fonte_atual()
    if f == "rotrix":
        return "rotrix|0|0|0"
    n = mt = tam = 0
    if os.path.isdir(PASTA_MASC):
        for raiz, _d, arqs in os.walk(PASTA_MASC):
            for a in arqs:
                if a.endswith(".txt"):
                    st = os.stat(os.path.join(raiz, a))
                    n += 1
                    mt = max(mt, int(st.st_mtime))
                    tam += st.st_size
    return "%s|%d|%d|%d" % (f, n, mt, tam)


def refazer_base():
    r = subprocess.run([sys.executable, os.path.join(AQUI, "construir_base.py")], cwd=AQUI,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300)
    linhas = (r.stdout or "").strip().splitlines()
    return r.returncode == 0, (linhas[0] if linhas else (r.stderr or "").strip()[-300:])


# ---------- comandos ----------
def _limpar_pasta(p, filtro=None):
    n = 0
    if not os.path.isdir(p):
        return 0
    for raiz, _d, arqs in os.walk(p, topdown=False):
        for a in arqs:
            if filtro is None or filtro(a):
                os.remove(os.path.join(raiz, a))
                n += 1
        if raiz != p and not os.listdir(raiz):
            os.rmdir(raiz)
    return n

def importar_mascaras(caminho, substituir=False):
    texto = ler_arquivo(caminho)
    blocos = separar(texto)
    res = {"acao": "mascaras", "arquivo": os.path.basename(caminho), "importadas": [],
           "recusadas": [], "avisos": []}
    if substituir:
        res["removidas_antes"] = _limpar_pasta(PASTA_MASC)
    ja = set()
    escritos = set()
    for i, b in enumerate(blocos, 1):
        linhas = b.split("\n")
        gat_user = []
        while linhas and (not linhas[0].strip() or _GATILHOS.match(linhas[0])):
            m = _GATILHOS.match(linhas.pop(0))
            if m:
                gat_user += [normalizar(g) for g in re.split(r"[|;]", m.group(1)) if normalizar(g)]
        if not linhas:
            continue
        titulo = _titulo_limpo(linhas[0])
        corpo = "\n".join(linhas[1:]).strip("\n")
        rotulo = titulo[:70] or ("máscara %d" % i)
        motivos = identificadores(b)
        if motivos:
            res["recusadas"].append({"titulo": rotulo, "motivo": "contém " + ", ".join(sorted(set(motivos)))})
            continue
        if len(corpo.strip()) < 20:
            res["recusadas"].append({"titulo": rotulo, "motivo": "sem texto de laudo abaixo do título"})
            continue
        mod = _modalidade(titulo)
        gat_auto = comandos_automaticos(titulo, mod)
        gatilhos = [g for g in gat_user + gat_auto if g not in ja]
        if not gatilhos:
            res["recusadas"].append({"titulo": rotulo, "motivo": "os comandos repetem os de outra máscara do arquivo"})
            continue
        ja.update(gatilhos)
        tit2, corpo2, av = lado_em_lacuna(titulo, corpo)
        tit_neg, corpo_neg = negritar(tit2, corpo2)
        reg, comp = _regiao_e_complemento(titulo)
        pasta = os.path.join(PASTA_MASC, mod, _slug(reg))
        os.makedirs(pasta, exist_ok=True)
        nome = ("normal" if not comp else "outra_" + _slug(comp, 30))
        arq = os.path.join(pasta, nome + ".txt")
        k = 2
        while arq in escritos or (os.path.exists(arq) and not substituir):
            arq = os.path.join(pasta, "%s_%d.txt" % (nome, k))
            k += 1
        escritos.add(arq)
        cab = ["# gatilhos: " + " | ".join(gatilhos),
               "# categoria: usuario",
               "# modalidade: " + mod,
               "# regiao: " + _slug(reg),
               "# tipo_mascara: " + ("normal" if not comp else "outra"),
               "# origem: " + os.path.basename(caminho)]
        open(arq, "w", encoding="utf-8").write("\n".join(cab) + "\n" + tit_neg + "\n\n" + corpo_neg + "\n")
        res["importadas"].append({"titulo": rotulo, "comandos": gatilhos[:4], "modalidade": mod,
                                  "arquivo": os.path.relpath(arq, DADOS).replace("\\", "/"),
                                  "avisos": av})
    if not blocos:
        res["avisos"].append("nenhuma máscara encontrada no arquivo")
    return res

def importar_laudos(caminho, substituir=False):
    texto = ler_arquivo(caminho)
    blocos = separar(texto)
    res = {"acao": "laudos", "arquivo": os.path.basename(caminho), "importados": 0,
           "recusados": [], "avisos": []}
    os.makedirs(PASTA_ESTILO, exist_ok=True)
    if substituir:
        res["removidos_antes"] = _limpar_pasta(PASTA_ESTILO, lambda a: a.startswith("usuario_"))
    existentes = [a for a in os.listdir(PASTA_ESTILO) if a.startswith("usuario_")]
    vagas = MAX_LAUDOS - len(existentes)
    for i, b in enumerate(blocos, 1):
        limpo = tirar_cabecalho_paciente(b).strip()
        rotulo = (_titulo_limpo(limpo.split("\n")[0]) if limpo else "")[:70] or ("laudo %d" % i)
        motivos = identificadores(limpo)
        if motivos:
            res["recusados"].append({"titulo": rotulo, "motivo": "contém " + ", ".join(sorted(set(motivos)))})
            continue
        if len(limpo) < 40:
            continue
        if vagas <= 0:
            res["avisos"].append("limite de %d laudos de estilo atingido; o resto não entrou" % MAX_LAUDOS)
            break
        h = hashlib.sha1(limpo.encode("utf-8")).hexdigest()[:10]
        arq = os.path.join(PASTA_ESTILO, "usuario_%s.txt" % h)
        if not os.path.exists(arq):
            open(arq, "w", encoding="utf-8").write(limpo + "\n")
            res["importados"] += 1
            vagas -= 1
    return res

def listar():
    masc = []
    if os.path.isdir(PASTA_MASC):
        for raiz, _d, arqs in os.walk(PASTA_MASC):
            for a in sorted(arqs):
                if not a.endswith(".txt"):
                    continue
                p = os.path.join(raiz, a)
                tit, gat = "", ""
                for l in open(p, encoding="utf-8"):
                    if l.startswith("# gatilhos:"):
                        gat = l.split(":", 1)[1].strip().split(" | ")[0]
                    elif l.strip() and not l.startswith("#"):
                        tit = l.strip().strip("*")
                        break
                tit = re.sub(r"\{(LADO|LADO_F|lado|lado_f)\|[^}]*\}", "[lado]", tit)
                masc.append({"titulo": tit, "comando": gat,
                             "arquivo": os.path.relpath(p, DADOS).replace("\\", "/")})
    laudos = 0
    if os.path.isdir(PASTA_ESTILO):
        laudos = len([a for a in os.listdir(PASTA_ESTILO) if a.startswith("usuario_")])
    return {"acao": "listar", "fonte": fonte_atual(), "mascaras": masc, "laudos": laudos}


def main(argv):
    como_json = "--json" in argv
    substituir = "--substituir" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    acao = args[0].lower()
    try:
        if acao == "mascaras" and len(args) >= 2:
            res = importar_mascaras(args[1], substituir)
            if res["importadas"] and fonte_atual() == "rotrix":
                definir_fonte("ambas")
                res["avisos"].append("fonte das máscaras passou para 'ambas' (as suas valem primeiro)")
            ok, msg = refazer_base()
            res["base"] = msg if ok else "ERRO ao refazer a base: " + msg
        elif acao == "laudos" and len(args) >= 2:
            res = importar_laudos(args[1], substituir)
        elif acao == "fonte" and len(args) >= 2:
            res = {"acao": "fonte", "fonte": definir_fonte(args[1])}
            ok, msg = refazer_base()
            res["base"] = msg if ok else "ERRO ao refazer a base: " + msg
        elif acao == "listar":
            res = listar()
        elif acao == "remover" and len(args) >= 2 and args[1] in ("mascaras", "laudos"):
            if args[1] == "mascaras":
                res = {"acao": "remover", "removidas": _limpar_pasta(PASTA_MASC)}
                if fonte_atual() != "rotrix":
                    definir_fonte("rotrix")          # sem máscara sua, "minhas" deixaria o banco vazio
                    res["fonte"] = "rotrix"
                ok, msg = refazer_base()
                res["base"] = msg if ok else "ERRO ao refazer a base: " + msg
            else:
                res = {"acao": "remover", "removidos": _limpar_pasta(PASTA_ESTILO, lambda a: a.startswith("usuario_"))}
        else:
            print(__doc__)
            return 2
        res["ok"] = True
    except Exception as e:
        res = {"ok": False, "erro": "%s: %s" % (type(e).__name__, e)}
    if como_json:
        sys.stdout.write(json.dumps(res, ensure_ascii=False))
    else:
        print(resumo_legivel(res))
    return 0 if res.get("ok") else 1


def resumo_legivel(res):
    """Saída para gente (o menu MINHAS_MASCARAS usa esta; o app usa --json)."""
    if not res.get("ok"):
        return "  [X] " + res.get("erro", "falhou")
    L = []
    a = res.get("acao")
    if a == "mascaras":
        L.append("  %d mascara(s) incluida(s) de %s" % (len(res["importadas"]), res.get("arquivo", "")))
        for m in res["importadas"]:
            L.append("   + %s  ->  diga \"%s\"" % (m["titulo"], (m.get("comandos") or ["?"])[0]))
            for av in m.get("avisos", []):
                L.append("       (%s)" % av)
        for m in res.get("recusadas", []):
            L.append("   - NAO ENTROU: %s — %s" % (m["titulo"], m["motivo"]))
    elif a == "laudos":
        L.append("  %d laudo(s) de estilo incluido(s) de %s" % (res.get("importados", 0), res.get("arquivo", "")))
        for m in res.get("recusados", []):
            L.append("   - NAO ENTROU: %s — %s" % (m["titulo"], m["motivo"]))
    elif a == "fonte":
        nomes = {"rotrix": "so as do Rotrix", "minhas": "so as suas", "ambas": "as duas (a sua vale primeiro)"}
        L.append("  mascaras que valem agora: " + nomes.get(res.get("fonte"), res.get("fonte", "")))
    elif a == "listar":
        nomes = {"rotrix": "so as do Rotrix", "minhas": "so as suas", "ambas": "as duas (a sua vale primeiro)"}
        L.append("  mascaras que valem: " + nomes.get(res.get("fonte"), ""))
        L.append("  %d mascara(s) sua(s):" % len(res.get("mascaras", [])))
        for m in res.get("mascaras", []):
            L.append("   . %s  ->  diga \"%s\"" % (m["titulo"], m.get("comando", "")))
        L.append("  %d laudo(s) de estilo seu(s)" % res.get("laudos", 0))
    elif a == "remover":
        L.append("  removido(s): %s" % (res.get("removidas", res.get("removidos", 0))))
        if res.get("fonte"):
            L.append("  mascaras que valem agora: so as do Rotrix")
    for av in res.get("avisos", []):
        L.append("  aviso: " + av)
    if res.get("base"):
        L.append("  " + res["base"])
    return "\n".join(L)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
