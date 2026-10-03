// 03/10: os comandos de voz da máscara, como ele digita na caixa da aba Máscaras.
// Aceita um por linha ou separados por "|" (o jeito do cabeçalho do arquivo).

/** "a | b" ou uma por linha -> lista limpa, sem repetição (sem diferenciar maiúscula) */
export const gatilhosDaCaixa = (t: string): string[] => {
  const vistos = new Set<string>();
  const fora: string[] = [];
  for (const g of t.split(/\n|\|/)) {
    const limpo = g.trim().replace(/\s+/g, " ");
    const chave = limpo.toLowerCase();
    if (limpo && !vistos.has(chave)) {
      vistos.add(chave);
      fora.push(limpo);
    }
  }
  return fora;
};
