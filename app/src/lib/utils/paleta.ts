/**
 * Rotrix L-1000: cor do app, escolhida a qualquer hora (botão "Cores").
 *
 * Cada paleta define o modo escuro e o claro. Ela sobrescreve, no elemento
 * raiz, as variáveis de `styles/theme.css` (--light-color-*, --dark-color-*,
 * --color-background-ui); o tema claro/escuro continua valendo por cima.
 * "original" tira as sobrescritas e volta às cores do Handy.
 *
 * A escolha fica no localStorage (compartilhado com a janela da barra de
 * gravação) e é avisada às outras janelas pelo evento "paleta-alterada".
 * Cor livre: o destaque é a cor escolhida; o resto é calculado para o texto
 * continuar legível (contraste 4,5:1).
 */

export interface Tons {
  bg: string;
  tx: string;
  ac: string;
  mid: string;
  stroke: string;
}

export interface Paleta {
  id: string;
  nome: string;
  descricao: string;
  escuro: Tons;
  claro: Tons;
  botao: string;
}

export interface EscolhaPaleta {
  id: string;
  cor?: string;
}

export const PALETA_STORAGE_KEY = "rotrix.paleta";
export const EVENTO_PALETA = "paleta-alterada";
export const ID_LIVRE = "livre";

// ---------- cor: conta simples em sRGB ----------

const hexOk = (h: string): boolean => /^#[0-9a-fA-F]{6}$/.test(h);

const paraRgb = (h: string): [number, number, number] => [
  parseInt(h.slice(1, 3), 16),
  parseInt(h.slice(3, 5), 16),
  parseInt(h.slice(5, 7), 16),
];

const paraHex = (c: number[]): string =>
  "#" +
  c
    .map((x) =>
      Math.max(0, Math.min(255, Math.round(x)))
        .toString(16)
        .padStart(2, "0"),
    )
    .join("");

/** Mistura a com b (t = 0: a; t = 1: b). */
export const misturar = (a: string, b: string, t: number): string => {
  const ca = paraRgb(a);
  const cb = paraRgb(b);
  return paraHex(ca.map((x, i) => x * (1 - t) + cb[i] * t));
};

const luminancia = (h: string): number => {
  const [r, g, b] = paraRgb(h).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export const contraste = (a: string, b: string): number => {
  const la = luminancia(a);
  const lb = luminancia(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
};

/** Aproxima `cor` de `rumo` (branco ou preto) até ter contraste `alvo` com `fundo`. */
const ajustar = (cor: string, fundo: string, rumo: string, alvo = 4.5): string => {
  let c = cor;
  for (let i = 0; i < 20 && contraste(c, fundo) < alvo; i++) {
    c = misturar(c, rumo, 0.08);
  }
  return c;
};

// ---------- paletas prontas ----------

const tons = (bg: string, tx: string, ac: string, mid: string, escuro: boolean): Tons => ({
  bg,
  tx,
  ac,
  mid,
  stroke: escuro ? misturar(ac, "#ffffff", 0.55) : misturar(tx, ac, 0.25),
});

export const PALETAS: Paleta[] = [
  {
    id: "original",
    nome: "Rosa (original)",
    descricao: "As cores do Handy.",
    escuro: { bg: "#2c2b29", tx: "#fbfbfb", ac: "#f28cbb", mid: "#808080", stroke: "#fad1ed" },
    claro: { bg: "#fbfbfb", tx: "#0f0f0f", ac: "#faa2ca", mid: "#808080", stroke: "#382731" },
    botao: "#da5893",
  },
  {
    id: "sala",
    nome: "Sala de laudo",
    descricao: "Grafite com azul aço. Pouco brilho.",
    escuro: tons("#1b1f24", "#e8edf2", "#82aee6", "#9aa4af", true),
    claro: tons("#f6f8fa", "#111827", "#2c5a96", "#5d6773", false),
    botao: "#2f5f9e",
  },
  {
    id: "petroleo",
    nome: "Petróleo",
    descricao: "Verde-azulado profundo.",
    escuro: tons("#162224", "#e4efee", "#5cc8ba", "#93a6a4", true),
    claro: tons("#f4f9f8", "#0f1f1d", "#17665d", "#586b69", false),
    botao: "#1c6f66",
  },
  {
    id: "ambar",
    nome: "Âmbar noturno",
    descricao: "Tons quentes para a noite.",
    escuro: tons("#221e1a", "#f2ebe3", "#e3a95f", "#aa9f93", true),
    claro: tons("#faf7f2", "#1f1a14", "#8a5214", "#6c6155", false),
    botao: "#8f5415",
  },
  {
    id: "matriz",
    nome: "Matriz",
    descricao: "Preto com verde fósforo.",
    escuro: tons("#0f1512", "#d9efe1", "#62d392", "#8fa699", true),
    claro: tons("#f3f8f5", "#0f1a14", "#1b6b3d", "#56695e", false),
    botao: "#1d6f40",
  },
  {
    id: "cromo",
    nome: "Cromo",
    descricao: "Metal líquido, quase sem cor.",
    escuro: tons("#1c1d20", "#eceef1", "#b9c6d6", "#9da2aa", true),
    claro: tons("#f6f7f8", "#16171a", "#465265", "#5f646c", false),
    botao: "#465265",
  },
];

/** Paleta calculada a partir de uma cor qualquer (o destaque). */
export const paletaLivre = (cor: string): Paleta => {
  const c = hexOk(cor) ? cor.toLowerCase() : "#82aee6";
  const bgE = misturar("#1c1d20", c, 0.07);
  const bgC = misturar("#f6f7f8", c, 0.04);
  const acE = ajustar(c, bgE, "#ffffff");
  const acC = ajustar(c, bgC, "#000000");
  return {
    id: ID_LIVRE,
    nome: "Cor livre",
    descricao: "Destaque na cor que você escolheu.",
    escuro: tons(bgE, misturar("#eceef1", c, 0.04), acE, ajustar(misturar("#9da2aa", c, 0.1), bgE, "#ffffff"), true),
    claro: tons(bgC, "#16171a", acC, ajustar(misturar("#5f646c", c, 0.1), bgC, "#000000"), false),
    botao: ajustar(c, "#ffffff", "#000000"),
  };
};

export const paletaDe = (e: EscolhaPaleta): Paleta =>
  e.id === ID_LIVRE && e.cor
    ? paletaLivre(e.cor)
    : PALETAS.find((p) => p.id === e.id) ?? PALETAS[0];

// ---------- aplicar e guardar ----------

const VARIAVEIS = (p: Paleta): Record<string, string> => ({
  "--dark-color-background": p.escuro.bg,
  "--dark-color-text": p.escuro.tx,
  "--dark-color-logo-primary": p.escuro.ac,
  "--dark-color-logo-stroke": p.escuro.stroke,
  "--dark-color-mid-gray": p.escuro.mid,
  "--light-color-background": p.claro.bg,
  "--light-color-text": p.claro.tx,
  "--light-color-logo-primary": p.claro.ac,
  "--light-color-logo-stroke": p.claro.stroke,
  "--light-color-mid-gray": p.claro.mid,
  "--color-background-ui": p.botao,
});

export const aplicarPaleta = (e: EscolhaPaleta): void => {
  const raiz = document.documentElement;
  const nomes = Object.keys(VARIAVEIS(PALETAS[0]));
  if (e.id === "original") {
    nomes.forEach((n) => raiz.style.removeProperty(n));
  } else {
    const v = VARIAVEIS(paletaDe(e));
    nomes.forEach((n) => raiz.style.setProperty(n, v[n]));
  }
  raiz.dataset.paleta = e.id;
};

export const getPaletaSalva = (): EscolhaPaleta => {
  try {
    const bruto = localStorage.getItem(PALETA_STORAGE_KEY);
    if (bruto) {
      const e = JSON.parse(bruto) as EscolhaPaleta;
      const conhecida = e.id === ID_LIVRE ? hexOk(e.cor ?? "") : PALETAS.some((p) => p.id === e.id);
      if (conhecida) return e;
    }
  } catch {
    // sem localStorage: fica a original
  }
  return { id: "original" };
};

export const salvarPaleta = (e: EscolhaPaleta): void => {
  try {
    localStorage.setItem(PALETA_STORAGE_KEY, JSON.stringify(e));
  } catch {
    // a cor vale nesta sessão mesmo sem guardar
  }
};
