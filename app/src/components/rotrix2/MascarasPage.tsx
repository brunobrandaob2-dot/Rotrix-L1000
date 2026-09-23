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
import { Mic, RefreshCw, Sparkles, Search, Check, Undo2 } from "lucide-react";
import { Button } from "../ui/Button";
import { useDitado } from "./useDitado";
import { TextoDeLaudo } from "./TextoDeLaudo";

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

interface Proposta {
  acao: "substituir" | "criar" | "trocar_frase";
  titulo?: string;
  titulos?: string[];
  nome?: string;
  regiao?: string;
  modalidade?: string;
  gatilhos?: string[];
  porque?: string;
  antes: string;
  depois: string;
  de?: string;
  para?: string;
}

interface RespostaIA {
  ok?: boolean;
  propostas?: Proposta[];
  recusadas?: { acao: string; motivo: string }[];
  recado?: string;
  lidas?: number;
  modelo?: string;
  motivo?: string;
  consideradas?: string[];
  aplicadas?: number;
  itens?: { titulo?: string; arquivo?: string }[];
  desfazer?: string;
  erros?: string[];
}

const PEDIDOS = [
  "essa é a máscara certa — troca a que está no banco por esta",
  "cria uma máscara nova com este texto",
  "padroniza o termo que está escrito de formas diferentes",
  "acha contradição entre a análise e a conclusão",
  "enxuga as conclusões longas",
];

const motivoEmPortugues = (m?: string): string => {
  if (!m) return "não deu certo";
  if (m === "nuvem_desligada") return "a IA está desligada nas configurações";
  if (m === "nuvem_sem_chave") return "falta a chave da IA nas configurações";
  if (m === "nuvem_ausente") return "o roteador está sem o módulo da IA";
  if (m === "instrucao_vazia") return "diga ou escreva o pedido primeiro";
  if (m === "nenhuma_mascara") return "não achei máscara parecida — diga a região ou cole a máscara";
  if (m === "resposta_fora_do_formato") return "a IA respondeu fora do formato; tente de novo";
  if (m === "nada_aprovado") return "nenhuma proposta aprovada";
  if (m === "oficina_ausente") return "o roteador está desatualizado (rode o ATUALIZAR_AGORA)";
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
  const [colado, setColado] = useState("");
  const [rodandoIA, setRodandoIA] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [saida, setSaida] = useState<RespostaIA | null>(null);
  const [aprovadas, setAprovadas] = useState<number[]>([]);
  const [ultimaAplicacao, setUltimaAplicacao] = useState("");
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

  const chamar = async (extra: Record<string, string>) => {
    const bruto = await invoke<string>("rotrix_mascaras_ia", {
      instrucao: pedido.trim(),
      busca: busca.trim(),
      texto: colado.trim(),
      aplicar: "",
      desfazer: "",
      ...extra,
    });
    return JSON.parse(bruto || "{}") as RespostaIA;
  };

  const rodar = async () => {
    if (!pedido.trim() && !colado.trim()) {
      setAviso("escreva o pedido ou cole a máscara");
      return;
    }
    setRodandoIA(true);
    setSaida(null);
    setAprovadas([]);
    setAviso("");
    try {
      const r = await chamar({});
      setSaida(r);
      setAprovadas((r.propostas || []).map((_, i) => i)); // tudo marcado por padrão
      if (!r.ok) setAviso(motivoEmPortugues(r.motivo));
      else if (!(r.propostas || []).length)
        setAviso(r.recado || "a IA não propôs mudança nenhuma");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setRodandoIA(false);
    }
  };

  const aplicar = async () => {
    const lista = (saida?.propostas || []).filter((_, i) => aprovadas.includes(i));
    if (!lista.length) {
      setAviso("marque ao menos uma proposta");
      return;
    }
    setAplicando(true);
    setAviso("gravando e refazendo o banco — leva alguns segundos…");
    try {
      const r = await chamar({ aplicar: JSON.stringify(lista) });
      if (r.ok) {
        setUltimaAplicacao(r.desfazer || "");
        setSaida(null);
        setAprovadas([]);
        setColado("");
        setAviso(
          `${r.aplicadas} mudança(s) no banco · já valem no ditado` +
            (r.erros && r.erros.length ? ` · ${r.erros.length} com erro` : ""),
        );
        await ler(busca.trim());
      } else {
        setAviso(motivoEmPortugues(r.motivo) + (r.erros?.length ? ` (${r.erros[0]})` : ""));
      }
    } catch (e) {
      setAviso(String(e));
    } finally {
      setAplicando(false);
    }
  };

  const desfazer = async () => {
    if (!ultimaAplicacao) return;
    setAplicando(true);
    setAviso("desfazendo…");
    try {
      const r = await chamar({ desfazer: ultimaAplicacao });
      setAviso(r.ok ? "desfeito — o banco voltou como estava" : motivoEmPortugues(r.motivo));
      if (r.ok) setUltimaAplicacao("");
      await ler(busca.trim());
    } catch (e) {
      setAviso(String(e));
    } finally {
      setAplicando(false);
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
          {/* oficina: pedido, propostas e aplicação */}
          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold">Mudar o banco pela IA</span>
              <div className="ms-auto flex items-center gap-1.5">
                {ultimaAplicacao && (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={aplicando}
                    onClick={() => void desfazer()}
                  >
                    <span className="flex items-center gap-1.5">
                      <Undo2 size={13} /> Desfazer a última
                    </span>
                  </Button>
                )}
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
                  disabled={rodandoIA || aplicando}
                  onClick={() => void rodar()}
                >
                  <span className="flex items-center gap-1.5">
                    <Sparkles size={14} />
                    {rodandoIA ? "lendo o banco…" : "Ver o que muda"}
                  </span>
                </Button>
              </div>
            </div>
            <div className="p-3 flex flex-col gap-2">
              <textarea
                ref={caixaPedido}
                value={pedido}
                onChange={(e) => setPedido(e.target.value)}
                rows={3}
                placeholder="o que você quer mudar. ex.: essa é a máscara certa de joelho, troca a do banco por esta"
                className="w-full resize-y rounded-lg border border-mid-gray/25 bg-background px-2.5 py-2 text-[12.5px] leading-relaxed outline-none focus:border-logo-primary/50"
              />
              <textarea
                value={colado}
                onChange={(e) => setColado(e.target.value)}
                rows={8}
                placeholder="cole aqui a máscara — do jeito certo, ou com os erros para ele arrumar (opcional)"
                className="w-full resize-y rounded-lg border border-mid-gray/25 bg-background px-2.5 py-2 text-[12px] leading-relaxed font-mono outline-none focus:border-logo-primary/50"
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
                ele acha sozinho a máscara que tem a ver com o pedido — se você colar
                uma, acha a correspondente. A mudança é gravada só depois que você
                aprova, sempre como máscara sua (a do Rotrix fica intacta).
              </p>

              {/* propostas */}
              {saida?.propostas?.length ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold">
                      {saida.propostas.length} proposta(s)
                    </span>
                    <span className="text-[10px] text-mid-gray">
                      {saida.lidas} máscara(s) lida(s) · {saida.modelo}
                    </span>
                    <Button
                      variant="primary"
                      size="sm"
                      className="ms-auto"
                      disabled={aplicando || !aprovadas.length}
                      onClick={() => void aplicar()}
                    >
                      <span className="flex items-center gap-1.5">
                        <Check size={14} />
                        {aplicando
                          ? "gravando…"
                          : `Aplicar no banco (${aprovadas.length})`}
                      </span>
                    </Button>
                  </div>
                  {saida.propostas.map((p, i) => {
                    const marcada = aprovadas.includes(i);
                    return (
                      <div
                        key={i}
                        className={`rounded-lg border p-2 ${
                          marcada
                            ? "border-logo-primary/40 bg-logo-primary/5"
                            : "border-mid-gray/20 opacity-60"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              setAprovadas((a) =>
                                a.includes(i) ? a.filter((x) => x !== i) : [...a, i],
                              )
                            }
                            className={`inline-flex h-4 w-4 items-center justify-center rounded border cursor-pointer ${
                              marcada
                                ? "bg-logo-primary border-logo-primary text-white"
                                : "border-mid-gray/40"
                            }`}
                          >
                            {marcada && <Check size={11} />}
                          </button>
                          <span className="text-[11px] font-semibold">
                            {p.acao === "substituir"
                              ? `trocar: ${p.titulo}`
                              : p.acao === "criar"
                                ? `máscara nova: ${p.nome}`
                                : `trocar frase em ${p.titulos?.length || 0} máscara(s)`}
                          </span>
                          {p.porque && (
                            <span className="text-[10px] text-mid-gray truncate">
                              {p.porque}
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <TextoDeLaudo
                            texto={p.antes || "(não existia)"}
                            className="text-[10.5px] leading-snug rounded border border-mid-gray/20 bg-mid-gray/5 p-2 max-h-40 overflow-y-auto"
                          />
                          <TextoDeLaudo
                            texto={p.depois}
                            className="text-[10.5px] leading-snug rounded border border-emerald-500/30 bg-emerald-500/5 p-2 max-h-40 overflow-y-auto"
                          />
                        </div>
                        {p.acao === "criar" && p.gatilhos?.length ? (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {p.gatilhos.map((g) => (
                              <span
                                key={g}
                                className="text-[9.5px] rounded bg-logo-primary/15 px-1.5 py-0.5"
                              >
                                {g}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ) : null}

              {saida?.recusadas?.length ? (
                <div className="text-[10.5px] text-mid-gray">
                  não deu para aceitar:{" "}
                  {saida.recusadas.map((r) => r.motivo).join(" · ")}
                </div>
              ) : null}
              {saida?.recado && !saida?.propostas?.length ? (
                <div className="text-[11px] rounded-lg border border-mid-gray/20 bg-mid-gray/5 p-2">
                  {saida.recado}
                </div>
              ) : null}
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
                <TextoDeLaudo
                  texto={texto}
                  className="text-[11.5px] leading-relaxed rounded-lg border border-mid-gray/20 bg-white text-black p-3"
                />
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
