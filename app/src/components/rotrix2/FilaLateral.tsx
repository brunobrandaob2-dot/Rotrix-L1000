/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — a fila ao lado da folha do Laudo (22/11/2026).
//
// "Eu quero poder estar só com a tela de laudo." A fila do lado tem quatro jeitos,
// escolhidos na engrenagem do topo dela:
//   aberta   — sempre ao lado da folha
//   fechada  — escondida; um trilho fino à esquerda (ou F2) mostra
//   escolher — some ao abrir um exame e volta quando o exame fica laudado
//   mouse    — escondida; encostou o mouse no trilho, aparece POR CIMA da folha
//              (a folha não muda de tamanho); tirou o mouse, some
// Clicar na aba Laudo estando nela também mostra/esconde (a Casca chama alternar).
import React, { useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ChevronLeft, ChevronRight, Settings2, Check } from "lucide-react";
import { Ajuda } from "./Dica";
import {
  type Fila,
  type Visualizador,
  lerFila,
  pronto,
  ehOutro,
  hora,
  nomeDoExame,
  nomeDoPaciente,
  abrirEstudos,
  abrirUm,
  salvarVisualizador,
  autoabrirLigado,
  ligarAutoabrir,
} from "./filaComum";

export type ModoFila = "aberta" | "fechada" | "escolher" | "mouse";

const CHAVE_MODO = "rotrix2.filaModo";
export const MODOS: { id: ModoFila; nome: string; dica: string }[] = [
  { id: "aberta", nome: "Sempre aberta", dica: "A fila fica sempre ao lado da folha." },
  { id: "fechada", nome: "Sempre escondida", dica: "Só a folha. F2, o trilho à esquerda ou clicar em Laudo de novo mostram a fila." },
  {
    id: "escolher",
    nome: "Só para escolher exame",
    dica: "Ao abrir um exame, a fila some e fica só a folha. Quando o exame fica laudado, ela volta para você escolher o próximo.",
  },
  {
    id: "mouse",
    nome: "Ao passar o mouse",
    dica: "A fila fica num trilho fino à esquerda. Encostou o mouse, ela aparece por cima da folha; tirou o mouse, ela some.",
  },
];

export const modoSalvo = (): ModoFila => {
  try {
    const m = localStorage.getItem(CHAVE_MODO) as ModoFila | null;
    return m && MODOS.some((x) => x.id === m) ? m : "aberta";
  } catch {
    return "aberta";
  }
};

interface Props {
  modo: ModoFila;
  aberta: boolean;
  aoMostrar: (v: boolean) => void;
  aoTrocarModo: (m: ModoFila) => void;
}

export const FilaLateral: React.FC<Props> = ({ modo, aberta, aoMostrar, aoTrocarModo }) => {
  const [fila, setFila] = useState<Fila | null>(null);
  const [marcados, setMarcados] = useState<string[]>([]);
  const [aviso, setAviso] = useState("");
  const [menu, setMenu] = useState(false);
  const [auto, setAuto] = useState(autoabrirLigado());
  const arrasto = useRef<{ valor: boolean } | null>(null);
  const flutua = modo === "mouse";

  const ler = useCallback(async () => {
    try {
      setFila(await lerFila());
    } catch {
      /* roteador parado: fica a lista de antes */
    }
  }, []);

  useEffect(() => {
    void ler();
    const t = setInterval(() => void ler(), 15000);
    const p = listen("rotrix-proximo-exame", () => void ler());
    const a = (e: Event) => setAuto(Boolean((e as CustomEvent<boolean>).detail));
    window.addEventListener("rotrix:autoabrir", a);
    const solta = () => (arrasto.current = null);
    document.addEventListener("mouseup", solta);
    return () => {
      clearInterval(t);
      p.then((fn) => fn());
      window.removeEventListener("rotrix:autoabrir", a);
      document.removeEventListener("mouseup", solta);
    };
  }, [ler]);

  // relê quando aparece, para não mostrar a lista velha
  useEffect(() => {
    if (aberta) void ler();
  }, [aberta, ler]);

  const itens = (fila?.itens || []).filter((e) => !pronto(e));
  const daVez = fila?.vez || fila?.atual || null;
  const vis: Visualizador = fila?.visualizador || "radiant";

  const abrir = async (id: string) => {
    const r = await abrirUm(id);
    setAviso(r.frase);
    if (r.ok && (modo === "escolher" || modo === "mouse")) aoMostrar(false);
    void ler();
  };

  const abrirMarcados = async () => {
    const r = await abrirEstudos(itens.filter((i) => marcados.includes(i.id)).map((i) => i.id));
    setAviso(r.frase);
    if (r.ok) {
      setMarcados([]);
      if (modo === "escolher" || modo === "mouse") aoMostrar(false);
    }
  };

  const apertar = (e: React.MouseEvent, id: string) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest("[data-abrir]")) return;
    e.preventDefault();
    const ja = marcados.includes(id);
    if (!e.ctrlKey && !e.metaKey && !ja) {
      setMarcados([id]);
      arrasto.current = { valor: true };
    } else {
      setMarcados((m) => (ja ? m.filter((x) => x !== id) : [...m, id]));
      arrasto.current = { valor: !ja };
    }
  };
  const passar = (id: string) => {
    const a = arrasto.current;
    if (!a) return;
    setMarcados((m) => (m.includes(id) === a.valor ? m : a.valor ? [...m, id] : m.filter((x) => x !== id)));
  };

  const trilho = (
    <button
      type="button"
      onClick={() => aoMostrar(true)}
      onMouseEnter={() => flutua && aoMostrar(true)}
      title="Mostrar a fila (F2)"
      className="w-9 shrink-0 h-full flex flex-col items-center gap-2 pt-3 border-e border-mid-gray/20 bg-mid-gray/5 hover:bg-mid-gray/10 cursor-pointer"
    >
      <ChevronRight size={15} className="text-mid-gray" />
      {itens.length > 0 && (
        <span className="text-[10px] font-bold rounded-full bg-logo-primary text-white px-1.5">{itens.length}</span>
      )}
      <span className="text-[11px] tracking-wider text-mid-gray [writing-mode:vertical-rl] rotate-180">FILA · F2</span>
    </button>
  );

  const painel = (
    <aside
      onMouseLeave={() => flutua && !arrasto.current && aoMostrar(false)}
      className={`w-[340px] shrink-0 flex flex-col min-h-0 border-e border-mid-gray/20 bg-background ${
        flutua ? "absolute inset-y-0 start-0 z-40 shadow-2xl" : "h-full"
      }`}
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 relative">
        <b className="text-[13px]">Fila</b>
        <span className="text-[11px] text-mid-gray">{itens.length} pendentes</span>
        <div className="ms-auto flex items-center gap-1">
          <button
            type="button"
            aria-label="Jeito da fila"
            onClick={() => setMenu((v) => !v)}
            className="h-6 w-6 grid place-items-center rounded hover:bg-mid-gray/15 cursor-pointer text-mid-gray"
          >
            <Settings2 size={14} />
          </button>
          <button
            type="button"
            aria-label="Esconder a fila (F2)"
            onClick={() => aoMostrar(false)}
            className="h-6 w-6 grid place-items-center rounded hover:bg-mid-gray/15 cursor-pointer text-mid-gray"
          >
            <ChevronLeft size={15} />
          </button>
        </div>
        {menu && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenu(false)} />
            <div className="absolute z-50 top-full end-2 mt-1 w-64 rounded-xl border border-mid-gray/30 bg-background shadow-2xl p-1.5">
              <div className="text-[10px] font-bold tracking-wider text-mid-gray px-2 pt-1 pb-1">FILA AO LADO DA FOLHA</div>
              {MODOS.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    aoTrocarModo(m.id);
                    setMenu(false);
                  }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-logo-primary/20 cursor-pointer text-[12.5px] text-start"
                >
                  <span className="w-3.5">{modo === m.id && <Check size={13} />}</span>
                  {m.nome}
                  <span className="ms-auto">
                    <Ajuda texto={m.dica} />
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto select-none">
        {itens.length === 0 ? (
          <p className="p-4 text-[12px] text-mid-gray">Nenhum exame pendente.</p>
        ) : (
          itens.map((i) => {
            const m = marcados.includes(i.id);
            const vez = i.id === daVez;
            const baixando = /baix/i.test(i.status || "");
            return (
              <div
                key={i.id}
                onMouseDown={(e) => apertar(e, i.id)}
                onMouseEnter={() => passar(i.id)}
                onDoubleClick={() => void abrir(i.id)}
                className={`grid grid-cols-[16px_40px_52px_minmax(0,1fr)] gap-2 items-center px-3 h-11 border-b border-mid-gray/10 text-[12px] ${
                  m ? "bg-logo-primary/15" : vez ? "bg-logo-primary/8" : "hover:bg-mid-gray/8"
                }`}
                style={vez ? { boxShadow: "inset 3px 0 0 var(--color-logo-primary, #82aee6)" } : undefined}
              >
                <span
                  className={`h-3.5 w-3.5 rounded border grid place-items-center ${
                    m ? "bg-logo-primary border-logo-primary text-white" : "border-mid-gray/40"
                  }`}
                >
                  {m && <Check size={10} />}
                </span>
                <span className="text-mid-gray tabular-nums text-[11px]">{hora(i.entrou)}</span>
                {baixando ? (
                  <span className="text-[10.5px] text-amber-600">baixando</span>
                ) : (
                  <button
                    type="button"
                    data-abrir
                    onClick={() => void abrir(i.id)}
                    className="h-6 rounded-md border border-logo-primary/50 bg-logo-primary/15 text-[11.5px] font-semibold cursor-pointer hover:bg-logo-primary/30"
                  >
                    Abrir
                  </button>
                )}
                <span className="min-w-0 flex flex-col leading-tight">
                  <b className="font-medium truncate">{nomeDoPaciente(i)}</b>
                  <span className="text-[10.5px] text-mid-gray truncate">
                    {(i.modalidade || "--").toUpperCase()} · {nomeDoExame(i)}
                    {ehOutro(i) ? " · Mobilemed/outros" : ""}
                  </span>
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-mid-gray/20 bg-mid-gray/5 px-3 py-2 flex flex-col gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="inline-flex">
            {(["radiant", "radiowant"] as Visualizador[]).map((v, i) => (
              <button
                key={v}
                type="button"
                onClick={async () => {
                  try {
                    await salvarVisualizador({ visualizador: v });
                    void ler();
                  } catch (e) {
                    setAviso(String(e));
                  }
                }}
                className={`h-6 px-2.5 text-[11.5px] border cursor-pointer ${i === 0 ? "rounded-s-md" : "rounded-e-md -ms-px"} ${
                  vis === v ? "bg-logo-primary border-logo-primary text-white" : "border-mid-gray/30 text-mid-gray"
                }`}
              >
                {v === "radiant" ? "RadiAnt" : "RadioWant"}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1 text-[11.5px] text-mid-gray">
            <input
              type="checkbox"
              checked={auto}
              onChange={(e) => {
                setAuto(e.target.checked);
                ligarAutoabrir(e.target.checked);
              }}
            />
            Auto
            <Ajuda texto="Autoabrir: quando o exame da vez fica laudado, o próximo exame pronto abre sozinho." lado="cima" />
          </label>
          <button
            type="button"
            disabled={!marcados.length}
            onClick={() => void abrirMarcados()}
            className="ms-auto h-6 px-2.5 rounded-md bg-logo-primary text-white text-[11.5px] font-semibold disabled:opacity-40 cursor-pointer"
          >
            {marcados.length > 1 ? `Abrir ${marcados.length}` : "Abrir marcados"}
          </button>
        </div>
        {aviso && <span className="text-[11px] text-mid-gray truncate">{aviso}</span>}
      </div>
    </aside>
  );

  if (!aberta) return trilho;
  if (flutua)
    return (
      <>
        {trilho}
        {painel}
      </>
    );
  return painel;
};

export default FilaLateral;
