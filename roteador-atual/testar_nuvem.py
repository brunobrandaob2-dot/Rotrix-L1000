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

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), ", ".join(falhas)))
    sys.exit(1)
print("rota de nuvem: tudo certo")
