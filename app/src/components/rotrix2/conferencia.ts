// Rotrix L-1000 — conferência do laudo, ao vivo, sem IA (09/11).
//
// Saiu do expoweb de 09/11, aprovado por ele. Lê o texto da folha e aponta o que
// costuma escapar no plantão: técnica sem contraste × realce, lado trocado entre
// análise e conclusão, achado só na conclusão, medida na conclusão (regra dele),
// lacuna sem preencher, linha [conferir] esquecida, indicação fora do "Em anexo.".
// Conta local, sempre igual. Sozinha não muda o laudo: aponta, e a trava pergunta
// ao copiar ou colar. 23/11 (pedido dele): cada aviso ganhou o seu "Corrigir" —
// o que é regra fixa (indicação, linha [conferir]) corrige aqui mesmo, sem IA; o
// que pede leitura do laudo (lado, achado, medida, contraste) vai para a IA com a
// ordem de mexer SÓ naquele ponto; lacuna leva o cursor até ela (o valor é dele).

export type Grau = "vermelho" | "amarelo";

/** Como o botão do aviso corrige: aqui (regra fixa), pela IA, ou indo até o lugar. */
export type Correcao =
  | { como: "local"; id: "indicacao" | "conferir"; rotulo: string }
  | { como: "ia"; instrucao: string; rotulo: string }
  | { como: "ir"; rotulo: string };

export interface Pendencia {
  grau: Grau;
  titulo: string;
  texto: string;
  trecho?: string;
  correcao?: Correcao;
}

const IA = (instrucao: string): Correcao => ({ como: "ia", instrucao, rotulo: "Corrigir com IA" });
const RE_INDICACAO = /^\s*(?:\*\*)?\s*INDICAÇÃO(?: CLÍNICA)?\s*(?:\*\*)?\s*:/i;
const RE_LACUNA = /@|___|\{[^}\n]*\}|\[(?!conferir)[^\]\n]*\]/i;
const RE_TITULO_SECAO = /^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{2,}\s*:/;

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
        correcao: IA(
          `A TÉCNICA diz sem contraste, mas a ANÁLISE fala em realce ou opacificação ("${m[0].trim()}"). ` +
            "Se o resto do laudo mostrar que houve contraste, corrija a TÉCNICA; senão, reescreva só esse trecho da ANÁLISE sem depender de contraste.",
        ),
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
        correcao: IA(
          `A CONCLUSÃO diz "${fc}", mas a ANÁLISE descreve ${org.n} ${[...ladosAn].join(" e ")}. ` +
            "Corrija o lado na CONCLUSÃO para ficar igual ao da ANÁLISE.",
        ),
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
        correcao: IA(
          `"${p.nome}" está na CONCLUSÃO e não está descrito na ANÁLISE. Descreva na ANÁLISE, na estrutura certa, ` +
            "só com o que a conclusão já diz, sem inventar medida, número ou detalhe.",
        ),
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
      correcao: IA(
        `A CONCLUSÃO tem medida ("${fc}"). Tire a medida da CONCLUSÃO` +
          (fora.length ? ` e leve ${fora.join(", ")} para a frase do achado na ANÁLISE.` : "; ela já está na ANÁLISE."),
      ),
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
      // lacuna na linha da indicação: o padrão dele resolve ("Em anexo.");
      // nas outras o valor é dele, e o botão leva o cursor até ela
      correcao: RE_INDICACAO.test(lac[0])
        ? { como: "local", id: "indicacao", rotulo: "Corrigir" }
        : { como: "ir", rotulo: "Ir até lá" },
    });
  if (/^\s*\[conferir/im.test(t))
    out.push({
      grau: "amarelo",
      titulo: "LINHA [CONFERIR] NA FOLHA",
      texto: "A linha de conferência da revisão ainda está no laudo.",
      correcao: { como: "local", id: "conferir", rotulo: "Tirar a linha" },
    });

  // 6. indicação
  const ind = s["INDICAÇÃO CLÍNICA"];
  if (ind !== undefined && !/^em anexo\.?$/i.test(ind.trim()))
    out.push({
      grau: "amarelo",
      titulo: "INDICAÇÃO",
      texto: 'Seu padrão é "Em anexo."',
      trecho: ind.trim() || "(vazia)",
      correcao: { como: "local", id: "indicacao", rotulo: 'Trocar por "Em anexo."' },
    });

  return out;
}

// ---------------------------------------------------------------------------
// Corrigir (23/11)
// ---------------------------------------------------------------------------

/** Uma ordem só para a IA, com todos os pontos que pedem leitura do laudo. */
export function instrucaoDeCorrecao(itens: Pendencia[]): string {
  const ordens = itens
    .map((p) => (p.correcao?.como === "ia" ? p.correcao.instrucao : ""))
    .filter(Boolean);
  if (!ordens.length) return "";
  return [
    "corrigir no laudo SOMENTE os pontos abaixo, sem mudar mais nada (o resto fica com as mesmas palavras e a mesma estrutura):",
    ...ordens.map((o) => `- ${o}`),
  ].join("\n");
}

/** As linhas da folha (blocos de 1º nível; texto solto vira bloco). */
const blocos = (folha: HTMLElement): HTMLElement[] => {
  for (const no of [...folha.childNodes])
    if (no.nodeType === Node.TEXT_NODE && (no.textContent || "").trim()) {
      const d = folha.ownerDocument.createElement("div");
      folha.replaceChild(d, no);
      d.appendChild(no);
    }
  return [...folha.children] as HTMLElement[];
};
const textoDe = (b: Element): string => (b.textContent || "").replace(/\u00a0/g, " ").trim();

/**
 * Indicação no padrão dele: "INDICAÇÃO CLÍNICA: Em anexo." Mexe só na linha da
 * indicação (e nas linhas de conteúdo logo abaixo, se o rótulo estava sozinho);
 * o rótulo fica em negrito. Devolve se mudou.
 */
export function corrigirIndicacao(folha: HTMLElement): boolean {
  const bs = blocos(folha);
  const i = bs.findIndex((b) => RE_INDICACAO.test(textoDe(b)));
  if (i < 0) return false;
  const b = bs[i];
  const doc = folha.ownerDocument;
  const t = textoDe(b);
  const fimDoRotulo = t.indexOf(":") + 1;
  const rotulo = t.slice(0, fimDoRotulo).replace(/\*\*/g, "").trim();
  const resto = t.slice(fimDoRotulo).replace(/\*\*/g, "").trim();
  if (/^em anexo\.?$/i.test(resto)) return false;
  // rótulo sozinho na linha: o conteúdo está nas linhas de baixo, até a próxima seção
  if (!resto)
    for (let j = i + 1; j < bs.length; j++) {
      const tj = textoDe(bs[j]);
      if (!tj || RE_TITULO_SECAO.test(tj)) break;
      bs[j].remove();
    }
  while (b.firstChild) b.removeChild(b.firstChild);
  const n = doc.createElement("b");
  n.textContent = rotulo;
  b.appendChild(n);
  b.appendChild(doc.createTextNode(" Em anexo."));
  return true;
}

/** Tira a(s) linha(s) "[conferir ...]" que a revisão deixou. */
export function tirarLinhasConferir(folha: HTMLElement): boolean {
  let mudou = false;
  for (const b of blocos(folha))
    if (/^\[conferir/i.test(textoDe(b))) {
      b.remove();
      mudou = true;
    }
  return mudou;
}

/** Seleciona a primeira lacuna (@, ___, {…}, […]) na folha e rola até ela. */
export function irAteLacuna(folha: HTMLElement): boolean {
  const doc = folha.ownerDocument;
  const andar = doc.createTreeWalker(folha, NodeFilter.SHOW_TEXT);
  for (let no = andar.nextNode(); no; no = andar.nextNode()) {
    const m = RE_LACUNA.exec(no.textContent || "");
    if (!m) continue;
    const r = doc.createRange();
    r.setStart(no, m.index);
    r.setEnd(no, m.index + m[0].length);
    const sel = doc.getSelection();
    folha.focus();
    sel?.removeAllRanges();
    sel?.addRange(r);
    (no.parentElement as HTMLElement | null)?.scrollIntoView({ block: "center" });
    return true;
  }
  return false;
}

/** Frase curta para o rodapé e para a trava. */
export function resumoDaConferencia(p: Pendencia[]): string {
  if (!p.length) return "sem pendências";
  const v = p.filter((x) => x.grau === "vermelho").length;
  return `${p.length} ${p.length === 1 ? "pendência" : "pendências"}${v ? ` (${v} ${v === 1 ? "grave" : "graves"})` : ""}`;
}
