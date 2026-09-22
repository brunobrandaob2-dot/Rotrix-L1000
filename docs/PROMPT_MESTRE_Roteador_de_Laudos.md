# PROMPT MESTRE: Roteador de Laudos (app único)

> Cole este documento inteiro no início da conversa com a IA ou com o desenvolvedor que vai construir o app. Ele reúne tudo o que foi decidido até 22/09/2026: o sistema que já funciona, o app que queremos, as regras de laudo, a IA, a interface, a privacidade, os erros já corrigidos e os testes de aceite. Os anexos trazem, sem cortes, os prompts de IA em uso, o guia de estilo e a especificação do banco de máscaras.

---

## 1. Seu papel e o objetivo

Você é o engenheiro responsável por transformar o **Roteador de Laudos**, que hoje são peças separadas, em **um único programa de desktop para Windows**, instalável, rápido e usado o dia inteiro por um radiologista.

Objetivo: o médico dita, o texto sai **formatado no padrão dele**, direto na caixa de texto do sistema de laudo que estiver usando (Leorad, Mobile Teleradiologia ou qualquer outro), **sem trocar de janela e sem clicar**. Tudo roda localmente com o banco de máscaras; a IA na nuvem é **opcional e só entra quando ele pede**.

Regras de trabalho:
- Não invente requisitos. O que estiver em "decisões em aberto" (seção 22) deve ser perguntado, não presumido.
- Nunca troque lateralidade, medida ou nível vertebral. Uma lacuna visível é sempre melhor que um dado inventado.
- Entregue por etapas (seção 21), cada uma testável sozinha e com uma prévia para o médico aprovar.

---

## 2. Quem usa

- **Dr. Bruno**, médico radiologista, região de Curitiba, português do Brasil.
- Volume: cerca de 2.000 tomografias e 3.000 radiografias por mês. Na fila do Radius, de 6 a 21/09/2026, passaram **594 estudos: TC 77%, RX 22%, RM e outros 1%**. Por isso **TC e RX têm prioridade** em máscaras, atalhos e testes.
- Ferramentas do dia a dia:
  - **Handy 0.9.7** (ditado local, Whisper medium);
  - **Leorad** (editor de laudo, aceita texto rico);
  - **RadiAnt** (visualizador DICOM);
  - **Radius** (fila de exames, roda via PowerShell);
  - **Mobile Teleradiologia** (site com caixa de texto de laudo);
  - Windows.
- Ele dita **só o texto do laudo**, sem cabeçalho, sem nome ou identificador de paciente.
- Quer rapidez, poucos cliques, mão no teclado ou no mouse, e poder laudar reclinado usando macros do mouse.

---

## 3. O que já existe e funciona (reaproveitar)

Pasta instalada: `C:\Users\bruno\Documents\laudo-router`. Versão atual do motor: **2026-09-21.6**.

| Peça | O que faz hoje |
|---|---|
| **Handy** (open source, MIT) | Captura a voz, transcreve localmente (Whisper medium, `custom_words` com vocabulário de radiologia; os ~80 últimos termos entram no prompt inicial do Whisper) e manda o texto a um "pós-processador" compatível com OpenAI em `127.0.0.1:8123`. Atalhos: `Ctrl+Espaço` = transcrição simples; `Ctrl+Alt+Espaço` = transcrição com pós-processamento (roteador). Histórico em `%APPDATA%\com.pais.handy\history.db` (tabela `transcription_history`). |
| **roteador.py** | Servidor HTTP local (porta 8123, endpoint `/v1/chat/completions` e `/v1/versao`). Recebe o ditado, casa com máscaras, blocos e frases do banco SQLite (`base.sqlite`, ~24 mil gatilhos, ~13 MB) e devolve o laudo. Recarrega o banco sozinho quando o arquivo muda. |
| **Colador** `handy_radiology_paste.exe` (v9) | Converte `**negrito**` em HTML/RTF, aplica regras de mapa/alias/comando e cola com `Ctrl+V` no campo ativo. |
| **formato.py** | Padroniza qualquer laudo (vindo do banco ou da nuvem) no formato do Bruno (seção 11). |
| **nuvem.py** | Chamada à API da Anthropic (modelo atual `claude-sonnet-5`), com cache de prompt, limite mensal (US$ 25), registro de gasto (`gasto.json`, `GASTO.ps1`), modos revisão / instrução / laudo / análise (prompts no Anexo A). |
| **atalho_win.py** | `Ctrl+Alt+A`: copia a seleção (ou `Ctrl+A` no campo), manda o laudo inteiro para a IA no modo "laudo", cola por cima já padronizado. Bipes: curto = começou; agudo = colou; grave = falhou (`atalho.log`). |
| **construir_base.py / validar_regiao.py** | Geram o banco a partir das pastas de máscaras e validam cada região (zero erro obrigatório). Geram sozinhos as formas curtas dos gatilhos ("tc cranio", "rx ombro"). |
| **dados/ouvido.tsv** | Dicionário de erros do reconhecimento de voz (`errado<TAB>certo`), aplicado a todo ditado. Ex.: `na horta → na aorta`, `antiromas → ateromas`, `falsificados → calcificados`, `calcanho → calcâneo`, `tem dinopatia → tendinopatia`, `rx de cavo → rx de cavum`, `visar laudo → revisar laudo`, `anjomografia → angiotomografia`. |
| **dados/estilo/** | `GUIA_ESTILO.md` (Anexo B) + 9 laudos reais do Bruno, usados como exemplo de estilo nos prompts da IA. |
| **Formatador HTML** (`formatador_laudos_tomografia_v5.html`) | Cola texto cru à esquerda e sai laudo formatado à direita: títulos e subtítulos em negrito, 1 linha em branco (dois `<p>` vazios antes de cada subtítulo, porque editores rich-text descartam um), opção de unir linhas quebradas, cópia em HTML com fallback texto, `Ctrl+Shift+C` copia, modo noturno. |
| **Radius** | Fila de exames. Arquivos de estado (`state.beta-v3.json`, `other-dicoms-state.json`, `statistics.json`) com `Status`, `Modality`, `StudyDescription`, `IsReported`, `QueueEnteredAt`. **Também têm `PatientName` e `AccessionNumber`: dados de paciente.** |
| **Atualizador** | `ATUALIZAR_AGORA.bat` → `APLICAR_ATUALIZACAO.ps1`: para o roteador (por processo e por porta), faz backup das máscaras, extrai `pacote\atualizacao.zip` no lugar, mantém as regras do usuário no `ouvido.tsv`, reconstrói o banco, reconfigura o Handy, sobe o roteador e confere a versão. Scripts PowerShell só em ASCII. |

---

## 4. O produto final em uma frase e seus princípios

**Um programa só** (base: cópia própria do Handy) que junta voz local, dicionário de ouvido, roteador de máscaras, formatador, fila do Radius e IA com a chave que cada usuário escolher. Ele flutua sobre qualquer programa e cola o laudo em qualquer caixa de texto.

Princípios:
1. **Velocidade:** do fim da fala ao texto colado, a parte local leva menos de 1 s.
2. **Zero clique no fluxo normal:** atalhos de teclado ou botões do mouse.
3. **Região automática:** a modalidade e a região vêm do exame aberto na fila.
4. **Sem trocar de janela:** o laudo cai onde está o cursor.
5. **Local por padrão:** sem internet e sem chave, tudo funciona com o banco.
6. **IA sob demanda:** só quando ele pede, com o modelo certo para cada exame.
7. **Nada identificável sai do computador.**

---

## 5. Arquitetura

- **Base:** fork do **Handy** (Tauri v2 + Rust + React/TypeScript, licença MIT). Pode ser copiado, modificado e redistribuído mantendo o aviso de licença MIT. **O nome, o logo e o ícone "Handy" não são abertos: o app precisa de nome e marca próprios** e não pode sugerir endosso.
- **Motor de voz:** o do Handy (Whisper e Parakeet, detecção de voz Silero). Modelo e vocabulário carregados na memória desde a abertura.
- **Roteador e formatador:** entram primeiro como estão (Python empacotado como *sidecar* do Tauri, sem janela de PowerShell); depois podem ser reescritos em Rust para ganhar velocidade. A interface entre eles continua sendo "texto ditado + perfil do exame → laudo".
- **Fila do Radius:** módulo que lê os arquivos de estado do Radius (seção 15).
- **IA:** módulo com provedores plugáveis (seção 13).
- **Pacote:** um instalador `.exe`/`.msi` para Windows, um ícone, atualização automática.
- **"App container":** sim, no sentido de um único programa que contém tudo. **Docker não serve para o posto de laudo**, porque não acessa com facilidade microfone, atalhos globais e colagem na caixa de texto de outro programa. Docker só entra no futuro, se virar produto, no **servidor** (contas, licenças, banco de máscaras compartilhado).

---

## 6. Fluxo do ditado ao laudo

1. **Ditar:** atalho de teclado ou botão do mouse. **Segurar** = um trecho. **Tocar** = escuta contínua (seção 7).
2. **Voz → texto:** local (Whisper ou Parakeet), com vocabulário de radiologia.
3. **Dicionário de ouvido:** corrige o que a voz erra sempre (`ouvido.tsv` + aproximação pelo vocabulário do banco, só para achar o gatilho).
4. **Roteador:** máscara do exame + blocos dos achados + lacunas preenchidas (seção 9). O **perfil automático** (modalidade + região da fila) ajuda a escolher.
5. **Formatador:** título, TÉCNICA / ANÁLISE / CONCLUSÃO em negrito, rótulos em negrito, espaçamento que o editor aceita (seção 11).
6. **Cola em qualquer campo:** texto rico onde estiver o cursor (Leorad, Mobile Teleradiologia, outro site ou programa). `Ctrl+Z` desfaz a colagem.
7. **IA só quando pedida:** `Ctrl+Alt+A` ou por voz ("revisar laudo", "conclusão direta", "descreva melhor o AVC"). O app monta o pedido, a IA devolve, o formatador padroniza e o app cola por cima.

Tempos de referência medidos: roteador aquecido 0,2 a 0,5 s por ditado; revisão pela IA ~18 s (`atalho.log`).

---

## 7. Modos de captação de voz

- **Segurar (push-to-talk):** segura o atalho, dita, solta; o trecho é processado e colado.
- **Escuta contínua:** toca o atalho uma vez (ou o botão do mouse) e o app fica escutando e reconhecendo. O médico **tira a mão do mouse do app, vai para o RadiAnt, olha as imagens e continua ditando**. A barra flutuante mostra o que está ouvindo. Quando volta ao campo do laudo, fala **"formar laudo"** (ou toca o atalho de novo): o roteador monta tudo o que foi ditado com o banco local e cola onde estiver o cursor.
- **Ditado livre:** texto sem máscara, só com o dicionário de ouvido e a formatação.
- **Comandos falados:** "parágrafo", "nova linha", pontuação falada ("vírgula", "ponto", "dois pontos", "abre/fecha parênteses"), "frase …" (frase solta do banco), "revisar laudo", instruções para a IA.
- **Pedidos livres à IA** (ex.: "descreva ascite moderada", "melhore a conclusão"): não são regras fixas do app. A IA atende pela instrução falada e pelo prompt do perfil de cada usuário (seção 16.7).

---

## 8. Modo flutuante (qualquer plataforma)

- O app **não prende o médico a uma janela própria**. Uma barra fina fica por cima de qualquer programa ou site.
- Os mesmos atalhos e funções valem em qualquer lugar. O laudo é colado **direto na caixa de texto que estiver com o cursor**: Leorad, Mobile Teleradiologia ou qualquer outra plataforma que aceite colar.
- Colagem em **texto rico** (HTML/RTF com negrito) com fallback para texto puro. A barra **não rouba o foco** do campo.
- Conteúdo da barra: indicador de gravação e tempo ("Escutando 02:14"), exame atual ("TC · TÓRAX", da fila), o que está sendo ouvido, a dica "fale *formar laudo*", o botão da IA (com o contador de gasto, seção 14) e a engrenagem de configuração.

---

## 9. Roteador: regras que já funcionam (manter)

**Tipos de conteúdo no banco:** `mascara` (normal / crônica / aguda), `bloco` (troca a linha de um rótulo da máscara normal), `frase` (frase solta, chamada com "frase …"), `achado`, `adendo`.

**Casamento do ditado:**
- A fórmula falada é **exame + lado + "com" achado, achado e achado**. Acentos e "de/do/da" não importam.
- **Formas curtas** geradas automaticamente a partir dos gatilhos: `tc / tomografia / tomografia computadorizada`, `rx / raio x / radiografia`, formas de angio, com ou sem "de/do/da" (sem texto próprio, preenchidas ao carregar, para o banco não crescer).
- **Preâmbulo removido só para casar:** "e", "é", "eh", "oi", "olá", "ok", "então", "bom", "te", "descreva", "descreve", "escreva", "me dê". O Whisper costuma inventar um "e " no começo de frases curtas.
- **Ouvido:** `ouvido.tsv` vale para o texto todo; a aproximação pelo vocabulário do banco (difflib ≥ 0,78, palavras de 5 letras ou mais que não existem no banco, com cache) vale só para achar o gatilho.
- **Blocos procurados primeiro na região do exame ditado**, então o gatilho pode ser curto e genérico.
- **Troca para máscara alterada** quando "<exame> com <trecho sem palavras de grau/lado>" casa exatamente com uma máscara alterada da mesma região (nunca por prefixo).
- **Qualificadores juntam no achado anterior:** um trecho que só qualifica ("plantar e posterior", "convexidade para a esquerda", "centrolobular e parasseptal nos lobos superiores") é anexado ao bloco anterior, inclusive encadeado ("plantar", depois "e posterior").
- **Trecho que a máscara já escreveu não vira pendência:** se todas as palavras de conteúdo do trecho já estão numa frase afirmativa do laudo (sem "sem / não / ausência"), ele não é marcado.
- **Achado não encontrado** entra visível no fim da ANÁLISE: `[não encontrado no banco — completar: …]`. Nunca some e nunca entra em lugar errado.
- **Montagem:** o bloco reescreve a linha inteira do rótulo; dois blocos na mesma frase somam; se não achar o rótulo, substitui a linha com as mesmas 3 primeiras palavras em vez de duplicar; conclusão com inicial maiúscula; "sem alterações significativas" sai da conclusão quando entra achado.
- **Voz para a IA:** "revisar laudo" sozinho → revisa a seleção. Verbo no imperativo ("faça, melhore, descreva, reescreva, resuma, deixe, padronize, acrescente, inclua, retire, tire, remova, organize, reorganize, transforme, ajuste, detalhe, simplifique, refaça, complete, enxugue, reformule, substitua, troque, coloque, escreva, redija") → instrução para a IA sobre o laudo selecionado. Exceção: "descreva / escreva / redija / coloque" + nome de exame → é pedido de máscara, não de IA.

**Lacunas (slots):** tabela completa no Anexo C. Além dela:
- `{nivel}` → "L4" ou "L4-L5";
- `{nivel_listese}` → "de L4 sobre L5" / "de L4 sobre o nível subjacente";
- `{lobo_completo}` → "lobo médio", "língula", "lobo inferior esquerdo";
- `{tamanho}` aceita vários eixos ("2,5 x 2,6 cm");
- opção falada preenche a lacuna (vence a opção mais longa dita; opções numéricas só depois de "grau");
- lacunas opcionais `{?nome:prefixo}` e `{?nome|opções}` somem se não forem ditas.

**Regra de segurança (a mais importante):** toda lateralidade, medida, nível, segmento, dedo, costela ou localização variável fica em lacuna. **Nunca escolher lado sozinho.** O que não foi ditado aparece como `[direito/esquerdo]` ou `___`.

**Desempenho (erro já corrigido):** a primeira consulta depois de ligar levava ~5 s (montagem do vocabulário) e passava do teto de 1,5 s, então o app devolvia o ditado cru. Agora o motor **aquece antes de atender** e o teto é 8 s. No app novo, o motor deve estar pronto antes de a barra aparecer como "pronta".

---

## 10. Banco de máscaras

- Organização: `dados/mascaras/<categoria>/<modalidade>/<regiao>/` com `normal.txt`, `cronica_*.txt`, `aguda_*.txt`, `blk_*.txt` e `frases.txt`. Categorias: `medicina_interna`, `neuro`, `angio`, `msk`, `_comum`. Hoje são 47 regiões validadas, com zero erro.
- Formato completo, gatilhos, blocos, frases, cotas e regras clínicas: **Anexo C** (vale para máscaras novas e para o editor de máscaras do app).
- **Radiografia tem formato próprio:** só título, TÉCNICA e ANÁLISE. ANÁLISE em frases diretas, uma por linha, **sem "Rótulo:"**, sem INDICAÇÃO, COMPARAÇÃO e CONCLUSÃO. Técnica padrão **"incidências anteroposterior e perfil."** (quando precisar de outras incidências, ele digita). Abdome: "incidência anteroposterior em decúbito dorsal."
- Exemplos de conteúdo recente (manter):
  - RX coluna com escoliose: "Desvio lateral do eixo longitudinal da coluna X, com convexidade para a {direita/esquerda}."
  - RX tornozelo/pé: "Entesopatia calcificada {plantar/posterior/plantar e posterior} no calcâneo." em linha própria no fim da ANÁLISE, seguida de "Demais partes moles sem alterações."
  - RX cavum (região nova): normal, 2 crônicas, 1 aguda, 4 blocos, 11 frases.
  - TC pelve (região nova), blocos novos de TC tórax, abdome superior, joelho e coluna lombar tirados dos laudos reais dele.
- O app deve ter um **editor de máscaras** com validação (mesmas regras do `validar_regiao.py`) e deve **preservar as máscaras e regras do usuário a cada atualização** (com backup antes).

---

## 11. Formatador: padrão do laudo do Bruno

Aplicado a **tudo** o que sai (banco ou IA), não importa como o texto chegou (markdown, linhas em branco a mais, cabeçalho em outra linha, lista numerada):

```
**TÍTULO EM CAIXA ALTA**

**TÉCNICA:**  texto na mesma linha, começando em minúscula.

**INDICAÇÃO CLÍNICA:**  Em anexo.

**ANÁLISE:**
**Fígado:**  texto começando em minúscula.
**Baço:**  texto.

**COMPARAÇÃO:**  texto na mesma linha.

**CONCLUSÃO:**
Achado um.
Achado dois.
```

- Cabeçalhos aceitos e convertidos:
  - TÉCNICA ← técnica do exame, protocolo;
  - INDICAÇÃO CLÍNICA ← indicação, informações clínicas, dados clínicos, história clínica;
  - ANÁLISE ← relatório, achados, descrição;
  - COMPARAÇÃO ← comparativo, estudo comparativo;
  - CONCLUSÃO ← impressão, impressão diagnóstica, opinião.
- TÉCNICA, INDICAÇÃO CLÍNICA e COMPARAÇÃO: texto na mesma linha, com dois espaços depois dos dois-pontos. ANÁLISE e CONCLUSÃO: texto abaixo.
- Na ANÁLISE, rótulo curto (até 6 palavras) antes de dois-pontos fica em **negrito**, e o texto depois dele começa em minúscula (sigla ou nome próprio fica como está).
- Remove markdown, marcadores e numeração. Conclusão sem numeração e sem hífen.
- **Radiografia:** só título, TÉCNICA e ANÁLISE, com frases diretas.
- Espaçamento robusto para editores rich-text: dois parágrafos vazios reais antes de cada subtítulo (o editor costuma descartar um).

---

## 12. Estilo de escrita do Bruno

O **Anexo B** (guia extraído dos laudos reais) vale para máscaras novas e para tudo o que a IA escrever. Em resumo:
- órgãos com achado primeiro;
- frase de achado na ordem achado → localização → medida → caracterização;
- grau de certeza com as expressões dele;
- normalidade curta ("sem particularidades", "sem alterações evidentes");
- artefatos registrados;
- conclusão com um achado por linha, do mais relevante ao menos relevante;
- achado normal não entra na conclusão.

**Preferências pessoais não são regras fixas do app.** As do Bruno estão no perfil dele no Leorad (Anexo E):
- subtópicos com a descrição na mesma linha;
- um parágrafo por linha;
- achados alterados primeiro;
- não citar a vesícula quando normal;
- descrever tecnicamente o que ele pedir.

Elas entram pelo **prompt do perfil** e pelos controles da aba Processamento (seção 16.7), e cada usuário escreve as suas. O app não embute regra clínica de estilo.

---

## 13. IA sob demanda

### 13.1 Quando entra
Nunca sozinha. Só com `Ctrl+Alt+A`, com "revisar laudo" ou com uma instrução falada. Sem chave configurada, o app funciona igual, só com o banco. No botão da IA existe a opção **"Nenhuma — só o banco"**.

### 13.2 Um botão: provedor → modelo
- Provedores: **Anthropic** (Haiku, Sonnet, Opus), **OpenAI** (GPT-5.6 Luna, Terra, Sol), **Gemini**, **OpenRouter**, **Ollama** (local, sem internet), **endpoint compatível com OpenAI** personalizado.
- A lista de modelos de cada provedor é **buscada na conta do usuário quando ele cola a chave**, para ficar sempre atual.
- Referências da OpenAI (set/2026):
  - na API estão Sol (o mais capaz), Terra (equilíbrio) e Luna (mais rápido e barato);
  - o GPT-6 Astra existe só no ChatGPT e não está disponível na API.
- Opção **"Automático pelo exame"**: o modelo muda sozinho conforme o exame aberto na fila.

### 13.3 Modelo e modo por tipo de exame (editável)

| Exame | Anthropic | OpenAI | Modo |
|---|---|---|---|
| RX | Haiku | Luna | só formatar |
| TC de rotina | a definir pelo Bruno | a definir | só formatar |
| RM | Sonnet | Sol | analisar |
| TC oncológica comparativa / RECIST | Sonnet (Opus opcional) | Sol | analisar |

- **Só formatar** (modelos leves): põe as frases na ordem da máscara, separa e delimita as seções, padroniza, corrige erros de voz. **Não raciocina sobre o caso, não descreve por conta própria, não conclui, não acrescenta achado.** Ideal para RX, que são frases curtas e simples. **Trava de conferência:** o app compara a saída com o ditado + a máscara e **marca qualquer palavra de conteúdo nova**; se houver achado novo, avisa antes de colar.
- **Analisar** (modelos fortes): reescreve com descrição sistemática, integra comparação, faz RECIST mostrando a conta (soma dos maiores eixos, comparação com baseline e nadir, só então a categoria).
- Modos já implementados no sistema atual, que continuam valendo (prompts no Anexo A):
  - **revisão**: só corrige transcrição;
  - **instrução**: aplica a instrução falada ao laudo inteiro;
  - **laudo**: executa as notas soltas ("incluir área de AVC", "refinar a análise", `[não encontrado…]`), reescreve a linha da máscara que contradiz o achado, apaga as notas e ajusta a conclusão;
  - **análise**: oncologia e raciocínio, com `___` onde faltar dado.
- Os laudos reais e o guia de estilo entram no bloco de sistema com **cache de prompt**, para custar pouco nas chamadas seguintes.

### 13.4 Pedido montado pelo app (envelope)
```
MODALIDADE: TC
REGIÃO: TÓRAX
TAREFA: revisar | formatar | laudo | analisar
LAUDO: (texto que está na tela)
PROMPT DO PERFIL: (campo "Prompt adicionado no processamento de todos os laudos" + campo do tipo de exame, se houver)
INSTRUÇÃO DO RADIOLOGISTA: conclusão direta
```
A IA devolve **só o laudo**. Vai só o texto do laudo: **nunca nome, data de nascimento, número de acesso ou qualquer identificador**. Antes de enviar, o app faz uma triagem de identificadores (CPF, números longos, datas de nascimento) e bloqueia se encontrar.

### 13.5 Regras que valem para qualquer modelo
- Nunca inventar achado, medida, lado, território, lobo, nível, número ou tempo de evolução; onde faltar, `___`.
- Nunca trocar direito/esquerdo nem alterar medidas; lateralidade ambígua vira `[direito/esquerdo]`.
- Não transformar achado em diagnóstico nem hipótese em certeza; não recomendar conduta que não foi ditada.
- Não deixar notas, ordens ou marcações `[ ]` no texto final.
- Saída sem markdown; o formatador do app aplica o negrito.

---

## 14. Contador de tokens e gasto

Fica **ao lado do botão da IA**, na barra flutuante e na estação:
- **Na barra:** o gasto de hoje em número pequeno (ex.: "hoje US$ 0,31").
- **Ao abrir o botão da IA:**
  - **este laudo:** tokens enviados e recebidos e o custo;
  - **hoje:** número de envios, total de tokens e custo;
  - **mês:** custo acumulado contra o limite (ex.: "US$ 4,20 de US$ 25"). A barra fica amarela perto do limite e **bloqueia novos envios** ao chegar nele.
- **Por modelo:** quanto foi Haiku, Sonnet, Luna, Sol etc., para ver quanto custa cada tipo de exame.
- **Na configuração:** limite mensal e moeda (dólar, como a API cobra, com valor aproximado em reais).
- O custo usa os tokens reais devolvidos pela API, incluindo cache: entrada + 1,25× criação de cache + 0,1× leitura de cache (Anthropic), com a tabela de preços de cada provedor. O custo aparece antes de colar.
- Hoje o sistema já guarda isso em `gasto.json` com limite de US$ 25/mês; o contador só passa a mostrar na tela.

---

## 15. Fila do Radius

- O app lê os arquivos de estado do Radius **só para pegar `Modality`, `StudyDescription`, `Status` e `IsReported`** e escolher o perfil (modalidade + região + máscara + modelo de IA).
- **`PatientName` e `AccessionNumber` nunca são enviados à IA nem gravados em log.** Na interface, o nome fica oculto ("Paciente ••••").
- Coluna lateral com a fila: laudado ✓, pronto, aberto, baixando…
- `Ctrl+Alt+N` marca o atual como laudado e abre o próximo.
- Com a fila, atalhos por modalidade (`Ctrl+Alt+T/R/M`) ficam opcionais.

---

## 16. Interface

### 16.1 Modo flutuante (padrão)
Barra fina, escura, sempre por cima, que não rouba o foco. Conteúdo descrito na seção 8.

### 16.2 Modo estação (opcional)
Uma janela no estilo de estação de laudo:
- **Topo:** botão de gravar (`Ctrl+Espaço`), exame atual (TC · TÓRAX), "perfil automático", "fila 3 / 12", alternância de tema, **botão da IA** ("IA: automática · Haiku ▾") com o contador, e a engrenagem.
- **Esquerda:** fila do Radius.
- **Centro:** editor com o laudo formatado. Lacunas destacadas (`[medida]`), `Tab` e `Shift+Tab` pulam entre elas. Embaixo, a linha "você disse: …" com o ditado cru.
- **Direita:** "Roteador usou" (máscara e blocos, em chips) e "não encontrado: …", lacunas pendentes e frases rápidas da região.
- **Menu do botão da IA:**
  - "Automático pelo exame" ✓;
  - Anthropic: Haiku (rápido · só formatar), Sonnet (RM · oncológica), Opus (mais caro);
  - OpenAI: Luna (rápido · só formatar), Terra (equilíbrio), Sol (análise);
  - Gemini, OpenRouter (modelos da conta);
  - Ollama (local, sem internet);
  - Nenhuma (só o banco);
  - botão "Revisar agora · Ctrl+Alt+A".

### 16.3 Tema
**Modo escuro** (padrão sugerido), claro e "seguir o sistema".

### 16.4 Configuração (uma tela)
- Tema.
- Voz: modelo e idioma (pt-BR).
- Escuta: segurar ou contínua.
- Depois do ditado: dicionário de ouvido ✓, comandos falados ✓, roteador ✓.
- IA: provedor e modelo, ou "automática pelo exame" com a tabela da seção 13.3 editável.
- Chave: colar a chave, que vai para o **Cofre de Credenciais do Windows** e nunca é mostrada de novo.
- IA · quando: "só quando eu pedir" (padrão) ou "em todo ditado" (pós-processamento automático, como no Leorad).
- Limite mensal e moeda.
- Atalhos: todos configuráveis.

### 16.5 Atalhos (todos configuráveis e mapeáveis em botões do mouse)

| Atalho | Ação |
|---|---|
| `Ctrl+Espaço` (segurar) | dita um trecho → roteador → cola formatado |
| `Ctrl+Alt+Espaço` (tocar) | liga/desliga a escuta contínua |
| fale "formar laudo" | monta tudo com o banco e cola |
| `Ctrl+Shift+Espaço` | ditado livre, sem máscara |
| `Ctrl+Alt+A` | IA revisa o laudo inteiro (fale a instrução junto) |
| `Tab` / `Shift+Tab` | próxima / anterior lacuna |
| `Ctrl+Alt+N` | próximo exame da fila |
| `Ctrl+Z` | desfaz a última colagem |

Atenção: hoje `Ctrl+Espaço` é o ditado simples e `Ctrl+Alt+Espaço` é o roteador. No app novo, o roteador passa a ser o `Ctrl+Espaço`. Mostrar essa mudança ao usuário na primeira abertura.

**Macros do mouse:** qualquer ação pode ir para um botão do mouse (pelo software do próprio mouse ou por mapeamento no app), para laudar sem teclado, inclusive reclinado.

### 16.7 Configuração por perfis: copiar os controles do Leorad

Objetivo, nas palavras do Bruno: uma aba para formatar o pós-processamento e a formatação dos laudos, e um botão para incluir um arquivo com os próprios laudos. Assim, quem instalar o app pode usar os laudos que já vêm com ele ou os seus, e explicar como os seus funcionam.

**Regra de projeto:** copiar os controles (botões, abas, chips, campos, prévia) das telas "Configurações do Assistant por perfis" do Leorad. **Não embutir regras clínicas ou de estilo no app.** Comportamentos como "descreva X gera descrição técnica" ou "não citar a vesícula normal" vêm do prompt que cada usuário escreve no perfil ou fala na hora.

- **Vários perfis com nome livre** (ex.: "Padrão Bruno", "Plantão TC", "RX rápido"). O perfil pode ser trocado pela barra ou por atalho, ou escolhido sozinho pela modalidade e região do exame aberto na fila. Botões: Salvar, Duplicar, Excluir, Exportar e Importar (arquivo .json, para levar para outro PC ou passar a um colega).
- Cada perfil tem **quatro abas: Formatação · Processamento · Voz · Máscaras**. O perfil "Padrão Bruno" vem pronto com tudo o que está neste documento.

**Aba Formatação.** Tem uma prévia ao vivo, "Como o laudo vai ficar": um laudo de exemplo com os marcadores "linha em branco", a contagem de seções e de linhas em branco, e destaque do que cada opção muda.
- Chaves gerais:
  - aplicar a formatação automaticamente nas máscaras;
  - colar como texto puro;
  - não aplicar formatação (experimental).
- Sub-abas: **Espaçamento, Corpo, Título, Seções, Tabela, Modo**.
- **Espaçamento:**
  - linhas em branco: "uma linha em branco antes de cada seção" (recomendado), "sem nenhuma linha em branco" ou "deixar como o laudo chegar" (com um botão "Espaçamento" na barra para aplicar na hora);
  - "juntar linhas em branco repetidas numa só";
  - o que conta como seção: "linha que termina com dois-pontos", "linha toda em MAIÚSCULAS" ou "está na minha lista de títulos" (lista editável);
  - entre uma frase e outra: quebra de linha ou parágrafo.
- **Título:** caixa alta, negrito, centralizado ou não, tamanho.
- **Seções:**
  - negrito e caixa alta dos cabeçalhos;
  - texto na mesma linha ou abaixo, por seção (TÉCNICA, INDICAÇÃO e COMPARAÇÃO na mesma linha; ANÁLISE e CONCLUSÃO abaixo);
  - rótulos da análise em negrito;
  - minúscula depois dos dois-pontos.
- **Corpo:** fonte e tamanho opcionais (o editor de destino pode sobrepor).
- **Tabela:** tabelas (ex.: lesões-alvo do RECIST) em tabela de texto rico ou em texto alinhado.
- **Modo:** texto rico, texto puro ou markdown.

**Aba Processamento (IA).**
- Chips de estilo, onde nada marcado significa o padrão do app:
  - escrita direta; escrita discursiva;
  - conclusão em tópicos; sem conclusão;
  - laudo estruturado com subtítulos;
  - responder à indicação clínica;
  - comparar com exames anteriores;
  - campo de observação ao final.
- Idioma em que o laudo é gerado.
- **Campo "Prompt adicionado no processamento de todos os laudos"** (igual ao do Leorad; é o "prompt do perfil"):
  - caixa de texto grande, com contador (ex.: "1695 / 2000") e o link "Carregar exemplo";
  - aviso embaixo do título: "Não inclua comandos de formatação (centralizar título, fonte, tamanho, cores etc.). Este campo é para orientações sobre o conteúdo e o estilo narrativo dos laudos.";
  - ali a pessoa delimita e escreve as características específicas dela e os comandos que devem valer sempre (ex.: "não mencionar a vesícula biliar nos laudos de abdome, somente se ela tiver alterações");
  - o texto vai **em todo pós-processamento feito pela IA** daquele perfil ("só formatar", "analisar", revisão e instrução), sempre depois das regras de segurança do app, que ele não pode desligar (não inventar achado, medida ou lado);
  - com "IA · quando" em "em todo ditado", ele vale para todos os laudos; em "só quando eu pedir", vale em cada envio à IA;
  - **campos por tipo de exame (opcionais):** além do campo geral, um campo igual para RX, TC, RM, angio ou uma região específica. Ele entra depois do geral, para delimitar comandos que valem só naquele exame;
  - o conteúdo aparece em "Ver o que será enviado à IA".
- **"Ver o que será enviado à IA"**: mostra o pedido final montado (envelope + chips + prompt do perfil + modelo das máscaras + laudo), para total transparência.
- Provedor e modelo (ou "automático pelo exame"), e o modo por exame (tabela 13.3).

**Aba Voz.**
- Modelo de reconhecimento (Whisper, Parakeet…) e idioma.
- **"Usar contexto das máscaras"**: o vocabulário e os gatilhos das máscaras do perfil entram no vocabulário do reconhecimento, como o `custom_words` de hoje.
- Dicionário de ouvido do perfil, editável.

**Aba Máscaras e laudos** (pedido do Bruno: para quem quiser usar os próprios laudos).
- **Botão "Incluir arquivo com meus laudos"**: aceita .txt, .docx, .zip ou uma pasta inteira, com laudos ou máscaras no formato da pessoa.
- **Escolher a fonte das máscaras:**
  - (a) o banco pronto do app, com as máscaras que já fizemos (47 regiões);
  - (b) só as minhas máscaras;
  - (c) as duas, com prioridade para as minhas quando o gatilho coincidir.
  - Liga e desliga por modalidade e por região.
- **Incluir as próprias máscaras:**
  - colar o texto ou importar arquivos (.txt, .docx ou uma pasta inteira);
  - cada máscara tem nome, gatilhos (as formas de falar), modalidade, região e tipo (normal, crônica, aguda, bloco ou frase).
- **Conversor:**
  - a máscara colada em qualquer formato é convertida para o formato do banco (Anexo C) pelo formatador local e, se o usuário quiser, pela IA;
  - passa pelo validador antes de entrar, que mostra o que não passou e por quê.
- **Campo "Como são os meus laudos"** (texto livre, editável). A pessoa descreve mais ou menos como funcionam os laudos dela: seções, rótulos, frases de normalidade, ordem, o que omitir. Esse texto é usado:
  1. pelo conversor;
  2. pelo formatador;
  3. no processamento da IA daquele perfil, para que o laudo final siga o modelo da pessoa.
- **Editor de máscaras:**
  - prévia;
  - teste de ditado ("digite ou dite um exemplo e veja qual máscara casa");
  - aviso de gatilho repetido;
  - histórico de versões;
  - exportar e importar um pacote de máscaras (.zip) para compartilhar com colegas.
- As máscaras do usuário **nunca são sobrescritas** pelas atualizações do banco pronto.

---

## 17. Privacidade, segurança e LGPD

- O nome do paciente e qualquer identificador **nunca saem do computador**.
- Arquivos DICOM e pacotes com nome de paciente **nunca são abertos, indexados ou enviados**.
- Laudos reais usados como exemplo de estilo ficam **sem identificação**; laudo com dado de paciente não entra no banco nem no pacote.
- A nuvem vem **desligada** até o usuário ativar; cada envio mostra o custo.
- **Chaves de API:** só no Cofre de Credenciais do Windows (hoje: arquivo `chave_anthropic.txt` na pasta). **Nunca colar chave em chat**; chave exposta deve ser trocada no painel do provedor.
- **Aprendizado local:** guarda só pares de palavras (errado → certo). **Nunca aprende lateralidade, posição, presença/ausência nem grau.**
- Logs sem conteúdo identificável.

---

## 18. Desempenho (metas)

- Motor de voz, vocabulário e banco carregados na abertura, sem espera no primeiro ditado.
- Parte local (ouvido + roteador + formatador + colagem): menos de 1 s.
- Se algum passo local estourar o tempo, **nunca colar o ditado cru calado**: avisar na barra.
- O banco recarrega sozinho quando muda.
- Mudança de código exige reinício do motor, e o app faz isso sozinho na atualização.

---

## 19. Instalação e atualização

- Um instalador; um ícone; sem janelas pretas.
- Atualização automática com: backup das máscaras antes; preservação de `ouvido.tsv` do usuário, aprendizado, configuração, gasto e chave; reconstrução do banco; reinício do motor; **conferência de versão** (endpoint `/v1/versao`). Se ainda estiver rodando uma versão antiga, avisar.
- Scripts auxiliares (se houver PowerShell) só em ASCII.

---

## 20. Erros já vividos: não repetir

1. Formas curtas ("tc cranio") caíam em máscara aguda por aproximação → gerar variantes curtas explícitas.
2. O PC nunca recebia a atualização (máscaras antigas) → atualização no lugar + conferência de versão.
3. Cache de vocabulário comparado com `is not` deixava tudo lento → comparar por valor.
4. Banco de 53 MB → variantes sem texto + VACUUM (~13 MB).
5. Whisper inventa "e " no começo → remover preâmbulo só para casar.
6. Triagem de nome dava falso positivo (regex sem distinção de maiúsculas) → regra removida.
7. Prompt da nuvem proibia acrescentar conteúdo e ignorava as notas → modo "laudo".
8. Medida cortada ("2,5 x 2,6" → "2,6") → tamanho com vários eixos.
9. Troca por prefixo para máscara alterada era gananciosa ("artrose medial" → máscara de gonartrose) → só casamento exato, cortando só palavras de grau e lado.
10. Gatilhos de blocos duplicados na mesma região → validador aponta.
11. Processo antigo segurava a porta 8123 → parar por processo e por porta, e conferir a versão.
12. Qualificador ditado com vírgulas ("entesopatia calcificada, plantar e posterior") virava "não encontrado" → encadear qualificadores.
13. Complemento que a máscara já tinha escrito ("convexidade para a esquerda") aparecia como pendência → conferir frase afirmativa.
14. Primeira consulta levava 5 s e colava o ditado cru → aquecer antes de atender.

---

## 21. Roteiro em 4 etapas (cada uma com prévia para aprovação)

1. **Cópia própria do Handy** com nome e ícone novos, aviso MIT mantido, build e instalador funcionando.
2. **Roteador e formatador dentro do app** (sidecar), sem janela de PowerShell; modo flutuante; escuta contínua; "formar laudo"; colagem rica em qualquer campo.
3. **Fila do Radius** na lateral; perfil automático; modo estação; modo escuro.
4. **IA com chave própria:** botão provedor → modelo, tabela por exame, modos "só formatar" e "analisar" com a trava de conferência, contador de tokens e gasto; atualização automática.
5. **Perfis e aba de Máscaras** (seção 16.7): importar, converter, validar e escolher a fonte das máscaras; campo "Como são as minhas máscaras"; exportar e importar perfis e pacotes.

**Código e compilação:**
- repositório privado no GitHub da conta **brunobrandaob2-dot** (nome sugerido: `rotrix-l1000`);
- instalador de Windows gerado automaticamente pelo GitHub Actions a cada versão e salvo na pasta do Bruno;
- fora do repositório: `chave_anthropic.txt`, `gasto.json`, `aprendizado.json`, histórico do Handy, arquivos do Radius e qualquer laudo com dado de paciente.

### Testes de aceite (o app deve reproduzir estes resultados)
Os resultados esperados, gerados pelo motor atual, estão no **Anexo D**. Além deles:
- Primeiro ditado logo depois de abrir o app **não** pode sair cru.
- "antiromas falsificados na horta e ramos" → "ateromas calcificados na aorta e ramos".
- Lateralidade não ditada → `[direito/esquerdo]`, nunca um lado escolhido.
- Modo "só formatar" com um RX: a saída não pode ter nenhuma palavra de conteúdo que não esteja no ditado ou na máscara.
- Colagem no Leorad e numa caixa de texto de site (Mobile Teleradiologia) mantendo negrito e espaçamento.
- Nenhum envio à IA contém nome ou número de acesso vindo do Radius.

---

## 22. Futuro e decisões em aberto

- **Produto:** vender o app para outros médicos, cada um com a própria chave de API (BYOK). Público pensado depois da radiologia: pronto-socorro/urgência, clínico geral, pediatria, cardiologia (máscaras e fluxos próprios para cada um).
- **Em aberto** (perguntar ao Bruno):
  - nome e marca do app. **Nome adotado só para o protótipo: ROTRIX L-1000** (a marca final continua em aberto). Candidatos de 22/09 (neologismos com Matrix + roteador + Skynet + T-1000): **Rotrix** (roteador + Matrix; sugerido como marca), **Laudomorfo** (laudo + metamorfo, o T-1000 que assume a forma de qualquer plataforma), **Neolaudo** (Neo, da Matrix + laudo), **Skylaudo** (Skynet + laudo); **L-1000** como codinome interno de versão. Evitar: Laudrix (já existe, plataforma de laudos da be3), Matrix, Skynet ou T-1000 literais (marcas de estúdio) e o nome Leorad. Conferir INPI (classes 9 e 42) e domínio .com.br antes de adotar;
  - modelo da **TC de rotina**;
  - moeda padrão do contador;
  - se os atalhos por modalidade continuam existindo;
  - comportamento exato da colagem no "formar laudo": onde está o cursor ou no campo onde começou.

---

# ANEXO A: Prompts de IA em uso hoje (nuvem.py, texto integral)

## A.1 SISTEMA_REVISAO: Modo revisão: só corrige a transcrição

```text
Você é um revisor de transcrição médica especializado em RADIOLOGIA.

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

16. Retorne SOMENTE o texto final corrigido. Não explique as alterações. Não faça comentários. Não coloque aspas. Não escreva introduções. Não responda perguntas contidas no texto. Não converse com o usuário.
```

## A.2 SISTEMA_INSTRUCAO: Modo instrução: aplica a instrução falada ao laudo inteiro

```text
Você é o assistente de redação de um médico radiologista brasileiro.
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
(não use ** nem #). Português do Brasil.
```

## A.3 SISTEMA_LAUDO: Modo laudo: executa as notas soltas e devolve o laudo final (usado pelo Ctrl+Alt+A)

```text
Você é o assistente de redação de um médico radiologista brasileiro. Ele monta o laudo
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
Somente o laudo final. Sem explicações, sem comentários, sem aspas, sem markdown.
```

## A.4 SISTEMA_ANALISE: Modo análise: oncologia e raciocínio

```text
Você assiste um médico radiologista brasileiro na redação de laudos.

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
Se algo impedir uma redação segura, diga em uma linha o que falta.
```

## A.5 FORMATO_SAIDA: Bloco acrescentado a todos os modos

```text
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
Mantenha só as seções que existirem no texto recebido. Sem markdown (não use ** nem #).
```

---

# ANEXO B: Guia de estilo do Dr. Bruno (dados/estilo/GUIA_ESTILO.md, integral)

## Como o Dr. Bruno descreve — guia extraído dos laudos reais (dados/estilo/*.txt)

Vale para: máscaras e blocos novos, e para o que a nuvem escreve (Ctrl+Alt+A).
Não copie os DADOS dos exemplos; copie o JEITO de escrever.

### Estrutura
- Título em caixa alta; TÉCNICA; INDICAÇÃO CLÍNICA "Em anexo."; ANÁLISE; COMPARAÇÃO; CONCLUSÃO.
- ANÁLISE por estrutura, "Rótulo: texto". Os órgãos COM achado vêm primeiro; os normais
  depois, em frases curtas ("Mediastino: sem alterações evidentes.").
- CONCLUSÃO: um achado por linha, do mais relevante para o menos relevante (o que muda
  conduta primeiro — lesão óssea suspeita, massa, ectasia com medida — e o degenerativo
  e os artefatos por último). Achado normal não entra na conclusão.

### Frase de achado
- Achado + localização + medida + caracterização, nessa ordem:
  "Nódulos pulmonares sólidos não calcificados, o maior localizado no lobo inferior
  esquerdo, medindo cerca de 0,6 cm."
- Medida: "medindo cerca de X", "medindo até X", "nos seus maiores eixos axiais",
  "o maior medindo até X". Vírgula decimal, "x" entre eixos.
- Múltiplos: "esparsos", "difusos", "distribuídos por ambos os campos pulmonares",
  "destacando-se ...", "o maior ...".
- Grau com palavra simples: discreto, acentuado, incipiente, raros, exuberante,
  moderada a acentuada.
- Descreve o mecanismo quando ele explica o achado: "relacionadas a decúbito e
  hipoventilação", "determinando distorção arquitetural", "com acotovelamento (kinking)".

### Grau de certeza (a assinatura do estilo)
- Achado benigno/inespecífico: "inespecíficos", "de aspecto sequelar", "residual",
  "de aspecto habitual".
- Possibilidade: "podendo representar ...", "sugerindo ...", "sugestiva de ...".
- Suspeita relevante: "altamente sugestivas de ...", "devendo-se considerar ... entre os
  diagnósticos diferenciais", "compatíveis com ...".
- Limite do método, dito com naturalidade: "sem identificação de fator obstrutivo
  evidente no segmento avaliado", "sem fator obstrutivo evidente pelo método",
  "de etiologia indeterminada pelo presente estudo", "ao método".
- Nunca afirma etiologia que a imagem não sustenta.

### Normalidade
- Curta e padronizada: "sem particularidades", "sem alterações evidentes",
  "dentro dos limites da normalidade", "morfologia e atenuação preservadas",
  "calibre e trajetos normais", "sem dimensões aumentadas", "ausente na pelve".
- Quando o órgão tem achado, completa com o que é normal nele na MESMA linha
  ("... Veia cava inferior pérvia.", "Rim esquerdo tópico, com dimensões normais,
  sem hidronefrose.").

### Qualidade técnica
- Artefatos são registrados na análise ("Presença de artefatos de movimentos
  respiratórios limitando parcialmente a avaliação" / "que reduzem parcialmente a
  resolução espacial do método sem invalidar o estudo") e, se relevantes, por último
  na conclusão.

### Vocabulário recorrente
ateromatose calcificada / ateromas parietais calcificados · alterações (osteo)degenerativas ·
espondiloartrose · opacidades fibroatelectásicas / subatelectásicas · estrias basais ·
vidro fosco · atenuação em mosaico · espessamento pleuroapical · distorção arquitetural ·
redução volumétrica · uretero-hidronefrose · ectasia do sistema coletor · bexiga de esforço ·
trabeculação parietal · linfonodomegalias · osteofitose marginal · geodos subcondrais ·
esclerose subcondral · anterolistese degenerativa grau 1 de L4 sobre L5 · abaulamentos
discais difusos · hipertrofia facetária · lesões de aspecto misto (lítico e blástico).

---

# ANEXO C: Especificação do banco de máscaras (ESPECIFICACAO_MASCARAS.md, seções 2 a 9, integral)

Modelos de forma de referência no projeto atual: `dados/mascaras/medicina_interna/tc/abdome/normal.txt`, `dados/mascaras/medicina_interna/tc/torax/normal.txt`, `dados/mascaras/neuro/angiotc/cranio_e_pescoco/normal.txt`; RX: `dados/mascaras/msk/rx/joelho/normal.txt`, `cronica_gonartrose.txt`, `blk_artrose_femorotibial_medial.txt`, `blk_derrame_articular.txt`. Validação: `python validar_regiao.py <pastas>` com zero erro.

### 2. Formato obrigatório de toda máscara

```
# gatilhos: gatilho 1 | gatilho 2 | gatilho 3
# categoria: medicina_interna | neuro | angio | msk
# modalidade: tc | rx | angiotc
# regiao: <nome da pasta da região>
# tipo_mascara: normal | cronica | aguda
**TÍTULO DO EXAME EM CAIXA ALTA**

**TÉCNICA:**  texto da técnica na mesma linha.

**INDICAÇÃO CLÍNICA:**  Em anexo.

**ANÁLISE:**
Rótulo:  texto.
Outro rótulo:  texto.

**COMPARAÇÃO:**  estudos anteriores não disponíveis para análise comparativa.

**CONCLUSÃO:**
Exame sem alterações significativas.
```

Regras que o validador confere:

1. Título na primeira linha do corpo, em **CAIXA ALTA**, entre `**` (negrito).
2. Os cinco cabeçalhos, exatamente assim e **nesta ordem**: `**TÉCNICA:**`, `**INDICAÇÃO CLÍNICA:**`,
   `**ANÁLISE:**`, `**COMPARAÇÃO:**`, `**CONCLUSÃO:**`. Caixa alta, dois-pontos, entre `**`.
   Uma linha em branco entre as seções.
3. TÉCNICA, INDICAÇÃO CLÍNICA e COMPARAÇÃO têm o texto **na mesma linha**, depois de **dois espaços**.
4. Cada linha da ANÁLISE: `Rótulo:  texto.` — **sem hífen**, rótulo, dois-pontos, **dois espaços**, texto.
   Uma frase complementar pode vir na linha seguinte sem traço (como "Não há sinais inflamatórios
   na região ileocecoapendicular." no abdome).
5. Textos-padrão: INDICAÇÃO CLÍNICA `Em anexo.` (sempre) — COMPARAÇÃO `estudos anteriores não
   disponíveis para análise comparativa.`
6. CONCLUSÃO da máscara **normal** deve conter a expressão `sem alterações significativas`
   (o motor a remove sozinho quando um bloco de alteração entra). Nas máscaras alteradas:
   um achado por linha, **sem numeração** (padrão do Bruno).
7. Ortografia pós-Acordo de 1990 (glenoide, deltoide, supraespinhal, anterossuperior).

### 2-RX. RADIOGRAFIA tem formato PRÓPRIO (vale para toda pasta `/rx/`)

Gabarito: `dados/mascaras/msk/rx/joelho/normal.txt`, `cronica_gonartrose.txt`,
`blk_artrose_femorotibial_medial.txt`, `blk_derrame_articular.txt`.

```
# gatilhos: raio x de joelho | rx de joelho | ...
# categoria: msk
# modalidade: rx
# regiao: joelho
# tipo_mascara: normal
**RADIOGRAFIA DO JOELHO {LADO|DIREITO/ESQUERDO}**

**TÉCNICA:**  incidências anteroposterior, perfil e axial de patela.

**ANÁLISE:**
Alinhamento articular preservado.
Espaços articulares preservados e superfícies articulares regulares.
Não há sinais de fraturas ou luxações.
Densidade óssea preservada.
Partes moles sem alterações.
```

- SÓ três partes: título, `**TÉCNICA:**`, `**ANÁLISE:**`. **Sem** INDICAÇÃO CLÍNICA, COMPARAÇÃO
  e CONCLUSÃO.
- ANÁLISE em **frases diretas**, uma por linha, **sem "Rótulo:"** e sem hífen. Frases curtas e
  simples, como o Bruno fala: "Espaço articular preservado." / "Artrose no compartimento medial
  do joelho." / "Redução do espaço articular femorotibial medial, com osteófitos marginais."
- Normal: 4–7 frases. Máscara alterada: a normal inteira com as frases afetadas trocadas.
- Blocos RX: `# secao:` = **o começo de uma frase da ANÁLISE do normal.txt** (as primeiras
  palavras, sem ponto, ex.: `# secao: Espaços articulares`, `# secao: Partes moles`,
  `# secao: Não há sinais de fraturas`). O bloco troca essa frase inteira. **Sem `# conclusao`.**
  A linha do bloco é uma frase direta.
- Dois blocos na mesma frase somam na mesma posição.
- Frases (`frases.txt`) de RX: diretas e curtas, sem conclusão.

### 3. Organização em pastas

```
dados/mascaras/<categoria>/<modalidade>/<regiao>/
    normal.txt                  1 máscara normal
    cronica_<nome>.txt          alterações crônicas / corriqueiras / degenerativas
    aguda_<nome>.txt            alterações agudas / urgência / trauma
    blk_<nome>.txt              blocos que encaixam na máscara normal da região
    frases.txt                  repertório de frases prontas da região
```

Nomes de pasta e de arquivo: minúsculas, sem acento, `_` no lugar de espaço.

**Crônica** = o que ele vê todo dia e não muda conduta de urgência: degenerativo, involutivo,
sequelar, ateromatose, esteatose, espondilose, artrose, calcificações, cistos simples.
**Aguda** = o que está acontecendo agora e pode mudar conduta hoje: fratura, luxação, sangramento,
isquemia aguda, infecção, obstrução, perfuração, embolia, dissecção.

### 4. Blocos (`blk_*.txt`)

```
# tipo: bloco
# secao: Fígado
# gatilhos: esteatose | esteatose hepatica | figado gorduroso
# conclusao: Esteatose hepática.
Fígado:  texto que SUBSTITUI a linha "Fígado:" da máscara normal.
```

- `# secao:` deve ser **idêntico** a um rótulo `Rótulo:` que exista no `normal.txt` da MESMA
  pasta. É assim que o motor sabe qual linha trocar. O validador confere.
- A linha do bloco reescreve a linha INTEIRA daquele rótulo (inclusive o que era normal nela).
- `# conclusao:` é uma frase só, que entra na CONCLUSÃO.
- Os blocos são procurados PRIMEIRO na região do exame ditado. Então o gatilho pode ser curto e
  genérico ("artrose", "derrame articular") — o "derrame articular" do joelho e o do quadril
  convivem sem conflito. Dê 2–4 formas de falar cada um.

### 5. Frases (`frases.txt`)

```
# tipo: frases
### gatilhos: derrame articular pequeno no joelho | pequeno derrame no joelho
Pequeno derrame articular femorotibial.
### gatilhos: cisto de baker no joelho | cisto poplíteo
Cisto sinovial poplíteo (cisto de Baker), medindo {tamanho}.
```

- São chamadas soltas, SEM contexto de exame ("frase derrame articular no raio x de joelho").
  Por isso **todo gatilho de frase precisa conter o nome da região** (ou ser inequívoco no banco
  inteiro, como "cisto de baker"). O validador reprova frase que roteia para outra pasta.
- Uma frase por entrada, pronta para colar dentro de uma ANÁLISE ou CONCLUSÃO.
- Misture achados crônicos, agudos e frases de normalidade úteis.

### 6. Gatilhos — o que ele vai FALAR

- Máscara **normal** — inclua o nome nu do exame e as variações:
  TC: `tomografia de joelho | tomografia do joelho | tc de joelho | tomografia de joelho normal |
  tc de joelho normal | tc joelho normal | tomografia de joelho sem alteracoes`
  RX: `raio x de joelho | rx de joelho | radiografia de joelho | raio x de joelho normal |
  rx de joelho normal | radiografia de joelho normal`
  AngioTC: `angiotomografia de ... | angio de ... | angio tc de ...` (+ normal)
- Formas curtas ("rx ombro", "tc cranio", "raio x do ombro") são geradas SOZINHAS pelo
  construir_base.py a partir dos gatilhos da máscara — não precisa escrevê-las.
- Máscara **alterada** — `<exame> com <achado>` em várias formas:
  `tomografia de joelho com artrose | tc de joelho com artrose | tc joelho artrose`
- Sem acento, minúsculas. Nunca repita um gatilho de máscara que exista em outra pasta —
  o validador aponta.
- Cada gatilho é uma forma NATURAL de falar. Nada de nome de arquivo.

### 7. Slots (lacunas que o ditado preenche)

| slot | vira | se o ditado não disser |
|---|---|---|
| `{lado\|direito/esquerdo}` | direito / esquerdo / bilateral | `[direito/esquerdo]` |
| `{lado_f\|direita/esquerda}` | direita / esquerda | `[direita/esquerda]` |
| `{lado_a\|à direita/à esquerda}` | à direita / à esquerda / bilateralmente | `[à direita/à esquerda]` |
| `{LADO\|DIREITO/ESQUERDO}` | em MAIÚSCULAS, para o título | `[DIREITO/ESQUERDO]` |
| `{contraste\|sem/com}` | "sem" / "com" / "sem e com" | `[sem/com]` |
| `{tamanho}` | "1,2 cm", "5 mm" | `___` |
| `{lobo}` `{lobo_cerebral}` `{segmento}` | do ditado | `___` |
| `{qualquer_nome\|a/b/c}` | nunca resolve sozinho | `[a/b/c]` |
| `{qualquer_nome}` | nunca resolve sozinho | `___` |

**REGRA DE SEGURANÇA — a mais importante do projeto:** toda lateralidade, medida, nível
vertebral, segmento, dedo, costela ou localização que varia de exame para exame vai em slot.
**Nunca escolha um lado por conta própria.** Lateralidade errada é o erro mais caro do laudo; uma
lacuna visível é infinitamente melhor que um lado inventado.

Articulações e segmentos de membro são unilaterais: o título leva `{LADO|DIREITO/ESQUERDO}`.
Bacia, coluna, tórax, abdome, crânio: sem lado no título.

### 8. Conteúdo clínico

- Português do Brasil, estilo do laudo brasileiro, voz do Bruno (seção 1).
- Nunca afirme malignidade nem etiologia que a imagem não sustenta: "indeterminado",
  "a esclarecer", "correlacionar com", "podendo corresponder a".
- Onde existir critério numérico consagrado, escreva o número: Kellgren-Lawrence 0–4,
  Meyerding I–V, Fazekas 0–3, Bosniak, Fleischner, índice cardiotorácico > 0,5, aorta ≥ 3,0 cm,
  relação VD/VE > 0,9, perda de altura vertebral em %, NASCET, ângulo alfa, distância AO, etc.
- Radiografia tem limite de método — diga isso onde a resposta depende de TC/RM:
  "a radiografia simples tem sensibilidade limitada para ___".
- Nunca invente achado para preencher máscara. O que é do exame vai em slot.
- Máscaras alteradas: ESCREVA A MÁSCARA INTEIRA (todas as linhas da ANÁLISE), com as linhas
  afetadas alteradas e as demais normais. Nada de "idem ao normal".

### 9. Cotas mínimas por região

| | normal | crônicas | agudas | blocos | frases |
|---|---|---|---|---|---|
| TC / AngioTC | 1 | 2–4 | 2–4 | 4–8 | 15–25 |
| RX | 1 | 1–3 | 1–3 | 3–6 | 10–20 |

---

# ANEXO D: Testes de aceite com o resultado esperado (gerados pelo motor 2026-09-21.6)

## D.1 Ditado: "radiografia do tornozelo esquerdo com entesopatia calcificada plantar e posterior no calcanho"

```text
**RADIOGRAFIA DO TORNOZELO ESQUERDO**

**TÉCNICA:**  incidências anteroposterior, perfil e mortise (anteroposterior com rotação interna de 15 a 20 graus).

**ANÁLISE:**
Pinça maleolar congruente, com espaço claro medial preservado.
Sindesmose tibiofibular sem alargamento.
Espaços articulares preservados.
Não há sinais de fraturas ou luxações.
Densidade óssea preservada.
Entesopatia calcificada plantar e posterior no calcâneo.
Demais partes moles sem alterações.
```

## D.2 Ditado: "radiografia do tornozelo esquerdo, entesopatia calcificada, plantar e posterior no calcanho."
(ditado com vírgulas e "calcanho": mesmo resultado do anterior)

```text
**RADIOGRAFIA DO TORNOZELO ESQUERDO**

**TÉCNICA:**  incidências anteroposterior, perfil e mortise (anteroposterior com rotação interna de 15 a 20 graus).

**ANÁLISE:**
Pinça maleolar congruente, com espaço claro medial preservado.
Sindesmose tibiofibular sem alargamento.
Espaços articulares preservados.
Não há sinais de fraturas ou luxações.
Densidade óssea preservada.
Entesopatia calcificada plantar e posterior no calcâneo.
Demais partes moles sem alterações.
```

## D.3 Ditado: "rx de coluna toracica com escoliose, convexidade para a esquerda"
(o complemento já escrito pela máscara não aparece como pendência)

```text
**RADIOGRAFIA DA COLUNA TORÁCICA**

**TÉCNICA:**  incidências anteroposterior e perfil.

**ANÁLISE:**
Desvio lateral do eixo longitudinal da coluna torácica, com convexidade para a esquerda.
Corpos vertebrais com altura preservada, sem sinais de fraturas.
Redução assimétrica dos espaços discais na concavidade da curva.
Elementos posteriores preservados.
Densidade óssea preservada.
Partes moles sem alterações.
```

## D.4 Ditado: "tc de torax com enfisema centrolobular e parasseptal nos lobos superiores"
(contraste não ditado fica em lacuna; o qualificador entra no bloco; a conclusão troca "sem alterações significativas" pelo achado)

```text
**TOMOGRAFIA COMPUTADORIZADA DO TÓRAX**

**TÉCNICA:**  exame realizado com técnica multislice e reconstruções multiplanares, [sem/com/sem e com] administração de contraste iodado endovenoso.

**INDICAÇÃO CLÍNICA:**  Em anexo.

**ANÁLISE:**
Parênquima pulmonar:  enfisema centrolobular e parasseptal nos lobos superiores.
Traqueia e brônquios:  calibre e trajetos normais.
Mediastino:  sem alterações evidentes.
Linfonodos mediastinais e hilares:  dentro dos limites da normalidade.
Aorta torácica:  trajeto e calibre habituais, com principais ramos preservados.
Derrames:  ausência de derrame pleural ou pericárdico.
Cúpulas diafragmáticas:  morfologia e posição habituais.
Estruturas ósseas e partes moles:  sem particularidades.

**COMPARAÇÃO:**  estudos anteriores não disponíveis para análise comparativa.

**CONCLUSÃO:**
Enfisema pulmonar centrolobular e parasseptal nos lobos superiores.
```

## D.5 Ditado: "radiografia do cavum"

```text
**RADIOGRAFIA DO CAVUM**

**TÉCNICA:**  incidência em perfil.

**ANÁLISE:**
Tecido adenoideano de dimensões normais.
Coluna aérea da rinofaringe preservada.
Palato mole de espessura e contornos normais.
Coluna aérea da orofaringe sem alterações.
Partes moles pré-vertebrais de espessura normal.
```

## D.6 Ditado: "e tc cranio"
(o "e" inventado pelo Whisper é ignorado; forma curta cai na máscara NORMAL, não na aguda; contraste não ditado fica [sem/com])

```text
**TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO**

**TÉCNICA:**  aquisição volumétrica, [sem/com] injeção intravenosa de contraste iodado.

**INDICAÇÃO CLÍNICA:**  Em anexo.

**ANÁLISE:**
Parênquima encefálico:  coeficientes de atenuação preservados, com diferenciação córtico-subcortical mantida. Não há áreas de isquemia aguda, hemorragia ou lesão expansiva.
Substância branca:  sem alterações de atenuação.
Núcleos da base:  de morfologia e atenuação preservadas.
Sistema ventricular:  de morfologia, dimensões e topografia normais.
Cisternas da base e sulcos corticais:  de amplitude preservada.
Linha média:  estruturas centradas.
Espaços extra-axiais:  sem coleções.
Fossa posterior:  tronco encefálico e hemisférios cerebelares de morfologia e atenuação preservadas.
Calcificações intracranianas:  sem calcificações de aspecto patológico.
Calota craniana e base do crânio:  sem sinais de fratura ou lesões focais.
Órbitas:  sem alterações evidentes nos segmentos incluídos no estudo.
Seios paranasais:  normopneumatizados nos segmentos incluídos no estudo.
Células mastoides:  normopneumatizadas.
Partes moles extracranianas:  sem particularidades.

**COMPARAÇÃO:**  estudos anteriores não disponíveis para análise comparativa.

**CONCLUSÃO:**
Exame sem alterações significativas.
```

---

# ANEXO E: Perfil atual do Bruno no Leorad (referência, 22/09/2026)

Serve de modelo dos controles a copiar e de exemplo de prompt de perfil. **O conteúdo do prompt é preferência do Bruno, não regra do app.**

- **Nome do perfil:** "Inferno na terra".
- **Formatação:**
  - aplicar formatação automaticamente nas máscaras: ligado;
  - linhas em branco: "deixar como o laudo chegar";
  - o que conta como seção: linha que termina com dois-pontos;
  - entre frases: parágrafo.
- **Processamento:**
  - chips marcados: escrita direta, laudo estruturado com subtítulos, comparar com exames anteriores, campo de observação ao final;
  - idioma: português Brasil.
- **Voz:** LEO Speech Engine V2, modo analítico, português Brasil, "usar contexto do autotexto" ligado.
- **Prompt do perfil:** trecho visível na tela, reproduzido como ele escreveu (o campo tem 1.695 de 2.000 caracteres; o restante não estava visível):

```text
Estruturar laudo e laudo com subtópicos estruturados, e após os dois pontos já seguir com a descrição na mesma linha (ex: rim: ..... fígado: .....) o laudo deve manter um padrão de texto com parágrafos, com linhas e parágrafos, E MAIS IMPORTANTE: não vai fazer tudo num bloco de texto so, coloque o próximo paragrafo na linha abaixo.
a TECNICA, Indicação: Em anexo, ANALISE, COMPARATIVO e CONCLUSAO (ou outros subtópicos quando tiver).
os achados alterados ou patológicos devem ocupar as primeiras linhas da análise, mantendo os achados normais ou não alterados abaixo.
sempre que eu fizer uma descrição como por exemplo, cistos bosniak I, ou descreva ascite modera, ou tambem descreva pavimentação em moisaico, quero que seja descrito de forma técnica, detalhada e com linguagem radiológica os achados sem que eu precise ditar toda a descrição.
não mencionar a vesícula biliar nos laudos de abdome, somente se ela tiver alterações
```

---

*Fim do prompt mestre. Versão de 22/09/2026. Arquivo-fonte: `Documents\laudo-router\PROMPT_MESTRE_Roteador_de_Laudos.md`.*
