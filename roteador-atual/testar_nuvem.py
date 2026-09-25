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
# Prova de que a rota LAUDO manda as regras de laudo inteiro. Antes isto olhava a palavra
# "FORMATADOR" na string escrita à mão; agora o prompt vem por bloco do
# REDATOR_ROTRIX.md, então a prova é a REGRA que só existe no caminho de laudo inteiro.
confere("prompt de laudo traz as regras de laudo inteiro",
        "MODO LAUDO INTEIRO" in c["system"][0]["text"]
        and "ORDEM POR IMPORTÂNCIA CLÍNICA" in c["system"][0]["text"])

# 2. RX -> OpenAI Luna, só formatar
cfg = dict(base, ia_por_exame={"rx": {"provedor": "openai", "modelo": "gpt-5.6-luna", "modo": "formatar"},
                               "onco": "anthropic:claude-sonnet-5"})
RESP["f"] = _oai(SAIDA_OK)
t, o = nuvem.chamar(PEDIDO, cfg, modo="laudo", marcar=False, max_tokens=4000)
u, h, c = ENVIADOS[-1]
confere("RX vai para a OpenAI", u.startswith("https://api.openai.com/") and c["model"] == "gpt-5.6-luna")
_sis_rx = c["messages"][0]["content"]
confere("RX preso no modo formatar",
        "MODO LAUDO INTEIRO" not in _sis_rx and "NÃO faça: título" in _sis_rx)
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


# ---------------------------------------------------------------------------
# 10. AUDITORIA DE CUSTO (25/09) — preço, cache e prompt por bloco
# ---------------------------------------------------------------------------
import prompts

# 10a. preço: "claude-opus" pegava o Opus 5.5 e cobrava 25% a mais
confere("preço: Opus 5.5 é 4/20, não 5/25",
        nuvem.preco("claude-opus-5-5-20260815") == (4.0, 20.0))
confere("preço: Opus 5 continua 5/25", nuvem.preco("claude-opus-5-20260101") == (5.0, 25.0))
confere("preço: Sonnet 5 é 2/10", nuvem.preco("claude-sonnet-5-20260201") == (2.0, 10.0))
confere("preço: Haiku 4.5 é 1/5", nuvem.preco("claude-haiku-4-5-20251001") == (1.0, 5.0))
confere("preço: prefixo mais longo vence o mais curto",
        nuvem.preco("claude-sonnet-5-x") != nuvem.preco("claude-sonnet-4-x"))

# 10b. leitura de cache não é 10% para todo mundo
confere("cache: Opus 5.5 lê a 5%", nuvem.mult_leitura_cache("claude-opus-5-5-x") == 0.05)
confere("cache: Fable 5.1 lê a 2,5%", nuvem.mult_leitura_cache("claude-fable-5-1-x") == 0.025)
confere("cache: Haiku lê a 10%", nuvem.mult_leitura_cache("claude-haiku-4-5-x") == 0.10)

# 10c. custo() cobra escrita e leitura de cache com o multiplicador do MODELO
_c_opus = nuvem.custo("claude-opus-5-5-x", 0, 0, cache_r=1_000_000)
confere("custo: 1M de leitura de cache no Opus 5.5 = 4,00 x 0,05", abs(_c_opus - 0.20) < 1e-9,
        "deu %.4f" % _c_opus)
_c_w5 = nuvem.custo("claude-haiku-4-5-x", 0, 0, cache_w=1_000_000, ttl="5m")
_c_w1 = nuvem.custo("claude-haiku-4-5-x", 0, 0, cache_w=1_000_000, ttl="1h")
confere("custo: escrita de 5 min é 1,25x", abs(_c_w5 - 1.25) < 1e-9, "deu %.4f" % _c_w5)
confere("custo: escrita de 1 hora é 2,0x", abs(_c_w1 - 2.00) < 1e-9, "deu %.4f" % _c_w1)

# 10d. piso de tamanho: abaixo dele a Anthropic ignora cache_control em silêncio
confere("cache: piso do Haiku é 4.096", nuvem.min_cache("claude-haiku-4-5-x") == 4096)
confere("cache: piso do Opus é 512", nuvem.min_cache("claude-opus-5-5-x") == 512)
confere("cache: prompt curto no Haiku não marca cache (senão paga 1,25x por nada)",
        nuvem.cache_de("x" * 5000, "claude-haiku-4-5-x", {}) is None)
confere("cache: prompt do caminho forte no Opus marca cache",
        nuvem.cache_de("x" * 12000, "claude-opus-5-5-x", {}) == "5m")
confere("cache: 'off' no config desliga", nuvem.cache_de("x" * 12000, "claude-opus-5-5-x",
                                                         {"cache": "off"}) is None)
confere("cache: por chamada, 1h só ganha com releitura",
        nuvem.gasto_por_chamada(0, "1h") > 1.0 and nuvem.gasto_por_chamada(9, "1h") < 1.0)
confere("cache: sem releitura nenhuma, escrever cache é prejuízo",
        nuvem.gasto_por_chamada(0, "5m") > nuvem.gasto_por_chamada(0, None))

# 10e. o corpo que vai para a API reflete a decisão de cache
RESP["f"] = _anth
nuvem.chamar(PEDIDO, dict(base, modelo="claude-haiku-4-5-20251001", limite_mes_usd=0),
             modo="revisao", marcar=False)
_u, _h, _corpo = ENVIADOS[-1]
confere("cache: caminho barato não pede cache no corpo da chamada",
        "cache_control" not in _corpo["system"][0])
nuvem.chamar(PEDIDO, dict(base, modelo="claude-opus-5-5-20260815", limite_mes_usd=0),
             modo="laudo", marcar=False)
_u, _h, _corpo = ENVIADOS[-1]
confere("cache: caminho forte no Opus pede cache no corpo da chamada",
        "cache_control" in _corpo["system"][0])

# 10f. prompt por bloco, vindo do REDATOR_ROTRIX.md
_ok_p, _probs_p = prompts.conferir()
confere("prompt: REDATOR_ROTRIX.md monta todas as rotas", _ok_p, "; ".join(_probs_p))
_p_bar = prompts.montar("revisao") or ""
_p_for = prompts.montar("laudo") or ""
_p_cmp = prompts.montar("analise") or ""
confere("prompt: caminho barato não traz as regras de laudo inteiro",
        "MODO LAUDO INTEIRO" not in _p_bar and "MODO LAUDO INTEIRO" in _p_for)
confere("prompt: caminho barato é menor que o forte", len(_p_bar) < len(_p_for))
confere("prompt: comparativo traz a regra da data e não a lista de erro de voz",
        "NUNCA chute data" in _p_cmp and "castrofrênicos" not in _p_cmp)
confere("prompt: a regra do lado está em toda rota",
        all("LADO nunca sai" in (prompts.montar(m) or "") for m in prompts.RECEITAS))
confere("prompt: a documentação do arquivo nunca vai para a nuvem",
        all("O que mudou em relação ao prompt original" not in (prompts.montar(m) or "")
            for m in prompts.RECEITAS))
confere("prompt: arquivo ilegível devolve None (o nuvem.py cai na reserva)",
        prompts.montar("laudo", os.devnull) is None)
# arquivo de verdade, com UM bloco a menos: não pode montar laudo sem a regra que falta
_md_furado = os.path.join(tmp, "furado.md")
_corpo_md = io.open(prompts.ARQUIVO, encoding="utf-8").read()
io.open(_md_furado, "w", encoding="utf-8").write(
    _corpo_md.replace("<!-- BLOCO: SEM_LACUNAS -->", "<!-- nao_e_bloco -->"))
confere("prompt: bloco que falta derruba a rota (não monta prompt pela metade)",
        prompts.montar("laudo", _md_furado) is None
        and prompts.montar("revisao", _md_furado) is None)

# 10g. teto dos exemplos de estilo (era 24.000 chars = ~4.400 tokens por chamada forte)
confere("estilo: teto padrão é 6.000 caracteres", nuvem.TETO_EXEMPLOS == 6000)
confere("estilo: teto 0 no config desliga os exemplos",
        nuvem._exemplos_estilo({"teto_exemplos_chars": 0}) == "")

# 10h. a decisão de cache sai do log DELE, não de chute
_logtmp = os.path.join(tmp, "log_cache.tsv")
with io.open(_logtmp, "w", encoding="utf-8") as _f:
    for _i in range(30):                       # uma chamada por minuto: encadeado
        _f.write("2026-09-25T10:%02d:00\tm\tok\tin=1\tout=1\tusd=0\tmes=0\n" % _i)
_k5 = nuvem.releituras_por_escrita(5 * 60, _logtmp)
_k60 = nuvem.releituras_por_escrita(60 * 60, _logtmp)
confere("cache: log encadeado dá releitura em 5 min", _k5 is not None and _k5 >= 4,
        "k5=%s" % _k5)
confere("cache: log encadeado dá muito mais releitura em 1 hora", _k60 > _k5,
        "k60=%s k5=%s" % (_k60, _k5))
with io.open(_logtmp, "w", encoding="utf-8") as _f:
    for _i in range(30):                       # uma chamada a cada 20 min: esparso
        _f.write("2026-09-25T%02d:%02d:00\tm\tok\tin=1\tout=1\tusd=0\tmes=0\n"
                 % (8 + (_i * 20) // 60, (_i * 20) % 60))
confere("cache: log esparso não tem releitura em 5 min",
        nuvem.releituras_por_escrita(5 * 60, _logtmp) == 0.0)
confere("cache: log curto não decide por estatística",
        nuvem.releituras_por_escrita(300, os.devnull) is None)

# 10i. trocas fixas de voz: saíram do prompt (token pago) para a tabela local (de graça)
try:
    import roteador as _rot
except Exception as _e:
    print("aviso   roteador não carregou (%s): parte 10i pulada" % type(_e).__name__)
    _rot = None
if _rot is not None:
    _pares = [("canola em topografia", "cânula"),
              ("seios castrofrenicos obliterados", "costofrênicos"),
              ("complexos osseo-metais permeaveis", "ostiomeatais"),
              ("celulas etimoidais", "etmoidais"),
              ("comixa media boliosa", "concha média bolhosa"),
              ("hemi torax direito", "hemitórax"),
              ("linfo nodo de 8 mm", "linfonodo"),
              ("parenquima pulmonar", "parênquima"),
              ("lesao in caracteristica", "incaracterística"),
              ("seio maxelar direito", "maxilar"),
              ("de essencia da lamina papiracea", "deiscência")]
    _ruins = [d for d, esp in _pares if esp not in _rot.ouvido_fixo(d)]
    confere("voz: as trocas fixas são consertadas localmente, sem pagar token",
            not _ruins, "não consertou: " + "; ".join(_ruins))
    confere("voz: regra de duas palavras casa com hífen também",
            "ostiomeatais" in _rot.ouvido_fixo("complexos osseo-metais")
            and "ostiomeatais" in _rot.ouvido_fixo("complexos osseo metais"))
    confere("voz: o prompt não repete a tabela local",
            "castrofrênicos → seios costofrênicos" not in (prompts.montar("revisao") or ""))


print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), ", ".join(falhas)))
    sys.exit(1)
print("rota de nuvem: tudo certo")
