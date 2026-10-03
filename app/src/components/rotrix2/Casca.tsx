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
import { escolherForte, escolherComparativo, conversa, regrasDaTabela } from "./modelos";
import { ligarCopiaLimpa } from "./copiaLimpa";

const GUARDADO = "rotrix2.modeloForte";
// 29/09 (auditoria): o seletor do botão LEVE era enfeite. O leve passa pelo
// Handy -> /v1/chat/completions do roteador, que ignora o "model" do pedido e
// usa Configurações (Modelo padrão + tabela por exame). A barra mostrava
// "5 6 luna" (escolha antiga guardada) e a chamada ia para o gpt-6-luna.
// Agora a barra mostra o que Configurações manda, e a escolha antiga é apagada.
const GUARDADO_LEVE = "rotrix2.modeloLeve";
// o Modelo padrão do config no momento em que ele escolheu o forte na barra:
// se ele trocar o Modelo padrão em Configurações, a escolha antiga da barra cai
const GUARDADO_BASE = "rotrix2.modeloForte.base";
// 27/09: o Comparativo tem a escolha dele, separada do botão forte do Laudo
const GUARDADO_COMPARATIVO = "rotrix2.modeloComparativo";

// Nome curto de um modelo, para caber no botão. Sai do PRÓPRIO identificador
// que o provedor devolveu — nenhum nome de fabricante escrito aqui. Assim a
// tela fica igual seja qual for a chave instalada.
// 29/09: id curto sai inteiro ("gpt-6-sol"); antes virava "Gpt 6 sol" e
// "gpt-5.6-terra" virava "5 6 terra", que não diz de que geração é.
const apelido = (modelo: string): string => {
  const cru = (modelo || "").split(/[:/]/).pop() || "";
  if (!cru) return "IA";
  if (cru.length <= 16 && !/\d{6,}$/.test(cru)) return cru;
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
  const [paraFolha, setParaFolha] = useState<{ texto: string; n: number; de?: string }>({
    texto: "",
    n: 0,
  });
  // a escolha antiga do leve não mandava em nada: some, para não enganar
  useEffect(() => {
    try {
      localStorage.removeItem(GUARDADO_LEVE);
    } catch {
      /* sem problema */
    }
  }, []);
  // tabela por exame de Configurações (ex.: TC -> gpt-6-sol), para a barra mostrar
  const [regras, setRegras] = useState<Record<string, string>>({});
  // 03/10: a IA do botão leve voltou a ser escolha da barra — agora gravada no
  // config.json (modelo_leve), onde o roteador lê nas chamadas do leve
  const [modeloLeve, setModeloLeve] = useState<string>("");
  // o modelo do botão forte é escolha da tela e fica guardado para a próxima vez
  const [modeloForte, setModeloForte] = useState<string>(() => {
    try {
      return localStorage.getItem(GUARDADO) || "";
    } catch {
      return "";
    }
  });
  const [modeloComparativo, setModeloComparativo] = useState<string>(() => {
    try {
      return localStorage.getItem(GUARDADO_COMPARATIVO) || "";
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
  const novaTentativa = useRef(0);
  const recarregarRef = useRef<() => Promise<void>>(async () => {});
  const recarregarIa = useCallback(async () => {
    let provedor = "anthropic";
    try {
      const e = JSON.parse((await invoke<string>("rotrix_ia_estado")) || "{}") as {
        provedor?: string;
        modelo?: string;
        modelo_leve?: string;
        ia_por_exame?: Record<string, { modelo?: string } | string>;
      };
      provedor = (e.provedor || "anthropic").toLowerCase();
      const doConfig = e.modelo || "";
      setIa({ provedor, modelo: doConfig });
      setModeloLeve(e.modelo_leve || "");
      setRegras(regrasDaTabela(e.ia_por_exame));
      // trocou o Modelo padrão em Configurações: a escolha antiga da barra cai
      try {
        const salvo = localStorage.getItem(GUARDADO) || "";
        const base = localStorage.getItem(GUARDADO_BASE) || "";
        if (salvo && doConfig && base !== doConfig) {
          localStorage.removeItem(GUARDADO);
          localStorage.setItem(GUARDADO_BASE, doConfig);
          setModeloForte("");
        }
      } catch {
        /* sem localStorage: fica como estava */
      }
    } catch {
      /* roteador parado: fica como estava */
    }
    try {
      const d = JSON.parse((await invoke<string>("rotrix_ia_modelos")) || "{}") as {
        ok?: boolean;
        motivo?: string;
        modelos?: { id: string; nome: string; provedor?: string }[];
        falhas?: Record<string, string>;
        atualizando?: string[];
      };
      // codex/pro da OpenAI, áudio, imagem, embedding: não conversam pela rota do
      // roteador (404). Fora de TODOS os seletores, mesmo com roteador antigo.
      const nova = (d.ok && d.modelos ? d.modelos : []).filter((m) => conversa(m.id));
      const chegando = d.motivo === "sem_resposta_ainda";
      // provedor lento (não falhou): a lista que já estava fica até a nova chegar
      setListaModelos((antes) => (nova.length === 0 && chegando && antes.length > 0 ? antes : nova));
      const falhou =
        (d.falhas || {})[provedor] || (!d.ok && !chegando ? d.motivo || "" : "");
      setAvisoIa(falhou ? explicarFalha(provedor, falhou) : "");
      // o roteador responde em < 2 s e termina a busca lenta por trás: pergunta de
      // novo daqui a 3 s (no máximo 2 vezes) para a lista completa aparecer sozinha
      if ((chegando || (d.atualizando || []).length > 0) && novaTentativa.current < 2) {
        novaTentativa.current += 1;
        setTimeout(() => void recarregarRef.current(), 3000);
      } else if (!chegando && !(d.atualizando || []).length) {
        novaTentativa.current = 0;
      }
    } catch (err) {
      // 26/09 (fim da tarde): aqui a lista era zerada CALADA. A barra do Laudo
      // escondia a escolha de modelo e ficava presa no do config, sem dizer por
      // quê. Agora a lista que já estava fica, e a barra diz o que aconteceu.
      setAvisoIa(
        "A lista de modelos não chegou (" +
          String(err) +
          "). A barra fica no modelo que já estava; saia e volte de Configurações para tentar de novo.",
      );
    }
  }, []);

  recarregarRef.current = recarregarIa;

  // tema escuro: Ctrl+C numa folha não leva a letra branca da tela para o RIS
  useEffect(() => ligarCopiaLimpa(), []);

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
  // o leve: a escolha da barra (config.json: modelo_leve); vazio = Modelo padrão.
  // Nos exames com regra na tabela por exame, a tabela manda (igual ao forte).
  const idLeve = modeloLeve || ia.modelo;
  const nomeLeve = idLeve ? apelido(idLeve) : "IA rápida";
  const trocarModeloLeve = async (id: string) => {
    // escolher o próprio Modelo padrão grava vazio: se ele trocar o padrão em
    // Configurações, o leve acompanha
    const valor = id === ia.modelo ? "" : id;
    const antes = modeloLeve;
    setModeloLeve(valor);
    try {
      await invoke("rotrix_ia_salvar", { ajustes: JSON.stringify({ modelo_leve: valor }) });
    } catch (e) {
      setModeloLeve(antes);
      setAvisoIa(`não gravei a IA do botão leve: ${String(e)}`);
    }
  };
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
    guardar(GUARDADO_BASE, ia.modelo);
  };

  // o seletor do Comparativo mexe só no Comparativo (antes mexia no forte do Laudo
  // e a tela do Comparativo voltava sozinha para o "mais forte" calculado)
  const idComparativo = escolherComparativo(listaModelos, modeloComparativo, ia.modelo) || forte;
  const trocarModeloComparativo = (id: string) => {
    setModeloComparativo(id);
    guardar(GUARDADO_COMPARATIVO, id);
  };

  const abrirNoLaudo = (texto: string, de?: string) => {
    setParaFolha((p) => ({ texto, n: p.n + 1, de }));
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
            modeloLeve={nomeLeve}
            idModeloLeve={idLeve}
            aoTrocarModeloLeve={(id) => void trocarModeloLeve(id)}
            regrasIa={regras}
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
            {/* comparativo: sem escolha, o mais forte do provedor do config; com
                escolha no seletor DELE, a escolha manda (separada da barra do Laudo) */}
            <ComparativoPage
              modelos={listaModelos}
              idModelo={idComparativo}
              aoTrocarModelo={trocarModeloComparativo}
            />
          </div>
        </div>
        {aba === "fila" && <FilaPage />}
        {aba === "prescricoes" && <PrescricoesPage />}
        {aba === "estruturados" && <EstruturadosPage />}
        {aba === "mascaras" && (
          <MascarasPage
            aoAbrirConfig={abrirConfig}
            aoAbrirNoLaudo={(texto, nome) => abrirNoLaudo(texto, `máscara ${nome}`)}
          />
        )}
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
