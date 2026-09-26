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

// Cabeçalhos de seção, em CAIXA ALTA no começo da linha ("TÉCNICA:", "CONCLUSÃO:").
const ROTULO = /^([A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÇ0-9 ./()-]{2,40}:)(\s*)(.*)$/;

// Rótulo de estrutura dentro da ANÁLISE: "Fígado:", "Vias biliares:", "Seios da face:".
// É o modelo de laudo estruturado dele — rótulo em NEGRITO, dois-pontos, depois a
// descrição. O ROTULO acima só pega CAIXA ALTA, então "Fígado:" saía sem negrito na
// folha e chegava sem negrito no RIS. Regra estreita de propósito, para não transformar
// prosa com dois-pontos em rótulo:
//   - começo da linha, primeira letra maiúscula
//   - só letras, espaço, hífen, vírgula e barra — sem ponto e SEM NÚMERO
//   - até 8 unidades e ROTULO_MAX caracteres
//   - dois-pontos seguidos de ESPAÇO e de texto (rótulo sozinho na linha não conta)
//   - não começa com palavra de ligação (é o que separa rótulo de prosa: os rótulos dele
//     são grupos nominais — "Vias biliares" —, a prosa começa com preposição/verbo).
//     "Achados" NÃO entra nessa lista: "Achados de alto risco" e "Achados
//     extracardíacos" são rótulos de verdade nas máscaras de coronárias.
//
// Os limites não foram chutados, saíram do banco: as 70 regiões têm 232 rótulos de
// estrutura distintos; o mais longo tem 52 caracteres e 8 unidades ("Artérias cerebrais
// anteriores, médias e posteriores"); os únicos caracteres não-letra são espaço, hífen e
// vírgula; e NENHUM tem dígito.
const ROTULO_ESTRUTURA =
  /^([A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][a-zá-úâêîôûàèìòùãõç]+(?:[ ,\-/]+[A-Za-zÁ-Úá-úâêîôûàèìòùãõç]+){0,7}:)( +)(\S.*)$/;
const ROTULO_MAX = 56;
// prosa que começa assim nunca é rótulo de estrutura
const NAO_ROTULO =
  /^(em|na|no|nas|nos|de|da|do|das|dos|com|sem|para|por|ao|aos|à|às|apos|após|antes|quando|se|nao|não|ha|há|havia|houve|nota|nota-se|observa|observa-se|observam|observam-se|verifica|verifica-se|identifica|identifica-se|exame|estudo|obs)\b/i;

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
  // "Fígado:  de dimensões normais..." — rótulo de estrutura da ANÁLISE em negrito.
  const e = ROTULO_ESTRUTURA.exec(cru);
  if (e && e[1].length <= ROTULO_MAX && !NAO_ROTULO.test(e[1])) {
    return `<div><b>${escapar(e[1])}</b>${escapar(e[2] + e[3])}</div>`;
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

/** A fonte da folha, a mesma no RIS e no Word. */
const FOLHA = "font-family:Arial,sans-serif;font-size:11pt;line-height:1.5";

/** O HTML da folha, limpo, para o clipboard em formato rico (botão Copiar). */
export const htmlDaFolha = (raiz: HTMLElement | null): string => {
  if (!raiz) return "";
  const copia = raiz.cloneNode(true) as HTMLElement;
  copia.querySelectorAll("[contenteditable]").forEach((e) =>
    e.removeAttribute("contenteditable"),
  );
  return `<div style="${FOLHA}">${copia.innerHTML}</div>`;
};

/**
 * Texto marcado ("**TÉCNICA:** ...") no HTML rico do clipboard.
 *
 * Existe porque em 26/09 ele viu isto: no Comparativo, "Colar no RIS" saía com
 * negrito e "Copiar" saía cru. O motivo era que só a folha do Laudo montava
 * HTML; as outras telas mandavam texto puro. O texto delas já vem marcado com
 * ** do roteador, então é só passar pelo mesmo renderizador da folha.
 */
export const htmlDeTexto = (texto: string): string =>
  `<div style="${FOLHA}">${textoEmHtml(texto)}</div>`;

/** O mesmo texto sem as marcas, para o campo que só aceita texto puro. */
export const semMarcas = (texto: string): string => (texto || "").replace(/\*\*/g, "");

/**
 * Põe no clipboard o HTML e o texto puro JUNTOS: quem aceita texto rico pega o
 * negrito, quem não aceita pega o laudo limpo, sem ** aparecendo.
 * Devolve true quando o formato rico entrou.
 */
export const copiarRico = async (html: string, texto: string): Promise<boolean> => {
  const Item = (window as unknown as { ClipboardItem?: typeof ClipboardItem }).ClipboardItem;
  if (Item && navigator.clipboard?.write) {
    try {
      await navigator.clipboard.write([
        new Item({
          "text/html": new Blob([html], { type: "text/html" }),
          "text/plain": new Blob([texto], { type: "text/plain" }),
        }),
      ]);
      return true;
    } catch {
      // alguns navegadores/campos recusam o formato rico: cai para o texto puro
    }
  }
  await navigator.clipboard.writeText(texto);
  return false;
};
