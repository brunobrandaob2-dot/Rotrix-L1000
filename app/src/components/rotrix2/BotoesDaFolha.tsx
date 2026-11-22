/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 — o botão Cálculos, no fim da fileira de formatação da folha.
//
// 22/11/2026 (v2): Escanometria e panorâmicas, Idade óssea, Densitometria e
// Prescrição saíram do Rotrix: os exames de print ficam na Mesa de Laudo.
// 09/11: Cálculos virou menu — o volume de sempre e as calculadoras novas do
// expoweb (adrenal, esteatose, VDT, Evans, NASCET). A aba Laudo abre uma delas já
// preenchida pelo evento "rotrix:calculadora" (sugestão da conferência).
//
// Cada um abre um painel. Nos exames de medida e na idade óssea o painel é um
// FORMULÁRIO: os números entram, o laudo sai pronto. A conta acontece no
// roteador, na máquina — a IA, quando entra, só lê o print e devolve valores.
// Isso não é detalhe de implementação: é o que faz o mesmo print dar sempre o
// mesmo laudo, e o que mantém a redação sendo a do médico, não a do modelo.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Calculator, ChevronDown, ImagePlus, X } from "lucide-react";
import { Button } from "../ui/Button";
import { ImagemNaFolha } from "./ImagemNaFolha";
import { reduzirParaIA, motivoDaImagem } from "./imagemParaIA";
import { motivoDoBloqueio } from "./bloqueio";
import { CALCULADORAS, EVENTO_CALCULADORA, type IdCalc, type Valores } from "./calculadoras";
import { PainelCalculadora } from "./PainelCalculadora";

// 03/10: "eu queria poder simplesmente anexar uma imagem, colar um print com as
// medidas" — o botão do print só mostrava um aviso. Agora o print passa pelo MESMO
// recorte da folha (tira a borda com nome gravado nos pixels e o metadado), vai ao
// roteador, a IA lê e devolve números; eles entram no formulário para ele conferir.
// A conta continua aqui na máquina, como sempre.
type Lido = {
  ok?: boolean;
  motivo?: string;
  detalhe?: string;
  valores?: Record<string, string>;
  nao_achei?: string[];
  obs?: string;
  anos?: number;
  meses?: number;
  entre?: string;
  achados?: string;
  confianca?: string;
  modelo?: string;
  custo_usd?: number;
};

export const motivoDaLeitura = (m?: string, detalhe?: string): string => {
  const x = (m || "").toLowerCase();
  const bloq = motivoDoBloqueio(m);
  if (bloq) return bloq;
  const img = motivoDaImagem(x);
  if (img) return img;
  if (x === "nuvem_desligada") return "a IA está desligada nas configurações";
  if (x.includes("sem_chave")) return "falta a chave da IA nas configurações";
  if (x === "resposta_fora_do_formato") return "a IA respondeu fora do formato; tente de novo";
  if (x === "imagem_nao_serve") return `a IA não conseguiu ler: ${detalhe || "imagem"}`;
  if (x.includes("not found") || x.includes("404"))
    return "o roteador é antigo para isto: rode o ATUALIZAR e o LIGAR";
  return m ? `a IA não leu o print (${m})` : "a IA não leu o print";
};

const lerPrint = async (
  alvo: string,
  dataUrl: string,
  extra: Record<string, string> = {},
): Promise<Lido> => {
  const imagem = await reduzirParaIA(dataUrl);
  const bruto = await invoke<string>("rotrix_ler_print", {
    alvo,
    imagem,
    extra: JSON.stringify(extra),
  });
  return JSON.parse(bruto || "{}") as Lido;
};

const centavos = (usd?: number): string =>
  typeof usd === "number"
    ? ` · ${(usd * 100).toFixed(usd * 100 < 1 ? 2 : 1).replace(".", ",")} centavo`
    : "";

// ---------------------------------------------------------------------------

interface Props {
  /** põe o texto na folha, no ponto do cursor */
  aoInserir: (texto: string) => void;
  /** avisos curtos para o rodapé da folha */
  aoAvisar?: (texto: string) => void;
}

// ---------------------------------------------------------------------------

const Menu: React.FC<{
  aberto: boolean;
  aoFechar: () => void;
  children: React.ReactNode;
}> = ({ aberto, aoFechar, children }) => {
  useEffect(() => {
    if (!aberto) return;
    const sair = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", sair);
    return () => window.removeEventListener("keydown", sair);
  }, [aberto, aoFechar]);
  if (!aberto) return null;
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={aoFechar} />
      <div className="absolute z-50 top-full mt-1 start-0 w-[330px] rounded-xl border border-mid-gray/30 bg-background shadow-2xl p-1.5">
        {children}
      </div>
    </>
  );
};

const ItemMenu: React.FC<{
  nome: string;
  resumo?: string;
  onClick: () => void;
}> = ({ nome, resumo, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="w-full text-start px-2.5 py-2 rounded-lg hover:bg-logo-primary/20 cursor-pointer"
  >
    <div className="text-[12.5px] font-semibold">{nome}</div>
    {resumo && <div className="text-[10.5px] text-mid-gray leading-tight">{resumo}</div>}
  </button>
);

const Fer: React.FC<{
  titulo: string;
  onClick: () => void;
  aberto?: boolean;
  children: React.ReactNode;
}> = ({ titulo, onClick, aberto, children }) => (
  <button
    type="button"
    title={titulo}
    onClick={onClick}
    className={`h-7 px-2 rounded-lg border flex items-center gap-1.5 text-[11.5px] cursor-pointer transition-colors ${
      aberto
        ? "border-logo-primary/60 bg-logo-primary/30 font-semibold"
        : "border-logo-primary/45 bg-logo-primary/12 hover:bg-logo-primary/22"
    }`}
  >
    {children}
  </button>
);

const hoje = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------------
// Painel dos cálculos de volume
// ---------------------------------------------------------------------------

interface Orgao {
  id: string;
  titulo: string;
  extras: string[];
}

const PainelCalculos: React.FC<{
  aoInserir: (t: string) => void;
  aoFechar: () => void;
}> = ({ aoInserir, aoFechar }) => {
  const [orgaos, setOrgaos] = useState<Orgao[]>([]);
  const [orgao, setOrgao] = useState("generico");
  const [eixos, setEixos] = useState({ l: "", ap: "", t: "" });
  const [emMm, setEmMm] = useState(false);
  const [lado, setLado] = useState("direito");
  const [psa, setPsa] = useState("");
  const [anterior, setAnterior] = useState("");
  const [r, setR] = useState<Record<string, unknown> | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    invoke<string>("rotrix_calculos_campos")
      .then((b) => {
        const d = JSON.parse(b || "{}") as { ok?: boolean; orgaos?: Orgao[] };
        if (d.ok && d.orgaos) setOrgaos(d.orgaos);
      })
      .catch(() => undefined);
  }, []);

  const extras = orgaos.find((o) => o.id === orgao)?.extras || [];

  const calcular = useCallback(async () => {
    setErro("");
    try {
      const bruto = await invoke<string>("rotrix_calculos", {
        pedido: JSON.stringify({
          orgao,
          l: eixos.l,
          ap: eixos.ap,
          t: eixos.t,
          em_mm: emMm,
          lado,
          psa: extras.includes("psa") ? psa : "",
          anterior: extras.includes("anterior") ? anterior : "",
        }),
      });
      const d = JSON.parse(bruto || "{}") as Record<string, unknown>;
      if (!d.ok) {
        setErro(String(d.detalhe || d.motivo || "não deu para calcular"));
        return;
      }
      setR(d);
    } catch (e) {
      setErro(String(e));
    }
  }, [orgao, eixos, emMm, lado, psa, anterior, extras]);

  const campo = (k: "l" | "ap" | "t", rot: string) => (
    <label className="flex flex-col gap-0.5">
      <span className="text-[10px] text-mid-gray">{rot}</span>
      <input
        value={eixos[k]}
        onChange={(e) => {
          setEixos((x) => ({ ...x, [k]: e.target.value }));
          setR(null);
        }}
        inputMode="decimal"
        className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
      />
    </label>
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <span className="text-[12.5px] font-semibold">Cálculo de volume</span>
        <span className="text-[10px] text-mid-gray">L × AP × T × 0,523</span>
        <button
          type="button"
          onClick={aoFechar}
          className="ms-auto p-1 rounded hover:bg-mid-gray/20 cursor-pointer"
          title="fechar"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        <div>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1">ONDE</div>
          <div className="flex flex-wrap gap-1.5">
            {orgaos.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => {
                  setOrgao(o.id);
                  setR(null);
                }}
                className={`text-[10.5px] px-2 py-1 rounded-md border cursor-pointer ${
                  orgao === o.id
                    ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
                    : "border-mid-gray/25 hover:bg-mid-gray/15"
                }`}
              >
                {o.titulo}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[9.5px] font-bold tracking-wider text-mid-gray">
              EIXOS ({emMm ? "mm" : "cm"})
            </span>
            <button
              type="button"
              onClick={() => {
                setEmMm((v) => !v);
                setR(null);
              }}
              className="text-[10px] px-1.5 py-0.5 rounded border border-mid-gray/25 cursor-pointer hover:bg-mid-gray/15"
            >
              usar {emMm ? "cm" : "mm"}
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {campo("l", "longitudinal")}
            {campo("ap", "anteroposterior")}
            {campo("t", "transverso")}
          </div>
        </div>

        {extras.includes("lado") && (
          <div>
            <div className="text-[9.5px] font-bold tracking-wider text-mid-gray mb-1">LADO</div>
            <div className="flex gap-1.5">
              {["direito", "esquerdo"].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setLado(s);
                    setR(null);
                  }}
                  className={`text-[10.5px] px-2.5 py-1 rounded-md border cursor-pointer ${
                    lado === s
                      ? "border-logo-primary/60 bg-logo-primary/25 font-bold"
                      : "border-mid-gray/25 hover:bg-mid-gray/15"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {extras.includes("psa") && (
          <label className="flex flex-col gap-0.5">
            <span className="text-[10px] text-mid-gray">PSA (ng/mL) — opcional, dá a densidade</span>
            <input
              value={psa}
              onChange={(e) => {
                setPsa(e.target.value);
                setR(null);
              }}
              inputMode="decimal"
              className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
            />
          </label>
        )}

        {extras.includes("anterior") && (
          <label className="flex flex-col gap-0.5">
            <span className="text-[10px] text-mid-gray">
              volume no exame anterior (cm³) — opcional
            </span>
            <input
              value={anterior}
              onChange={(e) => {
                setAnterior(e.target.value);
                setR(null);
              }}
              inputMode="decimal"
              className="h-7 rounded-lg border border-mid-gray/25 bg-background px-2 text-[12px]"
            />
          </label>
        )}

        {erro && (
          <div className="text-[11px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-2.5 py-2">
            {erro}
          </div>
        )}

        {r && (
          <>
            <div className="text-[10.5px] text-mid-gray border-t border-mid-gray/20 pt-2">
              volume <b className="text-text">{String(r.volume)} cm³</b>
              {r.densidade_psa !== undefined && (
                <> · densidade de PSA <b className="text-text">{String(r.densidade_psa)}</b></>
              )}
              {r.variacao_pct !== undefined && (
                <> · volume <b className="text-text">{String(r.variacao_pct)}%</b> · diâmetro{" "}
                  <b className="text-text">{String(r.variacao_diametro_pct)}%</b></>
              )}
            </div>
            <div className="rounded-lg papel p-3 text-[11.5px] leading-[1.55]">
              {String(r.frase || "")}
            </div>
            {((r.avisos as string[]) || []).map((a) => (
              <div
                key={a}
                className="text-[11px] rounded-lg border border-amber-400/35 bg-amber-100/10 text-amber-300 px-2.5 py-2"
              >
                {a}
              </div>
            ))}
          </>
        )}
      </div>

      <div className="flex gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button variant="primary" size="sm" onClick={() => void calcular()}>
          Calcular
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!r}
          onClick={() => {
            if (r) {
              aoInserir(String(r.frase || ""));
              aoFechar();
            }
          }}
        >
          Pôr na folha
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------

export const BotoesDaFolha: React.FC<Props> = ({ aoInserir }) => {
  const [menu, setMenu] = useState<"" | "calculos">("");
  const [painel, setPainel] = useState<
    | { tipo: "calculos" }
    | { tipo: "calc"; id: IdCalc; valores?: Valores; vez: number }
    | null
  >(null);
  // a conferência da folha achou números (adrenal com 3 UH, fígado e baço): abre preenchida
  useEffect(() => {
    const abrir = (e: Event) => {
      const d = (e as CustomEvent<{ id?: IdCalc; valores?: Valores }>).detail || {};
      if (d.id && CALCULADORAS[d.id]) {
        setMenu("");
        setPainel({ tipo: "calc", id: d.id, valores: d.valores, vez: Date.now() });
      }
    };
    window.addEventListener(EVENTO_CALCULADORA, abrir);
    return () => window.removeEventListener(EVENTO_CALCULADORA, abrir);
  }, []);

  const fechar = () => setPainel(null);

  return (
    <>
      <div className="w-px h-[18px] bg-mid-gray/30 mx-1" />

      <div className="relative">
        <Fer
          titulo="Volume (L × AP × T × 0,523) e as calculadoras: adrenal, esteatose, VDT, Evans, NASCET"
          aberto={menu === "calculos"}
          onClick={() => setMenu((m) => (m === "calculos" ? "" : "calculos"))}
        >
          <Calculator size={14} /> Cálculos <ChevronDown size={11} />
        </Fer>
        <Menu aberto={menu === "calculos"} aoFechar={() => setMenu("")}>
          <div className="text-[9.5px] font-bold tracking-wider text-mid-gray px-2 pt-1 pb-1">
            CALCULAR
          </div>
          <ItemMenu
            nome="Volume"
            resumo="L × AP × T × 0,523 — próstata, tireoide, ovário, bexiga e o resto"
            onClick={() => {
              setMenu("");
              setPainel({ tipo: "calculos" });
            }}
          />
          {Object.values(CALCULADORAS).map((c) => (
            <ItemMenu
              key={c.id}
              nome={c.nome}
              resumo={c.resumo}
              onClick={() => {
                setMenu("");
                setPainel({ tipo: "calc", id: c.id, vez: Date.now() });
              }}
            />
          ))}
          <div className="px-2.5 py-1.5 text-[10.5px] text-mid-gray">
            Conta na máquina, sem IA. Os limiares estão marcados para a sua revisão clínica.
          </div>
        </Menu>
      </div>

      {painel && (
        <div className="fixed inset-y-0 end-0 z-50 w-[430px] bg-background border-s border-mid-gray/30 shadow-2xl flex flex-col">
          {painel.tipo === "calculos" && (
            <PainelCalculos aoInserir={aoInserir} aoFechar={fechar} />
          )}
          {painel.tipo === "calc" && (
            <PainelCalculadora
              key={`${painel.id}-${painel.vez}`}
              calc={CALCULADORAS[painel.id]}
              inicial={painel.valores}
              aoInserir={aoInserir}
              aoFechar={fechar}
            />
          )}
        </div>
      )}
    </>
  );
};

export default BotoesDaFolha;
