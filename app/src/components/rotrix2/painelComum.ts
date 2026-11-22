// Rotrix L-1000 v2 — o que a aba Painel e a Casca dividem (22/11/2026).
//
// As teclas moram em painel.json, no roteador (painel.py). A tela só desenha e
// pede: carregar, salvar, executar, expediente, organizar e capturar posições.
import { invoke } from "@tauri-apps/api/core";

export type Grupo = "laudo" | "ia" | "texto" | "app" | "jan" | "sis";
export type Acao =
  | "programa"
  | "site"
  | "rotrix"
  | "sistema"
  | "atalho"
  | "texto"
  | "expediente"
  | "organizar"
  | "aparelho"
  | "multi";

export interface Lugar {
  display: string;
  layout: string;
  zone: number;
}

export interface Tecla {
  id: string;
  nome: string;
  acao: Acao;
  grupo: Grupo;
  icone?: string;
  larga?: boolean;
  atalho_global?: string;
  // programa
  tipo?: "exe" | "powershell" | "appx";
  alvo?: string;
  args?: string[];
  detectar?: string;
  titulo?: string;
  expediente?: boolean;
  lugar?: Lugar | null;
  // site
  sites?: string[];
  navegador?: string;
  perfil?: string;
  // rotrix / sistema
  comando?: string;
  // atalho / texto
  teclas?: string;
  texto?: string;
  // aparelho: nome (ou número) do perfil/página para "ir para"
  destino?: string;
  // multi: ids das teclas, em ordem, e a pausa entre elas
  passos?: string[];
  espera_ms?: number;
}

export interface Pagina {
  nome: string;
  teclas: Tecla[];
}

export interface Ajustes {
  navegador: string;
  navegador_exe: string;
  perfil: string;
  iniciar_expediente: boolean;
  atraso_s: number;
  organizar_ao_iniciar: boolean;
}

export interface ConfigPainel {
  versao: number;
  ajustes: Ajustes;
  paginas: Pagina[];
  /** fase 3: o mapa de cada modelo de Stream Deck / Stream Dock */
  aparelhos?: Record<string, unknown>;
}

export interface Monitor {
  id: string;
  nome: string;
  device: string;
  x: number;
  y: number;
  w: number;
  h: number;
  wx: number;
  wy: number;
  ww: number;
  wh: number;
  principal: boolean;
}

export interface Modelo {
  id: string;
  nome: string;
  zonas: { r: [number, number, number, number]; nome: string }[];
}

export interface EstadoPainel {
  ok: boolean;
  abertos: Record<string, boolean>;
  achados: Record<string, boolean>;
  lugares: Record<string, string>;
  monitores: Monitor[];
  modelos: Modelo[];
  navegadores: Record<string, boolean>;
}

export interface Resposta {
  ok: boolean;
  frase?: string;
  motivo?: string;
  na_tela?: boolean;
  comando?: string;
  config?: ConfigPainel;
  estado?: EstadoPainel;
  lugares?: Record<string, Lugar | null>;
  descricao?: Record<string, string>;
}

export const painel = async (acao: string, corpo: unknown = {}): Promise<Resposta> => {
  const bruto = await invoke<string>("rotrix_painel", { acao, corpo: JSON.stringify(corpo) });
  return JSON.parse(bruto || "{}") as Resposta;
};

// Cores foscas por grupo: o fundo é a cor bem diluída, a borda um pouco mais
// forte e o ícone na cor cheia — "iluminado, mas não neon".
export const COR: Record<Grupo, string> = {
  laudo: "#6f9ee6",
  ia: "#a59af0",
  texto: "#7fc4a3",
  app: "#e0a487",
  jan: "#d9b878",
  sis: "#a7b3c0",
};

export const NOME_GRUPO: Record<Grupo, string> = {
  laudo: "Laudo",
  ia: "Claude",
  texto: "Textos e máscaras",
  app: "Programas",
  jan: "Janelas",
  sis: "Sistema",
};

export const COMANDOS_ROTRIX: [string, string][] = [
  ["proximo", "Próximo da fila"],
  ["fila", "Mostrar / esconder a fila"],
  ["fila_aba", "Abrir a aba Fila"],
  ["laudo", "Ir para o Laudo"],
  ["colar", "Colar no RIS"],
  ["ditar_ia", "Ditar com IA (organiza e reescreve)"],
  ["ditar_mascara", "Máscara por voz (atalhos)"],
  ["ditar", "Transcrição crua (sem IA)"],
  ["conferencia", "Conferência"],
  ["revisar", "Revisar (conferir incoerências)"],
  ["analisar_rx", "Analisar RX"],
  ["coronarias", "Estruturados (coronárias)"],
  ["mascaras", "Máscaras"],
];

export const COMANDOS_SISTEMA: [string, string][] = [
  ["volume_mais", "Volume +"],
  ["volume_menos", "Volume −"],
  ["mudo", "Mudo"],
  ["musica", "Música: tocar / pausar"],
  ["proxima_musica", "Próxima música"],
  ["musica_anterior", "Música anterior"],
  ["bloquear", "Bloquear a tela"],
];

export const ACOES: [Acao, string][] = [
  ["programa", "Abrir programa"],
  ["site", "Abrir site"],
  ["rotrix", "Ação do Rotrix"],
  ["sistema", "Sistema (volume, música…)"],
  ["atalho", "Atalho de teclado"],
  ["texto", "Texto pronto"],
  ["expediente", "Iniciar expediente"],
  ["organizar", "Organizar janelas"],
  ["aparelho", "Trocar perfil / página do aparelho"],
  ["multi", "Multiação (várias teclas em sequência)"],
];

export const COMANDOS_APARELHO: [string, string][] = [
  ["perfil_proximo", "Próximo perfil"],
  ["perfil_anterior", "Perfil anterior"],
  ["perfil_ir", "Ir para o perfil…"],
  ["pagina_proxima", "Próxima página"],
  ["pagina_anterior", "Página anterior"],
  ["pagina_ir", "Ir para a página…"],
];

export const NAVEGADORES: [string, string][] = [
  ["padrao", "Padrão do Windows"],
  ["chrome", "Google Chrome"],
  ["edge", "Microsoft Edge"],
  ["brave", "Brave"],
  ["firefox", "Firefox"],
  ["opera", "Opera"],
];

/** Evento que a Casca escuta para as ações do Rotrix (próximo, colar, revisar…). */
export const comandoRotrix = (comando: string): void => {
  window.dispatchEvent(new CustomEvent("rotrix:painel-comando", { detail: { comando } }));
};

export const novaTecla = (): Tecla => ({
  id: `t_${Date.now().toString(36)}`,
  nome: "Nova tecla",
  acao: "site",
  grupo: "sis",
  icone: "globe",
  sites: ["https://"],
});
