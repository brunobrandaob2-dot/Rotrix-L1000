/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 (fase 3) — o Stream Deck / Stream Dock dentro do Painel.
//
// O desenho do aparelho conectado (ou de um modelo escolhido, para montar antes
// de ligar). Arraste uma tecla do Painel para uma tecla, botão ou giratório do
// desenho; clique numa peça para escolher o que ela faz. As imagens das teclas
// são desenhadas aqui (deckImagem.ts) e o roteador manda para o aparelho.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { Ajuda } from "./Dica";
import { type ConfigPainel, type Tecla, painel, COR } from "./painelComum";
import { iconeDe } from "./painelIcones";
import { imagemDaTecla, type Formato } from "./deckImagem";

interface ModeloCat {
  id: string;
  nome: string;
  familia: string;
  cols: number;
  linhas: number;
  botoes: number;
  giros: number;
  img: Formato;
  testado: boolean;
  slots: string[];
}

interface EstadoDeck {
  ok?: boolean;
  conectados: { chave: string; modelo: string; nome: string; pagina: number; erro: string; testado: boolean }[];
  sem_suporte: { nome: string }[];
  fabricante_aberto: string[];
  catalogo: Record<string, ModeloCat>;
  motivo?: string;
}

type Giro = { girar?: string; clique?: string };
type Mapa = Record<string, string | Giro>;
interface PaginaAparelho {
  nome: string;
  app: string;
  m: Mapa;
}
interface ConfAparelho {
  brilho: number;
  auto: boolean;
  paginas: PaginaAparelho[];
}

const GIROS: [string, string][] = [
  ["", "nada"],
  ["rolar", "Rolar (cortes no visualizador)"],
  ["zoom", "Zoom (Ctrl + rodinha)"],
  ["volume", "Volume do computador"],
  ["pagina", "Trocar a página do aparelho"],
  ["brilho", "Brilho do aparelho"],
];

const nomeDoSlot = (s: string, m: ModeloCat): string => {
  const n = Number(s.slice(1)) + 1;
  if (s[0] === "k") return `Tecla ${n}`;
  if (s[0] === "b") return `Botão sem tela ${"ABCDEFGH"[n - 1]}`;
  if (m.giros === 3) return `Giratório ${["esquerdo", "de cima", "direito"][n - 1]}`;
  return `Giratório ${n}`;
};

export const AparelhoPainel: React.FC<{
  cfg: ConfigPainel;
  aoSalvar: (c: ConfigPainel) => void;
}> = ({ cfg, aoSalvar }) => {
  const [est, setEst] = useState<EstadoDeck | null>(null);
  const [modeloSel, setModeloSel] = useState<string>("");
  const [pag, setPag] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const [alvo, setAlvo] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [aceso, setAceso] = useState<string | null>(null);

  const ler = useCallback(async () => {
    try {
      const r = (await painel("deck_estado")) as unknown as EstadoDeck;
      if (r && r.catalogo) setEst(r);
    } catch {
      /* roteador parado */
    }
  }, []);

  useEffect(() => {
    void ler();
    const t = setInterval(() => void ler(), 4000);
    // o roteador avisa (pela Casca) quando o aparelho troca de página sozinho
    const p = (e: Event) => {
      const d = (e as CustomEvent<{ indice: number }>).detail;
      if (typeof d?.indice === "number") setPag(d.indice);
    };
    const u = (e: Event) => {
      const d = (e as CustomEvent<{ slot: string }>).detail;
      if (d?.slot) {
        setAceso(d.slot);
        window.setTimeout(() => setAceso(null), 350);
      }
    };
    window.addEventListener("rotrix:deck-pagina", p);
    window.addEventListener("rotrix:deck-aperto", u);
    return () => {
      clearInterval(t);
      window.removeEventListener("rotrix:deck-pagina", p);
      window.removeEventListener("rotrix:deck-aperto", u);
    };
  }, [ler]);

  const conectado = est?.conectados[0];
  const modeloId = modeloSel || conectado?.modelo || "akp03e";
  const modelo = est?.catalogo[modeloId];
  const teclas = useMemo(() => cfg.paginas.flatMap((p) => p.teclas), [cfg]);
  const porId = useMemo(() => Object.fromEntries(teclas.map((t) => [t.id, t])), [teclas]);

  const conf: ConfAparelho = (cfg as unknown as { aparelhos?: Record<string, ConfAparelho> }).aparelhos?.[
    modeloId
  ] || { brilho: 80, auto: true, paginas: [{ nome: "Página 1", app: "", m: {} }] };
  const pagina = conf.paginas[Math.min(pag, conf.paginas.length - 1)];

  const gravar = (novo: ConfAparelho) => {
    const ap = { ...((cfg as unknown as { aparelhos?: Record<string, ConfAparelho> }).aparelhos || {}) };
    ap[modeloId] = novo;
    aoSalvar({ ...cfg, aparelhos: ap } as unknown as ConfigPainel);
  };
  const gravarMapa = (slot: string, valor: string | Giro | null) => {
    const m = { ...pagina.m };
    if (valor === null || valor === "") delete m[slot];
    else m[slot] = valor;
    gravar({ ...conf, paginas: conf.paginas.map((p, i) => (p === pagina ? { ...p, m } : p)) });
  };

  // --- imagens para o aparelho: refeitas SÓ quando o desenho muda ---
  // 22/11: o efeito dependia de objetos novos a cada leitura (4 s) e de cada
  // renderização; as imagens eram reenviadas sem parar. Agora a chave é o que
  // aparece nas teclas + quais aparelhos estão conectados (reconectou, repinta).
  const assinatura = JSON.stringify({
    m: modelo?.id,
    con: (est?.conectados || []).filter((c) => c.modelo === modelo?.id).map((c) => c.chave),
    p: conf.paginas.map((p) =>
      (modelo?.slots || [])
        .filter((x) => x[0] === "k")
        .map((s) => {
          const id = p.m[s];
          const t = typeof id === "string" ? porId[id] : null;
          return t ? [t.nome, t.grupo, t.icone || "", t.acao] : null;
        }),
    ),
  });
  const espera = useRef<number | null>(null);
  useEffect(() => {
    if (!modelo || !est?.conectados.some((c) => c.modelo === modelo.id)) return;
    if (espera.current) window.clearTimeout(espera.current);
    espera.current = window.setTimeout(async () => {
      const paginas: Record<number, Record<string, string>> = {};
      for (let i = 0; i < conf.paginas.length; i++) {
        paginas[i] = {};
        for (const s of modelo.slots.filter((x) => x[0] === "k")) {
          const id = conf.paginas[i].m[s];
          const t = typeof id === "string" ? porId[id] || null : null;
          paginas[i][s] = await imagemDaTecla(t, modelo.img, t ? iconeDe(t) : null);
        }
      }
      try {
        await painel("deck_imagens", { modelo: modelo.id, paginas });
      } catch (e) {
        setAviso(`não mandei as imagens: ${String(e)}`);
      }
    }, 700);
  }, [assinatura]);

  if (!est || !modelo)
    return <div className="text-[12.5px] text-mid-gray">procurando o aparelho…</div>;

  const soltar = (slot: string, id: string) => {
    setAlvo(null);
    const t = porId[id];
    if (!t) return;
    if (slot[0] === "g") gravarMapa(slot, { ...((pagina.m[slot] as Giro) || {}), clique: id });
    else gravarMapa(slot, id);
    setSel(slot);
    setAviso(`${nomeDoSlot(slot, modelo)}: ${t.nome}${conectado ? " · já está no aparelho" : ""}`);
  };

  const peca = (slot: string) => {
    const v = pagina.m[slot];
    const t = typeof v === "string" ? porId[v] : v && (v as Giro).clique ? porId[(v as Giro).clique!] : null;
    const comum = {
      onClick: () => setSel(slot),
      onDragOver: (e: React.DragEvent) => {
        e.preventDefault();
        setAlvo(slot);
      },
      onDragLeave: () => setAlvo(null),
      onDrop: (e: React.DragEvent) => {
        e.preventDefault();
        soltar(slot, e.dataTransfer.getData("text/plain"));
      },
    };
    const anel =
      alvo === slot
        ? "outline-2 outline-dashed outline-logo-primary outline-offset-2"
        : sel === slot
          ? "outline-2 outline-logo-primary outline-offset-2"
          : aceso === slot
            ? "outline-2 outline-emerald-400 outline-offset-1"
            : "";
    if (slot[0] === "g") {
      const g = (v as Giro) || {};
      return (
        <button
          key={slot}
          type="button"
          {...comum}
          title={`${nomeDoSlot(slot, modelo)} · girar: ${GIROS.find((x) => x[0] === g.girar)?.[1] || "nada"} · clicar: ${t?.nome || "nada"}`}
          className={`h-[52px] w-[52px] rounded-full border border-mid-gray/50 grid place-items-center text-[10px] leading-tight text-center cursor-pointer ${anel}`}
          style={{ background: "radial-gradient(circle at 40% 35%, #3a414b, #1c2026)", color: "#c6cfd8" }}
        >
          {g.girar ? GIROS.find((x) => x[0] === g.girar)?.[1].split(" ")[0] : "—"}
        </button>
      );
    }
    if (slot[0] === "b")
      return (
        <button
          key={slot}
          type="button"
          {...comum}
          className={`h-6 w-16 rounded-md border border-mid-gray/50 bg-[#1c2026] text-[10px] text-[#c6cfd8] truncate px-1 cursor-pointer ${anel}`}
        >
          {t?.nome || "—"}
        </button>
      );
    const Icone = t ? iconeDe(t) : null;
    const cor = t ? COR[t.grupo] : "#4a525d";
    return (
      <button
        key={slot}
        type="button"
        {...comum}
        className={`h-16 w-16 rounded-lg border flex flex-col items-center justify-center gap-0.5 text-[10.5px] leading-tight text-center p-0.5 cursor-pointer ${anel}`}
        style={{
          background: t ? `color-mix(in srgb, ${cor} 22%, #0b0d10)` : "#0b0d10",
          borderColor: t ? `color-mix(in srgb, ${cor} 45%, transparent)` : "#2c333c",
          color: t ? "#e8edf2" : "#4a525d",
        }}
      >
        {Icone && <Icone size={17} color={cor} strokeWidth={1.8} />}
        <span className="truncate max-w-full">{t?.nome || "vazia"}</span>
      </button>
    );
  };

  const lcd = modelo.slots.filter((s) => s[0] === "k");
  const botoes = modelo.slots.filter((s) => s[0] === "b");
  const giros = modelo.slots.filter((s) => s[0] === "g");
  const vSel = sel ? pagina.m[sel] : undefined;
  const opcoesTecla = (valor: string, troca: (v: string) => void) => (
    <select
      className="w-full h-8 rounded-md border border-mid-gray/30 bg-background px-2 text-[12.5px]"
      value={valor}
      onChange={(e) => troca(e.target.value)}
    >
      <option value="">— vazia —</option>
      {cfg.paginas.map((p) => (
        <optgroup key={p.nome} label={p.nome}>
          {p.teclas.map((t: Tecla) => (
            <option key={t.id} value={t.id}>
              {t.nome}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );

  return (
    <div className="rounded-xl border border-mid-gray/20 bg-mid-gray/5 p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <b className="text-[14px]">
          Aparelho
          <Ajuda texto="Arraste uma tecla do Painel para uma tecla, botão ou giratório do desenho. Clique numa peça para escolher o que ela faz. O Rotrix fala direto com o aparelho pela USB; o programa do fabricante precisa ficar fechado." />
        </b>
        <select
          className="h-7 rounded-md border border-mid-gray/30 bg-background px-2 text-[12.5px]"
          value={modeloId}
          onChange={(e) => {
            setModeloSel(e.target.value);
            setPag(0);
            setSel(null);
          }}
        >
          {Object.values(est.catalogo).map((m) => (
            <option key={m.id} value={m.id}>
              {m.nome}
              {est.conectados.some((c) => c.modelo === m.id) ? " · conectado" : ""}
            </option>
          ))}
        </select>
        <span
          className={`text-[11px] rounded-full px-2 py-0.5 border ${
            est.conectados.some((c) => c.modelo === modeloId)
              ? "border-emerald-500/40 text-emerald-500 bg-emerald-500/10"
              : "border-mid-gray/30 text-mid-gray"
          }`}
        >
          {est.conectados.some((c) => c.modelo === modeloId) ? "conectado" : "desconectado"}
        </span>
        {!modelo.testado && (
          <span className="text-[11px] text-amber-600">
            ainda não testado neste modelo
            <Ajuda texto="Este modelo foi montado pelo protocolo conhecido da Elgato, mas ainda não foi conferido num aparelho de verdade." />
          </span>
        )}
      </div>
      {est.fabricante_aberto.length > 0 && (
        <div className="text-[12px] rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5">
          Feche o programa do fabricante ({est.fabricante_aberto.join(", ")}): ele e o Rotrix brigariam pelas teclas.
        </div>
      )}
      {est.sem_suporte.length > 0 && (
        <div className="text-[12px] text-mid-gray">
          Conectado mas ainda sem suporte: {est.sem_suporte.map((s) => s.nome).join(", ")}.
        </div>
      )}

      <div className="flex gap-4 flex-wrap items-start">
        {/* o desenho */}
        <div className="rounded-2xl border border-[#2c333c] bg-[#101317] p-4 flex gap-4 items-center">
          <div className="flex flex-col gap-3">
            <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${modelo.cols}, 64px)` }}>
              {lcd.map(peca)}
            </div>
            {botoes.length > 0 && (
              <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${botoes.length}, 64px)` }}>
                {botoes.map(peca)}
              </div>
            )}
          </div>
          {giros.length > 0 &&
            (modelo.giros === 3 ? (
              <div className="flex flex-col items-center gap-2.5">
                {peca(giros[1])}
                <div className="flex gap-2.5">
                  {peca(giros[0])}
                  {peca(giros[2])}
                </div>
              </div>
            ) : (
              <div className="flex gap-2.5">{giros.map(peca)}</div>
            ))}
        </div>

        {/* a peça escolhida */}
        <div className="flex-1 min-w-[260px] flex flex-col gap-2.5">
          <div className="flex items-center gap-1.5 flex-wrap text-[12.5px]">
            <span className="text-mid-gray">Página do aparelho</span>
            {conf.paginas.map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setPag(i);
                  void painel("deck_pagina", { modelo: modeloId, indice: i });
                }}
                className={`h-6 px-2.5 rounded-md border text-[12px] cursor-pointer ${
                  p === pagina ? "bg-logo-primary border-logo-primary text-white" : "border-mid-gray/30"
                }`}
              >
                {p.nome}
                {p.app ? " (auto)" : ""}
              </button>
            ))}
            <button
              type="button"
              aria-label="Nova página do aparelho"
              onClick={() => {
                const nome = window.prompt("Nome da nova página do aparelho:", "RadiAnt");
                if (!nome) return;
                gravar({ ...conf, paginas: [...conf.paginas, { nome: nome.slice(0, 24), app: "", m: {} }] });
                setPag(conf.paginas.length);
              }}
              className="h-6 w-6 grid place-items-center rounded-md border border-mid-gray/30 cursor-pointer"
            >
              <Plus size={12} />
            </button>
          </div>
          <label className="flex items-center gap-2 text-[12.5px]">
            <span className="text-mid-gray w-28">
              Abre sozinha com
              <Ajuda texto="Parte do nome do programa (ex.: radiant, radiowant). Quando ele fica na frente, o aparelho vai para esta página; quando sai, volta." />
            </span>
            <input
              className="flex-1 h-7 rounded-md border border-mid-gray/30 bg-background px-2 text-[12.5px]"
              placeholder="nenhum programa"
              value={pagina.app}
              onChange={(e) =>
                gravar({ ...conf, paginas: conf.paginas.map((p) => (p === pagina ? { ...p, app: e.target.value } : p)) })
              }
            />
          </label>
          <label className="flex items-center gap-2 text-[12.5px]">
            <span className="text-mid-gray w-28">Brilho</span>
            <input
              type="range"
              min={5}
              max={100}
              value={conf.brilho}
              className="flex-1"
              onChange={(e) => {
                const b = Number(e.target.value);
                gravar({ ...conf, brilho: b });
                void painel("deck_brilho", { modelo: modeloId, brilho: b });
              }}
            />
            <span className="w-10 text-end tabular-nums">{conf.brilho}%</span>
          </label>
          <label className="flex items-center gap-2 text-[12.5px]">
            <input type="checkbox" checked={conf.auto} onChange={(e) => gravar({ ...conf, auto: e.target.checked })} />
            Trocar de página pelo programa da frente
          </label>

          {sel && (
            <div className="rounded-lg border border-mid-gray/25 bg-background p-3 flex flex-col gap-2">
              <div className="flex items-center">
                <b className="text-[13px]">{nomeDoSlot(sel, modelo)}</b>
                <button type="button" onClick={() => setSel(null)} className="ms-auto text-mid-gray cursor-pointer" aria-label="Fechar">
                  <X size={14} />
                </button>
              </div>
              {sel[0] === "g" ? (
                <>
                  <label className="grid grid-cols-[80px_1fr] items-center gap-2 text-[12.5px]">
                    <span className="text-mid-gray">Ao girar</span>
                    <select
                      className="h-8 rounded-md border border-mid-gray/30 bg-background px-2 text-[12.5px]"
                      value={(vSel as Giro)?.girar || ""}
                      onChange={(e) => gravarMapa(sel, { ...((vSel as Giro) || {}), girar: e.target.value })}
                    >
                      {GIROS.map(([id, nome]) => (
                        <option key={id} value={id}>
                          {nome}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid grid-cols-[80px_1fr] items-center gap-2 text-[12.5px]">
                    <span className="text-mid-gray">Ao clicar</span>
                    {opcoesTecla((vSel as Giro)?.clique || "", (v) => gravarMapa(sel, { ...((vSel as Giro) || {}), clique: v }))}
                  </label>
                  <div className="flex gap-1.5">
                    {(["girar-", "girar+", "clique"] as const).map((tipo) => (
                      <button
                        key={tipo}
                        type="button"
                        onClick={() => void painel("deck_simular", { modelo: modeloId, slot: sel, tipo })}
                        className="h-7 px-2.5 rounded-md border border-mid-gray/30 text-[12px] cursor-pointer"
                      >
                        {tipo === "girar-" ? "◀ girar" : tipo === "girar+" ? "girar ▶" : "clicar"}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  {opcoesTecla(typeof vSel === "string" ? vSel : "", (v) => gravarMapa(sel, v || null))}
                  <button
                    type="button"
                    onClick={() => void painel("deck_simular", { modelo: modeloId, slot: sel, tipo: "tecla" })}
                    className="self-start h-7 px-3 rounded-md bg-logo-primary text-white text-[12px] font-semibold cursor-pointer"
                  >
                    Apertar (simular)
                  </button>
                </>
              )}
            </div>
          )}
          {aviso && <span className="text-[12px] text-mid-gray">{aviso}</span>}
        </div>
      </div>
    </div>
  );
};

export default AparelhoPainel;
