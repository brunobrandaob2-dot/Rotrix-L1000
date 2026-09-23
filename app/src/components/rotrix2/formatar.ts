// Rotrix L-1000 v2 — texto do ditado/IA -> HTML da folha.
//
// O que voltava do roteador entrava como texto cru: a máscara perdia os
// títulos em negrito e as linhas longas passavam da margem da folha. Aqui o
// texto vira HTML com as mesmas marcas que o colador usa no RIS.

const escapar = (s: string): string =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

// Rótulos que a máscara usa no começo da linha ("TÉCNICA:", "CONCLUSÃO:").
const ROTULO = /^([A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÇ0-9 ./()-]{2,40}:)(\s*)(.*)$/;

const soMaiusculas = (linha: string): boolean => {
  const letras = linha.replace(/[^A-Za-zÁ-Úá-ú]/g, "");
  return letras.length >= 4 && letras === letras.toUpperCase();
};

/** `**assim**` vira negrito de verdade; o resto é escapado. */
const marcasEmNegrito = (linha: string): string =>
  escapar(linha)
    .split("**")
    .map((parte, i) => (i % 2 === 1 ? `<b>${parte}</b>` : parte))
    .join("");

/** Uma linha de laudo em HTML, com o título/rótulo em negrito. */
export const linhaEmHtml = (linha: string): string => {
  const cru = linha.replace(/\s+$/, "");
  if (!cru.trim()) return "<div><br></div>";
  // O roteador já devolve a máscara marcada ("**TÉCNICA:** ..."), porque é
  // assim que o colador faz negrito. Sem isto, os ** apareciam na folha.
  if (cru.split("**").length > 2) {
    return `<div>${marcasEmNegrito(cru)}</div>`;
  }
  const m = ROTULO.exec(cru);
  if (m) {
    return `<div><b>${escapar(m[1])}</b>${escapar(m[2] + m[3])}</div>`;
  }
  if (soMaiusculas(cru)) {
    return `<div><b>${escapar(cru)}</b></div>`;
  }
  return `<div>${escapar(cru)}</div>`;
};

/** Texto inteiro (máscara, laudo da IA) no HTML que a folha mostra. */
export const textoEmHtml = (texto: string): string =>
  (texto || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map(linhaEmHtml)
    .join("");

/** O que está na folha, de volta para texto — é isso que vai para o RIS. */
export const htmlEmTexto = (el: HTMLElement | null): string =>
  (el?.innerText || "").replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim();

/** Um bloco é um parágrafo na folha? (div, p, li, br viram quebra de linha) */
const BLOCO = /^(?:div|p|li|tr|h[1-6]|blockquote|pre|section|article)$/i;

const ehNegrito = (el: HTMLElement): boolean => {
  const nome = el.tagName.toLowerCase();
  if (nome === "b" || nome === "strong") return true;
  const peso = el.style?.fontWeight || "";
  return peso === "bold" || (Number(peso) >= 600);
};

/**
 * A folha vira TEXTO MARCADO: o que está em negrito sai entre `**`, uma linha
 * por parágrafo.
 *
 * É o formato que o colador (colador.exe) espera: ele transforma `**` em
 * negrito de verdade no RTF e no HTML do clipboard, e tira as marcas do texto
 * puro. Mandar innerText (como antes) chegava no RIS sem negrito nenhum.
 */
export const htmlEmMarcado = (raiz: HTMLElement | null): string => {
  if (!raiz) return "";
  const ABRE = "\u0001";
  const FECHA = "\u0002";
  const partes: string[] = [];

  const anda = (no: Node) => {
    if (no.nodeType === Node.TEXT_NODE) {
      const bruto = no.textContent || "";
      // indentação entre blocos (o "\n  " do HTML) não é conteúdo da folha
      if (/^\s*$/.test(bruto) && bruto.includes("\n")) return;
      const t = bruto.replace(/\u00a0/g, " ");
      if (t) partes.push(t);
      return;
    }
    if (no.nodeType !== Node.ELEMENT_NODE) return;
    const el = no as HTMLElement;
    const nome = el.tagName.toLowerCase();
    if (nome === "br") {
      partes.push("\n");
      return;
    }
    if (BLOCO.test(nome) && partes.length > 0) partes.push("\n");
    const forte = ehNegrito(el);
    if (forte) partes.push(ABRE);
    el.childNodes.forEach(anda);
    if (forte) partes.push(FECHA);
  };

  raiz.childNodes.forEach(anda);

  // Uma linha por vez: o negrito nunca atravessa a quebra — senão o cabeçalho
  // da linha de baixo entrava no mesmo par de ** do de cima.
  const linhas = partes.join("").split("\n").map((linha) => {
    let abertos = 0;
    let saida = "";
    for (const c of linha) {
      if (c === ABRE) {
        if (abertos === 0) saida += ABRE;
        abertos += 1;
      } else if (c === FECHA) {
        abertos = Math.max(0, abertos - 1);
        if (abertos === 0) saida += FECHA;
      } else {
        saida += c;
      }
    }
    if (abertos > 0) saida += FECHA;
    return saida
      .replace(new RegExp(ABRE + "(\\s*)" + FECHA, "g"), "$1")   // negrito vazio
      .replace(new RegExp(ABRE + "(\\s+)", "g"), "$1" + ABRE)     // espaço fora
      .replace(new RegExp("(\\s+)" + FECHA, "g"), FECHA + "$1")
      .replace(new RegExp("[" + ABRE + FECHA + "]", "g"), "**")
      .replace(/[ \t]+$/, "");
  });

  return linhas.join("\n").replace(/\n{3,}/g, "\n\n").trim();
};

/** O HTML da folha, limpo, para o clipboard em formato rico (botão Copiar). */
export const htmlDaFolha = (raiz: HTMLElement | null): string => {
  if (!raiz) return "";
  const copia = raiz.cloneNode(true) as HTMLElement;
  copia.querySelectorAll("[contenteditable]").forEach((e) =>
    e.removeAttribute("contenteditable"),
  );
  return `<div style="font-family:Arial,sans-serif;font-size:11pt;line-height:1.5">${copia.innerHTML}</div>`;
};
