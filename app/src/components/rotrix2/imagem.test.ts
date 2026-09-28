// bun src/components/rotrix2/imagem.test.ts
//
// 27/09: o print com a medida (TT-TG do protocolo de Lyon) estava na folha, mas
// o botão da IA mandava só o texto e depois apagava a imagem. Este teste segura:
//   1. só sai imagem posta pelo botão de imagem (data URL), na ordem da folha
//   2. o laudo que volta da IA traz as imagens de volta, no fim
//   3. a redução para a IA mantém a proporção e não aumenta imagem pequena
//   4. a LaudoPage manda as imagens e não escreve por cima delas

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { folhaComImagens, imagensDoHtml, medidaReduzida, motivoDaImagem } from "./imagemParaIA";

const aqui = dirname(fileURLToPath(import.meta.url));
const casos: [boolean, string][] = [];
const igual = (a: unknown, b: unknown, nome: string) =>
  casos.push([JSON.stringify(a) === JSON.stringify(b), `${nome}${JSON.stringify(a) === JSON.stringify(b) ? "" : `  (veio ${JSON.stringify(a)})`}`]);

const A = "data:image/png;base64,iVBORw0KGgoAAAA=";
const B = "data:image/jpeg;base64,/9j/4AAQSkZJRg==";
const folha =
  `<div><b>ANÁLISE:</b></div><div>Distância TT-TG direita:</div>` +
  `<div><img src="${A}" style="max-width:100%;height:auto"></div>` +
  `<div><img src="https://exemplo.com/x.png"></div>` +
  `<div><img alt="b" src="${B}"></div>`;

// 1
igual(imagensDoHtml(folha), [A, B], "as duas imagens da folha, na ordem; link externo não vai");
igual(imagensDoHtml("<div>só texto</div>"), [], "folha sem imagem: nada");
igual(imagensDoHtml(`<img src="data:image/svg+xml;base64,PHN2Zz4=">`), [], "SVG (pode ter texto escondido) não vai");

// 2
const volta = folhaComImagens("CONCLUSÃO:\nDistância TT-TG direita limítrofe (16 mm).", [A]);
casos.push([volta.includes("limítrofe (16 mm)") && volta.endsWith(`<div><img src="${A}" style="max-width:100%;height:auto" /></div>`),
  "o laudo da IA volta com a imagem no fim"]);
igual(imagensDoHtml(volta), [A], "a imagem que voltou é a mesma (original, não a reduzida)");

// 3
igual(medidaReduzida(3000, 1500), { w: 1568, h: 784 }, "3000x1500 -> 1568x784 (lado maior 1568)");
igual(medidaReduzida(800, 600), { w: 800, h: 600 }, "imagem pequena não é aumentada");
igual(medidaReduzida(1200, 4000), { w: 470, h: 1568 }, "retrato: o lado maior é a altura");

// motivos
casos.push([motivoDaImagem("imagens_demais").includes("no máximo 4"), "recusa por quantidade tem motivo em português"]);
casos.push([motivoDaImagem("nuvem_erro_http_500") === "", "erro que não é da imagem cai no aviso geral"]);

// 4
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
casos.push([/imagens:\s*paraIA/.test(laudo), "o botão da IA manda as imagens da folha"]);
casos.push([/folhaComImagens\(r\.texto,\s*imagens\)/.test(laudo), "o laudo que volta não apaga as imagens"]);
casos.push([!/folha\.current\.innerHTML = textoEmHtml\(r\.texto\)/.test(laudo), "ninguém mais escreve só o texto por cima da folha"]);
const rust = readFileSync(join(aqui, "../../../src-tauri/src/rotrix.rs"), "utf8");
casos.push([/imagens:\s*Option<Vec<String>>/.test(rust) && /"imagens":\s*imagens\.unwrap_or_default\(\)/.test(rust),
  "o comando do app leva as imagens ao roteador (opcional: o Histórico continua igual)"]);

console.log("=== imagem da folha para a IA ===");
let ruim = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHOU"}  ${nome}`);
  if (!ok) ruim++;
}
if (ruim) {
  console.log(`\n${ruim} FALHA(S)`);
  process.exit(1);
}
console.log("\nimagem para a IA: tudo certo");
