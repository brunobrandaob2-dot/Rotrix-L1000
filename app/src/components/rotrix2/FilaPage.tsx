/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Fila.
//
// Lista corrida dos exames que o Radius baixou, na ordem do download, com
// caixa de seleção: marque dois e abra juntos no RadiAnt para comparar.
// Clicar na linha escolhe o exame da vez (é ele que dá o cabeçalho da máscara).
//
// O roteador lê os arquivos de estado do Radius no próprio computador e só
// devolve hora, modalidade, descrição e situação. Nome de paciente não sobe.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { RefreshCw, FolderOpen, Layers, Check } from "lucide-react";
import { Button } from "../ui/Button";

interface Estudo {
  id: string;
  modalidade: string;
  descricao: string;
  status: string;
  laudado: boolean | null;
  entrou: string;
  cabecalho: string;
  mascara: string | null;
  feito?: boolean;
}

interface Fila {
  disponivel: boolean;
  pasta_existe?: boolean;
  itens: Estudo[];
  atual: string | null;
  vez?: string | null;
  escolhido?: string | null;
  perfil_automatico: boolean;
}

const hora = (iso: string): string => {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}:\d{2})/);
  if (m) return m[1];
  const d = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return d ? `${d[3]}/${d[2]}` : iso.slice(0, 5);
};

export const FilaPage: React.FC = () => {
  const [fila, setFila] = useState<Fila | null>(null);
  const [marcados, setMarcados] = useState<string[]>([]);
  const [soPendentes, setSoPendentes] = useState(false);
  const [aviso, setAviso] = useState("");
  const [carregando, setCarregando] = useState(false);

  const ler = useCallback(async () => {
    setCarregando(true);
    try {
      const bruto = await invoke<string>("rotrix_fila");
      setFila(JSON.parse(bruto || "{}"));
      setAviso("");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void ler();
    const t = setInterval(() => void ler(), 20000);
    const p = listen("rotrix-proximo-exame", () => void ler());
    return () => {
      clearInterval(t);
      p.then((fn) => fn());
    };
  }, [ler]);

  const escolher = async (id: string) => {
    try {
      const bruto = await invoke<string>("rotrix_fila_escolher", { id });
      JSON.parse(bruto || "{}");
      await ler();
    } catch (e) {
      setAviso(String(e));
    }
  };

  const marcarLaudado = async (id: string, feito: boolean) => {
    try {
      await invoke<string>("rotrix_fila_feito", { id, feito });
      await ler();
    } catch (e) {
      setAviso(String(e));
    }
  };

  const proximo = async () => {
    try {
      await invoke<string>("rotrix_fila_proximo");
      await ler();
    } catch (e) {
      setAviso(String(e));
    }
  };

  const abrirJuntos = async () => {
    if (!marcados.length) return;
    try {
      const bruto = await invoke<string>("rotrix_abrir_estudos", {
        ids: marcados,
      });
      const r = JSON.parse(bruto || "{}");
      if (!r.ok) {
        setAviso(
          r.motivo === "sem_caminho"
            ? "o Radius não guarda o caminho da pasta destes exames — abra pela pasta"
            : `não consegui abrir (${r.motivo || "erro"})`,
        );
      } else {
        setAviso(`abrindo ${marcados.length} no RadiAnt`);
      }
    } catch (e) {
      setAviso(String(e));
    }
  };

  const abrirPasta = async () => {
    try {
      await invoke("rotrix_abrir_pasta");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const alterna = (id: string) =>
    setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));

  const itens = (fila?.itens || []).filter(
    (i) => !soPendentes || !(i.feito || i.laudado),
  );
  const daVez = fila?.vez || fila?.atual || null;
  const oDaVez = itens.find((i) => i.id === daVez) || null;

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* barra */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <h2 className="text-base font-semibold">Fila</h2>
        <span className="text-[11px] rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 px-2 py-0.5">
          {itens.length} exame{itens.length === 1 ? "" : "s"}
        </span>
        <div className="ms-auto flex items-center gap-1.5">
          <Button
            variant={soPendentes ? "primary-soft" : "secondary"}
            size="sm"
            onClick={() => setSoPendentes((v) => !v)}
          >
            Só não laudados
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void abrirPasta()}>
            <span className="flex items-center gap-1.5">
              <FolderOpen size={14} /> Abrir a pasta
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
        <div className="flex-1 min-w-0 overflow-y-auto rounded-lg border border-mid-gray/20 bg-background">
          {!fila?.disponivel ? (
            <p className="p-4 text-sm text-mid-gray">
              O roteador não está lendo a pasta do Radius. Aponte a pasta em
              Configurações.
            </p>
          ) : itens.length === 0 ? (
            <p className="p-4 text-sm text-mid-gray">
              Nenhum exame baixado ainda. Assim que o Radius baixar, ele aparece
              aqui.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-mid-gray bg-mid-gray/5">
                  <th className="w-8 py-2" />
                  <th className="w-14 text-start font-medium">hora</th>
                  <th className="w-14 text-start font-medium">mod.</th>
                  <th className="text-start font-medium">exame</th>
                  <th className="w-28 text-start font-medium">situação</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((i) => {
                  const marcado = marcados.includes(i.id);
                  const vez = i.id === daVez;
                  const pronto = Boolean(i.feito || i.laudado);
                  return (
                    <tr
                      key={i.id}
                      onClick={() => void escolher(i.id)}
                      className={`border-t border-mid-gray/10 cursor-pointer ${
                        marcado ? "bg-logo-primary/10" : "hover:bg-mid-gray/5"
                      } ${pronto ? "opacity-50" : ""}`}
                    >
                      <td
                        className="py-2 text-center"
                        onClick={(e) => {
                          e.stopPropagation();
                          alterna(i.id);
                        }}
                      >
                        <span
                          className={`inline-flex h-4 w-4 items-center justify-center rounded border ${
                            marcado
                              ? "bg-logo-primary border-logo-primary text-white"
                              : "border-mid-gray/40"
                          }`}
                        >
                          {marcado && <Check size={11} />}
                        </span>
                      </td>
                      <td className="text-mid-gray tabular-nums">
                        {hora(i.entrou)}
                      </td>
                      <td>
                        <span className="text-[10px] font-bold rounded bg-logo-primary/15 px-1.5 py-0.5">
                          {(i.modalidade || "--").toUpperCase()}
                        </span>
                      </td>
                      <td className="truncate pe-2">
                        {i.descricao || i.cabecalho || "exame sem descrição"}
                      </td>
                      <td className="text-[11px]">
                        {vez && (
                          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 px-2 py-0.5">
                            da vez
                          </span>
                        )}
                        {pronto && !vez && (
                          <span className="text-mid-gray">laudado</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <p className="px-3 py-2 text-[11px] text-mid-gray border-t border-mid-gray/10">
            clique na linha para escolher o exame da vez · clique na caixa para
            juntar no RadiAnt
          </p>
        </div>

        {/* painel */}
        <div className="w-64 shrink-0 flex flex-col gap-3 overflow-y-auto">
          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="px-3 py-2 text-xs font-semibold border-b border-mid-gray/20 bg-mid-gray/5">
              Marcados para abrir · {marcados.length}
            </div>
            <div className="p-3 flex flex-col gap-2">
              {marcados.length === 0 ? (
                <p className="text-[11px] text-mid-gray">
                  Marque os exames que devem abrir juntos.
                </p>
              ) : (
                marcados.map((id) => {
                  const e = fila?.itens.find((x) => x.id === id);
                  return (
                    <div key={id} className="flex items-center gap-2 text-[11px]">
                      <span className="text-[10px] font-bold rounded bg-logo-primary/15 px-1.5 py-0.5">
                        {(e?.modalidade || "--").toUpperCase()}
                      </span>
                      <span className="truncate flex-1">
                        {e?.descricao || id}
                      </span>
                      <button
                        type="button"
                        className="text-mid-gray hover:text-text cursor-pointer"
                        onClick={() => alterna(id)}
                      >
                        ×
                      </button>
                    </div>
                  );
                })
              )}
              <Button
                variant="primary"
                size="sm"
                disabled={!marcados.length}
                onClick={() => void abrirJuntos()}
              >
                <span className="flex items-center justify-center gap-1.5">
                  <Layers size={14} /> Abrir no RadiAnt ({marcados.length})
                </span>
              </Button>
              {marcados.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setMarcados([])}
                >
                  Limpar seleção
                </Button>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="px-3 py-2 text-xs font-semibold border-b border-mid-gray/20 bg-mid-gray/5">
              Exame da vez
            </div>
            <div className="p-3 flex flex-col gap-2">
              <p className="text-[11px]">
                {oDaVez
                  ? oDaVez.descricao || oDaVez.cabecalho || "exame sem descrição"
                  : "nenhum escolhido"}
              </p>
              <div className="flex gap-2">
                {oDaVez && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void marcarLaudado(oDaVez.id, true)}
                  >
                    Laudado
                  </Button>
                )}
                <Button variant="secondary" size="sm" onClick={() => void proximo()}>
                  Próximo
                </Button>
              </div>
              <p className="text-[11px] text-mid-gray">
                {fila?.perfil_automatico
                  ? "a máscara do ditado já entra com o cabeçalho deste exame"
                  : "perfil automático desligado nas configurações"}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="px-3 py-2 bg-background border-t border-mid-gray/20 text-[11px] text-mid-gray">
        {aviso || "nome de paciente não sai do computador"}
      </div>
    </div>
  );
};

export default FilaPage;
