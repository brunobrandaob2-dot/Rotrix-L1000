/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Histórico, 24 horas.
//
// Esquerda: tabela hora · exame · tamanho do texto (o número do mockup, agora
// com rótulo: "car." = caracteres). Direita: o texto do ditado escolhido, o
// áudio e o que fazer com ele — colar no RIS, copiar, abrir na folha do Laudo
// ou rodar a IA de novo.
//
// Mais velho que 24 h não aparece. Áudio e texto ficam só neste computador.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { invoke } from "@tauri-apps/api/core";
import { readFile } from "@tauri-apps/plugin-fs";
import { Copy, FolderOpen, RefreshCw, Sparkles, Trash2, PenLine } from "lucide-react";
import { commands, events, type HistoryEntry } from "@/bindings";
import { useOsType } from "@/hooks/useOsType";
import { AudioPlayer, AudioPlayerGroup } from "../ui/AudioPlayer";
import { Button } from "../ui/Button";
import { copyToClipboard } from "../settings/history/clipboard";

const VINTE_QUATRO_H = 24 * 60 * 60 * 1000;
const PAGINA = 60;

const hora = (ms: number): string =>
  new Date(ms).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });

const textoFinal = (e: HistoryEntry): string =>
  e.post_processed_text || e.transcription_text || "";

export const HistoricoPage: React.FC<{
  aoAbrirNoLaudo?: (texto: string) => void;
  idModeloCompleto?: string;
}> = ({ aoAbrirNoLaudo, idModeloCompleto = "" }) => {
  const osType = useOsType();
  const [itens, setItens] = useState<HistoryEntry[]>([]);
  const [escolhido, setEscolhido] = useState<number | null>(null);
  const [soIA, setSoIA] = useState(false);
  const [busca, setBusca] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState<"" | "ia" | "colar">("");

  const ler = useCallback(async () => {
    setCarregando(true);
    try {
      const r = await commands.getHistoryEntries(null, PAGINA);
      if (r.status === "ok") {
        const corte = Date.now() - VINTE_QUATRO_H;
        // timestamp do Handy vem em segundos
        setItens(r.data.entries.filter((e) => e.timestamp * 1000 >= corte));
      }
    } catch (e) {
      setAviso(String(e));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void ler();
    const t = setInterval(() => void ler(), 5 * 60 * 1000); // deixa a lista cair sozinha
    return () => clearInterval(t);
  }, [ler]);

  useEffect(() => {
    const p = events.historyUpdatePayload.listen((e) => {
      const carga = e.payload;
      if (carga.action === "added") {
        setItens((prev) => [carga.entry, ...prev]);
      } else if (carga.action === "updated" || carga.action === "toggled") {
        setItens((prev) =>
          prev.map((x) =>
            "entry" in carga && x.id === carga.entry.id ? carga.entry : x,
          ),
        );
      } else if (carga.action === "deleted") {
        setItens((prev) => prev.filter((x) => x.id !== carga.id));
      }
    });
    return () => {
      p.then((fn) => fn());
    };
  }, []);

  const urlDoAudio = useCallback(
    async (arquivo: string) => {
      try {
        const r = await commands.getAudioFilePath(arquivo);
        if (r.status !== "ok") return null;
        if (osType === "linux") {
          const dados = await readFile(r.data);
          return URL.createObjectURL(new Blob([dados], { type: "audio/wav" }));
        }
        return convertFileSrc(r.data, "asset");
      } catch {
        return null;
      }
    },
    [osType],
  );

  const lista = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return itens.filter((e) => {
      if (soIA && !e.post_process_requested) return false;
      if (q && !textoFinal(e).toLowerCase().includes(q)) return false;
      return true;
    });
  }, [itens, soIA, busca]);

  const item = lista.find((e) => e.id === escolhido) || lista[0] || null;
  const texto = item ? textoFinal(item) : "";

  const apagar = async (id: number) => {
    setItens((prev) => prev.filter((e) => e.id !== id));
    try {
      await commands.deleteHistoryEntry(id);
    } catch (e) {
      setAviso(String(e));
      void ler();
    }
  };

  const colarNoRis = async () => {
    if (!texto) return;
    setOcupado("colar");
    try {
      await invoke("rotrix_colar", { texto });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupado("");
    }
  };

  const rodarIA = async () => {
    if (!texto) return;
    setOcupado("ia");
    setAviso("");
    try {
      const bruto = await invoke<string>("rotrix_ia_texto", {
        texto,
        instrucao: "",
        modelo: idModeloCompleto,
      });
      const r = JSON.parse(bruto || "{}") as {
        ok?: boolean;
        texto?: string;
        motivo?: string;
      };
      if (r.ok && r.texto) {
        aoAbrirNoLaudo?.(r.texto);
        setAviso("a IA rodou e o texto foi para a folha do Laudo");
      } else {
        setAviso(r.motivo || "a IA não respondeu");
      }
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupado("");
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* barra */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <h2 className="text-base font-semibold">Histórico</h2>
        <span className="text-[11px] rounded-full border border-logo-primary/30 bg-logo-primary/10 px-2 py-0.5">
          últimas 24 h · {lista.length} ditado{lista.length === 1 ? "" : "s"}
        </span>
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="buscar no texto"
          className="rounded-lg border border-mid-gray/25 bg-background px-2 py-1 text-xs outline-none w-44 focus:border-logo-primary/50"
        />
        <div className="ms-auto flex items-center gap-1.5">
          <Button
            variant={soIA ? "primary-soft" : "secondary"}
            size="sm"
            onClick={() => setSoIA((v) => !v)}
          >
            Só com IA
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void commands.openRecordingsFolder()}
          >
            <span className="flex items-center gap-1.5">
              <FolderOpen size={14} /> Pasta dos áudios
            </span>
          </Button>
          <Button variant="primary" size="sm" onClick={() => void ler()}>
            <span className="flex items-center gap-1.5">
              <RefreshCw size={14} className={carregando ? "animate-spin" : ""} />
              Atualizar
            </span>
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden flex gap-3 p-3">
        {/* tabela */}
        <div className="w-80 shrink-0 overflow-y-auto rounded-lg border border-mid-gray/20 bg-background">
          {lista.length === 0 ? (
            <p className="p-3 text-xs text-mid-gray">
              {carregando
                ? "lendo…"
                : "nada nas últimas 24 horas (ou nada com esse texto)."}
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-mid-gray bg-mid-gray/5">
                  <th className="w-12 py-1.5 text-start ps-2 font-medium">hora</th>
                  <th className="text-start font-medium">exame</th>
                  <th className="w-20 text-end pe-2 font-medium">texto</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((e) => (
                  <tr
                    key={e.id}
                    onClick={() => setEscolhido(e.id)}
                    className={`border-t border-mid-gray/10 cursor-pointer ${
                      item?.id === e.id
                        ? "bg-logo-primary/10 font-medium"
                        : "hover:bg-mid-gray/5"
                    }`}
                  >
                    <td className="py-1.5 ps-2 text-mid-gray tabular-nums">
                      {hora(e.timestamp * 1000)}
                    </td>
                    <td className="truncate max-w-0">
                      {e.title || "ditado solto"}
                      {e.post_process_requested && (
                        <span className="ms-1.5 text-[9px] font-bold rounded bg-logo-primary/20 px-1 py-0.5">
                          IA
                        </span>
                      )}
                    </td>
                    <td className="pe-2 text-end text-mid-gray tabular-nums">
                      {textoFinal(e).length.toLocaleString("pt-BR")} car.
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="px-2 py-1.5 text-[10px] text-mid-gray border-t border-mid-gray/10">
            car. = caracteres do texto final
          </p>
        </div>

        {/* item */}
        <div className="flex-1 min-w-0 flex flex-col gap-3 overflow-y-auto">
          {!item ? (
            <div className="rounded-lg border border-mid-gray/20 bg-background p-4 text-xs text-mid-gray">
              escolha um ditado na lista.
            </div>
          ) : (
            <>
              <div className="rounded-lg border border-mid-gray/20 bg-background">
                <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
                  <span className="text-xs font-semibold truncate">
                    {hora(item.timestamp * 1000)} · {item.title || "ditado solto"}
                    {item.post_process_requested ? " · máscara + IA" : ""}
                  </span>
                  <span className="ms-auto shrink-0 w-44">
                    <AudioPlayerGroup>
                      <AudioPlayer
                        onLoadRequest={() => urlDoAudio(item.file_name)}
                        className="w-full"
                      />
                    </AudioPlayerGroup>
                  </span>
                </div>
                <div className="p-3">
                  <pre className="whitespace-pre-wrap text-[11.5px] leading-relaxed font-sans rounded-lg border border-mid-gray/20 bg-white text-black p-3 max-h-64 overflow-y-auto select-text">
                    {texto || "(sem texto)"}
                  </pre>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={ocupado !== ""}
                      onClick={() => void colarNoRis()}
                    >
                      Colar no RIS
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void copyToClipboard(texto)}
                    >
                      <span className="flex items-center gap-1.5">
                        <Copy size={13} /> Copiar
                      </span>
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => aoAbrirNoLaudo?.(texto)}
                    >
                      <span className="flex items-center gap-1.5">
                        <PenLine size={13} /> Abrir no Laudo
                      </span>
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={ocupado !== ""}
                      onClick={() => void rodarIA()}
                    >
                      <span className="flex items-center gap-1.5">
                        <Sparkles size={13} />
                        {ocupado === "ia" ? "a IA está lendo…" : "Rodar a IA de novo"}
                      </span>
                    </Button>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-mid-gray/20 bg-background">
                <div className="px-3 py-2 text-xs font-semibold border-b border-mid-gray/20 bg-mid-gray/5">
                  Deste item
                </div>
                <div className="p-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[11px]">
                  <div className="flex justify-between border-b border-mid-gray/10 py-0.5">
                    <span className="text-mid-gray">Ditado cru</span>
                    <span>
                      {item.transcription_text.length.toLocaleString("pt-BR")} car.
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-mid-gray/10 py-0.5">
                    <span className="text-mid-gray">Texto final</span>
                    <span>{texto.length.toLocaleString("pt-BR")} car.</span>
                  </div>
                  <div className="flex justify-between border-b border-mid-gray/10 py-0.5">
                    <span className="text-mid-gray">Passou pela IA</span>
                    <span>{item.post_process_requested ? "sim" : "não"}</span>
                  </div>
                  <div className="flex justify-between border-b border-mid-gray/10 py-0.5">
                    <span className="text-mid-gray">Áudio</span>
                    <span className="truncate ps-2">{item.file_name}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-2 bg-background border-t border-mid-gray/20">
        {item && (
          <Button
            variant="danger-ghost"
            size="sm"
            onClick={() => void apagar(item.id)}
          >
            <span className="flex items-center gap-1.5">
              <Trash2 size={13} /> Apagar este item
            </span>
          </Button>
        )}
        <span className="ms-auto text-[11px] text-mid-gray">
          {aviso || "lista de 24 h · áudio e texto só neste computador"}
        </span>
      </div>
    </div>
  );
};

export default HistoricoPage;
