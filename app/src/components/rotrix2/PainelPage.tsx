/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Painel (22/11/2026): o Workflow Hub dentro do Rotrix.
//
// Teclas foscas, uma cor por grupo (laudo, Claude, textos, programas, janelas,
// sistema), em páginas. Bolinha verde = programa aberto. "Iniciar expediente"
// abre os programas marcados e põe cada janela no lugar dela nos monitores.
// Editar teclas: nome, ação, cor, lugar na tela, navegador, atalho.
// As teclas moram em painel.json (roteador, painel.py).
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppWindow,
  Plus,
  Monitor as MonitorIcone,
  ChevronLeft,
  ChevronRight,
  Trash2,
  X,
} from "lucide-react";
import { ICONES, iconePadrao } from "./painelIcones";
import { AparelhoPainel } from "./AparelhoPainel";
import { Ajuda } from "./Dica";
import {
  type ConfigPainel,
  type EstadoPainel,
  type Tecla,
  type Grupo,
  type Acao,
  type Lugar,
  painel,
  COR,
  NOME_GRUPO,
  ACOES,
  COMANDOS_ROTRIX,
  COMANDOS_SISTEMA,
  NAVEGADORES,
  comandoRotrix,
  novaTecla,
} from "./painelComum";

// --- tecla -------------------------------------------------------------------
const TeclaTile: React.FC<{
  t: Tecla;
  aberto?: boolean;
  numero?: number | null;
  editando: boolean;
  selecionada: boolean;
  ocupada: boolean;
  aoApertar: () => void;
  descricao: string;
}> = ({ t, aberto, numero, editando, selecionada, ocupada, aoApertar, descricao }) => {
  const Icone = ICONES[iconePadrao(t)] || AppWindow;
  const cor = COR[t.grupo] || COR.sis;
  return (
    <button
      type="button"
      onClick={aoApertar}
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", t.id)}
      className={`relative min-h-[104px] rounded-xl border p-3 flex flex-col justify-between text-start transition-[transform,box-shadow] active:scale-[0.97] cursor-pointer ${
        t.larga ? "col-span-2" : ""
      } ${editando ? "outline-1 outline-dashed outline-offset-2 outline-mid-gray/60" : ""}`}
      style={{
        borderColor: `color-mix(in srgb, ${cor} 42%, transparent)`,
        background: `radial-gradient(120% 80% at 50% 0%, color-mix(in srgb, ${cor} 16%, transparent), transparent 62%), color-mix(in srgb, ${cor} 9%, var(--color-background, #1b1f24))`,
        boxShadow: selecionada
          ? `0 0 0 2px ${cor}`
          : `inset 0 1px 0 color-mix(in srgb, ${cor} 24%, transparent)`,
        opacity: ocupada ? 0.6 : 1,
      }}
    >
      {aberto && (
        <span
          className="absolute top-3 end-3 h-[7px] w-[7px] rounded-full bg-emerald-400"
          style={{ boxShadow: "0 0 6px #34d399" }}
          title="aberto"
        />
      )}
      {numero != null && numero > 0 && !aberto && (
        <span
          className="absolute top-2.5 end-2.5 text-[11px] font-semibold rounded-full px-1.5"
          style={{ background: `color-mix(in srgb, ${cor} 24%, transparent)`, color: cor }}
        >
          {numero}
        </span>
      )}
      <span
        className="h-9 w-9 rounded-lg grid place-items-center"
        style={{ background: `color-mix(in srgb, ${cor} 18%, transparent)`, color: cor }}
      >
        <Icone size={19} strokeWidth={1.8} />
      </span>
      <span className="min-w-0">
        <b className="block text-[13.5px] font-semibold truncate">{t.nome}</b>
        <small className="block text-[11.5px] text-mid-gray truncate">{descricao || " "}</small>
      </span>
    </button>
  );
};

// --- campos do editor ------------------------------------------------------------
const Linha: React.FC<{ rotulo: string; ajuda?: string; children: React.ReactNode }> = ({
  rotulo,
  ajuda,
  children,
}) => (
  <label className="grid grid-cols-[112px_minmax(0,1fr)] gap-2 items-center text-[12.5px]">
    <span className="text-mid-gray">
      {rotulo}
      {ajuda && <Ajuda texto={ajuda} />}
    </span>
    {children}
  </label>
);
const campo =
  "w-full h-8 rounded-md border border-mid-gray/30 bg-background px-2 text-[12.5px]";

const SeletorLugar: React.FC<{
  lugar?: Lugar | null;
  estado: EstadoPainel | null;
  aoTrocar: (l: Lugar | null) => void;
}> = ({ lugar, estado, aoTrocar }) => {
  const mons = estado?.monitores || [];
  const mods = estado?.modelos || [];
  const mod = mods.find((m) => m.id === lugar?.layout) || mods[0];
  if (!mons.length || !mods.length) return <span className="text-mid-gray text-[12px]">sem monitores</span>;
  return (
    <div className="flex flex-col gap-1.5">
      <select
        className={campo}
        value={lugar ? lugar.display : ""}
        onChange={(e) =>
          aoTrocar(e.target.value ? { display: e.target.value, layout: lugar?.layout || "full", zone: lugar?.zone || 0 } : null)
        }
      >
        <option value="">sem lugar fixo</option>
        {mons.map((m) => (
          <option key={m.id} value={m.id}>
            {m.nome} · {m.w}×{m.h}
          </option>
        ))}
        {lugar && !mons.some((m) => m.id === lugar.display) && (
          <option value={lugar.display}>monitor desligado ({lugar.display.split("|")[1]})</option>
        )}
      </select>
      {lugar && mod && (
        <div className="flex gap-1.5">
          <select
            className={campo}
            value={lugar.layout}
            onChange={(e) => aoTrocar({ ...lugar, layout: e.target.value, zone: 0 })}
          >
            {mods.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome}
              </option>
            ))}
          </select>
          <select
            className={campo}
            value={lugar.zone}
            onChange={(e) => aoTrocar({ ...lugar, zone: Number(e.target.value) })}
          >
            {mod.zonas.map((z, i) => (
              <option key={i} value={i}>
                {z.nome}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

const EditorTecla: React.FC<{
  t: Tecla;
  estado: EstadoPainel | null;
  aoMudar: (t: Tecla) => void;
  aoMover: (d: -1 | 1) => void;
  aoTirar: () => void;
  aoFechar: () => void;
}> = ({ t, estado, aoMudar, aoMover, aoTirar, aoFechar }) => {
  const m = (p: Partial<Tecla>) => aoMudar({ ...t, ...p });
  const trocarAcao = (a: Acao) => {
    const base: Partial<Tecla> = { acao: a };
    if (a === "programa") Object.assign(base, { tipo: t.tipo || "exe", alvo: t.alvo || "" });
    if (a === "site") Object.assign(base, { sites: t.sites?.length ? t.sites : ["https://"] });
    if (a === "rotrix") Object.assign(base, { comando: "proximo", grupo: "laudo" as Grupo });
    if (a === "sistema") Object.assign(base, { comando: "volume_mais", grupo: "sis" as Grupo });
    if (a === "atalho") Object.assign(base, { teclas: t.teclas || "Ctrl+Shift+V" });
    if (a === "texto") Object.assign(base, { texto: t.texto || "" });
    if (a === "expediente" || a === "organizar") base.grupo = "jan";
    m(base);
  };
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <b className="text-[13.5px]">Tecla</b>
        <span className="text-[12px] text-mid-gray truncate">{t.nome}</span>
        <button type="button" onClick={aoFechar} className="ms-auto text-mid-gray hover:text-text cursor-pointer" aria-label="Fechar">
          <X size={15} />
        </button>
      </div>
      <Linha rotulo="Nome">
        <input className={campo} value={t.nome} maxLength={40} onChange={(e) => m({ nome: e.target.value })} />
      </Linha>
      <Linha rotulo="Ação">
        <select className={campo} value={t.acao} onChange={(e) => trocarAcao(e.target.value as Acao)}>
          {ACOES.map(([id, nome]) => (
            <option key={id} value={id}>
              {nome}
            </option>
          ))}
        </select>
      </Linha>

      {t.acao === "programa" && (
        <>
          <Linha rotulo="Tipo">
            <select className={campo} value={t.tipo} onChange={(e) => m({ tipo: e.target.value as Tecla["tipo"] })}>
              <option value="exe">Programa (.exe)</option>
              <option value="powershell">Script do PowerShell (.ps1)</option>
              <option value="appx">App da Loja da Microsoft</option>
            </select>
          </Linha>
          <Linha
            rotulo="Arquivo"
            ajuda={t.tipo === "appx" ? "O identificador do app da Loja (ex.: Claude_pzs8sxrjxfjjc!Claude)." : "Aceita variáveis do Windows, como %LOCALAPPDATA%."}
          >
            <input className={campo} value={t.alvo || ""} onChange={(e) => m({ alvo: e.target.value })} />
          </Linha>
          <Linha rotulo="Título da janela" ajuda="Parte do título da janela, para o Rotrix achar a janela certa (obrigatório para scripts .ps1).">
            <input className={campo} value={t.titulo || ""} onChange={(e) => m({ titulo: e.target.value })} />
          </Linha>
        </>
      )}

      {t.acao === "site" && (
        <>
          <Linha rotulo="Sites" ajuda="Um por linha. Abrem juntos.">
            <textarea
              className={`${campo} h-16 py-1 resize-y`}
              value={(t.sites || []).join("\n")}
              onChange={(e) => m({ sites: e.target.value.split("\n") })}
            />
          </Linha>
          <Linha rotulo="Navegador" ajuda="Vazio = o navegador escolhido em Telas e início.">
            <select className={campo} value={t.navegador || ""} onChange={(e) => m({ navegador: e.target.value })}>
              <option value="">o do Painel</option>
              {NAVEGADORES.map(([id, nome]) => (
                <option key={id} value={id}>
                  {nome}
                  {id !== "padrao" && estado && estado.navegadores[id] === false ? " (não instalado)" : ""}
                </option>
              ))}
            </select>
          </Linha>
          <Linha rotulo="Perfil" ajuda="Pasta do perfil do navegador (ex.: Profile 2). Vazio = o perfil de sempre.">
            <input className={campo} value={t.perfil || ""} onChange={(e) => m({ perfil: e.target.value })} />
          </Linha>
          <Linha rotulo="Título da janela" ajuda="Parte do título da janela do site, para trazer para a frente e posicionar.">
            <input className={campo} value={t.titulo || ""} onChange={(e) => m({ titulo: e.target.value })} />
          </Linha>
        </>
      )}

      {(t.acao === "rotrix" || t.acao === "sistema") && (
        <Linha rotulo="Comando">
          <select className={campo} value={t.comando} onChange={(e) => m({ comando: e.target.value })}>
            {(t.acao === "rotrix" ? COMANDOS_ROTRIX : COMANDOS_SISTEMA).map(([id, nome]) => (
              <option key={id} value={id}>
                {nome}
              </option>
            ))}
          </select>
        </Linha>
      )}
      {t.acao === "atalho" && (
        <Linha rotulo="Teclas" ajuda="Vai para a janela em que você estava antes de clicar no Rotrix. Ex.: Ctrl+Shift+V, Alt+F4, F5.">
          <input className={campo} value={t.teclas || ""} onChange={(e) => m({ teclas: e.target.value })} />
        </Linha>
      )}
      {t.acao === "texto" && (
        <Linha rotulo="Texto" ajuda="É colado na janela em que você estava antes de clicar no Rotrix.">
          <textarea
            className={`${campo} h-20 py-1 resize-y`}
            value={t.texto || ""}
            onChange={(e) => m({ texto: e.target.value })}
          />
        </Linha>
      )}

      {(t.acao === "programa" || t.acao === "site") && (
        <>
          <Linha rotulo="No expediente" ajuda="Abre sozinho ao Iniciar expediente.">
            <input type="checkbox" checked={Boolean(t.expediente)} onChange={(e) => m({ expediente: e.target.checked })} />
          </Linha>
          <Linha rotulo="Lugar na tela" ajuda="Em que monitor e em que pedaço dele a janela fica, como no Snap do Windows.">
            <SeletorLugar lugar={t.lugar} estado={estado} aoTrocar={(l) => m({ lugar: l })} />
          </Linha>
        </>
      )}

      <Linha rotulo="Cor">
        <div className="flex gap-1.5 flex-wrap">
          {(Object.keys(COR) as Grupo[]).map((g) => (
            <button
              key={g}
              type="button"
              title={NOME_GRUPO[g]}
              onClick={() => m({ grupo: g })}
              className="h-6 w-6 rounded-md border cursor-pointer"
              style={{
                background: `color-mix(in srgb, ${COR[g]} 30%, transparent)`,
                borderColor: t.grupo === g ? COR[g] : "transparent",
                boxShadow: t.grupo === g ? `0 0 0 1px ${COR[g]}` : undefined,
              }}
            />
          ))}
        </div>
      </Linha>
      <Linha rotulo="Ícone">
        <div className="flex gap-1 flex-wrap">
          {Object.entries(ICONES).map(([id, I]) => (
            <button
              key={id}
              type="button"
              onClick={() => m({ icone: id })}
              className={`h-6 w-6 grid place-items-center rounded cursor-pointer ${
                iconePadrao(t) === id ? "bg-logo-primary/30" : "hover:bg-mid-gray/15"
              }`}
            >
              <I size={13} />
            </button>
          ))}
        </div>
      </Linha>
      <Linha rotulo="Tecla larga">
        <input type="checkbox" checked={Boolean(t.larga)} onChange={(e) => m({ larga: e.target.checked })} />
      </Linha>
      <div className="flex gap-1.5 pt-1">
        <button type="button" onClick={() => aoMover(-1)} className="h-7 px-2 rounded-md border border-mid-gray/30 text-[12px] cursor-pointer">
          <ChevronLeft size={13} className="inline" /> mover
        </button>
        <button type="button" onClick={() => aoMover(1)} className="h-7 px-2 rounded-md border border-mid-gray/30 text-[12px] cursor-pointer">
          mover <ChevronRight size={13} className="inline" />
        </button>
        <button
          type="button"
          onClick={aoTirar}
          className="ms-auto h-7 px-2 rounded-md border border-red-500/40 text-red-400 text-[12px] cursor-pointer"
        >
          <Trash2 size={13} className="inline" /> Tirar
        </button>
      </div>
    </div>
  );
};

// --- Telas e início ---------------------------------------------------------------
const TelasEInicio: React.FC<{
  cfg: ConfigPainel;
  estado: EstadoPainel | null;
  aoMudarAjustes: (a: Partial<ConfigPainel["ajustes"]>) => void;
  aoCapturar: () => void;
  aoFechar: () => void;
}> = ({ cfg, estado, aoMudarAjustes, aoCapturar, aoFechar }) => {
  const mons = estado?.monitores || [];
  const teclas = cfg.paginas.flatMap((p) => p.teclas).filter((t) => t.lugar);
  const minX = Math.min(...mons.map((m) => m.x), 0);
  const minY = Math.min(...mons.map((m) => m.y), 0);
  const maxX = Math.max(...mons.map((m) => m.x + m.w), 1);
  const maxY = Math.max(...mons.map((m) => m.y + m.h), 1);
  const esc = 350 / (maxX - minX);
  const aj = cfg.ajustes;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <b className="text-[13.5px]">Telas e início</b>
        <Ajuda texto="O que era do Workflow Hub: onde cada programa fica nos monitores, o expediente ao ligar e o navegador dos sites." />
        <button type="button" onClick={aoFechar} className="ms-auto text-mid-gray hover:text-text cursor-pointer" aria-label="Fechar">
          <X size={15} />
        </button>
      </div>
      <div className="relative rounded-lg border border-mid-gray/20 bg-mid-gray/5" style={{ height: (maxY - minY) * esc + 16 }}>
        {mons.map((m) => (
          <div
            key={m.id}
            className="absolute rounded-md border border-mid-gray/40 bg-background/60"
            style={{ left: 8 + (m.x - minX) * esc, top: 8 + (m.y - minY) * esc, width: m.w * esc, height: m.h * esc }}
          >
            <span className="absolute bottom-0.5 end-1 text-[10px] text-mid-gray">
              {m.nome}
              {m.principal ? " · principal" : ""}
            </span>
            {teclas
              .filter((t) => t.lugar && t.lugar.display === m.id)
              .map((t) => {
                const mod = estado?.modelos.find((x) => x.id === t.lugar!.layout);
                const z = mod?.zonas[t.lugar!.zone];
                if (!z) return null;
                const [fx, fy, fw, fh] = z.r;
                return (
                  <div
                    key={t.id}
                    title={`${t.nome} · ${z.nome}`}
                    className="absolute rounded-[3px] text-[9.5px] leading-tight p-0.5 overflow-hidden"
                    style={{
                      left: `${fx * 100}%`,
                      top: `${fy * 100}%`,
                      width: `${fw * 100}%`,
                      height: `${fh * 100}%`,
                      background: `color-mix(in srgb, ${COR[t.grupo]} 22%, transparent)`,
                      outline: `1px solid color-mix(in srgb, ${COR[t.grupo]} 50%, transparent)`,
                      outlineOffset: -2,
                    }}
                  >
                    {t.nome}
                  </div>
                );
              })}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={aoCapturar}
        className="self-start h-7 px-3 rounded-md border border-mid-gray/30 text-[12px] cursor-pointer hover:bg-mid-gray/10"
      >
        Usar a posição de agora
        <Ajuda texto="Lê onde as janelas abertas estão agora e guarda como o lugar de cada programa." />
      </button>
      <Linha rotulo="Expediente ao ligar" ajuda="Quando o Rotrix abre (ele abre com o Windows), o expediente começa sozinho depois desses segundos. Dá para cancelar no aviso.">
        <span className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={aj.iniciar_expediente}
            onChange={(e) => aoMudarAjustes({ iniciar_expediente: e.target.checked })}
          />
          <input
            type="number"
            min={0}
            max={60}
            value={aj.atraso_s}
            onChange={(e) => aoMudarAjustes({ atraso_s: Number(e.target.value) })}
            className={`${campo} w-16`}
          />
          <span className="text-mid-gray text-[12px]">s</span>
        </span>
      </Linha>
      <Linha rotulo="Organizar ao iniciar" ajuda="Depois de abrir os programas, põe cada janela no seu lugar.">
        <input
          type="checkbox"
          checked={aj.organizar_ao_iniciar}
          onChange={(e) => aoMudarAjustes({ organizar_ao_iniciar: e.target.checked })}
        />
      </Linha>
      <Linha rotulo="Navegador dos sites" ajuda="Vale para OneLaudos e qualquer tecla de site; cada tecla pode trocar só para ela.">
        <select className={campo} value={aj.navegador} onChange={(e) => aoMudarAjustes({ navegador: e.target.value })}>
          {NAVEGADORES.map(([id, nome]) => (
            <option key={id} value={id}>
              {nome}
              {id !== "padrao" && estado && estado.navegadores[id] === false ? " (não instalado)" : ""}
            </option>
          ))}
        </select>
      </Linha>
      <Linha rotulo="Perfil" ajuda="Pasta do perfil do navegador (ex.: Profile 2). Vazio = o de sempre.">
        <input className={campo} value={aj.perfil} onChange={(e) => aoMudarAjustes({ perfil: e.target.value })} />
      </Linha>
    </div>
  );
};

// --- a página ------------------------------------------------------------------------
export const PainelPage: React.FC<{ pendentes: number }> = ({ pendentes }) => {
  const [cfg, setCfg] = useState<ConfigPainel | null>(null);
  const [estado, setEstado] = useState<EstadoPainel | null>(null);
  const [pag, setPag] = useState(0);
  const [editando, setEditando] = useState(false);
  const [sel, setSel] = useState<string | null>(null);
  const [telas, setTelas] = useState(false);
  const [aviso, setAviso] = useState("");
  const [ocupada, setOcupada] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const r = await painel("carregar");
      if (r.config) setCfg(r.config);
      if (r.estado) setEstado(r.estado);
      if (!r.ok)
        setAviso(
          r.motivo
            ? `o roteador não respondeu ao Painel (${r.motivo})`
            : "o roteador que está rodando é o antigo, sem o Painel: feche o Rotrix (e o Roteador de Laudos, se estiver aberto) e abra de novo",
        );
    } catch (e) {
      setAviso(
        /404|Not Found/i.test(String(e))
          ? "o roteador que está rodando é o antigo, sem o Painel: feche o Rotrix (e o Roteador de Laudos, se estiver aberto) e abra de novo"
          : `o Painel precisa do roteador ligado (${String(e)})`,
      );
    }
  }, []);

  useEffect(() => {
    void carregar();
    const t = setInterval(async () => {
      try {
        const r = await painel("estado");
        if (r && (r as unknown as EstadoPainel).abertos) setEstado(r as unknown as EstadoPainel);
      } catch {
        /* roteador parado: fica o de antes */
      }
    }, 8000);
    return () => clearInterval(t);
  }, [carregar]);

  // A tela muda na hora; o painel.json é gravado quando você para de digitar.
  // Tecla incompleta (programa sem arquivo, site sem endereço) fica na tela e
  // o aviso diz que ela ainda não foi gravada.
  const espera = React.useRef<number | null>(null);
  const salvar = useCallback((novo: ConfigPainel) => {
    setCfg(novo);
    if (espera.current) window.clearTimeout(espera.current);
    espera.current = window.setTimeout(async () => {
      try {
        const r = await painel("salvar", { config: novo });
        if (r.estado) setEstado(r.estado);
        const n = (c: ConfigPainel) => c.paginas.reduce((s, p) => s + p.teclas.length, 0);
        if (r.config && n(r.config) < n(novo))
          setAviso("uma tecla está incompleta (falta o arquivo, o site ou o atalho) e ainda não foi gravada");
        else setAviso("");
      } catch (e) {
        setAviso(`não gravei o Painel: ${String(e)}`);
      }
    }, 700);
  }, []);

  const pagina = cfg?.paginas[pag];
  const tSel = useMemo(() => pagina?.teclas.find((t) => t.id === sel) || null, [pagina, sel]);

  const mudarTecla = (t: Tecla) => {
    if (!cfg) return;
    const paginas = cfg.paginas.map((p, i) =>
      i === pag ? { ...p, teclas: p.teclas.map((x) => (x.id === t.id ? t : x)) } : p,
    );
    void salvar({ ...cfg, paginas });
  };

  const mover = (d: -1 | 1) => {
    if (!cfg || !pagina || !tSel) return;
    const ts = [...pagina.teclas];
    const i = ts.findIndex((x) => x.id === tSel.id);
    const j = i + d;
    if (j < 0 || j >= ts.length) return;
    [ts[i], ts[j]] = [ts[j], ts[i]];
    void salvar({ ...cfg, paginas: cfg.paginas.map((p, k) => (k === pag ? { ...p, teclas: ts } : p)) });
  };

  const tirar = () => {
    if (!cfg || !tSel) return;
    void salvar({
      ...cfg,
      paginas: cfg.paginas.map((p, k) => (k === pag ? { ...p, teclas: p.teclas.filter((x) => x.id !== tSel.id) } : p)),
    });
    setSel(null);
  };

  const adicionar = () => {
    if (!cfg) return;
    const t = novaTecla();
    void salvar({ ...cfg, paginas: cfg.paginas.map((p, k) => (k === pag ? { ...p, teclas: [...p.teclas, t] } : p)) });
    setSel(t.id);
  };

  const novaPagina = () => {
    if (!cfg) return;
    const nome = window.prompt("Nome da nova página:", "Plantão");
    if (!nome) return;
    void salvar({ ...cfg, paginas: [...cfg.paginas, { nome: nome.slice(0, 30), teclas: [] }] });
    setPag(cfg.paginas.length);
    setEditando(true);
  };

  const apertar = async (t: Tecla) => {
    if (editando) {
      setSel(t.id);
      setTelas(false);
      return;
    }
    if (t.acao === "rotrix") {
      comandoRotrix(t.comando || "");
      return;
    }
    setOcupada(t.id);
    if (t.acao === "expediente") setAviso("Iniciando o expediente: abrindo os programas e organizando as janelas…");
    try {
      const r = await painel(
        t.acao === "expediente" ? "expediente" : t.acao === "organizar" ? "organizar" : "executar",
        { id: t.id },
      );
      setAviso(r.frase || (r.ok ? t.nome : `não deu: ${r.motivo || "erro"}`));
      const e = await painel("estado");
      if ((e as unknown as EstadoPainel).abertos) setEstado(e as unknown as EstadoPainel);
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupada(null);
    }
  };

  const capturar = async () => {
    if (!cfg) return;
    try {
      const r = await painel("capturar");
      const lugares = r.lugares || {};
      const n = Object.values(lugares).filter(Boolean).length;
      if (!n) {
        setAviso("nenhuma janela aberta para ler a posição");
        return;
      }
      void salvar({
        ...cfg,
        paginas: cfg.paginas.map((p) => ({
          ...p,
          teclas: p.teclas.map((t) => (lugares[t.id] ? { ...t, lugar: lugares[t.id] } : t)),
        })),
      });
      setAviso(`posição de agora guardada para ${n} programa${n === 1 ? "" : "s"}`);
    } catch (e) {
      setAviso(String(e));
    }
  };

  const descricao = (t: Tecla): string => {
    const partes: string[] = [];
    if (t.atalho_global) partes.push(t.atalho_global);
    if (t.acao === "expediente") partes.push("abre e organiza");
    else if (t.acao === "programa" || t.acao === "site") {
      if (estado?.achados[t.id] === false) partes.push("não achado");
      else partes.push(estado?.abertos[t.id] ? "aberto" : "fechado");
    }
    return partes.join(" · ");
  };

  if (!cfg)
    return <div className="p-6 text-sm text-mid-gray">{aviso || "carregando o Painel…"}</div>;

  const lateral = (editando && tSel) || telas;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex-1 min-w-0 overflow-y-auto p-5 flex flex-col gap-3.5">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-lg font-semibold me-1">Painel</h2>
          <div className="flex gap-1">
            {cfg.paginas.map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setPag(i);
                  setSel(null);
                }}
                className={`h-7 px-3 rounded-md border text-[12.5px] cursor-pointer ${
                  i === pag ? "border-mid-gray/50 bg-mid-gray/15 font-semibold" : "border-mid-gray/25 text-mid-gray hover:text-text"
                }`}
              >
                {p.nome}
              </button>
            ))}
            <button
              type="button"
              aria-label="Nova página"
              onClick={novaPagina}
              className="h-7 w-7 grid place-items-center rounded-md border border-mid-gray/25 text-mid-gray cursor-pointer"
            >
              <Plus size={13} />
            </button>
          </div>
          <div className="ms-auto flex gap-1.5">
            <button
              type="button"
              onClick={() => {
                setTelas((v) => !v);
                setSel(null);
              }}
              className={`h-7 px-3 rounded-md border text-[12.5px] cursor-pointer flex items-center gap-1.5 ${
                telas ? "border-logo-primary bg-logo-primary/20" : "border-mid-gray/30"
              }`}
            >
              <MonitorIcone size={13} /> Telas e início
            </button>
            <button
              type="button"
              onClick={() => {
                setEditando((v) => !v);
                setSel(null);
              }}
              className={`h-7 px-3 rounded-md border text-[12.5px] cursor-pointer ${
                editando ? "border-logo-primary bg-logo-primary text-white font-semibold" : "border-mid-gray/30"
              }`}
            >
              {editando ? "Concluir edição" : "Editar teclas"}
            </button>
          </div>
        </div>

        <div className="grid gap-2.5 grid-cols-[repeat(auto-fill,minmax(132px,1fr))]">
          {(pagina?.teclas || []).map((t) => (
            <TeclaTile
              key={t.id}
              t={t}
              aberto={(t.acao === "programa" || t.acao === "site") && Boolean(estado?.abertos[t.id])}
              numero={t.acao === "rotrix" && t.comando === "proximo" ? pendentes : null}
              editando={editando}
              selecionada={editando && sel === t.id}
              ocupada={ocupada === t.id}
              aoApertar={() => void apertar(t)}
              descricao={descricao(t)}
            />
          ))}
          {editando && (
            <button
              type="button"
              onClick={adicionar}
              className="min-h-[104px] rounded-xl border border-dashed border-mid-gray/40 text-mid-gray text-[13px] cursor-pointer hover:text-text"
            >
              + tecla
            </button>
          )}
        </div>

        <div className="flex gap-3 flex-wrap items-center text-[12px] text-mid-gray">
          {(Object.keys(COR) as Grupo[]).map((g) => (
            <span key={g} className="flex items-center gap-1.5">
              <i className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: COR[g] }} />
              {NOME_GRUPO[g].toLowerCase()}
            </span>
          ))}
          <Ajuda texto="Bolinha verde: o programa está aberto (o clique traz a janela para a frente). Número: contagem ao vivo, como os exames pendentes." />
        </div>
        {aviso && <div className="text-[12.5px] text-mid-gray">{aviso}</div>}

        {/* fase 3: o Stream Deck / Stream Dock físico */}
        <AparelhoPainel cfg={cfg} aoSalvar={salvar} />
      </div>

      {lateral && (
        <aside className="w-[400px] shrink-0 border-s border-mid-gray/20 bg-mid-gray/5 overflow-y-auto p-4">
          {editando && tSel ? (
            <EditorTecla
              key={tSel.id}
              t={tSel}
              estado={estado}
              aoMudar={mudarTecla}
              aoMover={mover}
              aoTirar={tirar}
              aoFechar={() => setSel(null)}
            />
          ) : (
            <TelasEInicio
              cfg={cfg}
              estado={estado}
              aoMudarAjustes={(a) => void salvar({ ...cfg, ajustes: { ...cfg.ajustes, ...a } })}
              aoCapturar={() => void capturar()}
              aoFechar={() => setTelas(false)}
            />
          )}
        </aside>
      )}
    </div>
  );
};

export default PainelPage;
