# -*- coding: utf-8 -*-
"""Rota de nuvem do Roteador de Laudos.

Só é acionada por gatilho explícito. Nunca automática.
Antes de enviar, higieniza o texto e bloqueia se encontrar identificador.

Provedores: Anthropic (padrão) e qualquer API no formato OpenAI
(openai, gemini, openrouter, ollama local, ou "compativel" com URL própria).
Rota por exame (config.json -> ia_por_exame): cada tipo de exame pode ir para
um provedor/modelo diferente e ficar preso ao modo "formatar" (o modelo só
organiza, delimita e corrige; não descreve nem raciocina), com a trava de
conferência que aponta toda palavra de conteúdo que a IA acrescentou.
Sem ia_por_exame, o comportamento é o de sempre.
"""
import json, os, re, ssl, urllib.request, urllib.error, datetime, difflib, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")
LOG = os.path.join(AQUI, "nuvem.log")
GASTO = os.path.join(AQUI, "gasto.json")
URL = "https://api.anthropic.com/v1/messages"

# Provedores conhecidos. Tudo aqui pode ser trocado em config.json -> "provedores".
# A chave nunca vai no config: fica no arquivo indicado (na pasta do roteador)
# ou na variável de ambiente.
PROVEDORES = {
    "anthropic":  {"formato": "anthropic", "url": URL,
                   "arquivo_da_chave": "chave_anthropic.txt",
                   "variavel_de_ambiente": "ANTHROPIC_API_KEY"},
    "openai":     {"formato": "openai",
                   "url": "https://api.openai.com/v1/chat/completions",
                   "arquivo_da_chave": "chave_openai.txt",
                   "variavel_de_ambiente": "OPENAI_API_KEY"},
    "gemini":     {"formato": "openai",
                   "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   "arquivo_da_chave": "chave_gemini.txt",
                   "variavel_de_ambiente": "GEMINI_API_KEY"},
    "openrouter": {"formato": "openai",
                   "url": "https://openrouter.ai/api/v1/chat/completions",
                   "arquivo_da_chave": "chave_openrouter.txt",
                   "variavel_de_ambiente": "OPENROUTER_API_KEY"},
    "ollama":     {"formato": "openai",
                   "url": "http://127.0.0.1:11434/v1/chat/completions",
                   "arquivo_da_chave": "", "variavel_de_ambiente": "",
                   "sem_chave": True},
    "compativel": {"formato": "openai", "url": "",
                   "arquivo_da_chave": "chave_compativel.txt",
                   "variavel_de_ambiente": "ROTRIX_API_KEY"},
}

PADRAO = {
    "ativa": False,
    "provedor": "anthropic",
    "modelo": "",
    "arquivo_da_chave": "chave_anthropic.txt",
    "variavel_de_ambiente": "ANTHROPIC_API_KEY",
    "timeout_s": 40,
    "max_tokens": 1500,
    "limite_mes_usd": 10.0,
    "marcar_saida": True,
    "marca_inicio": "[[ análise assistida — revisar antes de assinar ]]",
    "marca_fim": "",
    "gatilhos": ["analise avancada", "analise", "analisar", "comparar exames",
                 "recist", "resposta de tratamento", "medir resposta"],
    "gatilhos_revisao": ["revisar", "revisao", "corrigir", "revisar laudo",
                         "corrigir texto", "revisar texto", "passar a limpo"],
    # rota por exame (vazio = tudo vai para provedor/modelo acima, como sempre).
    # Ex.: {"rx": {"provedor": "openai", "modelo": "gpt-5.6-luna", "modo": "formatar"},
    #       "onco": "anthropic:claude-sonnet-5"}
    # Tipos: rx, tc, rm, angio, onco (RECIST/oncológico), padrao (o resto).
    "ia_por_exame": {},
    "modos_com_trava": ["formatar"],   # modos em que a trava de conferência roda
    "precos": {},                      # correções de preço: {"prefixo-do-modelo": [entrada, saida]}
    "provedores": {},                  # correções de URL/arquivo de chave por provedor
}

# ---------- preços (USD por milhão de tokens) ----------
# Anthropic: platform.claude.com/docs/en/about-claude/pricing (set/2026).
# OpenAI GPT-5.6: Luna conferido na página oficial do modelo (0,20 / 1,20);
# Sol e Terra por fonte secundária (set/2026) — conferir e, se mudar, corrigir
# em config.json -> "precos", sem mexer no código.
# Leitura de cache: Anthropic 10% (+25% na escrita); OpenAI 10%.
PRECOS = [
    ("claude-fable",    10.0, 50.0),
    ("claude-mythos",   10.0, 50.0),
    ("claude-opus",      5.0, 25.0),
    ("claude-sonnet-5",  2.0, 10.0),
    ("claude-sonnet",    3.0, 15.0),
    ("claude-haiku",     1.0,  5.0),
    ("gpt-5.6-sol",      5.0, 30.0),
    ("gpt-5.6-terra",    2.0, 12.0),
    ("gpt-5.6-luna",     0.20, 1.20),
    # Gemini 3.8 Flash: preço de lançamento até 31/12/2026 (depois 1,50 / 7,50)
    ("gemini-3.8-flash", 0.75, 3.75),
]

def preco(modelo, c=None):
    """(usd_por_milhao_entrada, usd_por_milhao_saida). (0,0) se desconhecido."""
    m = (modelo or "").lower()
    if ":" in m:                                   # "openai:gpt-5.6-luna"
        m = m.split(":", 1)[1]
    extras = (c or {}).get("precos") or {}
    if isinstance(extras, dict):
        for prefixo in sorted(extras, key=len, reverse=True):
            v = extras[prefixo]
            if m.startswith(str(prefixo).lower()) and isinstance(v, (list, tuple)) and len(v) == 2:
                try:
                    return float(v[0]), float(v[1])
                except (TypeError, ValueError):
                    pass
    for prefixo, pin, pout in PRECOS:
        if m.startswith(prefixo):
            return pin, pout
    return 0.0, 0.0

def custo(modelo, n_in, n_out, c=None):
    pin, pout = preco(modelo, c)
    return (n_in / 1_000_000.0) * pin + (n_out / 1_000_000.0) * pout

# ---------- acumulador de gasto do mês ----------
def _mes():
    return datetime.date.today().strftime("%Y-%m")

def gasto_ler():
    base = {"mes": _mes(), "usd": 0.0, "chamadas": 0, "tokens_in": 0, "tokens_out": 0}
    try:
        d = json.load(open(GASTO, encoding="utf-8"))
        if d.get("mes") == base["mes"]:
            base.update(d)
    except Exception:
        pass
    return base

def gasto_somar(modelo, n_in, n_out, usd=None):
    g = gasto_ler()
    v = custo(modelo, n_in, n_out) if usd is None else float(usd)
    g["usd"] += v
    g["chamadas"] += 1
    g["tokens_in"] += n_in
    g["tokens_out"] += n_out
    # por modelo: alimenta o contador ao lado do botão de IA
    pm = g.get("por_modelo")
    if not isinstance(pm, dict):
        pm = {}
    item = pm.get(modelo) or {"usd": 0.0, "chamadas": 0, "tokens_in": 0, "tokens_out": 0}
    item["usd"] = float(item.get("usd", 0)) + v
    item["chamadas"] = int(item.get("chamadas", 0)) + 1
    item["tokens_in"] = int(item.get("tokens_in", 0)) + n_in
    item["tokens_out"] = int(item.get("tokens_out", 0)) + n_out
    pm[modelo] = item
    g["por_modelo"] = pm
    try:
        json.dump(g, open(GASTO, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return g

def config():
    c = dict(PADRAO)
    if os.path.exists(CONFIG):
        try:
            c.update(json.load(open(CONFIG, encoding="utf-8")))
        except Exception:
            pass
    return c

def chave(c):
    v = os.environ.get(c["variavel_de_ambiente"], "").strip()
    if v:
        return v
    p = os.path.join(AQUI, c["arquivo_da_chave"])
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return ""

def provedor_cfg(c, nome):
    """Dados do provedor (URL, formato, onde fica a chave), com as correções do config."""
    nome = (nome or "anthropic").lower()
    base = dict(PROVEDORES.get(nome) or PROVEDORES["compativel"])
    extra = ((c.get("provedores") or {}).get(nome)) or {}
    if isinstance(extra, dict):
        base.update({k: v for k, v in extra.items() if k != "chave"})   # chave nunca no config
    if nome == "anthropic":
        # compatibilidade: o config antigo guarda o arquivo/variável da Anthropic no topo
        base["arquivo_da_chave"] = c.get("arquivo_da_chave") or base["arquivo_da_chave"]
        base["variavel_de_ambiente"] = c.get("variavel_de_ambiente") or base["variavel_de_ambiente"]
    base["nome"] = nome
    return base

def chave_de(c, nome):
    """Chave do provedor: variável de ambiente ou arquivo na pasta. Nunca do config."""
    p = provedor_cfg(c, nome)
    var = (p.get("variavel_de_ambiente") or "").strip()
    if var:
        v = os.environ.get(var, "").strip()
        if v:
            return v
    arq = (p.get("arquivo_da_chave") or "").strip()
    if arq:
        caminho = os.path.join(AQUI, arq)
        if os.path.exists(caminho):
            try:
                return open(caminho, encoding="utf-8").read().strip()
            except OSError:
                pass
    if p.get("sem_chave"):
        return "local"
    return ""

# ---------- filtro de identificadores ----------
BLOQUEIOS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "CPF"),
    (re.compile(r"\b\d{2}/\d{2}/\d{4}\b"), "data completa"),
    (re.compile(r"\b\d{8,}\b"), "sequência longa de dígitos"),
    (re.compile(r"\bprontuário\s*n?[ºo]?\s*\d+", re.I), "número de prontuário"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.\w+\b"), "e-mail"),
]

def triagem(texto):
    """Devolve lista de motivos de bloqueio. Vazia = liberado."""
    return [nome for rx, nome in BLOQUEIOS if rx.search(texto or "")]

SISTEMA_REVISAO = """Você é um revisor de transcrição médica especializado em RADIOLOGIA.

Sua única função é transformar a transcrição de voz recebida em texto radiológico corretamente escrito, pontuado, formatado e gramaticalmente adequado.

NÃO RACIOCINE SOBRE O CASO CLÍNICO.
NÃO INTERPRETE OS ACHADOS.
NÃO DÊ OPINIÕES.
NÃO FAÇA DIAGNÓSTICOS.
NÃO CRIE CONCLUSÕES.
NÃO ACRESCENTE INFORMAÇÕES.
NÃO REMOVA INFORMAÇÕES CLÍNICAS.
NÃO MUDE O SENTIDO DO TEXTO.

Faça apenas revisão textual e normalização da transcrição.

REGRAS OBRIGATÓRIAS:

1. Corrija ortografia, acentuação, concordância, pontuação e capitalização.

2. Organize corretamente pontos, vírgulas, dois-pontos, ponto e vírgula e parênteses quando necessário para que as frases fiquem naturais e tecnicamente corretas.

3. Toda frase iniciada após ponto final deve começar com letra maiúscula.

4. Preserve as quebras de linha existentes quando forem coerentes. Não crie títulos, tópicos ou novas seções por iniciativa própria.

5. Corrija palavras reconhecidas incorretamente pelo sistema de voz quando a correção for evidente pelo contexto radiológico.

Exemplos:
"canola" -> "cânula"
"seios costo frenicos" -> "seios costofrênicos"
"hemi torax" -> "hemitórax"
"linfo nodo" -> "linfonodo"
"parenquima" -> "parênquima"

Esses exemplos são apenas ilustrativos. Utilize o vocabulário médico e radiológico correto quando houver erro fonético evidente.

6. NÃO substitua uma palavra duvidosa por outra apenas por parecer clinicamente mais provável. Se não houver segurança textual suficiente, preserve o conteúdo original.

7. Normalize números e unidades.

Exemplos:
"cinco milímetros" -> "5 mm"
"dois centímetros" -> "2 cm"
"um vírgula quatro centímetros" -> "1,4 cm"
"três por quatro milímetros" -> "3 x 4 mm"
"dois vírgula sete por um vírgula nove centímetros" -> "2,7 x 1,9 cm"
"cinco por quatro por três centímetros" -> "5 x 4 x 3 cm"
"vinte por cento" -> "20%"
"quarenta e cinco graus" -> "45°"
"dez mililitros" -> "10 mL"

Use vírgula como separador decimal em português.

8. NUNCA altere o valor de uma medida. Apenas converta sua forma escrita.

9. Preserve rigorosamente:
- números;
- medidas;
- lateralidade direita/esquerda;
- níveis vertebrais;
- segmentos anatômicos;
- nomes próprios;
- siglas;
- sequências;
- localização anatômica;
- comparações temporais.

10. Corrija comandos de pontuação falados quando forem claramente comandos e não parte do conteúdo.

Exemplos:
"ponto" -> .
"vírgula" -> ,
"dois pontos" -> :
"abre parênteses" -> (
"fecha parênteses" -> )

11. Remova hesitações e vícios de fala sem conteúdo quando forem apenas interrupções da fala.

12. Não embeleze excessivamente o texto. Preserve o estilo e a estrutura ditados pelo médico. Faça apenas os ajustes necessários para que o texto final fique correto, fluido e profissional.

13. Não transforme achados em hipóteses diagnósticas e não transforme hipóteses em afirmações.

14. Não introduza termos como "compatível com", "sugestivo de", "provável", "suspeito", "evidenciando" ou semelhantes se eles não estiverem presentes ou claramente implícitos na transcrição.

15. Se a frase já estiver correta, mantenha-a praticamente inalterada.

16. Retorne SOMENTE o texto final corrigido. Não explique as alterações. Não faça comentários. Não coloque aspas. Não escreva introduções. Não responda perguntas contidas no texto. Não converse com o usuário."""


SISTEMA_ANALISE = """Você assiste um médico radiologista brasileiro na redação de laudos.

REGRAS ABSOLUTAS
1. Nunca acrescente achado, medida, data ou lateralidade que não esteja no texto recebido.
2. Onde faltar um dado obrigatório, escreva ___ visível. Nunca preencha por inferência.
3. Não troque termos de gradação: infiltrativo, permeativo, expansivo, geográfico e
   localmente agressivo têm significados distintos e não são intercambiáveis.
4. Lateralidade é o erro mais caro do laudo. Se estiver ambígua no texto recebido,
   deixe [direito/esquerdo] em vez de escolher.
5. Números: vírgula decimal, unidade explícita, casa decimal compatível com o método.
6. Em avaliação de resposta oncológica, mostre a conta: some os maiores eixos,
   compare com o baseline E com o nadir, e só então nomeie a categoria.
7. Português do Brasil. Estrutura por tópicos.

Devolva apenas o texto do laudo, pronto para copiar. Sem preâmbulo.
Se algo impedir uma redação segura, diga em uma linha o que falta."""


SISTEMA_INSTRUCAO = """Você é o assistente de redação de um médico radiologista brasileiro.
Você recebe o LAUDO que está na tela dele e uma INSTRUÇÃO falada por ele sobre o que fazer
com esse laudo (por exemplo: "faça uma melhor descrição do AVC", "resuma a conclusão",
"padronize a descrição do nódulo", "deixe a análise mais objetiva").

O QUE VOCÊ FAZ
- Aplique a instrução ao laudo e devolva o LAUDO INTEIRO já modificado, pronto para colar
  no lugar do original.
- Mantenha a estrutura, os cabeçalhos (TÉCNICA:, INDICAÇÃO CLÍNICA:, ANÁLISE:, COMPARAÇÃO:,
  CONCLUSÃO:), a ordem das seções e o estilo do médico em tudo que a instrução não tocar.
- Na parte que a instrução pede para melhorar, use a terminologia radiológica brasileira
  padrão e a descrição sistemática que um radiologista experiente usaria (localização,
  território, extensão, densidade/sinal, efeito de massa, complicações pertinentes), SEMPRE
  a partir do que está escrito no laudo.
- Corrija também erros evidentes de transcrição por voz no laudo inteiro.

O QUE VOCÊ NUNCA FAZ
1. Nunca acrescente achado, medida, lateralidade, território, número, data ou tempo de
   evolução que não esteja no laudo. Se a boa descrição exigir um dado que não está lá,
   escreva ___ no lugar desse dado (ex.: "medindo ___", "território da artéria ___").
2. Nunca troque direito por esquerdo, nem altere valores de medidas.
3. Não transforme achado em diagnóstico nem hipótese em certeza. Não acrescente
   recomendação de conduta que o médico não pediu.
4. Se a instrução pedir algo que só daria para fazer inventando dados, faça o que for
   possível com o que existe e deixe ___ no resto.

SAÍDA
Somente o texto do laudo. Sem explicações, sem comentários, sem aspas, sem markdown
(não use ** nem #). Português do Brasil."""




SISTEMA_LAUDO = """Você é o assistente de redação de um médico radiologista brasileiro. Ele monta o laudo
por voz: primeiro cola uma MÁSCARA (laudo-modelo normal da região) e depois dita, em
qualquer ponto do texto — no início, no fim ou no meio —, os ACHADOS e as ORDENS dele,
muitas vezes de forma telegráfica e com erros de reconhecimento de voz. Exemplos do que
aparece solto no texto:
  "incluir área de AVC isquêmico no território da ACM esquerda"
  "acrescentar nódulo de 5 mm no lobo inferior direito"
  "refinar a análise"            "melhorar a descrição do fígado"
  "tirar a conclusão de normal"  "ateromas calcificados na aorta e ramos"
  [não encontrado no banco — completar: esteatose leve]

Você recebe o texto que está na tela (e, às vezes, uma INSTRUÇÃO FALADA separada) e devolve
o LAUDO FINAL, inteiro, pronto para assinar.

COMO FAZER
1. Separe o que é LAUDO do que é NOTA/ORDEM do médico (frases soltas fora da estrutura,
   verbos no infinitivo ou imperativo — incluir, acrescentar, refinar, melhorar, tirar,
   descrever —, achados ditados fora de lugar, e as marcações [não encontrado no banco —
   completar: ...]).
2. Execute cada nota e depois APAGUE a nota do texto:
   - Achado novo: escreva-o na ANÁLISE, na linha do órgão/estrutura correspondente
     ("Parênquima encefálico:", "Fígado:", "Pulmões:"...), com a redação e a descrição
     sistemática que um radiologista experiente usaria.
   - A linha da máscara que diz o CONTRÁRIO do achado deve ser reescrita, não mantida
     (ex.: com AVC, a frase "Não há áreas de isquemia aguda" sai; com derrame pleural,
     "seios costofrênicos livres" sai). O laudo final não pode se contradizer.
   - Achado com repercussão em outra estrutura já descrita (efeito de massa, desvio de
     linha média, compressão ventricular) só entra se estiver no texto ditado.
   - CONCLUSÃO: tire "exame sem alterações significativas" (ou equivalente) quando houver
     achado, e escreva um achado relevante por linha, do mais importante para o menos.
   - Ordem sobre a redação ("refinar a análise", "melhorar a descrição de X"): reescreva
     a parte indicada com terminologia radiológica brasileira padrão, sem mudar o conteúdo.
3. Corrija os erros de transcrição por voz no laudo inteiro (ortografia, acentuação,
   concordância, pontuação; ex.: "horta" -> "aorta", "antiromas falsificados" ->
   "ateromas calcificados", "tem dinopatia" -> "tendinopatia"), e normalize números e
   unidades ("cinco milímetros" -> "5 mm", "um vírgula dois" -> "1,2", vírgula decimal).

O QUE NUNCA FAZER
- Nunca invente achado, medida, lado, território, lobo, nível vertebral, número ou tempo
  de evolução. Se a boa descrição precisar de um dado que não foi ditado, escreva ___
  no lugar (ex.: "medindo ___", "no território da artéria ___").
- Nunca troque direito por esquerdo e nunca altere o valor de uma medida.
- Não transforme achado em diagnóstico definitivo nem hipótese em certeza; não acrescente
  recomendação de conduta que o médico não ditou.
- Não mude as partes da máscara que nenhuma nota tocou, além de corrigir erros.
- Não deixe nenhuma nota, ordem ou marcação [ ... ] no texto final.

EXEMPLO
Texto na tela:
  TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO
  TÉCNICA:  aquisição volumétrica, sem injeção intravenosa de contraste iodado.
  INDICAÇÃO CLÍNICA:  Em anexo.
  ANÁLISE:
  Parênquima encefálico:  coeficientes de atenuação preservados, com diferenciação
  córtico-subcortical mantida. Não há áreas de isquemia aguda, hemorragia ou lesão expansiva.
  Sistema ventricular:  de morfologia, dimensões e topografia normais.
  COMPARAÇÃO:  estudos anteriores não disponíveis para análise comparativa.
  CONCLUSÃO:
  Exame sem alterações significativas.
  incluir área de avc isquêmico agudo no território da acm esquerda
Laudo final:
  TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO
  TÉCNICA:  aquisição volumétrica, sem injeção intravenosa de contraste iodado.
  INDICAÇÃO CLÍNICA:  Em anexo.
  ANÁLISE:
  Parênquima encefálico:  área hipoatenuante córtico-subcortical no território da artéria
  cerebral média esquerda, com apagamento dos sulcos corticais adjacentes e perda da
  diferenciação córtico-subcortical, compatível com insulto isquêmico agudo/subagudo,
  medindo ___. Não há sinais de transformação hemorrágica. Demais regiões do parênquima com
  coeficientes de atenuação preservados.
  Sistema ventricular:  de morfologia, dimensões e topografia normais.
  COMPARAÇÃO:  estudos anteriores não disponíveis para análise comparativa.
  CONCLUSÃO:
  Área de isquemia aguda/subaguda no território da artéria cerebral média esquerda.
(Repare: "apagamento dos sulcos" e "sem transformação hemorrágica" são descrição
sistemática do achado ditado; se o médico tivesse dito outra coisa, prevalece o que ele
disse. A medida não foi ditada, então ficou ___.)

SAÍDA
Somente o laudo final. Sem explicações, sem comentários, sem aspas, sem markdown."""


SISTEMA_FORMATAR = """Você é um FORMATADOR de laudos radiológicos em português do Brasil.
Você NÃO é médico, NÃO interpreta o caso e NÃO raciocina sobre ele. Você só organiza texto.

Você recebe o texto que está na tela do radiologista: uma MÁSCARA (laudo-modelo normal) e
trechos que ele ditou em qualquer ponto (achados, conclusões e ordens de edição), com erros
de reconhecimento de voz. Às vezes vem também uma INSTRUÇÃO FALADA separada.

O QUE VOCÊ FAZ (e só isto)
1. Coloca cada frase ditada no lugar certo do laudo: na linha do órgão ou estrutura
   correspondente da ANÁLISE, ou na CONCLUSÃO quando foi ditada como conclusão.
   Use as MESMAS palavras que o médico ditou. As marcações
   [não encontrado no banco — completar: ...] são achados ditados: leve o conteúdo delas
   para a linha certa e apague a marcação.
2. Quando a frase ditada contradiz uma frase da máscara, apaga a frase da máscara
   (ex.: ditou derrame pleural -> sai "seios costofrênicos livres"). Se sobrar parte normal
   da mesma estrutura, pode escrever "Demais ..." com as palavras da própria máscara.
3. Se houver achado ditado e a conclusão da máscara disser que o exame é normal, troque
   essa frase pela lista dos achados ditados, com as palavras do médico, um por linha.
4. Executa ordens de edição explícitas (incluir, acrescentar, tirar, apagar, trocar, mover)
   e apaga a ordem do texto.
5. Corrige erros evidentes de reconhecimento de voz, ortografia, acentuação, concordância,
   pontuação e maiúsculas. Normaliza números e unidades ("cinco milímetros" -> "5 mm",
   vírgula decimal).

O QUE VOCÊ NUNCA FAZ
- Nunca acrescenta palavra de conteúdo que não foi ditada nem estava na máscara: nenhum
  achado, descrição, característica, medida, lado, localização, grau, hipótese, "compatível
  com", "sugestivo de" ou recomendação.
- Nunca "melhora", expande ou refina uma descrição. Se o médico pedir para descrever,
  refinar ou melhorar algo, não faça: mantenha o que foi ditado e acrescente, na última
  linha, exatamente: [pedido de descrição não executado no modo formatar]
- Nunca troca direito por esquerdo e nunca altera o valor de uma medida.
- Nunca deixa ordens ou marcações [ ... ] do médico no texto final.

SAÍDA
Somente o laudo inteiro. Sem explicações, sem comentários, sem aspas, sem markdown."""


FORMATO_SAIDA = """

FORMATO DE SAÍDA OBRIGATÓRIO (quando o texto for um laudo com seções):
TÍTULO DO EXAME EM CAIXA ALTA
(linha em branco)
TÉCNICA:  texto na mesma linha.
(linha em branco)
INDICAÇÃO CLÍNICA:  texto na mesma linha.
(linha em branco)
ANÁLISE:
Rótulo:  texto (um órgão/estrutura por linha, sem hífen, sem linha em branco entre elas)
(linha em branco)
COMPARAÇÃO:  texto na mesma linha.
(linha em branco)
CONCLUSÃO:
um achado por linha, sem numeração e sem hífen.
Radiografia: só título, TÉCNICA e ANÁLISE, com frases diretas uma por linha.
Mantenha só as seções que existirem no texto recebido. Sem markdown (não use ** nem #)."""


def _sem_acento(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(ch) != "Mn")

# tipo de exame: vale a palavra-chave que aparece PRIMEIRO no texto (o título),
# para "comparação com tomografia" no meio de uma RM não mudar o tipo
_TIPOS_EXAME = (("angio", ("ANGIOTOMOGRAFIA", "ANGIO-TC", "ANGIOTC", "ANGIO TC", "ANGIORRESSON",
                           "ANGIO-RM", "ANGIO RM", "ANGIORM")),
                ("rm", ("RESSONANCIA", " RM ")),
                ("tc", ("TOMOGRAFIA", " TC ")),
                ("rx", ("RADIOGRAFIA", "RAIO X", "RAIO-X", " RX ")),
                ("mamo", ("MAMOGRAFIA",)),
                ("us", ("ULTRASSONOGRAFIA", "ULTRASSOM", "ECOGRAFIA", " US ", "DOPPLER")))
_ONCO = re.compile(r"\bRECIST|\bONCOLOG|\bESTADIAMENTO|\bRESPOSTA (?:AO|DE|A) TRATAMENTO|"
                   r"\bLESO?(?:AO|ES) ALVO|\bNADIR\b|\bLUGANO\b|\bMRECIST|\bIRECIST")

def tipo_exame(texto):
    """'rx', 'tc', 'rm', 'angio', 'mamo', 'us' ou '' — pelo que aparece primeiro."""
    alto = " " + re.sub(r"[^A-Z0-9-]+", " ", _sem_acento(texto or "").upper()) + " "
    melhor, pos = "", None
    for tipo, chaves in _TIPOS_EXAME:
        for k in chaves:
            i = alto.find(k)
            if i >= 0 and (pos is None or i < pos):
                melhor, pos = tipo, i
    return melhor

def eh_onco(texto):
    """Pedido de avaliação oncológica (RECIST, estadiamento, resposta a tratamento)."""
    alto = re.sub(r"\s+", " ", _sem_acento(texto or "").upper())
    return bool(_ONCO.search(alto))


def _prompt_perfil(c, pedido=""):
    """Campo "Prompt adicionado no processamento de todos os laudos" (config.json:
    prompt_perfil) + campo opcional do tipo de exame (prompt_por_exame: {"rx": ..., "tc": ...}).
    Entra depois das regras do sistema, que continuam tendo prioridade."""
    geral = (c.get("prompt_perfil") or "").strip()[:2000]
    extra = ""
    por_exame = c.get("prompt_por_exame") or {}
    if isinstance(por_exame, dict) and por_exame:
        tipos = (["onco"] if eh_onco(pedido) else []) + [tipo_exame(pedido)]
        for tipo in tipos:
            if tipo and (por_exame.get(tipo) or "").strip():
                extra = por_exame[tipo].strip()[:2000]
                break
    if not geral and not extra:
        return ""
    txt = ("\n\nINSTRUÇÕES FIXAS DO RADIOLOGISTA (prompt do perfil). Valem para todo laudo, "
           "mas NUNCA acima das regras anteriores: não inventar achado, medida, lado ou número.\n")
    if geral:
        txt += geral + "\n"
    if extra:
        txt += "Para este tipo de exame: " + extra + "\n"
    return txt


def _exemplos_estilo():
    """Laudos reais do Bruno (dados/estilo/*.txt) -> exemplos de ESTILO no prompt.
    Entram no bloco de sistema (em cache), entao custam ~10% nas chamadas seguintes."""
    pasta = os.path.join(AQUI, "dados", "estilo")
    try:
        arqs = sorted(f for f in os.listdir(pasta) if f.endswith(".txt") and f != "LEIA.txt")
    except OSError:
        return ""
    partes, total = [], 0
    for f in arqs:
        t = open(os.path.join(pasta, f), encoding="utf-8").read().strip()
        if total + len(t) > 24000:          # teto de tamanho do prompt
            break
        partes.append(t); total += len(t)
    guia = ""
    try:
        guia = open(os.path.join(pasta, "GUIA_ESTILO.md"), encoding="utf-8").read().strip()
    except OSError:
        pass
    if not partes:
        return ("\n\n" + guia) if guia else ""
    return ("\n\n" + guia if guia else "") + ("\n\nEXEMPLOS DE LAUDOS DO PRÓPRIO MÉDICO — imite o vocabulário, o ritmo e o grau de "
            "detalhe destas descrições (os dados destes casos NÃO se aplicam ao laudo atual; o "
            "formato de saída continua sendo o definido acima):\n\n" +
            "\n\n---\n\n".join(partes))


# ---------- rota: qual provedor/modelo/modo atende este pedido ----------
_MODOS_RESTRINGIVEIS = ("analise", "laudo", "instrucao")

def _entrada_rota(v):
    """Aceita {"provedor":..,"modelo":..,"modo":..,"raciocinio":..} ou "provedor:modelo"."""
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return {}
        if ":" in v:
            p, m = v.split(":", 1)
            return {"provedor": p.strip().lower(), "modelo": m.strip()}
        return {"modelo": v}
    return dict(v) if isinstance(v, dict) else {}

def rota(pedido, c=None, modo="analise"):
    """Decide provedor, modelo e modo. Sem ia_por_exame = o de sempre (topo do config)."""
    c = c or config()
    prov_geral = (c.get("provedor") or "anthropic").strip().lower()
    r = {"provedor": prov_geral, "modelo": (c.get("modelo") or "").strip(), "modo": modo,
         "raciocinio": (c.get("raciocinio") or "").strip().lower(), "exame": "", "regra": "padrao"}
    tipo, onco = tipo_exame(pedido), eh_onco(pedido)
    r["exame"] = "onco" if onco else tipo
    restringir = (c.get("modo_ia") or "").strip().lower() in ("formatar", "so formatar", "só formatar")
    ia = c.get("ia_por_exame") or {}
    if isinstance(ia, dict) and ia:
        for k in (["onco"] if onco else []) + ([tipo] if tipo else []) + ["padrao"]:
            e = _entrada_rota(ia.get(k))
            if not e:
                continue
            prov = (e.get("provedor") or "").strip().lower()
            if prov:
                r["provedor"] = prov
                if prov != prov_geral and not (e.get("modelo") or "").strip():
                    r["modelo"] = ""          # modelo da Anthropic não serve para outro provedor
            if (e.get("modelo") or "").strip():
                r["modelo"] = e["modelo"].strip()
            if (e.get("raciocinio") or "").strip():
                r["raciocinio"] = e["raciocinio"].strip().lower()
            m = (e.get("modo") or "").strip().lower()
            if m in ("formatar", "so formatar", "só formatar"):
                restringir = True
            elif m in ("analisar", "analise", "livre"):
                restringir = False
            r["regra"] = k
            break
    if restringir and modo in _MODOS_RESTRINGIVEIS:
        r["modo"] = "formatar"
    return r


# ---------- trava de conferência ----------
_LIVRES = set("""para pela pelo pelas pelos como mais menos muito pouca pouco entre sobre
apos este esta estes estas esse essa esses essas isso isto seus suas estao tambem ainda
cada todo toda todos todas outro outra outros outras mesmo mesma quais onde quando qual
demais restante restantes tecnica indicacao clinica analise comparacao conclusao exame
anexo nota notas""".split())
_LADOS = (("direit", "direito"), ("esquerd", "esquerdo"), ("bilatera", "bilateral"))

def _tokens(t):
    return re.findall(r"[a-z]+", _sem_acento(t).lower())

def _numeros(t):
    return {n.replace(".", ",") for n in re.findall(r"\d+(?:[.,]\d+)?", t or "")}

def conferir(entrada, saida):
    """Compara o que foi enviado com o que voltou. Devolve a lista do que a IA
    ACRESCENTOU (palavras de conteúdo, números, lado). Lista vazia = nada novo.
    Tolera correção de reconhecimento de voz (palavra parecida) e número por extenso."""
    base = entrada or ""
    try:
        import revisor                      # números por extenso e vocabulário
        base = base + "\n" + revisor.revisar(entrada or "")
    except Exception:
        pass
    # linhas que a própria IA marca entre colchetes não entram na conta
    corpo = "\n".join(l for l in (saida or "").splitlines() if not l.strip().startswith("["))
    vocab = set(w for w in _tokens(base) if len(w) >= 3)
    novas, vistas = [], set()
    for original in re.findall(r"[A-Za-zÀ-ÿ]+", corpo):
        w = _sem_acento(original).lower()
        if len(w) < 4 or w in vocab or w in _LIVRES or w in vistas:
            continue
        vistas.add(w)
        if difflib.get_close_matches(w, vocab, n=1, cutoff=0.78):
            continue                         # "calcanho" -> "calcaneo", "horta" -> "aorta"
        novas.append(original.lower())
    avisos = []
    t_in, t_out = _sem_acento(base).lower(), _sem_acento(corpo).lower()
    lados = [nome for raiz, nome in _LADOS if raiz in t_out and raiz not in t_in]
    novas = [w for w in novas if not any(_sem_acento(w).startswith(raiz) for raiz, _n in _LADOS)]
    if novas:
        avisos.append(", ".join(novas[:8]) + (" …" if len(novas) > 8 else ""))
    nums = sorted(_numeros(corpo) - _numeros(base))
    if nums:
        avisos.append("número " + ", ".join(nums[:6]))
    for nome in lados:
        avisos.append("LADO " + nome.upper())
    return avisos


# ---------- envio ----------
class _ErroAPI(Exception):
    def __init__(self, code, det):
        Exception.__init__(self, "http %s" % code)
        self.code, self.det = code, det

def _post(url, corpo, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                 method="POST", headers=headers)
    ctx = ssl.create_default_context() if url.lower().startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise _ErroAPI(e.code, e.read().decode("utf-8", "replace")[:200])

def _enviar_anthropic(p, k, modelo, sistema, pedido, max_tokens, timeout, raciocinio):
    corpo = {
        "model": modelo,
        "max_tokens": max_tokens,
        # o prompt de sistema e sempre o mesmo: fica em cache na Anthropic e
        # as chamadas seguintes pagam ~10% dele
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": pedido}],
    }
    d = _post(p.get("url") or URL, corpo, {
        "content-type": "application/json",
        "x-api-key": k,
        "anthropic-version": "2023-06-01",
    }, timeout)
    partes = [b.get("text", "") for b in d.get("content", []) if b.get("type") == "text"]
    texto = "\n".join(x for x in partes if x).strip()
    # tokens REAIS cobrados, vindos da própria resposta da API
    u = d.get("usage", {}) or {}
    n_in = int(round(int(u.get("input_tokens", 0) or 0)
                     + 1.25 * int(u.get("cache_creation_input_tokens", 0) or 0)
                     + 0.10 * int(u.get("cache_read_input_tokens", 0) or 0)))
    n_out = int(u.get("output_tokens", 0) or 0)
    return texto, n_in, n_out, None

def _enviar_openai(p, k, modelo, sistema, pedido, max_tokens, timeout, raciocinio):
    """Formato /chat/completions (OpenAI, Gemini, OpenRouter, Ollama e compatíveis)."""
    corpo = {"model": modelo,
             "messages": [{"role": "system", "content": sistema},
                          {"role": "user", "content": pedido}]}
    corpo["max_completion_tokens" if p.get("nome") == "openai" else "max_tokens"] = max_tokens
    if raciocinio and raciocinio != "padrao":
        corpo["reasoning_effort"] = raciocinio
    h = {"content-type": "application/json"}
    if k and k != "local":
        h["authorization"] = "Bearer " + k
    if p.get("nome") == "openrouter":
        h["x-title"] = "Rotrix L-1000"
    try:
        d = _post(p["url"], corpo, h, timeout)
    except _ErroAPI as e:
        # modelo que não aceita o nível de raciocínio pedido: tenta de novo sem ele
        if e.code == 400 and "reasoning_effort" in corpo and "reason" in (e.det or "").lower():
            corpo.pop("reasoning_effort", None)
            d = _post(p["url"], corpo, h, timeout)
        else:
            raise
    ch = (d.get("choices") or [{}])[0] or {}
    conteudo = (ch.get("message") or {}).get("content")
    if isinstance(conteudo, list):
        conteudo = "\n".join(x.get("text", "") for x in conteudo if isinstance(x, dict))
    texto = (conteudo or "").strip()
    u = d.get("usage", {}) or {}
    pt = int(u.get("prompt_tokens", 0) or 0)
    cached = int(((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)) or 0)
    n_in = int(round((pt - cached) + 0.10 * cached))
    n_out = int(u.get("completion_tokens", 0) or 0)
    usd = u.get("cost") if isinstance(u.get("cost"), (int, float)) else None   # OpenRouter
    return texto, n_in, n_out, usd


def chamar(pedido, c=None, modo="analise", marcar=True, max_tokens=None):
    """Devolve (texto, origem). Nunca levanta excecao.

    modo: "revisao" usa o prompt de revisao textual (nao raciocina sobre o caso);
          "analise" usa o prompt de assistencia a redacao (RECIST, comparacoes);
          "laudo"/"instrucao" executam as ordens sobre o laudo inteiro;
          "formatar" so organiza, delimita e corrige (nunca descreve).
    A rota por exame (ia_por_exame) pode trocar o provedor/modelo e prender
    analise/laudo/instrucao no modo "formatar".
    """
    c = c or config()
    if not c.get("ativa"):
        return None, "nuvem_desligada"
    r = rota(pedido, c, modo)
    m_ef = r["modo"]
    sistema = {"revisao": SISTEMA_REVISAO, "instrucao": SISTEMA_INSTRUCAO, "laudo": SISTEMA_LAUDO,
               "formatar": SISTEMA_FORMATAR}.get(m_ef, SISTEMA_ANALISE) + FORMATO_SAIDA
    if m_ef in ("laudo", "instrucao"):
        sistema += _exemplos_estilo()
    sistema += _prompt_perfil(c, pedido)
    motivos = triagem(pedido)
    if motivos:
        return ("[não enviei para a nuvem: o texto contém " + ", ".join(motivos) +
                "]\n" + pedido), "nuvem_bloqueada"
    p = provedor_cfg(c, r["provedor"])
    if not p.get("url"):
        return None, "nuvem_sem_url"
    k = chave_de(c, r["provedor"])
    if not k:
        return None, "nuvem_sem_chave"
    if not r["modelo"]:
        return None, "nuvem_sem_modelo"
    rotulo = r["modelo"] if r["provedor"] == "anthropic" else "%s:%s" % (r["provedor"], r["modelo"])

    # teto de gasto do mês — trava antes de gastar, não depois
    limite = float(c.get("limite_mes_usd", 0) or 0)
    if limite > 0:
        g = gasto_ler()
        if g["usd"] >= limite:
            return ("[não enviei para a nuvem: o teto de US$ %.2f deste mês foi atingido "
                    "(gasto até agora US$ %.2f). Aumente limite_mes_usd no config.json "
                    "se quiser continuar.]\n%s" % (limite, g["usd"], pedido)), "nuvem_teto"

    # modelo básico da OpenAI em modo que não raciocina: pede raciocínio "none"
    rac = r["raciocinio"]
    if not rac and p.get("nome") == "openai" and m_ef in ("formatar", "revisao"):
        rac = "none"
    enviar = _enviar_anthropic if p.get("formato") == "anthropic" else _enviar_openai
    try:
        texto, n_in, n_out, usd = enviar(p, k, r["modelo"], sistema, pedido,
                                         int(max_tokens or c.get("max_tokens", 1500)),
                                         int(c.get("timeout_s", 40)), rac)
        if not texto:
            registrar(c, n_in, n_out, "vazia", modelo=rotulo)
            return None, "nuvem_vazia"
        c_call = float(usd) if usd is not None else custo(r["modelo"], n_in, n_out, c)
        g = gasto_somar(rotulo, n_in, n_out, usd=c_call)

        travas = c.get("modos_com_trava")
        if not isinstance(travas, list):
            travas = ["formatar"]
        avisos = conferir(pedido, texto) if m_ef in travas else []
        registrar(c, n_in, n_out, "ok_conferir" if avisos else "ok", c_call, g["usd"], modelo=rotulo)
        if avisos:
            texto = "[conferir — a IA acrescentou: " + "; ".join(avisos) + "]\n" + texto

        if marcar and c.get("marcar_saida"):
            ini, fim = c.get("marca_inicio", ""), c.get("marca_fim", "")
            if ini and "%s" not in ini:
                qual = (r["modelo"] + " · ") if r["regra"] != "padrao" else ""
                ini = "%s  (%sUS$ %.4f · mês US$ %.2f)" % (ini, qual, c_call, g["usd"])
            texto = (ini + "\n" if ini else "") + texto + ("\n" + fim if fim else "")
        return texto, "nuvem"
    except _ErroAPI as e:
        registrar(c, 0, 0, "http %s" % e.code, modelo=rotulo)
        return None, "nuvem_erro_http_%s: %s" % (e.code, e.det)
    except Exception as e:
        registrar(c, 0, 0, type(e).__name__, modelo=rotulo)
        return None, "nuvem_erro_%s" % type(e).__name__

def registrar(c, n_in, n_out, estado, usd=0.0, acumulado=0.0, modelo=None):
    """Log de auditoria. Nunca grava conteúdo de laudo — só contadores."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\tin=%d\tout=%d\tusd=%.5f\tmes=%.4f\n" % (
                datetime.datetime.now().isoformat(timespec="seconds"),
                modelo or c.get("modelo", ""), estado, n_in, n_out, usd, acumulado))
    except Exception:
        pass

def estado():
    """Situação da IA para a interface (botão de IA e contador). Nunca inclui chave."""
    c = config()
    ia = c.get("ia_por_exame") or {}
    return {
        "ativa": bool(c.get("ativa")),
        "provedor": (c.get("provedor") or "anthropic").lower(),
        "modelo": c.get("modelo") or "",
        "modo_ia": c.get("modo_ia") or "",
        "ia_por_exame": {k: _entrada_rota(v) for k, v in ia.items()} if isinstance(ia, dict) else {},
        "chaves": {nome: bool(chave_de(c, nome)) for nome in PROVEDORES},
        "limite_mes_usd": float(c.get("limite_mes_usd", 0) or 0),
        "gasto": gasto_ler(),
    }

def resumo():
    """Texto pronto para imprimir com o gasto do mês."""
    c = config()
    g = gasto_ler()
    lim = float(c.get("limite_mes_usd", 0) or 0)
    linhas = [
        "  mes . . . . . . . %s" % g["mes"],
        "  modelo  . . . . . %s" % (c.get("modelo") or "(nenhum)"),
        "  chamadas  . . . . %d" % g["chamadas"],
        "  tokens entrada  . %s" % f"{g['tokens_in']:,}".replace(",", "."),
        "  tokens saida  . . %s" % f"{g['tokens_out']:,}".replace(",", "."),
        "  gasto do mes  . . US$ %.4f" % g["usd"],
    ]
    if lim > 0:
        pct = (g["usd"] / lim * 100.0) if lim else 0
        linhas.append("  teto do mes . . . US$ %.2f  (%.1f%% usado)" % (lim, pct))
    if g["chamadas"]:
        linhas.append("  media por chamada US$ %.4f" % (g["usd"] / g["chamadas"]))
    pm = g.get("por_modelo") or {}
    if isinstance(pm, dict) and len(pm) > 0:
        linhas.append("  por modelo:")
        for nome, v in sorted(pm.items(), key=lambda x: -float(x[1].get("usd", 0))):
            linhas.append("    %-28s US$ %.4f  (%d chamadas)" % (
                nome[:28], float(v.get("usd", 0)), int(v.get("chamadas", 0))))
    ia = c.get("ia_por_exame") or {}
    if isinstance(ia, dict) and ia:
        linhas.append("  rota por exame:")
        for k, v in ia.items():
            e = _entrada_rota(v)
            linhas.append("    %-6s -> %s%s%s" % (
                k, (e.get("provedor") + ":") if e.get("provedor") else "",
                e.get("modelo") or "(modelo do topo)",
                "  [só formatar]" if (e.get("modo") or "").lower().startswith(("formatar", "so ", "só ")) else ""))
    return "\n".join(linhas)

if __name__ == "__main__":
    print()
    print("  GASTO DA ROTA DE NUVEM")
    print("  " + "-" * 40)
    print(resumo())
    print()
