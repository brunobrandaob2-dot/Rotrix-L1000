# IA por exame (Etapa 4, parte de dentro)

A IA continua **sob demanda**: só entra por gatilho (Ctrl+Alt+A, "revisar…", "analisar…", instrução falada). O banco local continua sendo o padrão de todo ditado.

O que muda: cada tipo de exame pode ir para um provedor e modelo diferentes, e os modelos básicos ficam presos ao modo **formatar**.

## Como ligar (config.json do roteador)

Sem `ia_por_exame`, tudo continua como hoje (Anthropic, modelo do topo do config).

```json
{
  "ativa": true,
  "provedor": "anthropic",
  "modelo": "claude-sonnet-5",
  "ia_por_exame": {
    "rx":    {"provedor": "openai", "modelo": "gpt-5.6-luna", "modo": "formatar"},
    "tc":    {"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001", "modo": "formatar"},
    "rm":    "anthropic:claude-sonnet-5",
    "onco":  "anthropic:claude-sonnet-5",
    "padrao": {"modo": "formatar"}
  }
}
```

- **Tipos:** `rx`, `tc`, `rm`, `angio`, `mamo`, `us`, `onco` e `padrao` (o resto).
- **onco** vale quando o texto fala em RECIST, oncológico, estadiamento, resposta ao tratamento, lesões-alvo, nadir, Lugano. Tem prioridade sobre o tipo do exame. Exemplo: TC oncológica vai para o Sonnet mesmo com a TC comum no Haiku.
- **Tipo do exame:** vale a palavra que aparece primeiro no texto (o título). "Comparação com tomografia" dentro de uma RM continua RM.
- **Forma curta:** `"provedor:modelo"`.

## Modo "formatar" (modelos básicos: Luna, Haiku)

O modelo só organiza, delimita e corrige:

- põe cada frase ditada na linha certa;
- apaga a frase da máscara que contradiz o achado;
- troca a conclusão "normal" pelos achados ditados, com as palavras do médico;
- corrige a transcrição e normaliza números e unidades.

Ele **nunca** descreve, expande nem refina. Quando o médico pede "descreva…" nesse modo, o texto ditado fica como está e o modelo escreve no fim: `[pedido de descrição não executado no modo formatar]`.

Para o modelo não raciocinar, os modelos da OpenAI recebem `reasoning_effort: "none"`. Se o modelo não aceitar esse valor, o roteador repete a chamada sem ele.

## Trava de conferência

No modo formatar, o roteador compara o que foi enviado com o que voltou. Se a IA mexeu no conteúdo, o laudo vem com uma linha no topo, por exemplo:

```
[conferir — a IA acrescentou: esporão, edema; número 7; LADO TORNOZELO DIREITO]
```

A trava aponta:

- **palavra de conteúdo nova**, inclusive sigla ("AVC");
- **troca pelo oposto** de uma palavra ditada: hipo↔hiper↔iso, normal→anormal, regular→irregular;
- **número novo** e **unidade trocada** (5 mm → 5 cm);
- **negação a mais** ("há derrame" → "não há derrame");
- **LADO**:
  - um lado junto de uma estrutura em que ele não foi ditado ("lobo inferior direito" → "esquerdo");
  - uma lacuna [direito/esquerdo] preenchida pela IA;
- **linha entre colchetes inventada** (só os avisos do próprio sistema ficam fora da conta).

Não disparam a trava:

- correção de reconhecimento de voz ("calcanho" → "calcâneo", "horta" → "aorta", "tem dinopatia" → "tendinopatia");
- sigla escrita por extenso no título (TC → TOMOGRAFIA);
- achado repetido na conclusão.

O que a trava **não** pega: uma negação ditada que a IA tirou ("não há derrame" → "há derrame"). O modo formatar pode apagar frases da máscara que contradizem o achado, então retirar uma frase não é marcado. Confira sempre a conclusão.

Para ligar a trava também em outros modos, use `"modos_com_trava": ["formatar", "laudo"]`.

## Chaves (nunca no chat, nunca no config)

Cada provedor lê a chave de um arquivo na pasta do roteador ou de uma variável de ambiente:

| Provedor | Arquivo | Variável |
|---|---|---|
| anthropic | chave_anthropic.txt | ANTHROPIC_API_KEY |
| openai | chave_openai.txt | OPENAI_API_KEY |
| gemini | chave_gemini.txt | GEMINI_API_KEY |
| openrouter | chave_openrouter.txt | OPENROUTER_API_KEY |
| ollama (local) | não precisa | — |
| compativel | chave_compativel.txt | ROTRIX_API_KEY (URL em `provedores.compativel.url`) |

## Gasto

- `gasto.json` passou a guardar o gasto **por modelo** (`por_modelo`). O total do mês continua igual e é o que a bandeja mostra.
- `GET http://127.0.0.1:8123/v1/ia` devolve a situação da IA para o botão e o contador: provedor, rota por exame, quais chaves existem (sim ou não, nunca a chave), gasto e teto.
- Preços do GPT-5.6 (US$ por milhão de tokens, entrada/saída):
  - Luna 0,20/1,20 (página oficial);
  - Terra 2/12 e Sol 5/30 (fonte secundária, conferir).
- Se algum preço mudar: `"precos": {"gpt-5.6-terra": [2.5, 15]}` no config.json, sem mexer no código.
- Modelo que não está na tabela conta como caro (US$ 5 / 25 por milhão), para o teto do mês continuar valendo. O Ollama, que roda no computador, conta zero.
- Resposta vazia da IA também entra no gasto, porque a API cobra do mesmo jeito.

## Teste

`python testar_nuvem.py` roda sem internet e sem chave (respostas simuladas). Ele também roda no GitHub a cada envio.
