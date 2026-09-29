// A imagem da folha vai para a IA junto com o laudo.
//
// 27/09: o botão de imagem já punha o print na folha (recortado e redesenhado
// num canvas: sai a borda com o nome gravado nos pixels e sai todo metadado).
// Mas o botão da IA mandava só o texto da folha (innerText), a IA nunca via a
// medida do print, e depois o laudo que voltava era escrito POR CIMA da folha,
// apagando a imagem. Ele anexou o print do TT-TG do protocolo de Lyon, pediu a
// conclusão, e "ele não entende".
//
// Agora: as imagens da folha vão junto (reduzidas ao tamanho que a IA usa) e,
// quando o laudo volta, voltam para a folha no fim do texto.

import { textoEmHtml } from "./formatar";

/** No máximo o que o roteador aceita (IMAGENS_MAX em roteador.py). */
export const IMAGENS_MAX = 4;

/** Lado maior que a IA aproveita. Acima disso ela reduz sozinha, e cobra o envio. */
export const LADO_MAX = 1568;

// 29/09 tarde: "colar a imagem no corpo do laudo" (Ctrl+V direto na folha) punha o
// print INTEIRO na folha — o navegador vira data URL sozinho — e ele ia para a IA
// sem o recorte: com o nome do paciente que o visualizador grava nos cantos. Agora
// a imagem limpa (recortada e redesenhada no canvas) leva esta marca, e só a
// marcada vai para a IA. Colar ou arrastar na folha abre o recorte (LaudoPage).
export const MARCA_LIMPA = 'data-rotrix="limpa"';

const TAG_IMG = /<img\b[^>]*>/gi;
const SRC_DATA = /\bsrc\s*=\s*"(data:image\/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+)"/i;

/**
 * As imagens que estão na folha, na ordem. Só as que passaram pelo recorte (marca
 * `data-rotrix="limpa"`, data URL feita no canvas, sem metadado). Link externo,
 * arquivo e imagem colada sem recorte nunca vão.
 */
export const imagensDoHtml = (html: string): string[] => {
  const saida: string[] = [];
  for (const m of (html || "").matchAll(TAG_IMG)) {
    const tag = m[0];
    const src = SRC_DATA.exec(tag);
    if (src && tag.includes(MARCA_LIMPA)) saida.push(src[1]);
  }
  return saida;
};

/** Quantas imagens da folha NÃO vão para a IA (sem recorte, link externo, SVG...). */
export const imagensSemRecorte = (html: string): number =>
  ((html || "").match(TAG_IMG) || []).length - imagensDoHtml(html).length;

export const imagensDaFolha = (el: HTMLElement | null): string[] => imagensDoHtml(el?.innerHTML || "");

/** O mesmo HTML que o botão de imagem põe na folha (LaudoPage, inserirImagem). */
export const htmlDaImagem = (dataUrl: string): string =>
  `<div><img src="${dataUrl}" ${MARCA_LIMPA} style="max-width:100%;height:auto" /></div>`;

/** O laudo que voltou da IA, com as imagens de volta no fim. */
export const folhaComImagens = (texto: string, imagens: string[]): string =>
  textoEmHtml(texto) + (imagens || []).map(htmlDaImagem).join("");

/** Tamanho novo mantendo a proporção, com o lado maior em no máximo `max`. */
export const medidaReduzida = (w: number, h: number, max = LADO_MAX): { w: number; h: number } => {
  const maior = Math.max(w, h);
  if (!maior || maior <= max) return { w, h };
  const k = max / maior;
  return { w: Math.max(1, Math.round(w * k)), h: Math.max(1, Math.round(h * k)) };
};

/** Reduz a imagem (no navegador) para o tamanho que a IA usa. A folha fica com a original. */
export const reduzirParaIA = (dataUrl: string, max = LADO_MAX): Promise<string> =>
  new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const { w, h } = medidaReduzida(img.naturalWidth, img.naturalHeight, max);
      if (w === img.naturalWidth && h === img.naturalHeight) {
        resolve(dataUrl);
        return;
      }
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      const ctx = c.getContext("2d");
      if (!ctx) {
        resolve(dataUrl);
        return;
      }
      ctx.drawImage(img, 0, 0, w, h);
      resolve(c.toDataURL("image/png"));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });

/** O motivo do roteador, quando a recusa foi por causa da imagem. */
export const motivoDaImagem = (m: string): string => {
  if (m.includes("imagens_demais")) return `no máximo ${IMAGENS_MAX} imagens por laudo para a IA`;
  if (m.includes("imagem_grande")) return "imagem grande demais para a IA; recorte menos área";
  if (m.includes("imagem_invalida")) return "a IA só recebe imagem posta pelo botão de imagem da folha";
  if (m.includes("imagem_desligada")) return "envio de imagem para a IA desligado (ia_imagens no config)";
  if (m.includes("imagem_sem_regra")) return "falta o bloco IMAGEM no REDATOR_ROTRIX.md; rode o ATUALIZAR";
  return "";
};
