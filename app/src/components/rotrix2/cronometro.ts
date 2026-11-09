// Rotrix L-1000 — cronômetro do laudo (09/11).
//
// Pedido dele: "um botão de cronômetro do momento que eu clico [no raciocínio] e que
// ele finaliza quando eu clico de volta e ela começa a ler o laudo, para que eu tenha
// noção de quanto tempo eu tô laudando aquele exame".
//
// Liga sozinho com o raciocínio e para quando o raciocínio desliga; o chip também
// liga e para na mão. Cada tempo fica só neste computador (localStorage
// "rotrix2.tempos"), com data, segundos e o TÍTULO do exame — nunca o laudo, nunca
// nome (§17): só entra um título que começa por modalidade.

export interface Tempo {
  /** fim, ISO local */
  fim: string;
  segundos: number;
  /** título do exame ("TOMOGRAFIA COMPUTADORIZADA DO ABDOME TOTAL") ou "" */
  exame: string;
  /** "raciocinio" (ligou junto) ou "mao" (chip) */
  como: "raciocinio" | "mao";
}

export const GUARDADO_TEMPOS = "rotrix2.tempos";
export const MAX_TEMPOS = 500;

/** 75 → "1:15"; 3725 → "1:02:05" */
export function formatarTempo(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

const MODALIDADE =
  /^(RADIOGRAFIA|RAIO|RX\b|TOMOGRAFIA|ANGIOTOMOGRAFIA|ANGIO|RESSON[ÂA]NCIA|ANGIORRESSON|ULTRASSONOGRAFIA|ULTRASSOM|USG?\b|DOPPLER|ECOGRAFIA|MAMOGRAFIA|DENSITOMETRIA|ESCANOMETRIA|PANOR[ÂA]MICA|TC\b|RM\b|CINTILOGRAFIA|PET|ENEMA|ESOFAGOGRAMA|URETROCISTOGRAFIA|HISTEROSSALPINGOGRAFIA|FLUOROSCOPIA|IDADE [ÓO]SSEA)/;

/** A primeira linha da folha, se for título de exame. Qualquer outra coisa vira "". */
export function tituloDoExame(texto: string): string {
  const primeira =
    (texto || "")
      .replace(/\*\*/g, "")
      .split("\n")
      .map((l) => l.trim())
      .find((l) => l !== "") || "";
  const t = primeira.toUpperCase();
  if (!MODALIDADE.test(t)) return "";
  if (/\d{5,}|@|:/.test(t)) return ""; // número longo, e-mail ou "PACIENTE:" não entram
  return t.slice(0, 90);
}

export function registrar(
  lista: Tempo[],
  novo: Tempo,
  max = MAX_TEMPOS,
): Tempo[] {
  if (!(novo.segundos >= 1)) return lista; // clique sem querer não conta
  const out = [...lista, novo];
  return out.length > max ? out.slice(out.length - max) : out;
}

/** O raciocínio para antes da IA montar a folha: o título chega depois. Dá nome ao
 * último tempo sem nome, se ele terminou há menos de 30 min. */
export function nomearUltimo(
  lista: Tempo[],
  exame: string,
  agora: Date,
): Tempo[] {
  if (!exame || !lista.length) return lista;
  const u = lista[lista.length - 1];
  if (u.exame) return lista;
  if (agora.getTime() - Date.parse(u.fim) > 30 * 60 * 1000) return lista;
  return [...lista.slice(0, -1), { ...u, exame }];
}

export function doDia(lista: Tempo[], dia: Date): Tempo[] {
  const d = dia.toDateString();
  return lista.filter((t) => new Date(t.fim).toDateString() === d);
}

export function resumo(lista: Tempo[], dia: Date): string {
  const hoje = doDia(lista, dia);
  if (!hoje.length) return "nenhum tempo hoje";
  const soma = hoje.reduce((a, t) => a + t.segundos, 0);
  return `hoje: ${hoje.length} ${hoje.length === 1 ? "exame" : "exames"} · média ${formatarTempo(soma / hoje.length)} · total ${formatarTempo(soma)}`;
}

/** ISO com o fuso local (o arquivo é dele, na hora dele) */
export function isoLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function lerTempos(): Tempo[] {
  try {
    const v = JSON.parse(localStorage.getItem(GUARDADO_TEMPOS) || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function gravarTempos(lista: Tempo[]): void {
  try {
    localStorage.setItem(GUARDADO_TEMPOS, JSON.stringify(lista));
  } catch {
    /* sem armazenamento: o cronômetro na tela continua valendo */
  }
}

/** CSV para ele abrir no Excel: data;hora;segundos;tempo;exame;como */
export function emCsv(lista: Tempo[]): string {
  const linhas = lista.map((t) => {
    const [data, hora] = t.fim.split("T");
    return [
      data,
      hora,
      String(t.segundos),
      formatarTempo(t.segundos),
      `"${t.exame.replace(/"/g, "'")}"`,
      t.como,
    ].join(";");
  });
  return ["data;hora;segundos;tempo;exame;como", ...linhas].join("\n");
}
