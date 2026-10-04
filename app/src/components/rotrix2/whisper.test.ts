// bun src/components/rotrix2/whisper.test.ts
//
// 04/10, ele: "instalei o whisper large v3, ele fica mais lento, tem como deixar ele
// mais rápido? tipo como você fez com o medium". O Medium da lista é comprimido
// (q4_1). O Large v3 inteiro, no processador, é o mais lento da lista. Entrou o
// Turbo comprimido (q5_0): o Large v3 com decodificador enxugado, metade do tamanho
// do Turbo cheio. Este teste segura a entrada na lista e o sha256 conferido.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const modelos = readFileSync(
  join(aqui, "../../../src-tauri/src/managers/model.rs"),
  "utf8",
);
const bloco = modelos.slice(
  modelos.indexOf('"turbo-q5".to_string()'),
  modelos.indexOf('"large".to_string()'),
);
const casos: [boolean, string][] = [
  [
    bloco.length > 0 && /id: "turbo-q5"/.test(bloco),
    "Turbo comprimido está na lista de modelos",
  ],
  [/ggml-large-v3-turbo-q5_0\.bin/.test(bloco), "arquivo q5_0 do Turbo"],
  [
    /394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2/.test(
      bloco,
    ),
    "sha256 igual ao do repositório oficial do whisper.cpp",
  ],
  [/supports_language_selection: true/.test(bloco), "deixa fixar o português"],
  [/whisper-medium-q4_1\.bin/.test(modelos), "o Medium comprimido continua"],
];
let falhas = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHA "}  ${nome}`);
  if (!ok) falhas++;
}
console.log(
  `\nwhisper (lista de modelos): ${falhas ? `${falhas} FALHA(S)` : "tudo certo"}`,
);
process.exit(falhas ? 1 : 0);
