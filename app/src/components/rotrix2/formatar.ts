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

/** Uma linha de laudo em HTML, com o título/rótulo em negrito. */
export const linhaEmHtml = (linha: string): string => {
  const cru = linha.replace(/\s+$/, "");
  if (!cru.trim()) return "<div><br></div>";
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
