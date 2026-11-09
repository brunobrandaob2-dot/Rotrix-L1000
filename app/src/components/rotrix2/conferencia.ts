// Rotrix L-1000 — conferência do laudo, ao vivo, sem IA (09/11).
//
// Saiu do expoweb de 09/11, aprovado por ele. Lê o texto da folha e aponta o que
// costuma escapar no plantão: técnica sem contraste × realce, lado trocado entre
// análise e conclusão, achado só na conclusão, medida na conclusão (regra dele),
// lacuna sem preencher, linha [conferir] esquecida, indicação fora do "Em anexo.".
// Conta local, sempre igual. Não muda o laudo: só aponta, e a trava pergunta ao
// copiar ou colar.

export type Grau = "vermelho" | "amarelo";

export interface Pendencia {
  grau: Grau;
  titulo: string;
  texto: string;
  trecho?: string;
}

export type Secoes = Record<string, string>;

export function secoes(t: string): Secoes {
  const s: Secoes = {};
  const re =
    /^(TÉCNICA|INDICAÇÃO CLÍNICA|INDICAÇÃO|ANÁLISE|COMPARAÇÃO|CONCLUSÃO|IMPRESSÃO|OPINIÃO)\s*:/gim;
  const marcas: { nome: string; ini: number; fim: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(t)))
    marcas.push({ nome: m[1].toUpperCase(), ini: m.index, fim: re.lastIndex });
  marcas.forEach((x, i) => {
    s[x.nome] = t
      .slice(x.fim, i + 1 < marcas.length ? marcas[i + 1].ini : t.length)
      .trim();
  });
  if (s["INDICAÇÃO"] !== undefined && s["INDICAÇÃO CLÍNICA"] === undefined)
    s["INDICAÇÃO CLÍNICA"] = s["INDICAÇÃO"];
  if (s["CONCLUSÃO"] === undefined)
    s["CONCLUSÃO"] = s["IMPRESSÃO"] ?? s["OPINIÃO"];
  return s;
}

export const frases = (t?: string): string[] =>
  (t || "")
    .split(/\n+|(?<=\.)\s+/)
    .map((x) => x.trim())
    .filter(Boolean);

const lado = (f: string): string | null =>
  /direit/i.test(f) ? "direito" : /esquerd/i.test(f) ? "esquerdo" : null;

// "renal" com \b: sem ele, "adrenal" e "suprarrenal" contavam como rim e a adrenal
// esquerda escondia a nefrolitíase trocada de lado (achado na prévia de 09/11)
const ORGAOS: { n: string; re: RegExp }[] = [
  { n: "rim", re: /\b(rim|rins|renal|renais)\b|nefro|calicinal|pielo/i },
  { n: "ureter", re: /ureter/i },
  { n: "ovário", re: /ovári|anex/i },
  { n: "mama", re: /\bmama/i },
  { n: "pulmão", re: /pulm|lobo (superior|médio|inferior)/i },
  { n: "adrenal", re: /adrenal|suprarrenal/i },
  { n: "joelho", re: /joelho/i },
  { n: "quadril", re: /quadril|coxofemoral/i },
  { n: "ombro", re: /ombro/i },
];

// achado da conclusão -> o que tem de existir na análise
const PARES: { c: RegExp; a: RegExp; nome: string }[] = [
  {
    c: /colelit/i,
    a: /colelit|c[aá]lculo[^.\n]*ves[ií]cula|ves[ií]cula[^.\n]*c[aá]lculo/i,
    nome: "colelitíase",
  },
  {
    c: /nefrolit/i,
    a: /nefrolit|c[aá]lculo[^.\n]*(rim|renal|calicinal|pielo)|(rim|renal|calicinal)[^.\n]*c[aá]lculo/i,
    nome: "nefrolitíase",
  },
  {
    c: /hidronefrose|ectasia pielocalicinal/i,
    a: /hidronefrose|dilata[çc][ãa]o[^.\n]*(coletor|pielocalicinal)|ectasia pielocalicinal/i,
    nome: "hidronefrose",
  },
  {
    c: /esteatose/i,
    a: /esteatose|atenua[çc][ãa]o|ecogenicidade/i,
    nome: "esteatose",
  },
  {
    c: /hepatomegalia/i,
    a: /hepatomegalia|f[ií]gado[^.\n]*aumentad/i,
    nome: "hepatomegalia",
  },
  { c: /derrame pleural/i, a: /derrame pleural/i, nome: "derrame pleural" },
  {
    c: /esplenomegalia/i,
    a: /esplenomegalia|ba[çc]o[^.\n]*aumentad/i,
    nome: "esplenomegalia",
  },
];

export function conferir(texto: string): Pendencia[] {
  const t = (texto || "").replace(/\*\*/g, "").replace(/ /g, " ");
  const out: Pendencia[] = [];
  if (!t.trim()) return out;
  const s = secoes(t);
  const tec = s["TÉCNICA"] || "";
  const an = s["ANÁLISE"] || "";
  const con = s["CONCLUSÃO"] || "";

  // 1. contraste na técnica × palavras de realce
  if (
    /sem (a )?(administra[çc][ãa]o (endovenosa )?d[eo] )?(meio de )?contraste/i.test(
      tec,
    ) &&
    !/ap[óo]s (a )?(administra|inje)/i.test(tec)
  ) {
    const m = an.match(
      /[^.\n]*(realce|realç|pérvi|falha de enchimento|impregna|opacificad)[^.\n]*/i,
    );
    if (m)
      out.push({
        grau: "vermelho",
        titulo: "TÉCNICA SEM CONTRASTE × REALCE",
        texto:
          "A técnica diz sem contraste, mas a análise fala em realce ou opacificação.",
        trecho: m[0].trim(),
      });
  }

  // 2. lado: conclusão × análise
  for (const fc of frases(con)) {
    const lc = lado(fc);
    if (!lc) continue;
    let org = ORGAOS.find((o) => o.re.test(fc));
    if (!org && /nefrolit|hidronefrose|pielo/i.test(fc)) org = ORGAOS[0];
    if (!org) continue;
    const ladosAn = new Set(
      frases(an)
        .filter((f) => org!.re.test(f))
        .map(lado)
        .filter((x): x is string => Boolean(x)),
    );
    if (ladosAn.size && !ladosAn.has(lc))
      out.push({
        grau: "vermelho",
        titulo: "LADO TROCADO",
        texto: `Conclusão: ${org.n} ${lc}. Análise: ${[...ladosAn].join(" e ")}.`,
        trecho: fc,
      });
  }

  // 3. achado da conclusão sem descrição na análise
  for (const p of PARES) {
    if (p.c.test(con) && !p.a.test(an))
      out.push({
        grau: "vermelho",
        titulo: "ACHADO SÓ NA CONCLUSÃO",
        texto: `"${p.nome}" está na conclusão e não está descrito na análise.`,
        trecho: frases(con).find((f) => p.c.test(f)),
      });
  }

  // 4. medida na conclusão (regra dele) e medida que não aparece na análise
  const anSemEspaco = an.replace(/\s/g, "");
  for (const fc of frases(con)) {
    const ms = fc.match(/\d+(?:[.,]\d+)?\s*(?:cm|mm)\b/gi);
    if (!ms) continue;
    const fora = ms.filter((x) => !anSemEspaco.includes(x.replace(/\s/g, "")));
    out.push({
      grau: "amarelo",
      titulo: "MEDIDA NA CONCLUSÃO",
      texto:
        "Sua regra: a medida fica na análise." +
        (fora.length ? ` E ${fora.join(", ")} não aparece na análise.` : ""),
      trecho: fc,
    });
  }

  // 5. lacunas e pendências
  const lac = t.match(
    /[^\n]*(@|___|\{[^}\n]*\}|\[(?!conferir)[^\]\n]*\])[^\n]*/i,
  );
  if (lac)
    out.push({
      grau: "amarelo",
      titulo: "LACUNA SEM PREENCHER",
      texto: "Ainda há @, ___ ou opção entre chaves ou colchetes.",
      trecho: lac[0].trim(),
    });
  if (/^\s*\[conferir/im.test(t))
    out.push({
      grau: "amarelo",
      titulo: "LINHA [CONFERIR] NA FOLHA",
      texto: "A linha de conferência da revisão ainda está no laudo.",
    });

  // 6. indicação
  const ind = s["INDICAÇÃO CLÍNICA"];
  if (ind !== undefined && !/^em anexo\.?$/i.test(ind.trim()))
    out.push({
      grau: "amarelo",
      titulo: "INDICAÇÃO",
      texto: 'Seu padrão é "Em anexo."',
      trecho: ind.trim() || "(vazia)",
    });

  return out;
}

/** Frase curta para o rodapé e para a trava. */
export function resumoDaConferencia(p: Pendencia[]): string {
  if (!p.length) return "sem pendências";
  const v = p.filter((x) => x.grau === "vermelho").length;
  return `${p.length} ${p.length === 1 ? "pendência" : "pendências"}${v ? ` (${v} ${v === 1 ? "grave" : "graves"})` : ""}`;
}
