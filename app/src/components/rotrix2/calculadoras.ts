// Rotrix L-1000 — calculadoras novas do botão Cálculos (09/11).
//
// Vieram da lista do LeoRad (P1) e passaram pelo expoweb de 09/11, aprovado por ele.
// Mesma doutrina do calculos.py: conta local, sempre igual, sem IA; a frase sai no
// formato dele, com vírgula e uma casa onde a medida pede. Todo limiar daqui está
// marcado para a revisão clínica dele (DOSSIÊ 6.2).
//
// `sugerirCalculadoras` lê o texto da folha e devolve a calculadora já preenchida
// com os números ditados (ex.: adrenal com 18 / 82 / 38 UH).

export type IdCalc = "adrenal" | "esteatose" | "vdt" | "evans" | "nascet";
export type Tom = "verde" | "amarelo" | "vermelho" | "cinza";
export type Valores = Record<string, string>;

export interface Campo {
  id: string;
  rotulo: string;
  unidade?: string;
  tipo?: "numero" | "data" | "opcoes";
  opcoes?: string[];
}

export interface Resultado {
  erro?: string;
  principal?: string;
  categoria?: { tom: Tom; texto: string };
  frase?: string;
  conta?: string;
}

export interface Calculadora {
  id: IdCalc;
  nome: string;
  resumo: string;
  campos: Campo[];
  exemplo: Valores;
  referencia: string;
  calcular: (v: Valores) => Resultado;
}

export const num = (v: string | undefined): number | null => {
  if (v === undefined) return null;
  const x = parseFloat(String(v).replace(",", ".").trim());
  return Number.isFinite(x) ? x : null;
};

export const br = (x: number, casas = 1): string =>
  x.toFixed(casas).replace(".", ",");

const ADRENAL: Calculadora = {
  id: "adrenal",
  nome: "Adrenal — washout (TC)",
  resumo: "sem contraste, portal e tardia (15 min)",
  campos: [
    { id: "u", rotulo: "Sem contraste", unidade: "UH" },
    { id: "e", rotulo: "Fase portal", unidade: "UH" },
    { id: "d", rotulo: "Tardia (15 min)", unidade: "UH" },
    {
      id: "lado",
      rotulo: "Lado",
      tipo: "opcoes",
      opcoes: ["esquerdo", "direito"],
    },
    { id: "tam", rotulo: "Maior eixo", unidade: "cm" },
  ],
  exemplo: { u: "18", e: "82", d: "38", lado: "esquerdo", tam: "2,1" },
  referencia:
    "≤ 10 UH sem contraste; washout absoluto ≥ 60% ou relativo ≥ 40% (ACR, incidentaloma adrenal). Para sua revisão clínica.",
  calcular(v) {
    const u = num(v.u),
      e = num(v.e),
      d = num(v.d),
      tam = num(v.tam);
    const lado = v.lado || "esquerdo";
    const medida = tam !== null ? `, medindo ${br(tam)} cm` : "";
    if (u === null) return { erro: "Falta a fase sem contraste." };
    if (u <= 10)
      return {
        principal: `${br(u, 0)} UH sem contraste`,
        categoria: { tom: "verde", texto: "≤ 10 UH: adenoma rico em lípides" },
        frase: `Nódulo adrenal ${lado}${medida}, com atenuação de ${br(u, 0)} UH na fase sem contraste, compatível com adenoma rico em lípides.`,
      };
    if (e === null || d === null)
      return {
        erro: "Acima de 10 UH: faltam as fases portal e tardia para o washout.",
      };
    if (e <= u)
      return { erro: "A fase portal tem de ser maior que a sem contraste." };
    const abs = ((e - d) / (e - u)) * 100;
    const rel = ((e - d) / e) * 100;
    const adenoma = abs >= 60 || rel >= 40;
    return {
      principal: `absoluto ${br(abs)}% · relativo ${br(rel)}%`,
      categoria: adenoma
        ? {
            tom: "verde",
            texto: "washout de adenoma (absoluto ≥ 60% ou relativo ≥ 40%)",
          }
        : { tom: "amarelo", texto: "washout não característico de adenoma" },
      frase:
        `Nódulo adrenal ${lado}${medida}, com atenuação de ${br(u, 0)} UH na fase sem contraste, ` +
        `${br(e, 0)} UH na fase portal e ${br(d, 0)} UH na fase tardia, com washout absoluto de ` +
        `${br(abs)}% e relativo de ${br(rel)}%, ${adenoma ? "compatível com adenoma" : "não característico de adenoma"}.`,
      conta:
        "absoluto = (portal − tardia) ÷ (portal − sem contraste) × 100 · relativo = (portal − tardia) ÷ portal × 100",
    };
  },
};

const ESTEATOSE: Calculadora = {
  id: "esteatose",
  nome: "Esteatose — TC sem contraste",
  resumo: "fígado e baço em UH",
  campos: [
    { id: "f", rotulo: "Fígado (média de ROIs)", unidade: "UH" },
    { id: "b", rotulo: "Baço", unidade: "UH" },
  ],
  exemplo: { f: "32", b: "51" },
  referencia:
    "Critério: fígado < 40 UH ou fígado − baço < −10 UH. Graus leves não são detectados com segurança pela TC sem contraste. Para sua revisão clínica.",
  calcular(v) {
    const f = num(v.f),
      b = num(v.b);
    if (f === null) return { erro: "Falta o fígado." };
    const dif = b !== null ? f - b : null;
    const sim = f < 40 || (dif !== null && dif < -10);
    const baco = b !== null ? `, baço com ${br(b, 0)} UH` : "";
    return {
      principal: `fígado ${br(f, 0)} UH${dif !== null ? ` · fígado − baço = ${br(dif, 0)} UH` : ""}`,
      categoria: sim
        ? {
            tom: "amarelo",
            texto: "critério de esteatose moderada a acentuada",
          }
        : {
            tom: "cinza",
            texto: "sem critério tomográfico de esteatose moderada a acentuada",
          },
      frase: sim
        ? `Redução difusa da atenuação do parênquima hepático (${br(f, 0)} UH${baco}), compatível com esteatose moderada a acentuada.`
        : `Atenuação do parênquima hepático de ${br(f, 0)} UH${b !== null ? ` (baço com ${br(b, 0)} UH)` : ""}, sem sinais tomográficos de esteatose moderada a acentuada.`,
      conta: "fígado < 40 UH ou fígado − baço < −10 UH",
    };
  },
};

const VDT: Calculadora = {
  id: "vdt",
  nome: "Nódulo — tempo de duplicação (VDT)",
  resumo: "dois exames, eixos em mm",
  campos: [
    { id: "d1", rotulo: "Data do 1º exame", tipo: "data" },
    { id: "a1", rotulo: "1º · eixo maior", unidade: "mm" },
    { id: "b1", rotulo: "1º · eixo 2 (opcional)", unidade: "mm" },
    { id: "c1", rotulo: "1º · eixo 3 (opcional)", unidade: "mm" },
    { id: "d2", rotulo: "Data do 2º exame", tipo: "data" },
    { id: "a2", rotulo: "2º · eixo maior", unidade: "mm" },
    { id: "b2", rotulo: "2º · eixo 2 (opcional)", unidade: "mm" },
    { id: "c2", rotulo: "2º · eixo 3 (opcional)", unidade: "mm" },
  ],
  exemplo: {
    d1: "2026-03-10",
    a1: "8",
    b1: "7",
    c1: "7",
    d2: "2026-09-08",
    a2: "10",
    b2: "9",
    c2: "8",
  },
  referencia:
    "V = π/6 × a × b × c; VDT = Δt × ln2 ÷ ln(V2/V1). < 400 / 400–600 / > 600 dias (NELSON). Sem eixos 2 e 3, usa o eixo maior nos três. Para sua revisão clínica.",
  calcular(v) {
    const vol = (a: number, b: number | null, c: number | null) =>
      (Math.PI / 6) * a * (b ?? a) * (c ?? b ?? a);
    const a1 = num(v.a1),
      a2 = num(v.a2);
    if (!v.d1 || !v.d2 || a1 === null || a2 === null)
      return { erro: "Faltam as duas datas e o eixo maior dos dois exames." };
    const dias = (Date.parse(v.d2) - Date.parse(v.d1)) / 864e5;
    if (!(dias > 0)) return { erro: "O 2º exame tem de ser depois do 1º." };
    const v1 = vol(a1, num(v.b1), num(v.c1));
    const v2 = vol(a2, num(v.b2), num(v.c2));
    const cresc = (v2 / v1 - 1) * 100;
    if (v2 <= v1)
      return {
        principal: `volume ${br(v1, 0)} → ${br(v2, 0)} mm³`,
        categoria: {
          tom: "verde",
          texto: "sem aumento de volume (VDT não se aplica)",
        },
        frase: `Nódulo sem aumento de volume no intervalo de ${Math.round(dias)} dias.`,
      };
    const t = (dias * Math.LN2) / Math.log(v2 / v1);
    const categoria: Resultado["categoria"] =
      t < 400
        ? { tom: "vermelho", texto: "< 400 dias: crescimento rápido" }
        : t <= 600
          ? { tom: "amarelo", texto: "400–600 dias: intermediário" }
          : { tom: "verde", texto: "> 600 dias: crescimento lento" };
    return {
      principal: `VDT ${Math.round(t)} dias · volume +${br(cresc)}%`,
      categoria,
      frase:
        `Nódulo com aumento volumétrico de ${br(cresc)}% em ${Math.round(dias)} dias ` +
        `(de ${br(v1, 0)} mm³ para ${br(v2, 0)} mm³), com tempo de duplicação volumétrica estimado em ${Math.round(t)} dias.`,
      conta: "V = π/6 × a × b × c · VDT = Δt × ln2 ÷ ln(V2/V1)",
    };
  },
};

const EVANS: Calculadora = {
  id: "evans",
  nome: "Índice de Evans",
  resumo: "cornos frontais ÷ diâmetro interno do crânio",
  campos: [
    { id: "f", rotulo: "Maior largura dos cornos frontais", unidade: "cm" },
    { id: "c", rotulo: "Maior diâmetro interno do crânio", unidade: "cm" },
  ],
  exemplo: { f: "4,2", c: "13,1" },
  referencia: "Limiar 0,30 (Evans). Para sua revisão clínica.",
  calcular(v) {
    const f = num(v.f),
      c = num(v.c);
    if (f === null || c === null || c <= 0)
      return { erro: "Faltam as duas medidas." };
    const i = f / c;
    return {
      principal: `Evans ${br(i, 2)}`,
      categoria:
        i > 0.3
          ? { tom: "amarelo", texto: "> 0,30: ventriculomegalia" }
          : { tom: "verde", texto: "≤ 0,30" },
      frase: `Índice de Evans de ${br(i, 2)}${i > 0.3 ? ", acima de 0,30" : ""}.`,
      conta: "Evans = cornos frontais ÷ diâmetro interno do crânio",
    };
  },
};

const NASCET: Calculadora = {
  id: "nascet",
  nome: "Estenose carotídea — NASCET",
  resumo: "angio-TC, diâmetros em mm",
  campos: [
    { id: "a", rotulo: "Menor luz residual (estenose)", unidade: "mm" },
    { id: "b", rotulo: "ACI distal normal", unidade: "mm" },
    {
      id: "lado",
      rotulo: "Lado",
      tipo: "opcoes",
      opcoes: ["direita", "esquerda"],
    },
  ],
  exemplo: { a: "1,8", b: "5,2", lado: "direita" },
  referencia:
    "< 50 / 50–69 / ≥ 70% (NASCET 1991). Quase-oclusão se descreve à parte. Para sua revisão clínica.",
  calcular(v) {
    const a = num(v.a),
      b = num(v.b);
    if (a === null || b === null) return { erro: "Faltam as duas medidas." };
    if (a >= b)
      return { erro: "A luz residual tem de ser menor que a ACI distal." };
    const p = (1 - a / b) * 100;
    const categoria: Resultado["categoria"] =
      p < 50
        ? { tom: "verde", texto: "< 50%" }
        : p < 70
          ? { tom: "amarelo", texto: "50–69%" }
          : { tom: "vermelho", texto: "≥ 70%" };
    return {
      principal: `${Math.round(p)}%`,
      categoria,
      frase:
        `Estenose da artéria carótida interna ${v.lado || "direita"} estimada em ${Math.round(p)}% pelos critérios NASCET ` +
        `(luz residual de ${br(a)} mm; ACI distal de ${br(b)} mm).`,
      conta: "NASCET = (1 − luz residual ÷ ACI distal normal) × 100",
    };
  },
};

export const CALCULADORAS: Record<IdCalc, Calculadora> = {
  adrenal: ADRENAL,
  esteatose: ESTEATOSE,
  vdt: VDT,
  evans: EVANS,
  nascet: NASCET,
};

export interface Sugestao {
  id: IdCalc;
  texto: string;
  valores: Valores;
}

/** O laudo cita a medida → a calculadora certa, já preenchida com o que foi ditado. */
export function sugerirCalculadoras(texto: string): Sugestao[] {
  const t = (texto || "").replace(/\*\*/g, "");
  const out: Sugestao[] = [];
  const ad = t.match(/adrenal[^\n]*/i);
  if (ad) {
    const uh = [...ad[0].matchAll(/(-?\d+(?:[.,]\d+)?)\s*UH/gi)].map(
      (m) => m[1],
    );
    const lado = /direit/i.test(ad[0]) ? "direito" : "esquerdo";
    const tam = (ad[0].match(/(\d+(?:[.,]\d+)?)\s*cm/i) || [])[1];
    if (uh.length >= 3)
      out.push({
        id: "adrenal",
        texto: `Adrenal ${lado === "direito" ? "direita" : "esquerda"} com ${uh.slice(0, 3).join(" / ")} UH (sem contraste / portal / tardia).`,
        valores: {
          u: uh[0],
          e: uh[1],
          d: uh[2],
          lado,
          ...(tam ? { tam } : {}),
        },
      });
    else if (uh.length)
      out.push({
        id: "adrenal",
        texto: "Adrenal com UH citada (faltam fases para o washout).",
        valores: { u: uh[0], lado },
      });
  }
  const fg = t.match(/f[ií]gado[^\n]*?(-?\d+(?:[.,]\d+)?)\s*UH/i);
  const bc = t.match(/ba[çc]o[^\n]*?(-?\d+(?:[.,]\d+)?)\s*UH/i);
  if (fg && bc)
    out.push({
      id: "esteatose",
      texto: `Fígado ${fg[1]} UH e baço ${bc[1]} UH.`,
      valores: { f: fg[1], b: bc[1] },
    });
  return out;
}

/** Evento que a aba Laudo dispara para o botão Cálculos abrir a calculadora preenchida. */
export const EVENTO_CALCULADORA = "rotrix:calculadora";
