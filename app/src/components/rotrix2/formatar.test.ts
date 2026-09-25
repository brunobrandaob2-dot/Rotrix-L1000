// bun src/components/rotrix2/formatar.test.ts
//
// O MODELO DE LAUDO ESTRUTURADO DELE. Ele cobrou isto de frente em 25/09:
//   "título, técnica, indicação clínica, análise, comparativo e conclusão, e estruturado
//    cada situação — fígado, dois pontos, em negrito, e aí a descrição do fígado.
//    Isso é o nosso modelo de laudo, isso não pode mudar."
//
// O que estava errado: `ROTULO` só reconhece rótulo em CAIXA ALTA, então os cabeçalhos
// de seção saíam em negrito e os rótulos de estrutura da ANÁLISE ("Fígado:", "Vias
// biliares:") saíam sem negrito nenhum — na folha e no que chega ao RIS.
//
// Este teste é a trava: se alguém mexer no renderizador e o rótulo perder o negrito, ou
// se prosa comum começar a virar rótulo, ele acusa.

import { linhaEmHtml } from "./formatar";

const CASOS: [string, boolean, string][] = [
  // cabeçalhos de seção — as cinco seções do banco
  ["**TOMOGRAFIA COMPUTADORIZADA DE ABDOME SUPERIOR E PELVE**", true, "título da máscara"],
  ["**TÉCNICA:**  aquisição volumétrica.", true, "cabeçalho já marcado"],
  ["TÉCNICA:  aquisição volumétrica.", true, "cabeçalho em caixa alta"],
  ["INDICAÇÃO CLÍNICA:  Em anexo.", true, "indicação clínica"],
  ["ANÁLISE:", true, "análise sozinha na linha"],
  ["COMPARAÇÃO:  estudos anteriores não disponíveis.", true, "comparação"],
  ["CONCLUSÃO:", true, "conclusão sozinha na linha"],

  // rótulos de estrutura dentro da ANÁLISE — o que estava saindo sem negrito
  ["Fígado:  de dimensões normais, contornos regulares.", true, "rótulo de uma palavra"],
  ["Baço:  de dimensões normais e densidade homogênea.", true, "rótulo curto"],
  ["Vias biliares:  sem dilatação.", true, "rótulo de duas palavras"],
  ["Transição toracoabdominal:  sem particularidades.", true, "rótulo longo"],
  ["Órgãos pélvicos:  sem particularidades.", true, "rótulo com acento na inicial"],
  ["Complexos ostiomeatais:  pérvios.", true, "rótulo técnico"],
  ["Musculatura paravertebral:  sem alterações.", true, "rótulo dos estruturados"],
  ["Parênquima encefálico:  coeficientes de atenuação preservados.", true, "rótulo do crânio"],
  ["Cone medular e cauda equina:  sem alterações.", true, "rótulo de quatro palavras"],

  // prosa NÃO pode virar rótulo
  ["Havia uma discreta quantidade de líquido livre na pelve.", false, "prosa comum"],
  ["Exame estável em relação ao estudo anterior, sem alterações significativas.", false,
   "frase do comparativo"],
  ["Nota-se imagem nodular no lobo superior direito, medindo 5 mm.", false,
   "prosa com vírgula"],
  ["Em relação ao estudo anterior de março de 2026: sem mudanças relevantes hoje.", false,
   "prosa longa com dois-pontos"],
  ["Fígado:", false, "rótulo sozinho, sem descrição — não é linha de análise"],

  // os rótulos MAIS LONGOS que existem de verdade no banco (52 chars, 7 palavras)
  ["Artérias carótidas externas e seus principais ramos:  pérvias.", true,
   "o rótulo mais longo do banco"],
  ["Artérias cerebrais anteriores, médias e posteriores:  pérvias.", true,
   "rótulo com vírgula no meio"],
  ["Articulações uncovertebrais e interapofisárias:  sem alterações.", true,
   "rótulo dos estruturados cervicais"],
  ["Arco aórtico e origens dos troncos supra-aórticos:  sem alterações.", true,
   "rótulo da angioTC"],
  ["Cone medular e cauda equina:  sem alterações.", true, "rótulo do cone medular"],

  // prosa que começa com ligação NUNCA é rótulo, mesmo curta e sem número
  ["Em relação ao estudo anterior: estável.", false, "prosa que começa com preposição"],
  ["Nota-se espessamento mural: segmento distal.", false, "prosa que começa com verbo"],
  ["Observa-se derrame pleural: à direita.", false, "outra prosa com verbo"],
  ["Sem alterações significativas: exame normal.", false, "prosa que começa com 'Sem'"],
  ["Achados de alto risco:  nenhum.", true, "rótulo real das coronárias"],
  ["Achados extracardíacos:  sem particularidades.", true, "outro rótulo das coronárias"],
];

let falhas = 0;
for (const [linha, esperaNegrito, nome] of CASOS) {
  const html = linhaEmHtml(linha);
  const temNegrito = html.includes("<b>");
  const ok = temNegrito === esperaNegrito;
  if (!ok) {
    falhas++;
    console.log(`FALHOU  ${nome}\n        esperava ${esperaNegrito ? "" : "SEM "}negrito -> ${html}`);
  } else {
    console.log(`ok      ${nome}`);
  }
}

// o negrito cobre SÓ o rótulo, nunca a descrição
const h = linhaEmHtml("Fígado:  de dimensões normais.");
if (!h.includes("<b>Fígado:</b>") || h.includes("normais.</b>")) {
  falhas++;
  console.log(`FALHOU  negrito cobre só o rótulo -> ${h}`);
} else {
  console.log("ok      negrito cobre só o rótulo, não a descrição");
}

// os DOIS espaços depois dos dois-pontos sobrevivem (é o formato do banco)
const d = linhaEmHtml("Fígado:  de dimensões normais.");
if (!d.includes("</b>  de dimens")) {
  falhas++;
  console.log(`FALHOU  os dois espaços do banco foram perdidos -> ${d}`);
} else {
  console.log("ok      os dois espaços depois dos dois-pontos sobrevivem");
}

console.log(falhas ? `\n${falhas} FALHA(S)` : "\nformatar: tudo certo");
if (falhas) process.exit(1);

// ---------------------------------------------------------------------------
// A PROVA DE VERDADE: os 232 rótulos de estrutura que existem no banco, não os
// que eu escolhi à mão. Gerado de dados/mascaras (rotulos_do_banco.json).
// ---------------------------------------------------------------------------
import banco from "./rotulos_do_banco.json";

const semNegrito = (banco.rotulos as string[]).filter(
  (r) => !linhaEmHtml(`${r}:  sem particularidades.`).includes("<b>"),
);
const negritoIndevido = (banco.prosa as string[]).filter((p) =>
  linhaEmHtml(p).includes("<b>"),
);

console.log(
  `\n${semNegrito.length ? "FALHOU" : "ok    "}  todos os ${banco.rotulos.length} rótulos do banco saem em negrito` +
    (semNegrito.length ? `\n        sem negrito: ${semNegrito.slice(0, 8).join(" | ")}` : ""),
);
console.log(
  `${negritoIndevido.length ? "FALHOU" : "ok    "}  nenhuma das ${banco.prosa.length} frases de prosa virou rótulo` +
    (negritoIndevido.length ? `\n        virou rótulo: ${negritoIndevido.slice(0, 5).join(" | ")}` : ""),
);
if (semNegrito.length || negritoIndevido.length) process.exit(1);
console.log("\nmodelo de laudo estruturado: intacto");
