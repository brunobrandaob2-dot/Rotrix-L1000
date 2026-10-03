// bun src/components/rotrix2/mascaras.test.ts
//
// 03/10, pedidos dele, de uma vez:
//   - aba Máscaras: "um botão em que eu possa jogar ela direto na caixa de laudo" e
//     "eu quero que essa caixa de texto seja editável" (comandos de voz e texto)
//   - "a barra ao lado da IA mais fraca ... não estou conseguindo selecionar"
//   - escanometria e idade óssea: "colar um print com as medidas" (era só aviso)
// Este teste segura a fiação, para nada disso voltar atrás sem ninguém ver.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gatilhosDaCaixa } from "./gatilhos";

const aqui = dirname(fileURLToPath(import.meta.url));
const ler = (f: string) => readFileSync(join(aqui, f), "utf8");
const mascaras = ler("MascarasPage.tsx");
const casca = ler("Casca.tsx");
const laudo = ler("LaudoPage.tsx");
const botoes = ler("BotoesDaFolha.tsx");
const rust = ler("../../../src-tauri/src/rotrix.rs");
const lib = ler("../../../src-tauri/src/lib.rs");

const g = gatilhosDaCaixa("rx de ombro\n  raio x  do ombro | RX DE OMBRO\n\n");
const casos: [boolean, string][] = [
  [
    g.length === 2 && g[0] === "rx de ombro" && g[1] === "raio x do ombro",
    "comandos: um por linha ou com |, sem repetição e sem espaço sobrando",
  ],
  [gatilhosDaCaixa("  \n | ").length === 0, "caixa vazia: nenhum comando"],
  [
    /Pôr no laudo/.test(mascaras) &&
      /aoAbrirNoLaudo\?\.\(t, escolhida\.nome\)/.test(mascaras),
    "Máscaras: botão Pôr no laudo manda o texto da folha",
  ],
  [
    /aoAbrirNoLaudo=\{\(texto, nome\) => abrirNoLaudo\(texto, `máscara \$\{nome\}`\)\}/.test(
      casca,
    ),
    "Casca: Máscaras -> folha do Laudo",
  ],
  [
    /<textarea[\s\S]{0,200}value=\{gatEdit\}/.test(mascaras) &&
      /<textarea[\s\S]{0,200}value=\{corpoEdit\}/.test(mascaras),
    "Máscaras: comandos e texto em caixas editáveis",
  ],
  [
    /acao: "editar", titulo: escolhida\.titulo, gatilhos, depois: corpoEdit/.test(
      mascaras,
    ),
    "Máscaras: Salvar grava pela oficina (acao editar)",
  ],
  [
    /aria-label="IA do botão leve"/.test(laudo) &&
      /onChange=\{\(e\) => aoTrocarModeloLeve\(e\.target\.value\)\}/.test(
        laudo,
      ),
    "Laudo: o seletor do leve existe e troca",
  ],
  [
    /rotrix_ia_salvar", \{ ajustes: JSON\.stringify\(\{ modelo_leve: valor \}\)/.test(
      casca,
    ),
    "Casca: a escolha do leve vai para o config.json",
  ],
  [
    /novo\.get\("modelo_leve"\)/.test(rust),
    "Rust: rotrix_ia_salvar aceita modelo_leve",
  ],
  [
    !/setErro\(\s*"colar o print entra junto/.test(botoes) &&
      /lerPrint\(exame, dataUrl\)/.test(botoes),
    "Escanometria: o botão do print lê de verdade (não é mais só aviso)",
  ],
  [
    /lerPrint\("idade_ossea", dataUrl, \{ sexo \}\)/.test(botoes),
    "Idade óssea: só a imagem e o sexo vão (a data de nascimento fica)",
  ],
  [
    /fn rotrix_ler_print/.test(rust) && /rotrix::rotrix_ler_print,/.test(lib),
    "Rust: rotrix_ler_print existe e está registrado",
  ],
  [
    (botoes.match(/<ImagemNaFolha/g) || []).length === 2,
    "print e radiografia passam pelo recorte da folha (sem nome nos pixels, sem metadado)",
  ],
];
let falhas = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHA "}  ${nome}`);
  if (!ok) falhas++;
}
console.log(
  `\nmáscaras, leve e print (app): ${falhas ? `${falhas} FALHA(S)` : "tudo certo"}`,
);
process.exit(falhas ? 1 : 0);
