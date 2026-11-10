// bun src/components/rotrix2/laudo0911.test.ts
//
// 09/11: o que entrou na aba Laudo depois do expoweb aprovado — cronômetro do
// raciocínio, conferência ao vivo + trava ao copiar/colar, e as calculadoras novas
// do botão Cálculos. Os exemplos são os mesmos do expoweb que ele clicou.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { conferir, secoes, resumoDaConferencia } from "./conferencia";
import { CALCULADORAS, sugerirCalculadoras } from "./calculadoras";
import {
  formatarTempo,
  tituloDoExame,
  registrar,
  nomearUltimo,
  resumo,
  emCsv,
  type Tempo,
} from "./cronometro";

const aqui = dirname(fileURLToPath(import.meta.url));
const laudo = readFileSync(join(aqui, "LaudoPage.tsx"), "utf8");
const botoes = readFileSync(join(aqui, "BotoesDaFolha.tsx"), "utf8");
const roteador = readFileSync(join(aqui, "../../../../roteador-atual/roteador.py"), "utf8");
const telaIA = readFileSync(join(aqui, "../settings/rotrix/RotrixIA.tsx"), "utf8");
const rust = readFileSync(join(aqui, "../../../src-tauri/src/rotrix.rs"), "utf8");
const tiposRust = (rust.match(/const TIPOS_EXAME: &\[&str\] = &\[([\s\S]*?)\];/) || ["", ""])[1];

const INCOERENTE = `TOMOGRAFIA COMPUTADORIZADA DO ABDOME TOTAL

TÉCNICA: Cortes axiais volumétricos, sem administração de meio de contraste iodado endovenoso, com reconstruções multiplanares.

INDICAÇÃO CLÍNICA: Em anexo.

ANÁLISE:
Rins: cálculo no grupo calicinal inferior do rim direito, medindo 0,6 cm, sem dilatação do sistema coletor.
Fígado: nódulo hipodenso no segmento 7, medindo 1,2 cm, com realce periférico.
Vesícula biliar normodistendida, de paredes finas.
Baço, pâncreas e adrenais sem alterações.

CONCLUSÃO:
Nefrolitíase à esquerda.
Nódulo hepático de 1,4 cm, indeterminado.
Colelitíase.`;

const LIMPO = `TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO

TÉCNICA: Cortes axiais volumétricos, sem administração de meio de contraste iodado endovenoso.

INDICAÇÃO CLÍNICA: Em anexo.

ANÁLISE:
Parênquima encefálico com coeficientes de atenuação preservados.
Sistema ventricular de dimensões normais.

CONCLUSÃO:
Exame dentro dos limites da normalidade.`;

const ADRENAL = `TOMOGRAFIA COMPUTADORIZADA DO ABDOME SUPERIOR

TÉCNICA: Cortes axiais volumétricos antes e após a administração de meio de contraste iodado endovenoso.

INDICAÇÃO CLÍNICA: Em anexo.

ANÁLISE:
Adrenal esquerda: nódulo de contornos regulares, medindo 2,1 cm, com atenuação de 18 UH na fase sem contraste, 82 UH na fase portal e 38 UH na fase tardia.
Fígado com 32 UH; baço com 51 UH.

CONCLUSÃO:
Nódulo adrenal esquerdo.`;

const inc = conferir(INCOERENTE);
const titulos = inc.map((p) => p.titulo);
const conta = (t: string) => titulos.filter((x) => x === t).length;
const ad = CALCULADORAS.adrenal.calcular({
  u: "18",
  e: "82",
  d: "38",
  lado: "esquerdo",
  tam: "2,1",
});
const adLip = CALCULADORAS.adrenal.calcular({ u: "6" });
const est = CALCULADORAS.esteatose.calcular({ f: "32", b: "51" });
const estNao = CALCULADORAS.esteatose.calcular({ f: "58", b: "52" });
const vdt = CALCULADORAS.vdt.calcular({
  d1: "2026-03-10",
  a1: "8",
  b1: "7",
  c1: "7",
  d2: "2026-09-08",
  a2: "10",
  b2: "9",
  c2: "8",
});
const vdtCaiu = CALCULADORAS.vdt.calcular({
  d1: "2026-03-10",
  a1: "10",
  d2: "2026-09-08",
  a2: "9",
});
const evans = CALCULADORAS.evans.calcular({ f: "4,2", c: "13,1" });
const nascet = CALCULADORAS.nascet.calcular({
  a: "1,8",
  b: "5,2",
  lado: "direita",
});
const sug = sugerirCalculadoras(ADRENAL);
const tempos: Tempo[] = registrar([], {
  fim: "2026-11-09T10:00:00",
  segundos: 252,
  exame: "",
  como: "raciocinio",
});

const casos: [boolean, string][] = [
  // ---- conferência
  [
    conta("TÉCNICA SEM CONTRASTE × REALCE") === 1,
    "técnica sem contraste × 'realce periférico'",
  ],
  [
    inc.some(
      (p) =>
        p.titulo === "LADO TROCADO" &&
        /rim esquerdo/.test(p.texto) &&
        /direito/.test(p.texto),
    ),
    "lado trocado: nefrolitíase à esquerda × rim direito",
  ],
  [
    inc.some(
      (p) =>
        p.titulo === "ACHADO SÓ NA CONCLUSÃO" && /colelitíase/.test(p.texto),
    ),
    "colelitíase só na conclusão",
  ],
  [
    inc.some(
      (p) =>
        p.titulo === "MEDIDA NA CONCLUSÃO" &&
        /1,4 cm não aparece/.test(p.texto),
    ),
    "1,4 cm na conclusão e não na análise",
  ],
  [conferir(LIMPO).length === 0, "laudo limpo: nada a apontar"],
  [
    conferir(
      INCOERENTE.replace(
        "Baço, pâncreas e adrenais sem alterações.",
        "Adrenal esquerda: nódulo medindo 2,1 cm.",
      ),
    ).some((p) => p.titulo === "LADO TROCADO"),
    "adrenal esquerda não é rim: o lado trocado do rim continua aparecendo",
  ],
  [
    !conferir(ADRENAL).some((p) => p.titulo === "LADO TROCADO"),
    "nódulo adrenal esquerdo × adrenal esquerda: sem falso lado trocado",
  ],
  [
    conferir(ADRENAL).every(
      (p) => p.titulo !== "TÉCNICA SEM CONTRASTE × REALCE",
    ),
    "'antes e após' contraste não dispara a regra do sem contraste",
  ],
  [
    conferir(LIMPO.replace("Em anexo.", "Dor abdominal.")).some(
      (p) => p.titulo === "INDICAÇÃO",
    ),
    "indicação fora do 'Em anexo.'",
  ],
  [
    conferir(LIMPO + "\nNódulo de ___ cm.").some(
      (p) => p.titulo === "LACUNA SEM PREENCHER",
    ),
    "lacuna ___",
  ],
  [
    conferir("[conferir: 2 mudanças]\n" + LIMPO).some(
      (p) => p.titulo === "LINHA [CONFERIR] NA FOLHA",
    ),
    "linha [conferir] esquecida",
  ],
  [
    conferir(LIMPO.replace(/^/gm, "").replace("ANÁLISE:", "**ANÁLISE:**"))
      .length === 0,
    "negrito em ** não atrapalha",
  ],
  [
    secoes("IMPRESSÃO: Normal.")["CONCLUSÃO"] === "Normal.",
    "IMPRESSÃO vale como conclusão",
  ],
  [resumoDaConferencia(inc).includes("graves"), "resumo conta as graves"],
  [conferir("").length === 0, "folha vazia: nada"],
  // ---- calculadoras (mesmos números do expoweb)
  [
    ad.principal === "absoluto 68,8% · relativo 53,7%" &&
      ad.categoria?.tom === "verde",
    "adrenal 18/82/38: absoluto 68,8% e relativo 53,7%, adenoma",
  ],
  [
    /^Nódulo adrenal esquerdo, medindo 2,1 cm, com atenuação de 18 UH/.test(
      ad.frase || "",
    ),
    "frase da adrenal no formato dele",
  ],
  [
    adLip.categoria?.texto.startsWith("≤ 10 UH") === true,
    "adrenal ≤ 10 UH: rico em lípides sem precisar de washout",
  ],
  [
    est.categoria?.tom === "amarelo" && /−?-?19 UH/.test(est.principal || ""),
    "esteatose 32/51: critério (fígado − baço = −19)",
  ],
  [estNao.categoria?.tom === "cinza", "fígado 58 / baço 52: sem critério"],
  [
    vdt.principal === "VDT 207 dias · volume +83,7%" &&
      vdt.categoria?.tom === "vermelho",
    "VDT 8×7×7 → 10×9×8 mm em 182 dias: 207 dias (< 400, rápido)",
  ],
  [
    /de 205 mm³ para 377 mm³/.test(vdt.frase || ""),
    "VDT: volumes π/6 × a × b × c na frase",
  ],
  [
    vdtCaiu.categoria?.texto.startsWith("sem aumento") === true,
    "VDT com nódulo menor: não se aplica",
  ],
  [
    evans.principal === "Evans 0,32" && evans.categoria?.tom === "amarelo",
    "Evans 4,2/13,1 = 0,32 > 0,30",
  ],
  [
    nascet.principal === "65%" && nascet.categoria?.texto === "50–69%",
    "NASCET 1,8/5,2 = 65%",
  ],
  [
    CALCULADORAS.nascet.calcular({ a: "6", b: "5" }).erro !== undefined,
    "NASCET recusa luz residual maior que a distal",
  ],
  [
    sug.some(
      (s) =>
        s.id === "adrenal" &&
        s.valores.u === "18" &&
        s.valores.e === "82" &&
        s.valores.d === "38" &&
        s.valores.lado === "esquerdo",
    ),
    "sugestão: adrenal preenchida com 18/82/38",
  ],
  [
    sug.some(
      (s) =>
        s.id === "esteatose" && s.valores.f === "32" && s.valores.b === "51",
    ),
    "sugestão: esteatose preenchida com fígado e baço",
  ],
  [sugerirCalculadoras(LIMPO).length === 0, "sem UH: nenhuma sugestão"],
  // ---- cronômetro
  [
    formatarTempo(75) === "1:15" &&
      formatarTempo(3725) === "1:02:05" &&
      formatarTempo(0) === "0:00",
    "formato m:ss e h:mm:ss",
  ],
  [
    tituloDoExame("**TOMOGRAFIA COMPUTADORIZADA DO TÓRAX**\n\nTÉCNICA: …") ===
      "TOMOGRAFIA COMPUTADORIZADA DO TÓRAX",
    "título do exame vem da primeira linha",
  ],
  [
    tituloDoExame("Maria da Silva\nTOMOGRAFIA") === "" &&
      tituloDoExame("PACIENTE: JOSÉ") === "",
    "linha que não é exame não entra (§17)",
  ],
  [tituloDoExame("RADIOGRAFIA 1234567") === "", "número longo não entra"],
  [
    registrar([], {
      fim: "2026-11-09T10:00:00",
      segundos: 0,
      exame: "",
      como: "mao",
    }).length === 0,
    "clique sem querer (0 s) não conta",
  ],
  [
    registrar(Array(500).fill(tempos[0]), tempos[0]).length === 500,
    "guarda no máximo 500",
  ],
  [
    nomearUltimo(
      tempos,
      "RADIOGRAFIA DO JOELHO",
      new Date("2026-11-09T10:10:00"),
    )[0].exame === "RADIOGRAFIA DO JOELHO",
    "título entra depois, no copiar/colar",
  ],
  [
    nomearUltimo(
      tempos,
      "RADIOGRAFIA DO JOELHO",
      new Date("2026-11-09T11:00:00"),
    )[0].exame === "",
    "mais de 30 min depois: não nomeia",
  ],
  [
    resumo(tempos, new Date("2026-11-09T12:00:00")) ===
      "hoje: 1 exame · média 4:12 · total 4:12",
    "resumo do dia",
  ],
  [
    emCsv(tempos).split("\n")[1] ===
      '2026-11-09;10:00:00;252;4:12;"";raciocinio',
    "CSV para o Excel",
  ],
  // ---- ligação na aba Laudo
  [
    /gravando === "completo" && antes !== "completo"[\s\S]{0,120}cronoLigar\("raciocinio"\)/.test(
      laudo,
    ),
    "cronômetro liga com o raciocínio",
  ],
  [
    /antes === "completo" && gravando !== "completo"[\s\S]{0,40}cronoParar\(\)/.test(
      laudo,
    ),
    "cronômetro para quando o raciocínio desliga",
  ],
  [
    /const itens = conferir\(texto\);\s*if \(itens\.length && !forcar\)/.test(
      laudo,
    ),
    "trava no Copiar",
  ],
  [
    /const itens = conferir\(htmlEmTexto\(folha\.current\)\);\s*if \(itens\.length && !forcar\)/.test(
      laudo,
    ),
    "trava no Colar no RIS (e no Ctrl+Enter)",
  ],
  [
    /autoFocus onClick=\{\(\) => setTrava\(null\)\}/.test(laudo),
    "na trava, Enter volta (o foco fica em Voltar e corrigir)",
  ],
  [
    /window\.addEventListener\(EVENTO_CALCULADORA/.test(botoes) &&
      /Object\.values\(CALCULADORAS\)/.test(botoes),
    "Cálculos abre as calculadoras novas e a sugerida",
  ],
  [
    /setPainel\(\{ tipo: "calculos" \}\)/.test(botoes),
    "o volume de sempre continua no menu",
  ],
  [
    /setPainel\(\{ tipo: "medidas", exame: "densitometria" \}\)/.test(botoes),
    "botão Densitometria abre o painel de medidas (campos e conta no roteador)",
  ],
  [
    /export const INSTRUCAO_REVISAR = "revisar o laudo";/.test(laudo) &&
      /INSTRUCAO_REVISAR = "revisar o laudo"/.test(roteador),
    "Revisar: a instrução do app é a que o roteador reconhece",
  ],
  [
    /export const INSTRUCAO_ANALISAR_RX = "analisar a radiografia";/.test(laudo) &&
      /INSTRUCAO_ANALISAR_RX = "analisar a radiografia"/.test(roteador),
    "Analisar RX: a instrução do app é a que o roteador reconhece",
  ],
  [
    /if \(!imagensDaFolha\(folha\.current\)\.length\)[\s\S]{0,200}return;[\s\S]{0,40}rodarIA\(\{ instrucao: INSTRUCAO_ANALISAR_RX \}\)/.test(
      laudo,
    ),
    "Analisar RX sem radiografia na folha: avisa e não gasta IA",
  ],
  [
    ["revisar", "revisar_2", "analisar_rx"].every(
      (k) => telaIA.includes(`chave: "${k}"`) && tiposRust.includes(`"${k}"`),
    ),
    "Configurações > IA: linhas Botão Revisar, 2ª IA e Analisar RX (e o Rust grava as três)",
  ],
  [
    /usar a revisão da 2ª IA/.test(laudo) && /setSegunda\(\{/.test(laudo),
    "rodapé oferece trocar pela revisão da 2ª IA",
  ],
];

let falhas = 0;
for (const [ok, nome] of casos) {
  console.log(`${ok ? "ok    " : "FALHA "}  ${nome}`);
  if (!ok) falhas++;
}
console.log(
  `\nlaudo 09/11 (app): ${falhas ? `${falhas} FALHA(S)` : `tudo certo (${casos.length})`}`,
);
process.exit(falhas ? 1 : 0);
