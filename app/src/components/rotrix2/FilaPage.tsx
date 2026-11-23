/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Fila (22/11/2026: a fila do Radius dentro do Rotrix).
//
// Abas como as do Radius, com nomes claros: E-Laudos · Laudados · Estatística ·
// Mobilemed e outros · Laudados outros. Um clique no botão Abrir (entre a hora
// e o nome) abre o exame; clicar e arrastar marca vários; Shift marca a faixa;
// Ctrl alterna um; Ctrl+A marca a aba inteira. O rodapé é o do Radius:
// visualizador (RadiAnt | RadioWant), janela do RadioWant, Autoabrir e os botões.
//
// O nome do paciente não sai do computador: o cabeçalho DICOM é lido aqui.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { RefreshCw, FolderOpen, Check } from "lucide-react";
import { Button } from "../ui/Button";
import { Ajuda } from "./Dica";
import { painel } from "./painelComum";
import {
  type Estudo,
  type Fila,
  type Visualizador,
  type JanelaRW,
  lerFila,
  pronto,
  baixando,
  ehOutro,
  hora,
  dia,
  tamanho,
  nomeDoExame,
  nomeDoPaciente,
  salvarVisualizador,
  abrirEstudos,
  abrirUm,
  autoabrirLigado,
  ligarAutoabrir,
} from "./filaComum";

type Aba = "elaudos" | "laudados" | "estatistica" | "outros" | "laudout";

const ABAS: { id: Aba; nome: string }[] = [
  { id: "elaudos", nome: "E-Laudos" },
  { id: "laudados", nome: "Laudados" },
  { id: "estatistica", nome: "Estatística" },
  { id: "outros", nome: "Mobilemed e outros" },
  { id: "laudout", nome: "Laudados outros" },
];

const daAba = (aba: Aba, e: Estudo): boolean => {
  if (aba === "elaudos") return !ehOutro(e) && !pronto(e);
  if (aba === "laudados") return !ehOutro(e) && pronto(e);
  if (aba === "outros") return ehOutro(e) && !pronto(e);
  if (aba === "laudout") return ehOutro(e) && pronto(e);
  return false;
};

const origem = (e: Estudo): string => (ehOutro(e) ? "Mobilemed / Downloads" : "E-Laudos");

const Seg: React.FC<{
  opcoes: [string, string][];
  valor: string;
  aoTrocar: (v: string) => void;
}> = ({ opcoes, valor, aoTrocar }) => (
  <div className="inline-flex">
    {opcoes.map(([id, nome], i) => (
      <button
        key={id}
        type="button"
        onClick={() => aoTrocar(id)}
        className={`h-7 px-3 text-[12px] border cursor-pointer -ms-px first:ms-0 ${
          i === 0 ? "rounded-s-md" : ""
        } ${i === opcoes.length - 1 ? "rounded-e-md" : ""} ${
          valor === id
            ? "bg-logo-primary border-logo-primary text-white relative"
            : "border-mid-gray/30 text-mid-gray hover:text-text"
        }`}
      >
        {nome}
      </button>
    ))}
  </div>
);

export const FilaPage: React.FC = () => {
  const [fila, setFila] = useState<Fila | null>(null);
  const [aba, setAba] = useState<Aba>("elaudos");
  const [marcados, setMarcados] = useState<string[]>([]);
  const [busca, setBusca] = useState("");
  const [aviso, setAviso] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [confirmar, setConfirmar] = useState<"" | "outros" | "marcados">("");
  const [auto, setAuto] = useState(autoabrirLigado());
  const ultimoClique = useRef<string | null>(null);
  // arrastar para marcar: o valor que o arrasto está aplicando (marcar ou desmarcar)
  const arrasto = useRef<{ valor: boolean; n: number } | null>(null);

  const ler = useCallback(async () => {
    setCarregando(true);
    try {
      setFila(await lerFila());
    } catch (e) {
      setAviso(String(e));
    } finally {
      setCarregando(false);
    }
  }, []);

  // Fase 4: o Rotrix baixa do E-Laudos. Quem atende os links (Radius ou Rotrix)
  // e o andamento; com download andando, a lista se atualiza a cada 2 s.
  const [el, setEl] = useState<{ atende?: string; baixando?: unknown[]; na_fila?: number } | null>(null);
  useEffect(() => {
    let vivo = true;
    const passo = async () => {
      try {
        const r = (await painel("elaudos_estado")) as unknown as {
          ok?: boolean;
          atende?: string;
          baixando?: unknown[];
          na_fila?: number;
        };
        if (!vivo || !r.ok) return;
        setEl(r);
        if ((r.baixando?.length || 0) + (r.na_fila || 0) > 0) setFila(await lerFila());
      } catch {
        /* roteador antigo (sem a fase 4) ou parado */
      }
    };
    void passo();
    const t = setInterval(() => void passo(), 2000);
    return () => {
      vivo = false;
      clearInterval(t);
    };
  }, []);
  const linksNoRotrix = el?.atende === "rotrix";
  const trocarLinks = async (v: string) => {
    try {
      const r = await painel(v === "rotrix" ? "elaudos_ligar" : "elaudos_desligar");
      setEl((x) => ({ ...(x || {}), atende: (r as unknown as { atende?: string }).atende || x?.atende }));
      setAviso(
        r.ok
          ? v === "rotrix"
            ? "pronto: clicar no exame no E-Laudos agora baixa pelo Rotrix"
            : "os links do E-Laudos voltaram para o Radius"
          : r.frase || `não deu: ${r.motivo || "erro"}`,
      );
    } catch (e) {
      setAviso(String(e));
    }
  };
  const downloadE = async (acao: "cancelar" | "repetir", id: string) => {
    try {
      const r = await painel(`elaudos_${acao}`, { id });
      setAviso(r.ok ? (acao === "cancelar" ? "download cancelado" : "baixando de novo") : r.frase || "não deu");
      setFila(await lerFila());
    } catch (e) {
      setAviso(String(e));
    }
  };

  useEffect(() => {
    void ler();
    const t = setInterval(() => void ler(), 15000);
    const p = listen("rotrix-proximo-exame", () => void ler());
    const a = (e: Event) => setAuto(Boolean((e as CustomEvent<boolean>).detail));
    window.addEventListener("rotrix:autoabrir", a);
    return () => {
      clearInterval(t);
      p.then((fn) => fn());
      window.removeEventListener("rotrix:autoabrir", a);
    };
  }, [ler]);

  const todos = fila?.itens || [];
  const itens = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return todos
      .filter((e) => daAba(aba, e))
      .filter(
        (e) =>
          !q || `${nomeDoPaciente(e)} ${nomeDoExame(e)} ${e.modalidade}`.toLowerCase().includes(q),
      );
  }, [todos, aba, busca]);

  const conta = (a: Aba) => todos.filter((e) => daAba(a, e)).length;
  const daVez = fila?.vez || fila?.atual || null;
  // 22/11 (teste dele): o botão escolhido muda NA HORA. Antes ele esperava o
  // roteador confirmar — e o roteador antigo (Documentos) não sabia guardar,
  // então o botão "voltava" calado para RadiAnt / Atual.
  const [visLocal, setVisLocal] = useState<Visualizador | null>(null);
  const [janelaLocal, setJanelaLocal] = useState<JanelaRW | null>(null);
  const vis: Visualizador = visLocal || fila?.visualizador || "radiant";
  const janela: JanelaRW = janelaLocal || fila?.radiowant_janela || "atual";
  const roteadorAntigo = Boolean(fila?.disponivel) && fila?.visualizador === undefined;
  const selecionado =
    todos.find((e) => e.id === ultimoClique.current) || todos.find((e) => e.id === daVez) || null;

  // trocar de aba limpa a seleção (o que estava marcado não aparece mais)
  useEffect(() => {
    setMarcados([]);
    ultimoClique.current = null;
  }, [aba]);

  // Ctrl+A marca a aba inteira, como em qualquer lista do Windows
  const todosMarcados = itens.length > 0 && itens.every((i) => marcados.includes(i.id));
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        const alvo = e.target as HTMLElement | null;
        if (alvo && /input|textarea/i.test(alvo.tagName)) return;
        if (alvo && alvo.isContentEditable) return;
        e.preventDefault();
        setMarcados(todosMarcados ? [] : itens.map((i) => i.id));
      }
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [itens, todosMarcados]);

  // soltar o mouse em qualquer lugar termina o arrasto
  useEffect(() => {
    const soltar = () => {
      if (arrasto.current && arrasto.current.n > 1)
        setAviso(`${arrasto.current.n} exames ${arrasto.current.valor ? "marcados" : "desmarcados"} arrastando`);
      arrasto.current = null;
    };
    document.addEventListener("mouseup", soltar);
    return () => document.removeEventListener("mouseup", soltar);
  }, []);

  const aoApertar = (e: React.MouseEvent, id: string) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("[data-abrir]")) return;
    e.preventDefault();
    if (e.shiftKey && ultimoClique.current) {
      const a = itens.findIndex((i) => i.id === ultimoClique.current);
      const b = itens.findIndex((i) => i.id === id);
      if (a >= 0 && b >= 0) {
        const [i, j] = a < b ? [a, b] : [b, a];
        const bloco = itens.slice(i, j + 1).map((x) => x.id);
        setMarcados((m) => [...new Set([...m, ...bloco])]);
        return;
      }
    }
    const ja = marcados.includes(id);
    if (!e.ctrlKey && !e.metaKey && !ja) {
      setMarcados([id]);
      arrasto.current = { valor: true, n: 1 };
    } else {
      setMarcados((m) => (ja ? m.filter((x) => x !== id) : [...m, id]));
      arrasto.current = { valor: !ja, n: 1 };
    }
    ultimoClique.current = id;
  };

  const aoPassar = (id: string) => {
    const a = arrasto.current;
    if (!a) return;
    setMarcados((m) => {
      const tem = m.includes(id);
      if (tem === a.valor) return m;
      a.n += 1;
      return a.valor ? [...m, id] : m.filter((x) => x !== id);
    });
  };

  const abrir = async (id: string) => {
    const r = await abrirUm(id);
    setAviso(r.frase);
    await ler();
  };

  const abrirMarcados = async () => {
    const ids = itens.filter((i) => marcados.includes(i.id)).map((i) => i.id);
    const r = await abrirEstudos(ids);
    setAviso(ids.length > 1 && r.ok ? `${r.frase}, juntos na mesma janela` : r.frase);
  };

  const marcarLaudados = async (ids: string[], frase: string) => {
    if (!ids.length) {
      setAviso("marque os exames primeiro");
      return;
    }
    try {
      for (const id of ids) await invoke<string>("rotrix_fila_feito", { id, feito: true });
      setAviso(frase.replace("{n}", String(ids.length)));
      setMarcados([]);
      await ler();
    } catch (e) {
      setAviso(String(e));
    }
  };

  const apagar = async (ids: string[]) => {
    setConfirmar("");
    if (!ids.length) return;
    try {
      const r = JSON.parse((await invoke<string>("rotrix_apagar_estudos", { ids })) || "{}");
      setAviso(
        r.ok
          ? `${r.apagados} exame(s) na Lixeira do Windows (dá para restaurar de lá)`
          : r.motivo === "falhou_apagar"
            ? "algum arquivo estava aberto — feche o visualizador e tente de novo"
            : `não consegui apagar (${r.motivo || "erro"})`,
      );
      setMarcados([]);
      await ler();
    } catch (e) {
      setAviso(String(e));
    }
  };

  const AVISO_ANTIGO =
    "o roteador que está rodando é o antigo e não guarda esta escolha: feche o Rotrix (e o Roteador de Laudos) e abra de novo";

  const trocarVisualizador = async (v: string) => {
    setVisLocal(v as Visualizador);
    try {
      await salvarVisualizador({ visualizador: v as Visualizador });
      const f = await lerFila();
      setFila(f);
      setAviso(
        f.visualizador === undefined
          ? AVISO_ANTIGO
          : `o botão Abrir agora abre no ${v === "radiowant" ? "RadioWant" : "RadiAnt"}`,
      );
    } catch (e) {
      setAviso(`não gravei o visualizador: ${String(e)}`);
    }
  };

  const trocarJanela = async (v: string) => {
    setJanelaLocal(v as JanelaRW);
    try {
      await salvarVisualizador({ radiowant_janela: v as JanelaRW });
      const f = await lerFila();
      setFila(f);
      setAviso(
        f.radiowant_janela === undefined
          ? AVISO_ANTIGO
          : v === "nova"
            ? "o RadioWant vai abrir cada exame numa janela nova"
            : "o exame novo vai substituir o que está aberto no RadioWant",
      );
    } catch (e) {
      setAviso(`não gravei a janela do RadioWant: ${String(e)}`);
    }
  };

  const abrirPasta = async () => {
    try {
      await invoke("rotrix_abrir_pasta");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const nMarcados = itens.filter((i) => marcados.includes(i.id)).length;
  const outrosTodos = todos.filter(ehOutro).map((e) => e.id);
  const pendentesDaAba = itens.filter((e) => !pronto(e)).map((e) => e.id);

  return (
    <div className="flex flex-col h-full min-h-0 bg-background">
      {/* abas como as do Radius */}
      <div className="flex items-stretch gap-0.5 px-3 border-b border-mid-gray/20 bg-mid-gray/5">
        {ABAS.map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => setAba(a.id)}
            className={`h-10 px-4 text-[13px] cursor-pointer border-b-2 ${
              aba === a.id
                ? "border-logo-primary text-text font-semibold bg-background"
                : "border-transparent text-mid-gray hover:text-text"
            }`}
          >
            {a.nome}
            {a.id !== "estatistica" && (
              <span className="ms-1 text-[11px] text-mid-gray">({conta(a.id)})</span>
            )}
          </button>
        ))}
        <div className="ms-auto flex items-center gap-1.5">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar paciente ou exame"
            className="h-7 w-56 rounded-md border border-mid-gray/30 bg-background px-2 text-[12px]"
          />
          <Button variant="secondary" size="sm" onClick={() => void abrirPasta()}>
            <span className="flex items-center gap-1.5">
              <FolderOpen size={14} /> Pasta
            </span>
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void ler()}>
            <RefreshCw size={14} className={carregando ? "animate-spin" : ""} />
          </Button>
        </div>
      </div>

      {/* lista ou estatística */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {!fila?.disponivel ? (
          <p className="p-4 text-sm text-mid-gray">
            O roteador não está lendo a pasta do Radius. Aponte a pasta em Configurações.
          </p>
        ) : aba === "estatistica" ? (
          <Estatistica itens={todos} />
        ) : itens.length === 0 ? (
          <p className="p-4 text-sm text-mid-gray">Nenhum exame nesta aba.</p>
        ) : (
          <table className="w-full text-[13px] select-none">
            <thead className="sticky top-0 bg-background z-10">
              <tr className="text-[10px] uppercase tracking-wide text-mid-gray border-b border-mid-gray/20">
                <th className="w-9 py-2">
                  <button
                    type="button"
                    aria-label="Marcar todos"
                    onClick={() => setMarcados(todosMarcados ? [] : itens.map((i) => i.id))}
                    className={`inline-flex h-4 w-4 items-center justify-center rounded border cursor-pointer ${
                      todosMarcados
                        ? "bg-logo-primary border-logo-primary text-white"
                        : "border-mid-gray/40"
                    }`}
                  >
                    {todosMarcados && <Check size={11} />}
                  </button>
                </th>
                <th className="w-16 text-start font-medium">baixado</th>
                <th className="w-20" />
                <th className="text-start font-medium">paciente</th>
                <th className="w-14 text-start font-medium">mod.</th>
                <th className="text-start font-medium">exame</th>
                <th className="w-24 text-start font-medium">tamanho</th>
                <th className="w-28 text-start font-medium">status</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((i) => {
                const marcado = marcados.includes(i.id);
                const vez = i.id === daVez;
                const emDownload = baixando(i);
                return (
                  <tr
                    key={i.id}
                    onMouseDown={(e) => aoApertar(e, i.id)}
                    onMouseEnter={() => aoPassar(i.id)}
                    onDoubleClick={() => void abrir(i.id)}
                    className={`border-b border-mid-gray/10 cursor-default ${
                      marcado ? "bg-logo-primary/15" : vez ? "bg-logo-primary/8" : "hover:bg-mid-gray/8"
                    }`}
                    style={vez ? { boxShadow: "inset 3px 0 0 var(--color-logo-primary, #82aee6)" } : undefined}
                  >
                    <td className="py-2 text-center">
                      <span
                        className={`inline-flex h-4 w-4 items-center justify-center rounded border ${
                          marcado ? "bg-logo-primary border-logo-primary text-white" : "border-mid-gray/40"
                        }`}
                      >
                        {marcado && <Check size={11} />}
                      </span>
                    </td>
                    <td className="text-mid-gray tabular-nums text-[12px]" title={dia(i.entrou)}>
                      {hora(i.entrou)}
                    </td>
                    <td>
                      {emDownload ? (
                        <button
                          type="button"
                          data-abrir
                          title="Cancelar o download"
                          onClick={() => void downloadE("cancelar", i.id)}
                          className="h-6 px-2 rounded-md border border-amber-500/40 text-[11px] text-amber-600 cursor-pointer hover:bg-amber-500/10"
                        >
                          Cancelar
                        </button>
                      ) : !ehOutro(i) && /^(falhou|cancelado|interrompido)/i.test(i.status || "") ? (
                        <button
                          type="button"
                          data-abrir
                          onClick={() => void downloadE("repetir", i.id)}
                          className="h-6 px-2 rounded-md border border-mid-gray/40 text-[11px] cursor-pointer hover:bg-mid-gray/10"
                        >
                          De novo
                        </button>
                      ) : (
                        <button
                          type="button"
                          data-abrir
                          onClick={() => void abrir(i.id)}
                          className="h-6 px-3 rounded-md border border-logo-primary/50 bg-logo-primary/15 text-[12px] font-semibold cursor-pointer hover:bg-logo-primary/30"
                        >
                          Abrir
                        </button>
                      )}
                    </td>
                    <td className="font-medium max-w-[28ch] truncate pe-2" title={nomeDoPaciente(i)}>
                      {nomeDoPaciente(i)}
                    </td>
                    <td className="text-mid-gray">{(i.modalidade || "--").toUpperCase()}</td>
                    <td className="truncate pe-2 max-w-[40ch]" title={`${nomeDoExame(i)} · ${origem(i)}`}>
                      {nomeDoExame(i)}
                    </td>
                    <td className="text-mid-gray tabular-nums text-[12px]">{tamanho(i.bytes)}</td>
                    <td className={`text-[12px] ${pronto(i) ? "text-emerald-600" : emDownload ? "text-amber-600" : ""}`}>
                      {vez && !pronto(i) ? "da vez" : pronto(i) ? "Laudado" : i.status || "Pronto"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* rodapé do Radius */}
      <div className="border-t border-mid-gray/20 bg-mid-gray/5 px-4 pt-2 pb-3 flex flex-col gap-2">
        {roteadorAntigo && (
          <div className="text-[12px] rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1">
            {AVISO_ANTIGO}.
          </div>
        )}
        <div className="flex items-center gap-4 text-[12px] text-mid-gray flex-wrap">
          <span>
            E-Laudos: {conta("elaudos")} | Laudados: {conta("laudados") + conta("laudout")} | Mobilemed e
            outros: {conta("outros")}
          </span>
          <span className="ms-auto truncate max-w-[60%]">
            {aviso ||
              (selecionado
                ? `Selecionado: ${nomeDoPaciente(selecionado)} • ${(selecionado.modalidade || "").toUpperCase()} • ${nomeDoExame(selecionado)} • ${pronto(selecionado) ? "Laudado" : selecionado.status || "Pronto"}`
                : "Selecionado: —")}
          </span>
        </div>
        <div className="flex items-end gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-mid-gray">Visualizador</span>
            <Seg
              opcoes={[
                ["radiant", "RadiAnt"],
                ["radiowant", "RadioWant"],
              ]}
              valor={vis}
              aoTrocar={(v) => void trocarVisualizador(v)}
            />
          </div>
          <div className={`flex flex-col gap-1 ${vis === "radiowant" ? "" : "opacity-45"}`}>
            <span className="text-[11px] text-mid-gray">
              Janela RadioWant
              <Ajuda texto="Atual: o exame novo substitui o que está aberto no RadioWant. Nova: abre numa janela a mais. Só vale com o RadioWant escolhido." />
            </span>
            <Seg
              opcoes={[
                ["atual", "Atual"],
                ["nova", "Nova"],
              ]}
              valor={janela}
              aoTrocar={(v) => void trocarJanela(v)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-mid-gray">
              Baixar do E-Laudos
              <Ajuda texto="Quem baixa quando você clica num exame no E-Laudos. Rotrix: o próprio Rotrix baixa (até 3 ao mesmo tempo) e o exame aparece aqui na aba E-Laudos, sem o Radius. Radius: volta para o Radius Download Queue." />
            </span>
            <Seg
              opcoes={[
                ["radius", "Radius"],
                ["rotrix", "Rotrix"],
              ]}
              valor={linksNoRotrix ? "rotrix" : "radius"}
              aoTrocar={(v) => void trocarLinks(v)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-mid-gray">
              Autoabrir
              <Ajuda texto="Ligado: quando o exame da vez fica laudado, o próximo exame pronto do E-Laudos abre sozinho no visualizador." />
            </span>
            <Seg
              opcoes={[
                ["nao", "Desligado"],
                ["sim", "Ligado"],
              ]}
              valor={auto ? "sim" : "nao"}
              aoTrocar={(v) => {
                setAuto(v === "sim");
                ligarAutoabrir(v === "sim");
                setAviso(v === "sim" ? "Autoabrir ligado: laudou, o próximo abre sozinho" : "Autoabrir desligado");
              }}
            />
          </div>

          <div className="ms-auto flex items-center gap-2 flex-wrap">
            <Button
              variant="primary"
              size="sm"
              disabled={!nMarcados}
              onClick={() => void abrirMarcados()}
            >
              {nMarcados > 1 ? `Abrir ${nMarcados} marcados juntos` : "Abrir marcados"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!nMarcados}
              onClick={() =>
                void marcarLaudados(
                  itens.filter((i) => marcados.includes(i.id) && !pronto(i)).map((i) => i.id),
                  "{n} marcado(s) como laudado(s)",
                )
              }
            >
              Marcar como laudados
            </Button>
            {confirmar === "" ? (
              <>
                {nMarcados > 0 && (
                  <Button variant="danger-ghost" size="sm" onClick={() => setConfirmar("marcados")}>
                    Apagar marcados
                  </Button>
                )}
                <Button
                  variant="danger-ghost"
                  size="sm"
                  disabled={!outrosTodos.length}
                  onClick={() => setConfirmar("outros")}
                >
                  Apagar exames e arquivos OUTROS
                </Button>
              </>
            ) : (
              <span className="flex items-center gap-2 rounded-md border border-red-500/40 bg-red-500/5 px-2 py-1 text-[12px]">
                {confirmar === "outros"
                  ? `Mandar os ${outrosTodos.length} exame(s) de Mobilemed e outros para a Lixeira?`
                  : `Mandar ${nMarcados} exame(s) marcado(s) para a Lixeira?`}
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() =>
                    void apagar(
                      confirmar === "outros"
                        ? outrosTodos
                        : itens.filter((i) => marcados.includes(i.id)).map((i) => i.id),
                    )
                  }
                >
                  Apagar
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setConfirmar("")}>
                  Cancelar
                </Button>
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={!pendentesDaAba.length}
              onClick={() => void marcarLaudados(pendentesDaAba, "{n} exame(s) marcados como laudados")}
            >
              Marcar todos como laudados
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const Estatistica: React.FC<{ itens: Estudo[] }> = ({ itens }) => {
  const laudados = itens.filter(pronto).length;
  const pend = itens.length - laudados;
  const bytes = itens.reduce((s, e) => s + (e.bytes || 0), 0);
  const porMod: Record<string, number> = {};
  for (const e of itens) {
    const m = (e.modalidade || "--").toUpperCase();
    porMod[m] = (porMod[m] || 0) + 1;
  }
  const Cartao: React.FC<{ rotulo: string; valor: string }> = ({ rotulo, valor }) => (
    <div className="rounded-xl border border-mid-gray/20 bg-mid-gray/5 p-4 flex flex-col gap-1">
      <span className="text-[12px] text-mid-gray">{rotulo}</span>
      <span className="text-2xl font-semibold tabular-nums">{valor}</span>
    </div>
  );
  return (
    <div className="p-4 grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3 content-start">
      <Cartao rotulo="Laudados" valor={String(laudados)} />
      <Cartao rotulo="Pendentes" valor={String(pend)} />
      <Cartao rotulo="Na fila (todas as abas)" valor={String(itens.length)} />
      <Cartao rotulo="Ocupando no disco" valor={tamanho(bytes) || "—"} />
      <div className="col-span-full rounded-xl border border-mid-gray/20 bg-mid-gray/5 p-4 flex flex-col gap-2">
        <span className="text-[12px] text-mid-gray">Por modalidade</span>
        <div className="flex gap-5 flex-wrap text-sm">
          {Object.entries(porMod)
            .sort((a, b) => b[1] - a[1])
            .map(([m, n]) => (
              <span key={m}>
                <b className="text-lg tabular-nums">{n}</b> {m}
              </span>
            ))}
        </div>
      </div>
    </div>
  );
};

export default FilaPage;
