# -*- coding: utf-8 -*-
"""Rota de nuvem do Roteador de Laudos (API da Anthropic).

Só é acionada por gatilho explícito. Nunca automática.
Antes de enviar, higieniza o texto e bloqueia se encontrar identificador.
"""
import json, os, re, ssl, urllib.request, urllib.error, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")
LOG = os.path.join(AQUI, "nuvem.log")
GASTO = os.path.join(AQUI, "gasto.json")
URL = "https://api.anthropic.com/v1/messages"

PADRAO = {
    "ativa": False,
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
}

# ---------- preços (USD por milhão de tokens) ----------
# Conferidos em platform.claude.com/docs/en/about-claude/pricing (set/2026).
# Se a Anthropic mudar a tabela, é só corrigir aqui.
PRECOS = [
    ("claude-fable",    10.0, 50.0),
    ("claude-mythos",   10.0, 50.0),
    ("claude-opus",      5.0, 25.0),
    ("claude-sonnet-5",  2.0, 10.0),
    ("claude-sonnet",    3.0, 15.0),
    ("claude-haiku",     1.0,  5.0),
]

def preco(modelo):
    """(usd_por_milhao_entrada, usd_por_milhao_saida). (0,0) se desconhecido."""
    m = (modelo or "").lower()
    for prefixo, pin, pout in PRECOS:
        if m.startswith(prefixo):
            return pin, pout
    return 0.0, 0.0

def custo(modelo, n_in, n_out):
    pin, pout = preco(modelo)
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

def gasto_somar(modelo, n_in, n_out):
    g = gasto_ler()
    g["usd"] += custo(modelo, n_in, n_out)
    g["chamadas"] += 1
    g["tokens_in"] += n_in
    g["tokens_out"] += n_out
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


def chamar(pedido, c=None, modo="analise", marcar=True, max_tokens=None):
    """Devolve (texto, origem). Nunca levanta excecao.

    modo: "revisao" usa o prompt de revisao textual (nao raciocina sobre o caso);
          "analise" usa o prompt de assistencia a redacao (RECIST, comparacoes).
    """
    c = c or config()
    sistema = {"revisao": SISTEMA_REVISAO, "instrucao": SISTEMA_INSTRUCAO, "laudo": SISTEMA_LAUDO}.get(modo, SISTEMA_ANALISE) + FORMATO_SAIDA
    if modo in ("laudo", "instrucao"):
        sistema += _exemplos_estilo()
    if not c.get("ativa"):
        return None, "nuvem_desligada"
    motivos = triagem(pedido)
    if motivos:
        return ("[não enviei para a nuvem: o texto contém " + ", ".join(motivos) +
                "]\n" + pedido), "nuvem_bloqueada"
    k = chave(c)
    if not k:
        return None, "nuvem_sem_chave"
    if not c.get("modelo"):
        return None, "nuvem_sem_modelo"

    # teto de gasto do mês — trava antes de gastar, não depois
    limite = float(c.get("limite_mes_usd", 0) or 0)
    if limite > 0:
        g = gasto_ler()
        if g["usd"] >= limite:
            return ("[não enviei para a nuvem: o teto de US$ %.2f deste mês foi atingido "
                    "(gasto até agora US$ %.2f). Aumente limite_mes_usd no config.json "
                    "se quiser continuar.]\n%s" % (limite, g["usd"], pedido)), "nuvem_teto"

    corpo = json.dumps({
        "model": c["modelo"],
        "max_tokens": int(max_tokens or c.get("max_tokens", 1500)),
        # o prompt de sistema e sempre o mesmo: fica em cache na Anthropic e
        # as chamadas seguintes pagam ~10% dele
        "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": pedido}],
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=corpo, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": k,
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=int(c.get("timeout_s", 40)),
                                    context=ssl.create_default_context()) as r:
            d = json.loads(r.read().decode("utf-8"))
        partes = [b.get("text", "") for b in d.get("content", []) if b.get("type") == "text"]
        texto = "\n".join(p for p in partes if p).strip()
        if not texto:
            return None, "nuvem_vazia"

        # tokens REAIS cobrados, vindos da própria resposta da API
        u = d.get("usage", {}) or {}
        n_in = int(round(int(u.get("input_tokens", 0) or 0)
                         + 1.25 * int(u.get("cache_creation_input_tokens", 0) or 0)
                         + 0.10 * int(u.get("cache_read_input_tokens", 0) or 0)))
        n_out = int(u.get("output_tokens", 0))
        c_call = custo(c["modelo"], n_in, n_out)
        g = gasto_somar(c["modelo"], n_in, n_out)
        registrar(c, n_in, n_out, "ok", c_call, g["usd"])

        if marcar and c.get("marcar_saida"):
            ini, fim = c.get("marca_inicio", ""), c.get("marca_fim", "")
            if ini and "%s" not in ini:
                ini = "%s  (US$ %.4f · mês US$ %.2f)" % (ini, c_call, g["usd"])
            texto = (ini + "\n" if ini else "") + texto + ("\n" + fim if fim else "")
        return texto, "nuvem"
    except urllib.error.HTTPError as e:
        det = e.read().decode("utf-8", "replace")[:200]
        registrar(c, 0, 0, "http %s" % e.code)
        return None, "nuvem_erro_http_%s: %s" % (e.code, det)
    except Exception as e:
        registrar(c, 0, 0, type(e).__name__)
        return None, "nuvem_erro_%s" % type(e).__name__

def registrar(c, n_in, n_out, estado, usd=0.0, acumulado=0.0):
    """Log de auditoria. Nunca grava conteúdo de laudo — só contadores."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s\t%s\t%s\tin=%d\tout=%d\tusd=%.5f\tmes=%.4f\n" % (
                datetime.datetime.now().isoformat(timespec="seconds"),
                c.get("modelo", ""), estado, n_in, n_out, usd, acumulado))
    except Exception:
        pass

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
    return "\n".join(linhas)

if __name__ == "__main__":
    print()
    print("  GASTO DA ROTA DE NUVEM")
    print("  " + "-" * 40)
    print(resumo())
    print()
