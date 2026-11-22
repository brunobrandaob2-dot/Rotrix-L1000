// Rotrix L-1000 v2 — o que a Fila (aba e lateral do Laudo) e a Casca dividem:
// os tipos da fila, como abrir exames no visualizador escolhido e o Autoabrir.
//
// O visualizador (RadiAnt ou RadioWant) e a janela do RadioWant ficam no
// config.json do roteador: assim o botão Abrir, o Autoabrir e o atalho
// Ctrl+Alt+R obedecem à mesma escolha.
import { invoke } from "@tauri-apps/api/core";

export interface Estudo {
  id: string;
  modalidade: string;
  descricao: string;
  status: string;
  laudado: boolean | null;
  entrou: string;
  iniciais?: string;
  /** nome por extenso, lido do cabeçalho DICOM AQUI no computador */
  nome?: string;
  /** "pasta" = ZIP solto em Downloads (Mobilemed e outros); senão veio do E-Laudos */
  origem?: string;
  cabecalho?: string;
  mascara?: string | null;
  feito?: boolean;
  arquivos?: number;
  bytes?: number;
}

export type Visualizador = "radiant" | "radiowant";
export type JanelaRW = "atual" | "nova";

export interface Fila {
  disponivel: boolean;
  pasta_existe?: boolean;
  itens: Estudo[];
  atual: string | null;
  vez?: string | null;
  escolhido?: string | null;
  perfil_automatico: boolean;
  visualizador?: Visualizador;
  radiowant_janela?: JanelaRW;
  radiowant_achado?: boolean;
  radiant_achado?: boolean;
}

export const NOME_VISUALIZADOR: Record<Visualizador, string> = {
  radiant: "RadiAnt",
  radiowant: "RadioWant",
};

export const lerFila = async (): Promise<Fila> =>
  JSON.parse((await invoke<string>("rotrix_fila")) || "{}") as Fila;

export const pronto = (e: Estudo): boolean => Boolean(e.feito || e.laudado);
/** veio do E-Laudos (Radius) ou é um ZIP solto (Mobilemed e outros)? */
export const ehOutro = (e: Estudo): boolean => e.origem === "pasta";

export const hora = (iso: string): string => {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}:\d{2})/);
  if (m) return m[1];
  const d = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return d ? `${d[3]}/${d[2]}` : iso.slice(0, 5);
};

export const dia = (iso: string): string => {
  const d = (iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return d ? `${d[3]}/${d[2]}` : "";
};

export const tamanho = (bytes?: number): string => {
  if (!bytes) return "";
  const mb = bytes / 1048576;
  return mb >= 1024 ? `${(mb / 1024).toFixed(1).replace(".", ",")} GB` : `${Math.round(mb)} MB`;
};

export const nomeDoExame = (e: Estudo): string =>
  e.descricao || e.cabecalho || (ehOutro(e) ? "ZIP baixado por fora" : "exame sem descrição");

export const nomeDoPaciente = (e: Estudo): string => e.nome || e.iniciais || "—";

/** grava no config.json a escolha do visualizador e/ou da janela do RadioWant */
export const salvarVisualizador = async (ajuste: {
  visualizador?: Visualizador;
  radiowant_janela?: JanelaRW;
}): Promise<void> => {
  await invoke("rotrix_ia_salvar", { ajustes: JSON.stringify(ajuste) });
};

const motivoAbrir = (m: string | undefined, vis: string): string => {
  if (m === "sem_caminho") return "o Radius não guarda o caminho destes exames — abra pela pasta";
  if (m === "radiant_nao_encontrado") return "não achei o RadiAnt instalado neste computador";
  if (m === "radiowant_nao_encontrado")
    return "não achei o RadioWant: aponte o RadioWant.exe na fila do Radius ou em Config.";
  return `não consegui abrir no ${vis} (${m || "erro"})`;
};

/** Abre os exames no visualizador do config. Devolve a frase para o rodapé. */
export const abrirEstudos = async (ids: string[]): Promise<{ ok: boolean; frase: string }> => {
  if (!ids.length) return { ok: false, frase: "marque um ou mais exames" };
  try {
    const r = JSON.parse((await invoke<string>("rotrix_abrir_estudos", { ids })) || "{}") as {
      ok?: boolean;
      motivo?: string;
      abertos?: number;
      visualizador?: Visualizador;
    };
    const vis = NOME_VISUALIZADOR[r.visualizador || "radiant"];
    if (!r.ok) return { ok: false, frase: motivoAbrir(r.motivo, vis) };
    return {
      ok: true,
      frase: `abrindo ${r.abertos} exame${r.abertos === 1 ? "" : "s"} no ${vis}`,
    };
  } catch (e) {
    return { ok: false, frase: String(e) };
  }
};

/** Abre um exame só e o deixa como "exame da vez" (o ditado usa o cabeçalho dele). */
export const abrirUm = async (id: string): Promise<{ ok: boolean; frase: string }> => {
  try {
    await invoke<string>("rotrix_fila_escolher", { id });
  } catch {
    /* sem problema: abre mesmo assim */
  }
  return abrirEstudos([id]);
};

// --- Autoabrir --------------------------------------------------------------
// Ligado: quando o exame da vez fica laudado (colado no RIS ou marcado), o
// próximo exame pronto do E-Laudos abre sozinho no visualizador.
const CHAVE_AUTO = "rotrix2.autoabrir";

export const autoabrirLigado = (): boolean => {
  try {
    return localStorage.getItem(CHAVE_AUTO) === "1";
  } catch {
    return false;
  }
};

export const ligarAutoabrir = (v: boolean): void => {
  try {
    localStorage.setItem(CHAVE_AUTO, v ? "1" : "0");
    window.dispatchEvent(new CustomEvent("rotrix:autoabrir", { detail: v }));
  } catch {
    /* sem localStorage: fica só nesta sessão */
  }
};

/** O próximo exame a abrir: o mais antigo pronto e não laudado do E-Laudos. */
export const proximoPendente = (f: Fila, menosEste?: string | null): Estudo | null => {
  const cands = (f.itens || []).filter(
    (e) => !pronto(e) && !ehOutro(e) && e.id !== menosEste && !/baix/i.test(e.status || ""),
  );
  if (!cands.length) return null;
  return [...cands].sort((a, b) => (a.entrou || "").localeCompare(b.entrou || ""))[0];
};
