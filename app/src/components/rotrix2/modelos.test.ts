// bun src/components/rotrix2/modelos.test.ts
//
// A TRAVA DO DINHEIRO. 26/09: 34 centavos em três laudos — 11,05¢ cada, que é
// exatamente a linha "laudo / Fable 5" do auditar_custo.py. No Haiku a mesma
// tarefa custa 1,10¢. Ninguém escolheu o Fable: o botão forte caía em
// `listaModelos[0]`, o primeiro id que a API devolve.
//
// Em 24/09 eu consertei esse defeito no botão LEVE e deixei o FORTE como estava.
// Ele instalou aquela versão e seguiu pagando dez vezes mais. Este teste existe
// para que nenhum botão volte a escolher modelo por ordem de lista.

import { escolherLeve, escolherForte, maisForte, maisBarato } from "./modelos";

// A lista como a API devolveu no dia — Fable em primeiro, que foi o estrago.
const LISTA = [
  { id: "claude-fable-5-1" },
  { id: "claude-opus-5-5" },
  { id: "claude-sonnet-5" },
  { id: "claude-haiku-4-5" },
];

const casos: [boolean, string][] = [
  // --- o defeito que custou os 34 centavos
  [escolherForte(LISTA, "", "") !== "claude-fable-5-1", "forte NÃO cai no primeiro da lista"],
  [escolherForte(LISTA, "", "") === "claude-opus-5-5", "forte sem nada escolhido = opus"],
  [maisForte(LISTA) === "claude-opus-5-5", "maisForte prefere opus a sonnet"],

  // --- a escolha dele manda, sempre
  [
    escolherForte(LISTA, "claude-haiku-4-5", "claude-opus-5-5") === "claude-haiku-4-5",
    "o que ele escolheu na barra ganha do config.json",
  ],
  [
    escolherForte(LISTA, "modelo-que-sumiu", "claude-sonnet-5") === "claude-sonnet-5",
    "escolha antiga que o provedor não tem mais cai no config.json",
  ],
  [
    escolherForte(LISTA, "", "claude-sonnet-5") === "claude-sonnet-5",
    "config.json ganha do palpite quando o provedor confirma o modelo",
  ],
  [
    escolherForte(LISTA, "", "modelo-que-nao-existe") === "claude-opus-5-5",
    "config.json com modelo inexistente não vira escolha",
  ],

  // --- o botão leve, que já estava certo, continua certo
  [maisBarato(LISTA) === "claude-haiku-4-5", "maisBarato acha o haiku"],
  [escolherLeve(LISTA, "") === "claude-haiku-4-5", "leve sem nada escolhido = haiku"],
  [
    escolherLeve(LISTA, "claude-sonnet-5") === "claude-sonnet-5",
    "leve respeita a escolha dele",
  ],

  // --- provedor desconhecido: nada reconhecido, aí sim o primeiro serve
  [escolherForte([{ id: "xyz-1" }, { id: "xyz-2" }], "", "") === "xyz-1", "sem pista, o primeiro"],
  [escolherForte([], "", "claude-opus-5-5") === "claude-opus-5-5", "lista vazia usa o config.json"],
  [escolherForte([], "", "") === "", "sem lista e sem config, devolve vazio"],
];

console.log("=== qual IA cada botão aciona ===");
let ruim = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHOU"}  ${nome}`);
  if (!ok) ruim++;
}
if (ruim) {
  console.log(`\n${ruim} FALHA(S) — algum botão voltou a escolher modelo por ordem de lista.`);
  process.exit(1);
}
console.log("\nescolha de modelo: nenhum botão paga caro por acaso");
