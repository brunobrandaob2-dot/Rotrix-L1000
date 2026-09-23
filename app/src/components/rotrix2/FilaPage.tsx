/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Fila.
//
// Lista corrida dos exames na ordem do download: os que o Radius registrou e
// também os que apareceram na pasta por fora (baixados pelo navegador). Dá
// para marcar um, vários ou todos, abrir juntos no RadiAnt e apagar do
// computador (vai para a Lixeira do Windows, então dá para restaurar).
//
// O nome do paciente não sai do computador: o roteador manda só as INICIAIS,
// junto de hora, modalidade, descrição e situação.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { RefreshCw, FolderOpen, Layers, Check, Trash2, Download } from "lucide-react";
import { Button } from "../ui/Button";
import { Dica } from "./Dica";

interface Estudo {
  id: string;
  modalidade: string;
  descricao: string;
  status: string;
  laudado: boolean | null;
  entrou: string;
  iniciais?: string;
  origem?: string;
  cabecalho?: string;
  mascara?: string | null;
  feito?: boolean;
  arquivos?: number;
  bytes?: number;
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

const dia = (iso: string): string => {
  const d = (iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return d ? `${d[3]}/${d[2]}` : "";
};

const tamanho = (bytes?: number): string => {
  if (!bytes) return "";
  const mb = bytes / 1048576;
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
};

const nomeDoExame = (e: Estudo): string =>
  e.descricao || e.cabecalho || (e.origem === "pasta" ? "pasta baixada por fora" : "exame sem descrição");

export const FilaPage: React.FC = () => {
  const [fila, setFila] = useState<Fila | null>(null);
  const [marcados, setMarcados] = useState<string[]>([]);
  const [soPendentes, setSoPendentes] = useState(false);
  const [aviso, setAviso] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const ultimoClique = useRef<string | null>(null);

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

  const itens = (fila?.itens || []).filter(
    (i) => !soPendentes || !(i.feito || i.laudado),
  );
  const daVez = fila?.vez || fila?.atual || null;
  const oDaVez = itens.find((i) => i.id === daVez) || null;
  const todosMarcados = itens.length > 0 && marcados.length === itens.length;

  // Ctrl+A marca a lista inteira, como em qualquer lista do Windows
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        const alvo = e.target as HTMLElement | null;
        if (alvo && /input|textarea/i.test(alvo.tagName)) return;
        e.preventDefault();
        setMarcados(todosMarcados ? [] : itens.map((i) => i.id));
      }
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [itens, todosMarcados]);

  const escolher = async (id: string) => {
    try {
      await invoke<string>("rotrix_fila_escolher", { id });
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
      const bruto = await invoke<string>("rotrix_abrir_estudos", { ids: marcados });
      const r = JSON.parse(bruto || "{}");
      if (!r.ok) {
        setAviso(
          r.motivo === "sem_caminho"
            ? "o Radius não guarda o caminho da pasta destes exames — abra pela pasta"
            : r.motivo === "radiant_nao_encontrado"
              ? "não achei o RadiAnt instalado neste computador"
              : `não consegui abrir (${r.motivo || "erro"})`,
        );
      } else {
        setAviso(`abrindo ${r.abertos} exame(s) no RadiAnt`);
      }
    } catch (e) {
      setAviso(String(e));
    }
  };

  const apagar = async () => {
    if (!marcados.length) return;
    setConfirmar(false);
    try {
      const bruto = await invoke<string>("rotrix_apagar_estudos", { ids: marcados });
      const r = JSON.parse(bruto || "{}");
      if (r.ok) {
        setAviso(
          `${r.apagados} exame(s) na Lixeira do Windows · ${r.fora_da_lista} fora da lista`,
        );
      } else {
        setAviso(
          r.motivo === "falhou_apagar"
            ? "algum arquivo estava aberto e não deu para apagar — feche o RadiAnt e tente de novo"
            : `não consegui apagar (${r.motivo || "erro"})`,
        );
      }
      setMarcados([]);
      await ler();
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

  const alterna = (id: string, faixa = false) => {
    if (faixa && ultimoClique.current) {
      const a = itens.findIndex((i) => i.id === ultimoClique.current);
      const b = itens.findIndex((i) => i.id === id);
      if (a >= 0 && b >= 0) {
        const [i, j] = a < b ? [a, b] : [b, a];
        const bloco = itens.slice(i, j + 1).map((x) => x.id);
        setMarcados((m) => [...new Set([...m, ...bloco])]);
        ultimoClique.current = id;
        return;
      }
    }
    ultimoClique.current = id;
    setMarcados((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  };

  const porFora = itens.filter((i) => i.origem === "pasta").length;

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* barra */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <h2 className="text-base font-semibold">Fila</h2>
        <span className="text-[11px] rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 px-2 py-0.5">
          {itens.length} exame{itens.length === 1 ? "" : "s"}
          {porFora > 0 ? ` · ${porFora} por fora` : ""}
        </span>
        <div className="ms-auto flex items-center gap-1.5">
          <Button
            variant={soPendentes ? "primary-soft" : "secondary"}
            size="sm"
            onClick={() => setSoPendentes((v) => !v)}
          >
            Só não laudados
          </Button>
          <Dica texto="Abre a pasta onde o Radius baixa os exames.">
            <Button variant="secondary" size="sm" onClick={() => void abrirPasta()}>
              <span className="flex items-center gap-1.5">
                <FolderOpen size={14} /> Abrir a pasta
              </span>
            </Button>
          </Dica>
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
              Nenhum exame na pasta ainda. Assim que o Radius baixar — ou você
              baixar pelo navegador — ele aparece aqui.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-mid-gray bg-mid-gray/5">
                  <th className="w-9 py-2">
                    <Dica texto="Marcar ou desmarcar a lista inteira (Ctrl+A)." lado="baixo">
                      <button
                        type="button"
                        aria-label="Marcar todos"
                        onClick={() =>
                          setMarcados(todosMarcados ? [] : itens.map((i) => i.id))
                        }
                        className={`inline-flex h-4 w-4 items-center justify-center rounded border cursor-pointer ${
                          todosMarcados
                            ? "bg-logo-primary border-logo-primary text-white"
                            : marcados.length
                              ? "border-logo-primary text-logo-primary"
                              : "border-mid-gray/40"
                        }`}
                      >
                        {todosMarcados ? (
                          <Check size={11} />
                        ) : marcados.length ? (
                          <span className="h-0.5 w-2 bg-logo-primary" />
                        ) : null}
                      </button>
                    </Dica>
                  </th>
                  <th className="w-14 text-start font-medium">hora</th>
                  <th className="w-14 text-start font-medium">paciente</th>
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
                      onClick={(e) => alterna(i.id, (e as unknown as MouseEvent).shiftKey)}
                      onDoubleClick={() => void escolher(i.id)}
                      className={`border-t border-mid-gray/10 cursor-pointer select-none ${
                        marcado ? "bg-logo-primary/10" : "hover:bg-mid-gray/5"
                      } ${pronto ? "opacity-50" : ""}`}
                    >
                      <td className="py-2 text-center">
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
                      <td className="text-mid-gray tabular-nums" title={dia(i.entrou)}>
                        {hora(i.entrou)}
                      </td>
                      <td className="text-mid-gray tabular-nums text-xs">
                        {i.iniciais || "—"}
                      </td>
                      <td>
                        <span className="text-[10px] font-bold rounded bg-logo-primary/15 px-1.5 py-0.5">
                          {(i.modalidade || "--").toUpperCase()}
                        </span>
                      </td>
                      <td className="truncate pe-2">
                        {nomeDoExame(i)}
                        {i.origem === "pasta" && (
                          <span className="ms-1.5 inline-flex items-center gap-1 text-[9px] font-semibold rounded bg-amber-400/20 text-amber-700 px-1 py-0.5">
                            <Download size={9} /> fora do Radius
                            {i.bytes ? ` · ${tamanho(i.bytes)}` : ""}
                          </span>
                        )}
                      </td>
                      <td className="text-[11px]">
                        {vez && (
                          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 px-2 py-0.5">
                            da vez
                          </span>
                        )}
                        {pronto && !vez && <span className="text-mid-gray">laudado</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <p className="px-3 py-2 text-[11px] text-mid-gray border-t border-mid-gray/10">
            clique marca · Shift+clique marca a faixa · Ctrl+A marca tudo ·
            clique duplo escolhe o exame da vez
          </p>
        </div>

        {/* painel */}
        <div className="w-64 shrink-0 flex flex-col gap-3 overflow-y-auto">
          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="px-3 py-2 text-xs font-semibold border-b border-mid-gray/20 bg-mid-gray/5">
              Marcados · {marcados.length}
            </div>
            <div className="p-3 flex flex-col gap-2">
              {marcados.length === 0 ? (
                <p className="text-[11px] text-mid-gray">
                  Marque os exames para abrir juntos ou apagar.
                </p>
              ) : (
                marcados.slice(0, 8).map((id) => {
                  const e = fila?.itens.find((x) => x.id === id);
                  return (
                    <div key={id} className="flex items-center gap-2 text-[11px]">
                      <span className="text-[10px] font-bold rounded bg-logo-primary/15 px-1.5 py-0.5">
                        {(e?.modalidade || "--").toUpperCase()}
                      </span>
                      <span className="truncate flex-1">
                        {e ? `${e.iniciais || ""} ${nomeDoExame(e)}`.trim() : id}
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
              {marcados.length > 8 && (
                <p className="text-[10px] text-mid-gray">
                  e mais {marcados.length - 8}…
                </p>
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
              {!confirmar ? (
                <Button
                  variant="danger-ghost"
                  size="sm"
                  disabled={!marcados.length}
                  onClick={() => setConfirmar(true)}
                >
                  <span className="flex items-center justify-center gap-1.5">
                    <Trash2 size={14} /> Apagar do computador
                  </span>
                </Button>
              ) : (
                <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-2 flex flex-col gap-2">
                  <p className="text-[11px]">
                    Mandar {marcados.length} exame(s) para a Lixeira do Windows?
                    Dá para restaurar de lá.
                  </p>
                  <div className="flex gap-2">
                    <Button variant="danger" size="sm" onClick={() => void apagar()}>
                      Apagar
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setConfirmar(false)}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
              {marcados.length > 0 && !confirmar && (
                <Button variant="secondary" size="sm" onClick={() => setMarcados([])}>
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
                  ? `${oDaVez.iniciais || ""} ${nomeDoExame(oDaVez)}`.trim()
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
        {aviso || "da lista sai só as iniciais — o nome do paciente não sai do computador"}
      </div>
    </div>
  );
};

export default FilaPage;
