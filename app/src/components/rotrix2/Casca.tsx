/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — a casca do app: a barra das abas e a aba aberta.
//
// Laudo · Fila · Adendos · Máscaras · Histórico · Config. A barra é estreita e
// fica sempre visível; cada aba ocupa a janela inteira, sem moldura em volta.
// A Fila mostra quantos exames estão esperando.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  PenLine,
  Rows3,
  FilePlus2,
  Pill,
  Grid3x3,
  LayoutGrid,
  Clock,
  Cog,
} from "lucide-react";
import HandyTextLogo from "../icons/HandyTextLogo";
import type { SidebarSection } from "../Sidebar";
import type { OnboardingPreviewStep } from "../settings";
import { LaudoPage } from "./LaudoPage";
import { FilaPage } from "./FilaPage";
import { AdendoPage } from "./AdendoPage";
import { ComparativoPage } from "./ComparativoPage";
import { PrescricoesPage } from "./PrescricoesPage";
import { EstruturadosPage } from "./EstruturadosPage";
import { MascarasPage } from "./MascarasPage";
import { HistoricoPage } from "./HistoricoPage";
import { ConfigPage } from "./ConfigPage";

type SubAdendo = "adendo" | "comparativo";

export type Aba =
  | "laudo"
  | "fila"
  | "adendos"
  | "prescricoes"
  | "estruturados"
  | "mascaras"
  | "historico"
  | "config";

const ABAS: { id: Aba; nome: string; icone: React.ElementType }[] = [
  { id: "laudo", nome: "Laudo", icone: PenLine },
  { id: "fila", nome: "Fila", icone: Rows3 },
  { id: "adendos", nome: "Adendos", icone: FilePlus2 },
  { id: "prescricoes", nome: "Prescrições", icone: Pill },
  { id: "estruturados", nome: "Estruturados", icone: Grid3x3 },
  { id: "mascaras", nome: "Máscaras", icone: LayoutGrid },
  { id: "historico", nome: "Histórico", icone: Clock },
  { id: "config", nome: "Config.", icone: Cog },
];

// A lista de modelos vem da API do provedor instalado, não de tabela aqui.
// Tabela escrita à mão envelhece e amarra o app a um fornecedor: quem instala
// com chave de outro continuava vendo os nomes do primeiro na tela.
import { escolherLeve, escolherForte, maisForteDoAtual } from "./modelos";

const GUARDADO = "rotrix2.modeloForte";
const GUARDADO_LEVE = "rotrix2.modeloLeve";

// Nome curto de um modelo, para caber no botão. Sai do PRÓPRIO identificador
// que o provedor devolveu — nenhum nome de fabricante escrito aqui. Assim a
// tela fica igual seja qual for a chave instalada.
const apelido = (modelo: string): string => {
  const cru = (modelo || "").split(/[:/]/).pop() || "";
  if (!cru) return "IA";
  // tira data no fim ("-20251001") e números de versão soltos, e deixa a
  // primeira parte com letra maiúscula: "claude-haiku-4-5-2025…" -> "Haiku 4.5"
  const partes = cru
    .replace(/[-_]?\d{6,}$/, "")
    .split(/[-_.]/)
    .filter((x) => x && !/^(latest|preview|exp|chat|instruct)$/i.test(x));
  const nome = partes.slice(-3).join(" ").trim() || cru;
  return (nome.charAt(0).toUpperCase() + nome.slice(1)).slice(0, 16);
};

// O motivo que o roteador devolve quando a lista de modelos de um provedor
// falha, em português de gente. Aparece na barra do Laudo.
const explicarFalha = (provedor: string, motivo: string): string => {
  const nome = provedor.charAt(0).toUpperCase() + provedor.slice(1);
  const m = motivo.toLowerCase();
  const porque = m.includes("401")
    ? "a API recusou a chave (errada, incompleta ou revogada)"
    : m.includes("403")
      ? "a chave não tem permissão para os modelos"
      : m.includes("429")
        ? "sem saldo ou acima do limite da conta"
        : m.includes("sem_chave")
          ? "não há chave gravada para ele"
          : m.includes("urlerror") || m.includes("timeout")
            ? "não chegou na API (internet, firewall ou proxy)"
            : "não respondeu (" + motivo + ")";
  return `${nome}: ${porque}. A IA não vai trocar de provedor sozinha — confira em Configurações > IA.`;
};

interface Props {
  aoVerOnboarding: (passo: OnboardingPreviewStep) => void;
}

export const Casca: React.FC<Props> = ({ aoVerOnboarding }) => {
  const [aba, setAba] = useState<Aba>("laudo");
  const [subAdendo, setSubAdendo] = useState<SubAdendo>("adendo");
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
  const [modeloLeve, setModeloLeve] = useState<string>(() => {
    try {
      return localStorage.getItem(GUARDADO_LEVE) || "";
    } catch {
      return "";
    }
  });
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

  const [listaModelos, setListaModelos] = useState<
    { id: string; nome: string; provedor?: string }[]
  >([]);
  // o provedor do config que NÃO respondeu à lista de modelos, e por quê
  const [avisoIa, setAvisoIa] = useState<string>("");

  // A lista de modelos vem de quem tem a chave; sem chave, fica vazia e os
  // botões de IA seguem funcionando com o modelo que está na configuração.
  //
  // 26/09 (tarde): o provedor e a lista eram lidos UMA vez, quando o app abria.
  // Ele trocou para OpenAI em Configurações, salvou, voltou ao Laudo — e a barra
  // continuava na Anthropic até fechar o app. Agora relê ao sair de Configurações.
  const recarregarIa = useCallback(async () => {
    let provedor = "anthropic";
    try {
      const e = JSON.parse((await invoke<string>("rotrix_ia_estado")) || "{}") as {
        provedor?: string;
        modelo?: string;
      };
      provedor = (e.provedor || "anthropic").toLowerCase();
      setIa({ provedor, modelo: e.modelo || "" });
    } catch {
      /* roteador parado: fica como estava */
    }
    try {
      const d = JSON.parse((await invoke<string>("rotrix_ia_modelos")) || "{}") as {
        ok?: boolean;
        motivo?: string;
        modelos?: { id: string; nome: string; provedor?: string }[];
        falhas?: Record<string, string>;
      };
      setListaModelos(d.ok && d.modelos ? d.modelos : []);
      const falhou = (d.falhas || {})[provedor] || (!d.ok ? d.motivo || "" : "");
      setAvisoIa(falhou ? explicarFalha(provedor, falhou) : "");
    } catch {
      setListaModelos([]);
      setAvisoIa("");
    }
  }, []);

  useEffect(() => {
    void recarregarIa();
  }, [recarregarIa]);

  const abaAnterior = useRef<Aba>(aba);
  useEffect(() => {
    if (abaAnterior.current === "config" && aba !== "config") {
      void recarregarIa();
    }
    abaAnterior.current = aba;
  }, [aba, recarregarIa]);

  // Qual IA cada botão aciona. A regra inteira, e o porquê dela, está em
  // modelos.ts — foi ali que o "modelo caro escolhido por ninguém" morreu.
  const idLeve = escolherLeve(listaModelos, modeloLeve);
  const leve = { id: idLeve, nome: apelido(idLeve) };
  const forte = escolherForte(listaModelos, modeloForte, ia.modelo);

  const guardar = (chave: string, id: string) => {
    try {
      localStorage.setItem(chave, id);
    } catch {
      /* sem problema: no próximo início volta para o modelo da configuração */
    }
  };

  const trocarModelo = (id: string) => {
    setModeloForte(id);
    guardar(GUARDADO, id);
  };

  const trocarModeloLeve = (id: string) => {
    setModeloLeve(id);
    guardar(GUARDADO_LEVE, id);
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
        {/*
          Laudo e Adendos ficam SEMPRE montados, escondidos com `hidden`. A folha
          é um contentEditable: o texto mora no DOM, não em estado do React.
          Desmontar a aba (o antigo `aba === "laudo" && <LaudoPage/>`) jogava
          fora o laudo inteiro ao trocar de aba — e o ditado com outra aba aberta
          não tinha onde cair. As outras abas continuam sob demanda.
        */}
        <div className={aba === "laudo" ? "h-full" : "hidden"}>
          <LaudoPage
            modeloLeve={leve.nome}
            idModeloLeve={leve.id}
            aoTrocarModeloLeve={trocarModeloLeve}
            modeloCompleto={apelido(forte)}
            idModeloCompleto={forte}
            textoEntrando={paraFolha}
            modelos={listaModelos}
            aoTrocarModelo={trocarModelo}
            avisoIa={avisoIa}
          />
        </div>
        <div className={aba === "adendos" ? "h-full flex flex-col min-h-0" : "hidden"}>
          {/* duas sub-abas: escrever um adendo, ou comparar com o exame anterior */}
          <div className="flex items-center gap-1 px-3 pt-2 pb-1 border-b border-mid-gray/20">
            {(
              [
                ["adendo", "Adendo"],
                ["comparativo", "Comparativo"],
              ] as [SubAdendo, string][]
            ).map(([id, nome]) => (
              <button
                key={id}
                type="button"
                onClick={() => setSubAdendo(id)}
                className={`px-3 py-1 rounded-lg text-[12px] cursor-pointer ${
                  subAdendo === id
                    ? "bg-logo-primary/25 font-semibold"
                    : "hover:bg-mid-gray/15 text-mid-gray"
                }`}
              >
                {nome}
              </button>
            ))}
          </div>
          <div className={subAdendo === "adendo" ? "flex-1 min-h-0" : "hidden"}>
            <AdendoPage
              modelos={listaModelos}
              idModelo={forte}
              aoTrocarModelo={trocarModelo}
            />
          </div>
          <div className={subAdendo === "comparativo" ? "flex-1 min-h-0" : "hidden"}>
            {/* comparativo entra no modelo mais forte disponível, não no que
                estiver escolhido na barra do Laudo */}
            <ComparativoPage
              modelos={listaModelos}
              idModelo={maisForteDoAtual(listaModelos) || forte}
              aoTrocarModelo={trocarModelo}
            />
          </div>
        </div>
        {aba === "fila" && <FilaPage />}
        {aba === "prescricoes" && <PrescricoesPage />}
        {aba === "estruturados" && <EstruturadosPage />}
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
