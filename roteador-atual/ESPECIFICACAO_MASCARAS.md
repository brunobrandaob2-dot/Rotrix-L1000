# Especificação do banco de máscaras — Roteador de Laudos

Você vai escrever máscaras de laudo radiológico para o Dr. Bruno, radiologista em Curitiba,
que lauda ~2.000 tomografias e ~3.000 radiografias por mês. Ele dita pelo Handy; o roteador
casa o ditado com um gatilho e cola o texto do banco. O texto sai EXATAMENTE como você
escrever aqui, então escreva como ele escreveria.

## 1. O modelo de forma é o laudo DELE

Leia antes de escrever qualquer coisa — estes três arquivos são o gabarito de forma e de voz:

- `dados/mascaras/medicina_interna/tc/abdome/normal.txt`
- `dados/mascaras/medicina_interna/tc/torax/normal.txt`
- `dados/mascaras/neuro/angiotc/cranio_e_pescoco/normal.txt`

Eles vieram de laudos reais dele. Copie a estrutura, o ritmo das frases e o vocabulário:
"sem particularidades", "de dimensões normais", "contornos regulares", "considerando os
limites do método", "calibre e trajeto habituais". Frases curtas, descritivas, sóbrias.

Leia também `dados/estilo/GUIA_ESTILO.md` (como ele descreve no dia a dia: ordem da frase,
medidas, grau de certeza, normalidade) e os laudos reais em `dados/estilo/*.txt`.

## 2. Formato obrigatório de toda máscara

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

## 2-RX. RADIOGRAFIA tem formato PRÓPRIO (vale para toda pasta `/rx/`)

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

### RX literal (como o ditado de radiografia é montado)

O ditado de RX é uma lista de achados. O roteador (`rx_literal.py`) acha a máscara pela abertura
("raio x de tórax no leito") e põe **cada achado com as palavras ditadas** na frase certa da
ANÁLISE, sem conclusão e sem grau que não foi dito:

- a frase normal da mesma estrutura é trocada (âncoras por estrutura: campos pulmonares, seios
  costofrênicos, área cardíaca, mediastino, hilos, cúpulas, arcabouço, alinhamento, corpos
  vertebrais, espaços discais, elementos posteriores, sacroilíacas, espaços articulares,
  fraturas, densidade, partes moles, adenoide, seios da face...);
- osteófitos entram DEPOIS de "Corpos vertebrais com altura preservada";
- partes moles (entesopatia, calcificação, edema) entram antes de "Partes moles", que vira
  "Demais partes moles sem alterações.";
- dispositivos (tubo, sonda, cateter, dreno, prótese, placa, parafusos) abrem a ANÁLISE, um
  por linha; as linhas de dispositivo com lacuna da máscara do leito saem;
- "<exame> com <achado>" que casa com máscara alterada vira a normal + o achado literal; rótulo
  genérico ("alterações crônicas", "do idoso", "degenerativas", "após queda", "no leito")
  mantém a máscara pronta;
- "descrever <achado>" usa a máscara alterada ou o bloco do banco.

Por isso as **frases normais de RX precisam nomear a estrutura** ("Espaços discais
preservados.", "Seios costofrênicos livres.") — é por elas que o achado acha o lugar. Região nova
de RX pode ter só a `normal.txt`; os blocos e as alteradas servem ao "descrever".
Desligar: `"rx_literal": false` no config.json.

### Correções do médico (22/09/2026)

`correcao.py`. A caixa "Corrigir" do app manda o texto para `/v1/correcao`. O roteador entende
sozinho três tipos — grafia (vai para `dados/ouvido.tsv`), frase que não deve sair e frase que
deve sair sempre (`dados/minhas_regras.json`, com escopo opcional por região) — e guarda o resto
como nota em `dados/correcoes.jsonl`. Com `usar_ia`, o pedido confuso passa pela IA, que só pode
devolver esses mesmos tipos; o laudo nunca é enviado. As regras "tirar"/"acrescentar" são
aplicadas no texto final (`aplicar_regras`, chamado no POST antes de formatar). Toda regra tem
código e `desfazer`, que também tira a linha do ouvido.tsv.

### Modo estação e perfil (22/09/2026)

- **Exame da vez.** `estacao_atual` = o exame escolhido na estação, senão o aberto no Radius,
  senão o primeiro pendente. `POST /v1/fila/proximo` marca o da vez como feito e passa ao
  seguinte (Ctrl+Alt+N no app); `/v1/fila/escolher` e `/v1/fila/feito` fazem o resto. O que fica
  gravado em `dados/estacao.json` são só os códigos embaralhados, nunca nome ou número de acesso.
- **Perfil** (`perfil.py`): `/v1/perfil/exportar` e `/v1/perfil/importar`. Vão as máscaras do
  usuário, o `ouvido.tsv`, o `aprendizado.json` e as chaves de config que são do radiologista;
  os laudos de estilo só com `incluir_estilo`. A chave de IA nunca entra. Na importação, só
  caminhos conhecidos são aceitos (nada de `..`), o `ouvido.tsv` é somado e a base é regerada.

### Regras do laudo (22/09/2026, pedido do Bruno) — valem para RX e TC

1. **Alterações primeiro.** Na ANÁLISE, as frases de alteração abrem o laudo, na ordem ditada
   (dispositivos antes). As frases normais vêm abaixo, na ordem da máscara. Na TC, sobe a linha
   inteira da estrutura alterada ("Fígado: ...", "Rins: ..."). Desligar: `"alteradas_primeiro": false`.
2. **Com a alteração, a normal da mesma estrutura sai.** Na RX, cada pedaço positivo do achado
   ("espondilose COM FRATURA", "prótese com REDUÇÃO DA DENSIDADE") tira a frase normal que ele
   desmente. Na TC, o achado que o banco não tem entra **com as palavras ditadas** no rótulo da
   estrutura (escolhido pelo vocabulário dos blocos daquela região); a descrição normal do
   rótulo sai e as negativas que o achado desmente também. Continua na conclusão, com as
   mesmas palavras. Sem estrutura clara, fica marcado no fim como antes. Desligar: `"tc_literal": false`.
3. **Rótulo não é achado.** "alterações crônicas", "alterações da idade", "sem alterações"
   ditos no meio dos achados não viram frase.
4. **Grafia.** Palavra fora do banco que, com uma troca s/z/ç/ss, vira palavra do banco é
   corrigida ("risartrose" → rizartrose, "esparça" → esparsa). Erros de ouvido fixos no
   `dados/ouvido.tsv` ("orta" → aorta, "ácido metálica" → haste metálica).
5. **Modalidade.** "ressonância de joelho" ou "ultrassom de abdome" nunca caem em máscara de RX
   ou de TC por aproximação.
6. **Texto livre** sai com maiúscula no início e ponto final.

## 3. Organização em pastas

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

## 4. Blocos (`blk_*.txt`)

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

## 5. Frases (`frases.txt`)

```
# tipo: frases
## gatilhos: derrame articular pequeno no joelho | pequeno derrame no joelho
Pequeno derrame articular femorotibial.
## gatilhos: cisto de baker no joelho | cisto poplíteo
Cisto sinovial poplíteo (cisto de Baker), medindo {tamanho}.
```

- São chamadas soltas, SEM contexto de exame ("frase derrame articular no raio x de joelho").
  Por isso **todo gatilho de frase precisa conter o nome da região** (ou ser inequívoco no banco
  inteiro, como "cisto de baker"). O validador reprova frase que roteia para outra pasta.
- Uma frase por entrada, pronta para colar dentro de uma ANÁLISE ou CONCLUSÃO.
- Misture achados crônicos, agudos e frases de normalidade úteis.

## 6. Gatilhos — o que ele vai FALAR

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

## 7. Slots (lacunas que o ditado preenche)

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

## 8. Conteúdo clínico

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

## 9. Cotas mínimas por região

| | normal | crônicas | agudas | blocos | frases |
|---|---|---|---|---|---|
| TC / AngioTC | 1 | 2–4 | 2–4 | 4–8 | 15–25 |
| RX | 1 | 1–3 | 1–3 | 3–6 | 10–20 |

## 10. Validação — obrigatória antes de terminar

Rode, a partir de `/home/claude/dist/laudo-router/app`:

```
python3 validar_regiao.py dados/mascaras/<categoria>/<modalidade>/<regiao> [outras pastas...]
```

Ele monta uma base TEMPORÁRIA (não interfere nos outros agentes), roteia cada gatilho e compõe
cada bloco sobre a normal. **Zero ERRO é obrigatório.** Corrija e rode de novo até zerar.
Não rode `construir_base.py` sem `LAUDO_BASE` apontando para um arquivo seu em /tmp: outros
agentes estão trabalhando em paralelo.

**Só escreva nas suas pastas.** Não mexa em arquivos de outras regiões nem no motor.
