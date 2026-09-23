/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Máscaras.
//
// Esquerda: o banco, agrupado por região, com busca. Direita, em cima: a caixa
// onde você fala o que a IA deve fazer no banco inteiro (revisar escrita, achar
// contradição, padronizar termo) e volta uma lista de propostas — nada é
// alterado sem você aprovar. Direita, embaixo: o texto da máscara escolhida.
//
// A IA lê só o texto das máscaras. Laudo de paciente nunca entra aqui.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Mic, RefreshCw, Sparkles, Search } from "lucide-react";
import { Button } from "../ui/Button";
import { useDitado } from "./useDitado";

interface Mascara {
  titulo: string;
  nome: string;
  categoria: string;
  modalidade: string;
  regiao: string;
  subtipo: string;
  gatilhos: string[];
  tamanho: number;
}

interface Banco {
  ok?: boolean;
  total?: number;
  regioes?: Record<string, number>;
  mascaras?: Mascara[];
  cortou?: boolean;
}

interface RespostaIA {
  ok?: boolean;
  resposta?: string;
  lidas?: number;
  modelo?: string;
  motivo?: string;
}

const PEDIDOS = [
  "revisa a escrita de todas as máscaras desta região",
  "acha contradição entre a análise e a conclusão",
  "padroniza o termo que está escrito de formas diferentes",
  "enxuga as conclusões longas",
  "diz qual máscara está faltando nesta região",
];

const motivoEmPortugues = (m?: string): string => {
  if (!m) return "não deu certo";
  if (m === "nuvem_desligada") return "a IA está desligada nas configurações";
  if (m === "nuvem_sem_chave") return "falta a chave da IA nas configurações";
  if (m === "nuvem_ausente") return "o roteador está sem o módulo da IA";
  if (m === "instrucao_vazia") return "diga ou escreva o pedido primeiro";
  if (m === "nenhuma_mascara") return "a busca não achou máscara nenhuma";
  if (m.startsWith("limite")) return "o limite de gasto do mês foi atingido";
  return m;
};

export const MascarasPage: React.FC<{
  aoAbrirConfig?: (secao: string) => void;
}> = ({ aoAbrirConfig }) => {
  const [busca, setBusca] = useState("");
  const [banco, setBanco] = useState<Banco | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [escolhida, setEscolhida] = useState<Mascara | null>(null);
  const [texto, setTexto] = useState("");
  const [pedido, setPedido] = useState("");
  const [rodandoIA, setRodandoIA] = useState(false);
  const [saida, setSaida] = useState<RespostaIA | null>(null);
  const [aviso, setAviso] = useState("");
  const caixaPedido = useRef<HTMLTextAreaElement>(null);

  const ler = useCallback(async (q: string) => {
    setCarregando(true);
    try {
      const bruto = await invoke<string>("rotrix_mascaras_banco", {
        busca: q,
        titulo: "",
      });
      setBanco(JSON.parse(bruto || "{}"));
      setAviso("");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void ler("");
  }, [ler]);

  // busca com folga, para não varrer o banco a cada letra
  useEffect(() => {
    const t = setTimeout(() => void ler(busca.trim()), 260);
    return () => clearTimeout(t);
  }, [busca, ler]);

  const abrir = async (m: Mascara) => {
    setEscolhida(m);
    setTexto("");
    try {
      const bruto = await invoke<string>("rotrix_mascaras_banco", {
        busca: "",
        titulo: m.titulo,
      });
      setTexto((JSON.parse(bruto || "{}") as { texto?: string }).texto || "");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const ditado = useDitado("transcribe", (t) => {
    if (!t) return;
    setPedido((p) => (p ? p + " " + t : t));
    caixaPedido.current?.focus();
  });

  const rodar = async () => {
    const p = pedido.trim();
    if (!p) {
      setAviso("diga ou escreva o pedido primeiro");
      return;
    }
    setRodandoIA(true);
    setSaida(null);
    setAviso("");
    try {
      const bruto = await invoke<string>("rotrix_mascaras_ia", {
        instrucao: p,
        busca: busca.trim(),
      });
      const r = JSON.parse(bruto || "{}") as RespostaIA;
      setSaida(r);
      if (!r.ok) setAviso(motivoEmPortugues(r.motivo));
    } catch (e) {
      setAviso(String(e));
    } finally {
      setRodandoIA(false);
    }
  };

  const grupos = useMemo(() => {
    const g = new Map<string, Mascara[]>();
    for (const m of banco?.mascaras || []) {
      const lista = g.get(m.regiao) || [];
      lista.push(m);
      g.set(m.regiao, lista);
    }
    return [...g.entries()];
  }, [banco]);

  const regioes = Object.keys(banco?.regioes || {}).length;
  const mostradas = banco?.mascaras?.length || 0;

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* barra */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <h2 className="text-base font-semibold">Máscaras</h2>
        <span className="text-[11px] rounded-full border border-logo-primary/30 bg-logo-primary/10 px-2 py-0.5">
          {(banco?.total || 0).toLocaleString("pt-BR")} máscaras · {regioes}{" "}
          regiões
        </span>
        <label className="flex items-center gap-1.5 rounded-lg border border-mid-gray/25 bg-background px-2 py-1">
          <Search size={13} className="text-mid-gray" />
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="buscar região, máscara ou comando"
            className="bg-transparent outline-none text-xs w-56"
          />
        </label>
        <div className="ms-auto flex items-center gap-1.5">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => aoAbrirConfig?.("rotrix")}
          >
            Importar as minhas
          </Button>
          <Button variant="primary" size="sm" onClick={() => void ler(busca.trim())}>
            <span className="flex items-center gap-1.5">
              <RefreshCw size={14} className={carregando ? "animate-spin" : ""} />
              Atualizar
            </span>
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden flex gap-3 p-3">
        {/* lista */}
        <div className="w-64 shrink-0 overflow-y-auto rounded-lg border border-mid-gray/20 bg-background">
          {mostradas === 0 ? (
            <p className="p-3 text-xs text-mid-gray">
              {carregando ? "lendo o banco…" : "nada com esse nome."}
            </p>
          ) : (
            grupos.map(([regiao, lista]) => (
              <div key={regiao}>
                <div className="sticky top-0 px-3 py-1.5 text-[10px] uppercase tracking-wide text-mid-gray bg-mid-gray/10 backdrop-blur">
                  {regiao} · {lista.length}
                </div>
                {lista.map((m) => (
                  <button
                    key={m.titulo}
                    type="button"
                    onClick={() => void abrir(m)}
                    className={`w-full text-start px-3 py-1.5 text-xs border-t border-mid-gray/10 cursor-pointer flex items-center gap-2 ${
                      escolhida?.titulo === m.titulo
                        ? "bg-logo-primary/15 font-medium"
                        : "hover:bg-mid-gray/5"
                    }`}
                  >
                    <span className="truncate flex-1">{m.nome}</span>
                    {m.modalidade && (
                      <span className="text-[9px] font-bold rounded bg-mid-gray/15 px-1 py-0.5 shrink-0">
                        {m.modalidade.toUpperCase()}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ))
          )}
          {banco?.cortou && (
            <p className="px-3 py-2 text-[10px] text-mid-gray border-t border-mid-gray/10">
              mostrando as primeiras {mostradas} — refine a busca
            </p>
          )}
        </div>

        {/* direita */}
        <div className="flex-1 min-w-0 flex flex-col gap-3 overflow-y-auto">
          {/* IA no banco */}
          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold">
                Pedir para a IA trabalhar no banco
              </span>
              <div className="ms-auto flex items-center gap-1.5">
                <Button
                  variant={ditado.gravando ? "danger" : "primary-soft"}
                  size="sm"
                  onPointerDown={ditado.apertou}
                  onPointerUp={ditado.soltou}
                  onPointerLeave={ditado.soltou}
                >
                  <span className="flex items-center gap-1.5">
                    <Mic size={14} />
                    {ditado.gravando ? "gravando — clique para parar" : "Falar o pedido"}
                  </span>
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={rodandoIA}
                  onClick={() => void rodar()}
                >
                  <span className="flex items-center gap-1.5">
                    <Sparkles size={14} />
                    {rodandoIA ? "lendo as máscaras…" : "Rodar"}
                  </span>
                </Button>
              </div>
            </div>
            <div className="p-3 flex flex-col gap-2">
              <textarea
                ref={caixaPedido}
                value={pedido}
                onChange={(e) => setPedido(e.target.value)}
                rows={2}
                placeholder="ex.: revisa a escrita de todas as máscaras de joelho e me mostra onde a frase está diferente do meu padrão"
                className="w-full resize-y rounded-lg border border-mid-gray/25 bg-background px-2 py-1.5 text-xs outline-none focus:border-logo-primary/50"
              />
              <div className="flex flex-wrap gap-1.5">
                {PEDIDOS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPedido(p)}
                    className="text-[10px] rounded-md border border-mid-gray/25 px-1.5 py-0.5 hover:bg-mid-gray/10 cursor-pointer"
                  >
                    {p}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-mid-gray">
                a IA lê as máscaras que estão na lista da esquerda
                {busca.trim() ? ` (filtro “${busca.trim()}”)` : " (sem filtro: as primeiras 25)"}{" "}
                — nada é alterado sem você aprovar.
              </p>
              {saida?.ok && (
                <div className="rounded-lg border border-mid-gray/20 bg-mid-gray/5 p-2">
                  <div className="text-[10px] text-mid-gray mb-1">
                    {saida.lidas} máscara(s) lida(s) · {saida.modelo}
                  </div>
                  <pre className="whitespace-pre-wrap text-[11px] leading-relaxed font-sans">
                    {saida.resposta}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {/* máscara escolhida */}
          <div className="rounded-lg border border-mid-gray/20 bg-background flex-1 min-h-40 flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold truncate">
                {escolhida ? escolhida.nome : "escolha uma máscara na lista"}
              </span>
              {escolhida && (
                <span className="text-[10px] text-mid-gray shrink-0">
                  {escolhida.tamanho} caracteres
                </span>
              )}
            </div>
            <div className="p-3 overflow-y-auto">
              {escolhida && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {escolhida.gatilhos.map((g) => (
                    <span
                      key={g}
                      className="text-[10px] rounded bg-logo-primary/15 px-1.5 py-0.5"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              )}
              {texto ? (
                <pre className="whitespace-pre-wrap text-[11.5px] leading-relaxed font-sans rounded-lg border border-mid-gray/20 bg-white text-black p-3">
                  {texto}
                </pre>
              ) : (
                <p className="text-xs text-mid-gray">
                  o texto da máscara aparece aqui, com os comandos de voz que a
                  chamam.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-2 bg-background border-t border-mid-gray/20">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => aoAbrirConfig?.("rotrix")}
        >
          Corrigir uma frase
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => aoAbrirConfig?.("rotrix")}
        >
          Exportar perfil
        </Button>
        <span className="ms-auto text-[11px] text-mid-gray">
          {aviso || "a IA lê só o texto das máscaras — nunca laudo de paciente"}
        </span>
      </div>
    </div>
  );
};

export default MascarasPage;
