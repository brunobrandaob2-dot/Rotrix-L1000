// bun src/components/rotrix2/juntar.test.ts
//
// 27/09: frases prontas ditadas uma a uma abriam uma linha "Parênquima pulmonar:"
// cada. Ele quer a estrutura numa linha só, com todas as frases dela.

import { chaveDaEstrutura, destinosNaFolha, juntarConteudo } from "./juntarEstrutura";

const casos: [boolean, string][] = [];
const igual = (a: unknown, b: unknown, nome: string) =>
  casos.push([JSON.stringify(a) === JSON.stringify(b), `${nome}${JSON.stringify(a) === JSON.stringify(b) ? "" : `  (veio ${JSON.stringify(a)})`}`]);

// --- o caso dele: três frases do parênquima, uma a uma
let linha = "bandas parenquimatosas basais.";
linha = juntarConteudo(linha, "estrias fibroatelectásicas nas bases pulmonares.");
linha = juntarConteudo(linha, "enfisema centrolobular nos lobos superiores.");
igual(
  linha,
  "bandas parenquimatosas basais. Estrias fibroatelectásicas nas bases pulmonares. Enfisema centrolobular nos lobos superiores.",
  "três frases do parênquima numa linha só, na ordem ditada",
);

// --- a normalidade da máscara sai quando chega o achado
igual(
  juntarConteudo("sem alterações significativas.", "enfisema centrolobular nos lobos superiores."),
  "enfisema centrolobular nos lobos superiores.",
  "'sem alterações significativas' sai quando chega achado",
);
igual(
  juntarConteudo(
    "atelectasias laminares nas bases pulmonares, sem distorção arquitetural. Não há consolidações ou nódulos suspeitos.",
    "enfisema centrolobular nos lobos superiores.",
  ),
  "atelectasias laminares nas bases pulmonares, sem distorção arquitetural. Enfisema centrolobular nos lobos superiores.",
  "a frase 'Não há...' do achado anterior sai (mesma regra do roteador)",
);
igual(
  juntarConteudo("enfisema centrolobular nos lobos superiores.", "enfisema centrolobular nos lobos superiores."),
  "enfisema centrolobular nos lobos superiores.",
  "a mesma frase ditada duas vezes não duplica",
);
igual(juntarConteudo("bandas basais", "enfisema."), "bandas basais. Enfisema.", "põe o ponto que faltava antes de juntar");

// --- 27/09 (2): a normalidade que chega com o achado novo não pode negar o que já está na linha
igual(
  juntarConteudo("consolidação no lobo inferior esquerdo.", "atelectasias laminares. Não há consolidações ou nódulos suspeitos."),
  "consolidação no lobo inferior esquerdo. Atelectasias laminares.",
  "sem contradição: 'Não há consolidações' sai quando há consolidação na linha",
);
igual(
  juntarConteudo("enfisema centrolobular.", "atelectasias laminares. Não há consolidações ou nódulos suspeitos."),
  "enfisema centrolobular. Atelectasias laminares. Não há consolidações ou nódulos suspeitos.",
  "normalidade que não contradiz fica",
);

// --- rótulo x cabeçalho
casos.push([chaveDaEstrutura("Parênquima pulmonar:  bandas.")?.chave === "parenquima pulmonar", "reconhece o rótulo de estrutura"]);
casos.push([chaveDaEstrutura("CONCLUSÃO:") === null, "CONCLUSÃO não é estrutura"]);
casos.push([chaveDaEstrutura("Técnica:  aquisição volumétrica.") === null, "TÉCNICA não é estrutura"]);
casos.push([chaveDaEstrutura("Sem alterações: nada") === null, "prosa que começa com 'Sem' não vira rótulo"]);

// --- onde cada frase entra
const folha = [
  "TOMOGRAFIA COMPUTADORIZADA DO TÓRAX",
  "",
  "TÉCNICA:  aquisição volumétrica.",
  "",
  "ANÁLISE:",
  "Parênquima pulmonar:  sem alterações significativas.",
  "Pleura:  sem derrames.",
  "",
  "CONCLUSÃO:",
  "Parênquima pulmonar:  (linha fora da análise, não conta)",
];
igual(
  destinosNaFolha(folha, ["Parênquima pulmonar:  enfisema centrolobular.", "Mediastino:  linfonodos."]),
  [5, -1],
  "parênquima vai para a linha dele NA ANÁLISE; estrutura que não existe entra normal",
);
igual(
  destinosNaFolha(["Parênquima pulmonar:  bandas.", "Pleura:  ok."], ["Parênquima pulmonar:  enfisema."]),
  [0],
  "folha sem ANÁLISE (só frases soltas): junta com a linha de mesma estrutura",
);
igual(destinosNaFolha(folha, ["Opacidades reticulares basais."]), [-1], "frase sem rótulo entra normal");

console.log("=== a mesma estrutura numa linha só ===");
let ruim = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHOU"}  ${nome}`);
  if (!ok) ruim++;
}
if (ruim) {
  console.log(`\n${ruim} FALHA(S)`);
  process.exit(1);
}
console.log("\njuntar estrutura: tudo certo");
