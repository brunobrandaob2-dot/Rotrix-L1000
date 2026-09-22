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
        and "7" in l1 and "LADO DIREITO" in l1, l1)
p = formato.padronizar(t)
confere("aviso fica numa linha própria depois de padronizar", p.splitlines()[0] == l1, p[:120])

# 4. oncológico -> Anthropic, análise livre
RESP["f"] = _anth
r = nuvem.rota("TOMOGRAFIA DE TÓRAX\navaliação RECIST 1.1", cfg, "analise")
confere("RECIST vai para a regra onco", r["regra"] == "onco" and r["modo"] == "analise"
        and r["provedor"] == "anthropic", str(r))

# 5. tipo de exame pelo que aparece primeiro
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

print()
if falhas:
    print("%d FALHA(S): %s" % (len(falhas), ", ".join(falhas)))
    sys.exit(1)
print("rota de nuvem: tudo certo")
