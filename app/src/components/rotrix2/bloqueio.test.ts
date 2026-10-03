// bun src/components/rotrix2/bloqueio.test.ts
//
// 03/10: "pq a nuvem está dizendo que a IA está bloqueada?". A recusa da triagem
// (§17) aparecia como "a IA não respondeu (nuvem_bloqueada)". Agora diz o que e onde.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { motivoDoBloqueio } from "./bloqueio";

const aqui = dirname(fileURLToPath(import.meta.url));
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
const m = motivoDoBloqueio(
  "nuvem_bloqueada: sequência longa de dígitos “987654321” na folha",
);
const casos: [boolean, string][] = [
  [
    m ===
      "não enviei para a IA: sequência longa de dígitos “987654321” na folha. Tire isso e aperte de novo.",
    "recusa com o que e onde",
  ],
  [
    motivoDoBloqueio("nuvem_bloqueada").startsWith(
      "não enviei para a IA: o texto tem um identificador",
    ),
    "roteador velho (sem explicação): frase genérica, não 'não respondeu'",
  ],
  [
    motivoDoBloqueio("nuvem_teto") === "" && motivoDoBloqueio(undefined) === "",
    "outro motivo não vira recusa",
  ],
  [
    /const bloqueio = motivoDoBloqueio\(motivo\);\s*if \(bloqueio\) return bloqueio;\s*const m =/.test(
      laudo,
    ),
    "a aba Laudo usa a frase, antes de qualquer outro motivo",
  ],
];
let falhas = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHA "}  ${nome}`);
  if (!ok) falhas++;
}
console.log(
  `\nbloqueio (app): ${falhas ? `${falhas} FALHA(S)` : "tudo certo"}`,
);
process.exit(falhas ? 1 : 0);
