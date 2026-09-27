// bun src/components/rotrix2/tema.test.ts
//
// 27/09: no tema escuro ele quer a folha cinza-chumbo bem escuro com letra
// branca. Estava `bg-white text-black` fixo em dez lugares. Este teste segura:
//   1. nenhuma folha do Rotrix volta a ter cor fixa (tem de seguir o tema)
//   2. o tema escuro tem papel escuro e letra branca; o claro, branco e preto
//   3. o Ctrl+C das folhas passa pela cópia limpa (senão a letra BRANCA da tela
//      vai para o RIS e o laudo some no fundo branco de lá)

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// import.meta.dir é só do Bun: o tsc do build do .exe não conhece e PARA o build
// (27/09: foi isso que segurou a versão nova no GitHub)
const aqui = dirname(fileURLToPath(import.meta.url));
const casos: [boolean, string][] = [];

const telas = readdirSync(aqui).filter((f) => f.endsWith(".tsx"));
const comCorFixa = telas.filter((f) =>
  /\bbg-white\b|\btext-black\b/.test(readFileSync(join(aqui, f), "utf8")),
);
casos.push([comCorFixa.length === 0, "nenhuma folha com branco/preto fixo: " + (comCorFixa.join(", ") || "ok")]);

const tema = readFileSync(join(aqui, "../../styles/theme.css"), "utf8");
const valor = (nome: string) => (tema.match(new RegExp(`--${nome}:\\s*([^;]+);`)) || [])[1]?.trim() || "";
casos.push([valor("dark-color-papel") === "#1e1f21", "escuro: papel cinza-chumbo (#1e1f21)"]);
casos.push([valor("dark-color-papel-texto") === "#ffffff", "escuro: letra branca"]);
casos.push([valor("light-color-papel") === "#ffffff" && valor("light-color-papel-texto") === "#000000",
  "claro: continua papel branco e letra preta"]);
const escuros = (tema.match(/--color-papel:\s*var\(--dark-color-papel\)/g) || []).length;
casos.push([escuros === 2, "escuro vale pelo Windows (prefers-color-scheme) E pela escolha no app (data-theme)"]);

const app = readFileSync(join(aqui, "../../App.css"), "utf8");
casos.push([/\.papel\s*\{[^}]*--color-papel\)/.test(app), "classe .papel usa as cores do tema"]);
casos.push([/\[data-rotrix="folha"\] \*[^}]*color: inherit !important/.test(app),
  "texto colado com cor própria não some no escuro"]);

const casca = readFileSync(join(aqui, "Casca.tsx"), "utf8");
casos.push([/ligarCopiaLimpa\(\)/.test(casca), "cópia limpa ligada (Ctrl+C não leva a cor da tela)"]);
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
casos.push([/data-rotrix="folha"/.test(laudo) && /\bpapel\b/.test(laudo), "folha do Laudo segue o tema"]);

console.log("=== folha no tema claro e escuro ===");
let ruim = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHOU"}  ${nome}`);
  if (!ok) ruim++;
}
if (ruim) {
  console.log(`\n${ruim} FALHA(S)`);
  process.exit(1);
}
console.log("\ntema da folha: tudo certo");
