// bun src/components/rotrix2/raciocinio.test.ts
//
// 02/10: o botão de RACIOCÍNIO. Ele dita "descreva X" e quer a frase padrão; e os
// gatilhos do roteador encaixavam frase de outro achado antes de a IA ver o ditado.
// Decisão dele: o roteador vira um switch no botão de raciocínio.
//   desligado (padrão): grava cru ("transcribe"), a fala NÃO entra na folha, vai
//     para a IA como `ditado` (bloco DESCREVA no roteador)
//   ligado: grava pelo roteador, o que ele montou entra na folha e a IA recebe a fala
//     crua junto (`roteado: true`, bloco ROTEADO)
// Conferido de ponta a ponta no Chromium com eventos simulados; este teste segura a
// fiação para ela não voltar atrás sem ninguém ver.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
const rust = readFileSync(join(aqui, "../../../src-tauri/src/rotrix.rs"), "utf8");
const acoes = readFileSync(join(aqui, "../../../src-tauri/src/actions.rs"), "utf8");
const casos: [boolean, string][] = [
  [/modo === "completo" && !comRoteador \? "transcribe"/.test(laudo),
    "raciocínio sem roteador grava cru (sem passar pelos gatilhos)"],
  [/esperandoIA\.current && !comRoteadorRef\.current[\s\S]{0,200}rodarIA\(\{ ditado: texto \}\)/.test(laudo),
    "sem roteador: a fala vai para a IA como ditado e não entra na folha"],
  [/listen<string>\("rotrix-ditado-cru"/.test(laudo) && /rodarIA\(\{ ditado: falaCrua, roteado: true \}\)/.test(laudo),
    "com roteador: a IA recebe a fala crua e sabe que o roteador passou"],
  [/role="switch"/.test(laudo) && /GUARDADO_ROTEADOR/.test(laudo), "o switch existe e fica guardado"],
  [/if \(!texto && !ditado\)/.test(laudo), "folha vazia + ditado não é 'folha vazia'"],
  [/ditado: Option<String>/.test(rust) && /"ditado": ditado\.unwrap_or_default\(\)/.test(rust)
    && /"roteado": roteado\.unwrap_or\(false\)/.test(rust), "o comando do app leva ditado e roteado ao roteador"],
  [/emit\("rotrix-ditado-cru", transcription\.clone\(\)\)/.test(acoes) && /folha_vai_querer_o_texto\(\)/.test(acoes),
    "o app emite a fala crua antes da roteada, só para a folha"],
];

console.log("=== botão de raciocínio ===");
let ruim = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHOU"}  ${nome}`);
  if (!ok) ruim++;
}
if (ruim) {
  console.log(`\n${ruim} FALHA(S)`);
  process.exit(1);
}
console.log("\nraciocínio: tudo certo");
