// bun src/components/rotrix2/conferencia.test.ts
//
// 23/11: cada aviso da Conferência tem o seu "Corrigir". Confere QUAL correção
// cada aviso recebe (aqui, IA ou ir até lá) e a ordem que vai para a IA.
// A mexida na folha (corrigirIndicacao, tirarLinhasConferir, irAteLacuna) é
// conferida no navegador da prévia: precisa de DOM.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { conferir, instrucaoDeCorrecao } from "./conferencia";

let falhas = 0;
const confere = (nome: string, ok: boolean, extra?: unknown) => {
  console.log(`${ok ? "ok    " : "FALHA "} ${nome}${ok || extra === undefined ? "" : `  -> ${JSON.stringify(extra)}`}`);
  if (!ok) falhas++;
};

const doPrint = `TOMOGRAFIA COMPUTADORIZADA DO TÓRAX
TÉCNICA: exame realizado com técnica multislice, com administração de contraste iodado endovenoso.
INDICAÇÃO CLÍNICA: {indicação clínica}.
ANÁLISE:
Parênquima pulmonar sem opacidades.
CONCLUSÃO:
Exame dentro da normalidade.`;
const p1 = conferir(doPrint);
const lac = p1.find((p) => p.titulo === "LACUNA SEM PREENCHER");
const ind = p1.find((p) => p.titulo === "INDICAÇÃO");
confere("o caso do print: lacuna e indicação", Boolean(lac && ind), p1.map((p) => p.titulo));
confere("lacuna NA indicação: corrige aqui (Em anexo.)", lac?.correcao?.como === "local", lac?.correcao);
confere("indicação: corrige aqui, sem IA", ind?.correcao?.como === "local" && ind.correcao.id === "indicacao", ind?.correcao);
confere("só regra fixa: nada vai para a IA", instrucaoDeCorrecao(p1) === "");

const incoerente = `TOMOGRAFIA COMPUTADORIZADA DO ABDOME TOTAL
TÉCNICA: exame realizado sem administração de contraste.
INDICAÇÃO CLÍNICA: Em anexo.
ANÁLISE:
Rim direito com cálculo de 5 mm no grupo calicinal inferior. Aorta pérvia, sem falha de enchimento.
Medida do fígado: @ cm.
CONCLUSÃO:
Nefrolitíase à esquerda medindo 8 mm. Colelitíase.
[conferir: a IA trocou o lado]`;
const p2 = conferir(incoerente);
const de = (t: string) => p2.find((p) => p.titulo === t);
confere("lado trocado vai para a IA", de("LADO TROCADO")?.correcao?.como === "ia", de("LADO TROCADO")?.correcao);
confere("achado só na conclusão vai para a IA", de("ACHADO SÓ NA CONCLUSÃO")?.correcao?.como === "ia");
confere("medida na conclusão vai para a IA", de("MEDIDA NA CONCLUSÃO")?.correcao?.como === "ia");
confere("contraste × realce vai para a IA", de("TÉCNICA SEM CONTRASTE × REALCE")?.correcao?.como === "ia");
confere("lacuna fora da indicação: Ir até lá (o valor é dele)", de("LACUNA SEM PREENCHER")?.correcao?.como === "ir",
  de("LACUNA SEM PREENCHER")?.correcao);
confere("linha [conferir]: tira aqui", (() => {
  const c = de("LINHA [CONFERIR] NA FOLHA")?.correcao;
  return c?.como === "local" && c.id === "conferir";
})());
const ordem = instrucaoDeCorrecao(p2);
const linhas = ordem.split("\n");
confere("uma ordem só, começando por 'SOMENTE os pontos abaixo'", /SOMENTE os pontos abaixo/.test(linhas[0]), linhas[0]);
confere("um item por aviso que pede leitura (4)", linhas.filter((l) => l.startsWith("- ")).length === 4, linhas);
confere("a ordem cita o trecho do laudo", ordem.includes("Nefrolitíase à esquerda medindo 8 mm"));
confere("a ordem do achado proíbe inventar medida", /sem inventar medida/.test(ordem));
confere("a ordem não começa como o botão Revisar (o roteador trataria como revisão)",
  !/^revisar/i.test(ordem));

// a tela usa os botões e o Desfazer
const aqui = dirname(fileURLToPath(import.meta.url));
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
confere("cada aviso com correção mostra o botão", /\{p\.correcao\.rotulo\}/.test(laudo));
confere("Corrigir tudo existe", /Corrigir tudo/.test(laudo));
confere("o Desfazer volta o laudo de antes de tudo", /if \(locais\) setUltimoIA\(antes\)/.test(laudo));

console.log(`\nconferência (corrigir): ${falhas ? `${falhas} falha(s)` : "tudo certo"}`);
if (falhas) process.exit(1);
