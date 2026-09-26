// Qual IA o botão da barra aciona — e, principalmente, qual ele NUNCA aciona
// por acidente.
//
// 26/09: ele gastou 34 centavos em três laudos, 11 centavos cada. A tabela do
// auditar_custo tem a linha exata: rota "laudo" no Fable 5 = 11,05¢. No Haiku a
// mesma tarefa custa 1,10¢.
//
// De onde veio: o botão FORTE caía em `listaModelos[0]` — o primeiro id que a
// API do provedor devolve, que não tem nada a ver com preço nem com qualidade.
// Em 24/09 eu consertei esse mesmo defeito no botão LEVE e deixei o FORTE como
// estava. Ele instalou aquela versão e continuou pagando o caro, escolhido por
// ninguém. O `maisForte()` já existia e era usado só no Comparativo.
//
// A regra agora, na ordem:
//   1. o que ELE escolheu na barra (fica salvo) — escolha dele sempre manda
//   2. o modelo do config.json, se o provedor confirmou que existe
//   3. o mais forte RECONHECÍVEL da lista (opus > sonnet > ...)
//   4. só então o primeiro da lista, quando nada foi reconhecido
//
// A lista vem da API do provedor instalado, nunca de tabela escrita aqui:
// tabela de fornecedor envelhece e amarra o app a uma marca só.
//
// 26/09 (tarde): ele pôs a chave da OpenAI, trocou para OpenAI e o laudo foi
// para o Claude Opus (13¢). A lista da OpenAI não respondia; sem modelo dela na
// lista, os passos 3 e 4 pegavam o mais forte que EXISTIA — de outro provedor,
// calado. Agora os palpites (3 e 4) só olham os modelos do provedor do config.
// Outro provedor só entra se ELE escolher na barra (passo 1). Se o provedor do
// config não respondeu, o botão fica no modelo do config e a chamada falha à
// vista, com o motivo, em vez de pagar outra conta sem ninguém saber.

/** Pistas de id do modelo BARATO de cada provedor. Dica de ordenação, não tabela. */
export const PISTA_BARATO = /haiku|mini|flash|lite|small|nano|fast|turbo/i;

/** Pistas de id do modelo FORTE. "opus" ganha de "sonnet" quando os dois existem. */
export const PISTA_FORTE = /opus|ultra|max|pro\b|large|sonnet/i;

export const maisBarato = (modelos: { id: string }[]): string =>
  modelos.find((m) => PISTA_BARATO.test(m.id))?.id || modelos[0]?.id || "";

export const maisForte = (modelos: { id: string }[]): string => {
  const fortes = modelos.filter((m) => PISTA_FORTE.test(m.id));
  return (
    fortes.find((m) => /opus|ultra|max/i.test(m.id))?.id || fortes[0]?.id || modelos[0]?.id || ""
  );
};

const existe = (modelos: { id: string }[], id: string): boolean =>
  !!id && modelos.some((m) => m.id === id);

/** Os provedores que o roteador põe na frente do id ("openai:gpt-…"). */
const PREFIXO_PROVEDOR = /^(anthropic|openai|gemini|openrouter|ollama|compativel):/;

/**
 * Só os modelos do provedor do config.json. O roteador manda os do provedor do
 * config com o id puro e os dos outros como "provedor:modelo" (com `provedor`).
 */
export const doProvedorAtual = <T extends { id: string; provedor?: string }>(
  modelos: T[],
): T[] => modelos.filter((m) => !m.provedor && !PREFIXO_PROVEDOR.test(m.id));

/** O modelo do botão leve: escolha dele, senão o mais barato DO PROVEDOR do config. */
export const escolherLeve = (modelos: { id: string }[], salvo: string): string => {
  if (existe(modelos, salvo)) return salvo;
  const atuais = doProvedorAtual(modelos);
  return atuais.length ? maisBarato(atuais) : "";
};

/**
 * O modelo do botão forte: escolha dele, senão o do config.json, senão o mais
 * forte RECONHECÍVEL — nunca o primeiro da lista por acaso.
 */
export const escolherForte = (
  modelos: { id: string }[],
  salvo: string,
  doConfig: string,
): string =>
  (existe(modelos, salvo) && salvo) ||
  (existe(modelos, doConfig) && doConfig) ||
  maisForte(doProvedorAtual(modelos)) ||
  doConfig ||
  "";

/** O mais forte, mas só do provedor do config (o Comparativo usa este). */
export const maisForteDoAtual = (modelos: { id: string }[]): string =>
  maisForte(doProvedorAtual(modelos));
