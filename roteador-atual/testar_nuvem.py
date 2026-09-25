# -*- coding: utf-8 -*-
"""Testa a rota de nuvem SEM internet e SEM chave de verdade (respostas simuladas).

Roda no GitHub a cada envio e pode rodar no PC: python testar_nuvem.py
Não mexe em gasto.json nem em nuvem.log da pasta (usa arquivos temporários).
"""
import io, json, os, sys, tempfile, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import nuvem, formato

tmp = tempfile.mkdtemp()
nuvem.GASTO = os.path.join(tmp, "gasto.json")
nuvem.LOG = os.path.join(tmp, "nuvem.log")
nuvem.AQUI = tmp                       # nenhum arquivo de chave real é lido
os.environ["ANTHROPIC_API_KEY"] = "teste-anthropic"
os.environ["OPENAI_API_KEY"] = "teste-openai"
for v in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "ROTRIX_API_KEY"):
    os.environ.pop(v, None)

ENVIADOS, RESP = [], {}

class _R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass

def _falso(req, timeout=None, context=None):
    corpo = json.loads(req.data.decode("utf-8"))
    ENVIADOS.append((req.full_url, dict(req.header_items()), corpo))
    return RESP["f"](req.full_url, corpo)
urllib.request.urlopen = _falso

def _anth(url, corpo):
    return _R(json.dumps({"content": [{"type": "text", "text": "LAUDO"}],
                          "usage": {"input_tokens": 1000, "output_tokens": 200}}).encode())

SAIDA_OK = ("RADIOGRAFIA DO TORNOZELO ESQUERDO\n\nANÁLISE:\nRelações articulares preservadas.\n"
            "Entesopatia calcificada plantar e posterior no calcâneo.\nDemais partes moles sem alterações.")
SAIDA_INVENTA = ("RADIOGRAFIA DO TORNOZELO ESQUERDO\n\nANÁLISE:\nEntesopatia calcificada plantar e "
                 "posterior no calcâneo, com esporão de 7 mm e edema no tornozelo direito.")

def _oai(texto):
    def f(url, corpo):
        return _R(json.dumps({"choices": [{"message": {"content": texto}}],
                              "usage": {"prompt_tokens": 2000, "completion_tokens": 100,
                                        "prompt_tokens_details": {"cached_tokens": 1500}}}).encode())
    return f

PEDIDO = ("LAUDO NA TELA:\nRADIOGRAFIA DO TORNOZELO ESQUERDO\nANÁLISE:\nRelações articulares "
          "preservadas.\nPartes moles sem alterações.\n"
          "entesopatia calcificada plantar e posterior no calcanho")

falhas = []
def confere(nome, cond, extra=""):
    print(("ok    " if cond else "FALHOU") + "  " + nome + (("  " + extra) if extra and not cond else ""))
    if not cond:
        falhas.append(nome)

base = dict(nuvem.PADRAO, ativa=True, modelo="claude-sonnet-5", limite_mes_usd=0)

# 1. sem rota por exame: Anthropic, como sempre
RESP["f"] = _anth
t, o = nuvem.chamar(PEDIDO, dict(base), modo="laudo", marcar=False, max_tokens=4000)
u, h, c = ENVIADOS[-1]
confere("padrão continua Anthropic", o == "nuvem" and u == nuvem.URL and c["model"] == "claude-sonnet-5")
confere("prompt de laudo (não o formatador)", "FORMATADOR" not in c["system"][0]["text"])

# 2. RX -> OpenAI Luna, só formatar
cfg = dict(base, ia_por_exame={"rx": {"provedor": "openai", "modelo": "gpt-5.6-luna", "modo": "formatar"},
                               "onco": "anthropic:claude-sonnet-5"})
RESP["f"] = _oai(SAIDA_OK)
t, o = nuvem.chamar(PEDIDO, cfg, modo="laudo", marcar=False, max_tokens=4000)
u, h, c = ENVIADOS[-1]
confere("RX vai para a OpenAI", u.startswith("https://api.openai.com/") and c["model"] == "gpt-5.6-luna")
confere("RX preso no modo formatar", "FORMATADOR" in c["messages"][0]["content"])
confere("modelo básico sem raciocínio", c.get("reasoning_effort") == "none")
confere("OpenAI usa max_completion_tokens", c.get("max_completion_tokens") == 4000)
confere("saída limpa não recebe aviso", o == "nuvem" and not t.startswith("[conferir"), t[:80])

# 3. trava de conferência
RESP["f"] = _oai(SAIDA_INVENTA)
t, o = nuvem.chamar(PEDIDO, cfg, modo="laudo", marcar=False)
l1 = t.splitlines()[0]
confere("trava aponta palavra, número e lado", l1.startswith("[conferir") and "esporão" in l1
        and "7" in l1 and "LADO" in l1 and "DIREITO" in l1, l1)

# 3b. trava: trocas perigosas que não podem passar
def trava(a, b):
    return nuvem.conferir(a, b)
confere("lado trocado junto da mesma estrutura", any("LADO" in x for x in
        trava("nódulo no lobo inferior direito", "Nódulo no lobo inferior esquerdo.")))
confere("lacuna de lado preenchida pela IA", any("lacuna" in x for x in
        trava("RADIOGRAFIA DO JOELHO [DIREITO/ESQUERDO]", "RADIOGRAFIA DO JOELHO DIREITO")))
confere("negação acrescentada", any("negação" in x for x in trava("Há derrame pleural.", "Não há derrame pleural.")))
confere("unidade trocada (mm -> cm)", any("medida" in x for x in trava("nódulo de 5 mm", "Nódulo de 5 cm.")))
confere("oposto: hipo -> hiper", any("TROCA" in x for x in trava("área hipoatenuante", "Área hiperatenuante.")))
confere("oposto: normal -> anormal", any("TROCA" in x for x in trava("exame normal", "Exame anormal.")))
confere("linha entre colchetes inventada é conferida", any("12" in x for x in
        trava("Fígado normal.", "Fígado normal.\n[Achado adicional: nódulo de 12 mm]")))
confere("negação removida (não há derrame -> há derrame)", any("NEGAÇÃO REMOVIDA" in x for x in
        trava("Seios costofrênicos livres. Não há derrame pleural.", "Seios costofrênicos livres. Há derrame pleural.")))
confere("achado ditado substitui a frase negada da máscara sem aviso",
        trava("Não há derrame pleural.\nderrame pleural à direita", "Derrame pleural à direita.") == [])
confere("sigla acrescentada (AVC)", any("avc" in x for x in trava("isquemia na acm esquerda", "AVC na ACM esquerda.")))
confere("correção de voz não dispara a trava",
        trava("antiromas falsificados na horta; tem dinopatia do supra espinhal",
              "Ateromas calcificados na aorta; tendinopatia do supraespinhal.") == [])
confere("repetir o achado na conclusão não dispara a trava",
        trava("LAUDO NA TELA:\nTC DE TÓRAX\nnódulo no lobo superior direito",
              "TOMOGRAFIA COMPUTADORIZADA DE TÓRAX\nNódulo no lobo superior direito.\nCONCLUSÃO:\nNódulo no lobo superior direito.") == [])
p = formato.padronizar(t)
confere("aviso fica numa linha própria depois de padronizar", p.splitlines()[0] == l1, p[:120])

# 4. oncológico -> Anthropic, análise livre
RESP["f"] = _anth
r = nuvem.rota("TOMOGRAFIA DE TÓRAX\navaliação RECIST 1.1", cfg, "analise")
confere("RECIST vai para a regra onco", r["regra"] == "onco" and r["modo"] == "analise"
        and r["provedor"] == "anthropic", str(r))

# 5. tipo de exame pelo que aparece primeiro
confere("marca da IA (US$) não vira ultrassom",
        nuvem.tipo_exame("[[ análise assistida ]]  (US$ 0,01)\nRADIOGRAFIA DO JOELHO") == "rx")
confere("instrução antes do laudo não muda o tipo",
        nuvem.tipo_exame("INSTRUÇÃO FALADA: compare com a tomografia\n\nLAUDO NA TELA:\nRADIOGRAFIA DO TÓRAX") == "rx")
confere("RM com comparação de TC continua RM",
        nuvem.tipo_exame("RESSONÂNCIA DO JOELHO\nCOMPARAÇÃO: tomografia prévia") == "rm")
confere("ditado curto 'rx de joelho'", nuvem.tipo_exame("rx de joelho direito") == "rx")

# 6. erros e bloqueios
confere("identificador bloqueia", nuvem.chamar("rx de joelho cpf 123.456.789-00", cfg)[1] == "nuvem_bloqueada")
cfg2 = dict(base, ia_por_exame={"rx": "gemini:gemini-flash"})
confere("provedor sem chave não envia", nuvem.chamar("rx de joelho", cfg2)[1] == "nuvem_sem_chave")
cfg3 = dict(base, ia_por_exame={"rx": {"provedor": "openai"}})
confere("troca de provedor sem modelo não envia", nuvem.chamar("rx de joelho", cfg3)[1] == "nuvem_sem_modelo")
def _401(url, corpo):
    raise urllib.error.HTTPError(url, 401, "x", {}, io.BytesIO(b'{"error":"chave"}'))
RESP["f"] = _401
confere("erro HTTP devolve None", nuvem.chamar(PEDIDO, cfg, modo="laudo")[0] is None)

# 7. gasto por modelo e estado sem chave
g = nuvem.gasto_ler()
confere("gasto separado por modelo", "openai:gpt-5.6-luna" in g.get("por_modelo", {})
        and "claude-sonnet-5" in g.get("por_modelo", {}))
confere("estado nunca mostra chave", "teste-" not in json.dumps(nuvem.estado()))
confere("preço Luna", nuvem.preco("gpt-5.6-luna") == (0.20, 1.20))

# 7b. chave salva pelo PowerShell (UTF-16), exemplo de estilo com identificador, preço desconhecido
open(os.path.join(tmp, "chave_gemini.txt"), "wb").write("chave-gemini-teste\r\n".encode("utf-16"))
confere("chave em UTF-16 (PowerShell) é lida", nuvem.chave_de(base, "gemini") == "chave-gemini-teste")
os.makedirs(os.path.join(tmp, "dados", "estilo"), exist_ok=True)
open(os.path.join(tmp, "dados", "estilo", "a.txt"), "w", encoding="utf-8").write("TC DO CRÂNIO\nPaciente: Fulano\nnormal")
open(os.path.join(tmp, "dados", "estilo", "b.txt"), "w", encoding="cp1252").write("RADIOGRAFIA DO TÓRAX\nCampos pulmonares livres.")
ex = nuvem._exemplos_estilo()
confere("exemplo de estilo com identificador não vai", "Fulano" not in ex and "Campos pulmonares" in ex)
confere("modelo sem preço conta como caro (teto vale)", nuvem.custo("modelo-novo", 1000000, 0) > 0)
def _vazia(url, corpo):
    return _R(json.dumps({"content": [], "usage": {"input_tokens": 1000, "output_tokens": 0}}).encode())
RESP["f"] = _vazia
antes = nuvem.gasto_ler()["chamadas"]
confere("resposta vazia também entra no gasto",
        nuvem.chamar(PEDIDO, dict(base), modo="laudo")[1] == "nuvem_vazia" and nuvem.gasto_ler()["chamadas"] == antes + 1)

# 8. "formar laudo com IA": monta com o banco e manda o laudo montado para a rota do exame
try:
    import roteador
except Exception as e:
    roteador = None
    print("aviso   roteador não carregou (%s): parte 8 pulada" % type(e).__name__)
if roteador is not None and not roteador.BANCO.itens:   # sem base.sqlite
    roteador = None
    print("aviso   sem base.sqlite (rode construir_base.py): parte 8 pulada")
if roteador is not None:
    cfg_rx = dict(cfg)
    nuvem.config = lambda: dict(cfg_rx)
    RESP["f"] = _oai(SAIDA_OK)
    antes = len(ENVIADOS)
    t, o = roteador.rotear("rx de tornozelo esquerdo com entesopatia calcificada plantar e posterior "
                           "no calcanho. Formar laudo com IA.")
    enviado = ENVIADOS[-1][2]["messages"][1]["content"] if len(ENVIADOS) > antes else ""
    confere("formar laudo com IA usa a rota do exame (RX na Luna)",
            o == "nuvem_formar" and len(ENVIADOS) == antes + 1
            and ENVIADOS[-1][2]["model"] == "gpt-5.6-luna", o)
    confere("vai o laudo montado, sem **", enviado.startswith("LAUDO NA TELA:\n") and "**" not in enviado
            and "TÉCNICA" in enviado)
    RESP["f"] = _401
    t, o = roteador.rotear("rx de joelho direito com artrose medial, formar laudo com IA")
    confere("IA falhou: devolve o laudo local", o.startswith("nuvem_indisponivel_local")
            and "JOELHO DIREITO" in t, o)
    antes = len(ENVIADOS)
    t, o = roteador.rotear("rx de joelho direito com artrose medial, formar laudo")
    confere("formar laudo sem IA não chama a nuvem", len(ENVIADOS) == antes and o.startswith("formar:"), o)

# ---------------------------------------------------------------------------
# A chave da TELA manda; a variável de ambiente é o reserva.
# O caso real: quem tem ANTHROPIC_API_KEY no Windows gravava a chave nova pela
# tela, via "configurada" em verde, e o roteador seguia com a velha. A ordem
# estava invertida — a variável vinha antes do arquivo.
# ---------------------------------------------------------------------------
print()
_var = "ROTRIX_TESTE_CHAVE"
os.environ[_var] = "chave-da-variavel"
_c = dict(nuvem.PADRAO)
_c["provedores"] = {"compativel": {"arquivo_da_chave": "k.txt",
                                   "variavel_de_ambiente": _var,
                                   "url": "https://exemplo.invalido/v1/chat/completions"}}
_arq = os.path.join(nuvem.AQUI, "k.txt")

_k, _o = nuvem.chave_e_origem(_c, "compativel")
confere("sem arquivo, vale a variável de ambiente",
        _k == "chave-da-variavel" and _o.startswith("variavel:"), "%r %r" % (_k, _o))

io.open(_arq, "w", encoding="utf-8").write("chave-da-tela\n")
_k, _o = nuvem.chave_e_origem(_c, "compativel")
confere("a chave gravada pela tela vence a variável de ambiente",
        _k == "chave-da-tela" and _o.startswith("arquivo:"), "%r %r" % (_k, _o))

io.open(_arq, "w", encoding="utf-8").write("   \n")
_k, _o = nuvem.chave_e_origem(_c, "compativel")
confere("arquivo vazio não derruba a chave: cai na variável",
        _k == "chave-da-variavel", repr(_k))
os.remove(_arq)
os.environ.pop(_var, None)

confere("o estado da IA nunca devolve a chave",
        "teste-anthropic" not in json.dumps(nuvem.estado(), ensure_ascii=False))
confere("o estado diz de onde a chave veio", "origem_da_chave" in nuvem.estado())

# provedor pelo prefixo: é o que tira o nome do fabricante da tela
_pref = [("sk-ant-abc", "anthropic"), ("sk-or-abc", "openrouter"), ("AIzaSyABC", "gemini"),
         ("sk-proj-abc", "openai"), ("sk-abc", "openai"), ("xyz", "")]
confere("provedor detectado pelo prefixo da chave",
        all(nuvem.provedor_da_chave(k) == e for k, e in _pref),
        str([(k, nuvem.provedor_da_chave(k)) for k, e in _pref if nuvem.provedor_da_chave(k) != e]))

# a lista de modelos sai da URL do próprio provedor, sem tabela no código
_urls = [("anthropic", "https://api.anthropic.com/v1/models"),
         ("openai", "https://api.openai.com/v1/models"),
         ("openrouter", "https://openrouter.ai/api/v1/models")]
confere("URL da lista de modelos derivada do provedor",
        all(nuvem._url_de_modelos(nuvem.provedor_cfg(nuvem.PADRAO, p)) == u for p, u in _urls))

_sem = nuvem.modelos(dict(nuvem.PADRAO, provedores={"openai": {"variavel_de_ambiente": "NAO_EXISTE_X"}}),
                     "openai")
confere("sem chave, a lista de modelos nem sai para a rede",
        not _sem.get("ok") and _sem.get("motivo") == "sem_chave" and not _sem.get("modelos"),
        repr(_sem.get("motivo")))

# gravar_config junta em vez de sobrescrever, e nunca grava chave
_guarda_cfg = nuvem.CONFIG
nuvem.CONFIG = os.path.join(tmp, "nuvem_teste.json")
io.open(nuvem.CONFIG, "w", encoding="utf-8").write('{"provedor": "openai", "modelo": "x"}')
nuvem.gravar_config({"modelos_vistos": {"openai": [{"id": "m", "nome": "m"}]}, "chave": "SEGREDO"})
_lido = json.loads(io.open(nuvem.CONFIG, encoding="utf-8").read())
confere("gravar_config junta e não apaga o que já estava",
        _lido.get("provedor") == "openai" and "modelos_vistos" in _lido, repr(sorted(_lido)))
confere("gravar_config nunca grava chave", "chave" not in _lido)
os.remove(nuvem.CONFIG)
nuvem.CONFIG = _guarda_cfg


# ---------------------------------------------------------------- economia
# Ele gastou US$ 10 em cinco dias. Conserto de texto, formatacao e palavra mal
# ouvida vao no modelo BARATO; comparativo e reorganizacao por importancia
# clinica pagam o forte. Na duvida, BARATO: laudo economico errado ele percebe
# na hora, laudo caro por precaucao so aparece na fatura.
_cache_ant = None
if os.path.exists(nuvem.CACHE_MODELOS):
    _cache_ant = io.open(nuvem.CACHE_MODELOS, encoding="utf-8").read()
os.makedirs(os.path.dirname(nuvem.CACHE_MODELOS), exist_ok=True)
io.open(nuvem.CACHE_MODELOS, "w", encoding="utf-8", newline="\n").write(json.dumps(
    {"provedor": "anthropic", "modelos": ["claude-opus-5-20260814",
     "claude-sonnet-5-20260514", "claude-haiku-4-5-20251001"]}))
_ce = dict(nuvem.config())
_ce["modelo"], _ce["provedor"], _ce["ia_por_exame"] = "claude-opus-5-20260814", "anthropic", {}

confere("economia: escolhe o mais barato da lista REAL do provedor",
        nuvem.modelo_barato(_ce) == "claude-haiku-4-5-20251001", nuvem.modelo_barato(_ce))
for _p in ("corrige a ortografia disso", "formata esse texto",
           "incluir nodulo de 5 mm no lobo superior direito",
           "acrescentar derrame pleural a direita"):
    confere("economia: %r vai no barato" % _p[:28],
            nuvem.rota(_p, _ce, "laudo")["regra"] == "economia",
            nuvem.rota(_p, _ce, "laudo")["modelo"])
for _p in ("compare com o exame de marco e diga o que mudou", "compare com o de marco",
           "reorganizar por importancia clinica", "refinar a analise",
           "estavel em relacao ao estudo anterior"):
    confere("economia: %r paga o forte" % _p[:28],
            nuvem.rota(_p, _ce, "laudo")["regra"] != "economia")

os.remove(nuvem.CACHE_MODELOS)
confere("economia: sem a lista do provedor nao inventa modelo", nuvem.modelo_barato(_ce) == "")
confere("economia: sem a lista nao troca o modelo",
        nuvem.rota("corrige isso", _ce, "revisao")["regra"] != "economia")

confere("economia: conserto curto pede saida pequena", nuvem.teto_saida("corrige isso", _ce) <= 400)
confere("economia: teto de saida respeita max_tokens",
        nuvem.teto_saida("x" * 20000, _ce) <= int(_ce.get("max_tokens", 1500) or 1500))
confere("economia: prompt barato e menor que o forte",
        len(nuvem.SISTEMA_BARATO) < len(nuvem.SISTEMA_LAUDO))
confere("economia: SEM_LACUNAS protege o lado", "LADO nunca sai" in nuvem.SEM_LACUNAS)
confere("economia: SEM_LACUNAS proibe a lacuna", "___" in nuvem.SEM_LACUNAS)

if _cache_ant is not None:
    io.open(nuvem.CACHE_MODELOS, "w", encoding="utf-8", newline="\n").write(_cache_ant)


print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), ", ".join(falhas)))
    sys.exit(1)
print("rota de nuvem: tudo certo")
