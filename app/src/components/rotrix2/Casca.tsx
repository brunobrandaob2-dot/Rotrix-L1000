/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — a casca do app: a barra das abas e a aba aberta.
//
// Laudo · Fila · Adendos · Máscaras · Histórico · Config. A barra é estreita e
// fica sempre visível; cada aba ocupa a janela inteira, sem moldura em volta.
// A Fila mostra quantos exames estão esperando.
import React, { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { PenLine, Rows3, FilePlus2, LayoutGrid, Clock, Cog } from "lucide-react";
import HandyTextLogo from "../icons/HandyTextLogo";
import type { SidebarSection } from "../Sidebar";
import type { OnboardingPreviewStep } from "../settings";
import { LaudoPage } from "./LaudoPage";
import { FilaPage } from "./FilaPage";
import { AdendoPage } from "./AdendoPage";
import { MascarasPage } from "./MascarasPage";
import { HistoricoPage } from "./HistoricoPage";
import { ConfigPage } from "./ConfigPage";

export type Aba = "laudo" | "fila" | "adendos" | "mascaras" | "historico" | "config";

const ABAS: { id: Aba; nome: string; icone: React.ElementType }[] = [
  { id: "laudo", nome: "Laudo", icone: PenLine },
  { id: "fila", nome: "Fila", icone: Rows3 },
  { id: "adendos", nome: "Adendos", icone: FilePlus2 },
  { id: "mascaras", nome: "Máscaras", icone: LayoutGrid },
  { id: "historico", nome: "Histórico", icone: Clock },
  { id: "config", nome: "Config.", icone: Cog },
];

// Os modelos que o botão forte pode usar, por provedor. O primeiro de cada
// lista é o básico (só formatar) e é o que o botão leve usa.
const MODELOS: Record<string, { id: string; nome: string }[]> = {
  anthropic: [
    { id: "claude-haiku-4-5-20251001", nome: "Haiku 4.5" },
    { id: "claude-sonnet-5", nome: "Sonnet 5" },
    { id: "claude-opus-5", nome: "Opus 5" },
    { id: "claude-fable-5-1", nome: "Fable 5.1" },
  ],
  openai: [
    { id: "gpt-5.6-luna", nome: "Luna" },
    { id: "gpt-5.6-terra", nome: "Terra" },
    { id: "gpt-5.6-sol", nome: "Sol" },
  ],
  gemini: [{ id: "gemini-3.8-flash", nome: "Flash" }],
};

const GUARDADO = "rotrix2.modeloForte";

// O modelo "leve" de cada provedor é o básico (só formatar) — o mesmo que a
// tela de IA oferece em primeiro lugar.
const LEVE: Record<string, { id: string; nome: string }> = {
  anthropic: { id: "claude-haiku-4-5-20251001", nome: "Haiku" },
  openai: { id: "gpt-5.6-luna", nome: "Luna" },
  gemini: { id: "gemini-3.8-flash", nome: "Flash" },
};

const APELIDOS = [
  ["opus", "Opus"],
  ["sonnet", "Sonnet"],
  ["haiku", "Haiku"],
  ["fable", "Fable"],
  ["terra", "Terra"],
  ["luna", "Luna"],
  ["sol", "Sol"],
  ["flash", "Flash"],
  ["pro", "Pro"],
];

const apelido = (modelo: string): string => {
  const m = (modelo || "").toLowerCase();
  for (const [chave, nome] of APELIDOS) if (m.includes(chave)) return nome;
  return modelo ? modelo.split(/[:/]/).pop()!.slice(0, 12) : "IA";
};

interface Props {
  aoVerOnboarding: (passo: OnboardingPreviewStep) => void;
}

export const Casca: React.FC<Props> = ({ aoVerOnboarding }) => {
  const [aba, setAba] = useState<Aba>("laudo");
  const [secaoConfig, setSecaoConfig] = useState<SidebarSection>("general");
  const [naFila, setNaFila] = useState(0);
  const [ia, setIa] = useState<{ provedor: string; modelo: string }>({
    provedor: "anthropic",
    modelo: "",
  });
  const [paraFolha, setParaFolha] = useState<{ texto: string; n: number }>({
    texto: "",
    n: 0,
  });
  // o modelo do botão forte é escolha da tela e fica guardado para a próxima vez
  const [modeloForte, setModeloForte] = useState<string>(() => {
    try {
      return localStorage.getItem(GUARDADO) || "";
    } catch {
      return "";
    }
  });

  // quantos exames estão esperando (marcador da aba Fila)
  const contarFila = useCallback(async () => {
    try {
      const bruto = await invoke<string>("rotrix_fila");
      const f = JSON.parse(bruto || "{}") as {
        itens?: { feito?: boolean; laudado?: boolean | null }[];
      };
      setNaFila((f.itens || []).filter((i) => !(i.feito || i.laudado)).length);
    } catch {
      setNaFila(0);
    }
  }, []);

  useEffect(() => {
    void contarFila();
    const t = setInterval(() => void contarFila(), 60000);
    const p = listen("rotrix-proximo-exame", () => void contarFila());
    return () => {
      clearInterval(t);
      p.then((fn) => fn());
    };
  }, [contarFila]);

  useEffect(() => {
    invoke<string>("rotrix_ia_estado")
      .then((bruto) => {
        const e = JSON.parse(bruto || "{}") as {
          provedor?: string;
          modelo?: string;
        };
        setIa({
          provedor: (e.provedor || "anthropic").toLowerCase(),
          modelo: e.modelo || "",
        });
      })
      .catch(() => undefined);
  }, []);

  const leve = LEVE[ia.provedor] || { id: "", nome: "Leve" };
  const listaModelos = MODELOS[ia.provedor] || [];
  const forte =
    (modeloForte && listaModelos.some((m) => m.id === modeloForte) && modeloForte) ||
    ia.modelo;

  const trocarModelo = (id: string) => {
    setModeloForte(id);
    try {
      localStorage.setItem(GUARDADO, id);
    } catch {
      /* sem problema: no próximo início volta para o modelo da configuração */
    }
  };

  const abrirNoLaudo = (texto: string) => {
    setParaFolha((p) => ({ texto, n: p.n + 1 }));
    setAba("laudo");
  };

  const abrirConfig = (secao: string) => {
    setSecaoConfig(secao as SidebarSection);
    setAba("config");
  };

  return (
    <div className="flex-1 flex min-h-0 overflow-hidden">
      {/* barra das abas */}
      <div className="w-24 shrink-0 flex flex-col items-center gap-1 border-e border-mid-gray/20 bg-background py-2">
        <HandyTextLogo width={72} className="mb-2" />
        {ABAS.map((a) => {
          const Icone = a.icone;
          const ativo = aba === a.id;
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => setAba(a.id)}
              title={a.nome}
              className={`relative w-[84px] py-2 rounded-lg flex flex-col items-center gap-0.5 text-[11px] cursor-pointer transition-colors ${
                ativo
                  ? "bg-logo-primary/25 font-semibold"
                  : "hover:bg-mid-gray/15 opacity-85 hover:opacity-100"
              }`}
            >
              <Icone width={18} height={18} />
              {a.nome}
              {a.id === "fila" && naFila > 0 && (
                <span className="absolute top-1 end-2 text-[9px] font-bold rounded-full bg-logo-primary text-white px-1.5">
                  {naFila}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* aba aberta */}
      <div className="flex-1 min-w-0 min-h-0">
        {aba === "laudo" && (
          <LaudoPage
            modeloLeve={leve.nome}
            modeloCompleto={apelido(forte)}
            idModeloCompleto={forte}
            textoEntrando={paraFolha}
            modelos={listaModelos}
            aoTrocarModelo={trocarModelo}
          />
        )}
        {aba === "fila" && <FilaPage />}
        {aba === "adendos" && (
          <AdendoPage
            modelos={listaModelos}
            idModelo={forte}
            aoTrocarModelo={trocarModelo}
          />
        )}
        {aba === "mascaras" && <MascarasPage aoAbrirConfig={abrirConfig} />}
        {aba === "historico" && (
          <HistoricoPage aoAbrirNoLaudo={abrirNoLaudo} idModeloCompleto={forte} />
        )}
        {aba === "config" && (
          <ConfigPage
            secao={secaoConfig}
            aoTrocarSecao={setSecaoConfig}
            aoVerOnboarding={aoVerOnboarding}
          />
        )}
      </div>
    </div>
  );
};

export default Casca;
