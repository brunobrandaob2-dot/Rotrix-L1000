// Rotrix L-1000 v2 (fase 3) — desenha a imagem de cada tecla do aparelho.
//
// O roteador não tem Pillow: quem desenha é a tela, num <canvas>, e manda o
// JPEG pronto, já no tamanho e na rotação do modelo (o AKP03E quer 64x64 girada
// 90° no sentido horário; o Stream Deck MK.2, 72x72 de cabeça para baixo).
// Mesmo visual das teclas do Painel: fosco, cor do grupo, ícone e nome.
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Tecla } from "./painelComum";
import { COR } from "./painelComum";

export interface Formato {
  w: number;
  h: number;
  rot: number;
  espelhar: boolean;
}

const carregarSvg = (svg: string): Promise<HTMLImageElement> =>
  new Promise((ok, falha) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = falha;
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  });

const misturar = (hex: string, fundo: [number, number, number], p: number): string => {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  const m = c.map((v, i) => Math.round(v * p + fundo[i] * (1 - p)));
  return `rgb(${m[0]},${m[1]},${m[2]})`;
};

/** JPEG (base64, sem o prefixo data:) de uma tecla — ou da tecla vazia. */
export const imagemDaTecla = async (
  t: Tecla | null,
  fmt: Formato,
  Icone: React.ElementType | null,
): Promise<string> => {
  const { w, h } = fmt;
  const base = document.createElement("canvas");
  base.width = w;
  base.height = h;
  const c = base.getContext("2d")!;
  const fundo: [number, number, number] = [16, 19, 23];
  c.fillStyle = `rgb(${fundo.join(",")})`;
  c.fillRect(0, 0, w, h);
  if (t) {
    const cor = COR[t.grupo] || COR.sis;
    // fosco iluminado: a cor bem diluída, mais clara em cima
    const g = c.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, misturar(cor, fundo, 0.3));
    g.addColorStop(1, misturar(cor, fundo, 0.12));
    c.fillStyle = g;
    c.fillRect(0, 0, w, h);
    c.fillStyle = misturar(cor, fundo, 0.85);
    c.fillRect(0, 0, w, Math.max(3, Math.round(h * 0.06)));
    if (Icone) {
      const tam = Math.round(w * 0.38);
      const svg = renderToStaticMarkup(
        React.createElement(Icone, { size: tam, color: cor, strokeWidth: 2, xmlns: "http://www.w3.org/2000/svg" }),
      );
      try {
        const img = await carregarSvg(svg);
        c.drawImage(img, (w - tam) / 2, h * 0.14, tam, tam);
      } catch {
        /* sem ícone: fica só o nome */
      }
    }
    // nome, encolhendo a letra até caber
    let px = Math.round(w * 0.17);
    c.fillStyle = "#e8edf2";
    c.textAlign = "center";
    c.textBaseline = "alphabetic";
    const nome = t.nome;
    do {
      c.font = `600 ${px}px "Segoe UI", Inter, sans-serif`;
      px -= 1;
    } while (c.measureText(nome).width > w - 6 && px > 8);
    let texto = nome;
    while (c.measureText(texto).width > w - 6 && texto.length > 3) texto = texto.slice(0, -2) + "…";
    c.fillText(texto, w / 2, h - Math.round(h * 0.11));
  }
  // rotação / espelho do modelo
  const out = document.createElement("canvas");
  out.width = w;
  out.height = h;
  const o = out.getContext("2d")!;
  o.translate(w / 2, h / 2);
  o.rotate((fmt.rot * Math.PI) / 180);
  if (fmt.espelhar) o.scale(-1, 1);
  o.drawImage(base, -w / 2, -h / 2);
  return out.toDataURL("image/jpeg", 0.9).split(",")[1] || "";
};
