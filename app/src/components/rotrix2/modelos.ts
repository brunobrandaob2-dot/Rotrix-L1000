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

/**
 * Pistas de id de modelo que NÃO conversa pela rota do roteador (/chat/completions):
 * codex e "-pro" da OpenAI só existem na API Responses (404), e os de áudio,
 * imagem, embedding e busca não escrevem laudo. 27/09: o Comparativo caía no
 * "gpt-5.1-codex-max" porque "max" é pista de forte — e dava 404.
 */
export const NAO_CONVERSA =
  /codex|^(?:gpt-[\w.]+|o\d+)-pro(-|$)|deep-research|turbo-instruct|embed|tts|whisper|dall-e|image|audio|realtime|moderation|transcri|\bsearch\b|sora/i;

/** O id conversa pela rota do roteador? (tira o "provedor:" da frente antes) */
export const conversa = (id: string): boolean => !NAO_CONVERSA.test((id || "").replace(/^[a-z]+:/, ""));

const conversam = <T extends { id: string }>(modelos: T[]): T[] =>
  modelos.filter((m) => conversa(m.id));

export const maisBarato = (modelos: { id: string }[]): string => {
  const ok = conversam(modelos);
  return ok.find((m) => PISTA_BARATO.test(m.id))?.id || ok[0]?.id || "";
};

/** O forte que a pista RECONHECE (opus > sonnet > ...); "" se nenhum id der pista. */
export const forteReconhecido = (modelos: { id: string }[]): string => {
  const fortes = conversam(modelos).filter((m) => PISTA_FORTE.test(m.id));
  return fortes.find((m) => /opus|ultra|max/i.test(m.id))?.id || fortes[0]?.id || "";
};

export const maisForte = (modelos: { id: string }[]): string =>
  forteReconhecido(modelos) || conversam(modelos)[0]?.id || "";

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

/** O mais forte, mas só do provedor do config. */
export const maisForteDoAtual = (modelos: { id: string }[]): string =>
  maisForte(doProvedorAtual(modelos));

/**
 * O modelo do Comparativo. 27/09: a tela do Comparativo mostrava SEMPRE o "mais
 * forte" calculado — trocar no seletor não pegava (voltava sozinho) e ainda
 * mexia no botão forte do Laudo por baixo. Agora:
 *   1. o que ELE escolheu no Comparativo (guardado à parte do Laudo)
 *   2. o forte reconhecível do provedor do config (opus, sonnet...)
 *   3. o modelo do config.json, se existe na lista (a OpenAI não dá pista no id)
 *   4. o primeiro do provedor do config que conversa
 */
export const escolherComparativo = (
  modelos: { id: string; provedor?: string }[],
  salvo: string,
  doConfig: string,
): string => {
  const atuais = doProvedorAtual(modelos);
  return (
    (existe(modelos, salvo) && conversa(salvo) && salvo) ||
    forteReconhecido(atuais) ||
    (existe(modelos, doConfig) && doConfig) ||
    maisForte(atuais) ||
    doConfig ||
    ""
  );
};
