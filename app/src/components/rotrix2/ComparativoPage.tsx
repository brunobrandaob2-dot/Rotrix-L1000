/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — Comparativo (sub-aba de Adendos).
//
// Exame anterior à esquerda, TRAVADO. Exame atual à direita, editável — o
// ditado cai só aqui.
//
// A regra que define esta tela: a IA nunca traz um achado do anterior para o
// laudo de agora. Você não olhou as imagens de hoje procurando aquilo;
// enquanto não olhar, é PENDÊNCIA, não descrição. Ausência de menção não é
// ausência de achado, e é exatamente aí que laudo comparativo erra.
import React, { useCallback, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Lock, Sparkles, Mic, ListChecks, CornerDownLeft, Copy, Trash2 } from "lucide-react";
import { Button } from "../ui/Button";
import { useDitado } from "./useDitado";
import { htmlDeTexto, semMarcas, copiarRico } from "./formatar";

interface Linha {
  achado: string;
  anterior: string;
  atual: string;
  situacao: "aumentou" | "estavel" | "diminuiu" | "resolvido" | "novo" | "pendente";
  frase: string;
}

const CORES: Record<Linha["situacao"], string> = {
  aumentou: "border-amber-400/45 bg-amber-100/10 text-amber-300",
  diminuiu: "border-emerald-400/40 bg-emerald-100/10 text-emerald-300",
  estavel: "border-mid-gray/30 text-mid-gray",
  resolvido: "border-emerald-400/40 bg-emerald-100/10 text-emerald-300",
  novo: "border-logo-primary/50 bg-logo-primary/15 text-logo-primary",
  pendente: "border-amber-500/60 bg-amber-200/12 text-amber-200",
};

const NOMES: Record<Linha["situacao"], string> = {
  aumentou: "aumentou",
  diminuiu: "diminuiu",
  estavel: "estável",
  resolvido: "resolvido",
  novo: "novo",
  pendente: "pendente — você precisa olhar",
};

const motivo = (m?: string): string => {
  if (!m) return "não deu certo";
  if (m === "anterior_vazio") return "cole o exame anterior";
  if (m === "atual_vazio") return "escreva ou dite o exame atual";
  if (m === "mudancas_vazias") return "diga o que está diferente hoje";
  if (m === "tem_identificador") return "tem identificador de paciente — veja abaixo";
  if (m === "nuvem_desligada") return "a IA está desligada nas configurações";
  if (m === "resposta_fora_do_formato") return "a IA respondeu fora do formato; tente de novo";
  return m;
};

interface Props {
  modelos?: { id: string; nome: string }[];
  idModelo?: string;
  aoTrocarModelo?: (id: string) => void;
}

export const ComparativoPage: React.FC<Props> = ({
  modelos = [],
  idModelo = "",
  aoTrocarModelo,
}) => {
  const [anterior, setAnterior] = useState("");
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [resumo, setResumo] = useState("");
  const [erro, setErro] = useState("");
  const [achados, setAchados] = useState<string[]>([]);
  const [ocupado, setOcupado] = useState("");
  const [aviso, setAviso] = useState("");
  // "só o que mudou" esconde as linhas estáveis. As PENDÊNCIAS nunca somem:
  // são justamente o que ele ainda não olhou nas imagens de hoje.
  const [soMudou, setSoMudou] = useState(true);
  // o que ele viu de diferente hoje, com as palavras dele
  const [mudancas, setMudancas] = useState("");
  const [revisao, setRevisao] = useState<{
    linhas: string[];
    mantidas: number[];
    mudadas: number[];
  } | null>(null);
  const atual = useRef<HTMLTextAreaElement>(null);

  const [ondeDitar, setOndeDitar] = useState<"mudancas" | "atual">("mudancas");
  const { gravando, apertou, soltou } = useDitado("transcribe", (texto) => {
    if (ondeDitar === "mudancas") {
      setMudancas((x) => (x ? x.replace(/\s*$/, " ") : "") + texto);
      return;
    }
    const el = atual.current;
    if (!el) return;
    el.value = (el.value ? el.value.replace(/\s*$/, "\n") : "") + texto;
    el.focus();
  });

  const textoAtual = () => atual.current?.value ?? "";

  const trazerEstrutura = useCallback(async () => {
    if (!anterior.trim()) {
      setErro("cole o exame anterior primeiro");
      return;
    }
    setErro("");
    try {
      const b = await invoke<string>("rotrix_estrutura", { texto: anterior });
      const d = JSON.parse(b || "{}") as { estrutura?: string; quantos?: number };
      const el = atual.current;
      if (el) {
        el.value = d.estrutura || "";
        el.focus();
      }
      setAviso(`${d.quantos || 0} cabeçalhos · só o esqueleto, sem nenhum achado`);
    } catch (e) {
      setErro(String(e));
    }
  }, [anterior]);

  // Só o anterior colado: a IA diz O QUE PROCURAR hoje. Nenhuma frase de laudo
  // sai daqui — ela não viu as imagens de agora.
  const oQueProcurar = useCallback(async () => {
    if (!anterior.trim()) {
      setErro("cole o exame anterior primeiro");
      return;
    }
    setErro("");
    setAchados([]);
    setOcupado("checklist");
    try {
      const b = await invoke<string>("rotrix_checklist", {
        anterior,
        modelo: idModelo || "",
      });
      const d = JSON.parse(b || "{}") as {
        ok?: boolean;
        achados?: Linha[];
        motivo?: string;
        pendentes?: number;
      };
      if (!d.ok) {
        setErro(motivo(d.motivo));
        setAchados(((d as { achados?: string[] }).achados as string[]) || []);
        return;
      }
      setLinhas(d.achados || []);
      setResumo("");
      setSoMudou(false);
      setAviso(
        `${d.pendentes || 0} achado(s) para conferir nas imagens de hoje — nada foi escrito no atual`,
      );
    } catch (e) {
      setErro(String(e));
    } finally {
      setOcupado("");
    }
  }, [anterior, idModelo]);

  // O caminho que ele quer: cola o anterior, DIZ o que está diferente, e o
  // laudo de hoje aparece inteiro na direita. O que ele não mencionou vem do
  // anterior palavra por palavra — e o programa conta quantas linhas são
  // essas, porque são as que entram no laudo de hoje sem ninguém ter olhado a
  // imagem de hoje por causa delas.
  const gerarAtual = useCallback(async () => {
    if (!anterior.trim()) {
      setErro("cole o exame anterior primeiro");
      return;
    }
    if (!mudancas.trim()) {
      setErro("diga o que está diferente hoje");
      return;
    }
    setErro("");
    setAchados([]);
    setOcupado("gerar");
    try {
      const b = await invoke<string>("rotrix_atualizar_anterior", {
        anterior,
        mudancas,
        modelo: idModelo || "",
      });
      const d = JSON.parse(b || "{}") as {
        ok?: boolean;
        texto?: string;
        linhas?: string[];
        mantidas?: number[];
        mudadas?: number[];
        n_mantidas?: number;
        motivo?: string;
      };
      if (!d.ok) {
        setErro(motivo(d.motivo));
        setAchados(((d as { achados?: string[] }).achados as string[]) || []);
        return;
      }
      const el = atual.current;
      if (el) {
        el.value = d.texto || "";
        el.focus();
      }
      setRevisao({
        linhas: d.linhas || [],
        mantidas: d.mantidas || [],
        mudadas: d.mudadas || [],
      });
      setLinhas(null);
      setAviso(
        `${d.n_mantidas || 0} linha(s) vieram do anterior sem mudança — confira antes de assinar`,
      );
    } catch (e) {
      setErro(String(e));
    } finally {
      setOcupado("");
    }
  }, [anterior, mudancas, idModelo]);

  const comparar = useCallback(async () => {
    setErro("");
    setAchados([]);
    setOcupado("comparar");
    try {
      const b = await invoke<string>("rotrix_comparativo", {
        anterior,
        atual: textoAtual(),
        modelo: idModelo || "",
      });
      const d = JSON.parse(b || "{}") as {
        ok?: boolean;
        achados?: Linha[];
        resumo?: string;
        motivo?: string;
        pendentes?: number;
      };
      if (!d.ok) {
        setErro(motivo(d.motivo));
        setAchados(((d as { achados?: string[] }).achados as string[]) || []);
        return;
      }
      setLinhas(d.achados || []);
      setResumo(d.resumo || "");
      setAviso(
        d.pendentes
          ? `${d.pendentes} achado(s) do anterior que o atual não menciona — responda olhando as imagens`
          : "nenhuma pendência",
      );
    } catch (e) {
      setErro(String(e));
    } finally {
      setOcupado("");
    }
  }, [anterior, idModelo]);

  const porNaDireita = (frase: string) => {
    const el = atual.current;
    if (!el || !frase) return;
    el.value = el.value.replace(/\s*$/, "\n") + frase;
    el.focus();
    setAviso("frase acrescentada no atual");
  };

  const copiar = async () => {
    const t = textoAtual();
    if (!t) return;
    try {
      const rico = await copiarRico(htmlDeTexto(t), semMarcas(t));
      setAviso(
        rico
          ? "laudo atual copiado, com a formatação"
          : "laudo atual copiado (sem formatação: o campo não aceita texto rico)",
      );
    } catch {
      setAviso("não consegui copiar");
    }
  };

  const colar = async () => {
    try {
      await invoke("rotrix_colar", { texto: textoAtual() });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    }
  };

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 flex-wrap">
        <Button variant="secondary" size="sm" onClick={() => void trazerEstrutura()}>
          Trazer a estrutura
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void oQueProcurar()}
          disabled={ocupado === "checklist"}
        >
          {ocupado === "checklist" ? "lendo o anterior…" : "O que procurar"}
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => void gerarAtual()}
          disabled={ocupado === "gerar"}
        >
          <span className="flex items-center gap-1.5">
            <Sparkles size={14} />
            {ocupado === "gerar" ? "montando…" : "Gerar o atual"}
          </span>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void comparar()}
          disabled={ocupado === "comparar"}
        >
          {ocupado === "comparar" ? "comparando…" : "Comparar os dois"}
        </Button>
        <button
          type="button"
          onPointerDown={apertou}
          onPointerUp={soltou}
          onPointerLeave={soltou}
          className={`h-7 px-3 rounded-lg border text-[11.5px] cursor-pointer flex items-center gap-1.5 ${
            gravando
              ? "border-red-400/60 bg-red-400/20 font-semibold"
              : "border-mid-gray/30 hover:bg-mid-gray/15"
          }`}
        >
          <Mic size={14} /> {gravando ? "gravando…" : "Ditar no atual"}
        </button>
        <div className="ms-auto flex items-center gap-2">
          <span className="text-[11px] text-mid-gray">{aviso}</span>
          {modelos.length > 1 && (
            <select
              value={idModelo}
              onChange={(e) => aoTrocarModelo?.(e.target.value)}
              title="qual IA faz a comparação"
              className="h-7 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
            >
              {modelos.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {erro && (
        <div className="mx-3 mt-2 text-[11.5px] rounded-lg border border-amber-400/40 bg-amber-100/10 text-amber-300 px-3 py-2">
          {erro}
          {achados.length > 0 && (
            <div className="mt-1 text-[11px]">
              encontrei: {achados.join(", ")} — tire do texto e compare de novo
            </div>
          )}
        </div>
      )}

      <div className="px-3 py-2 border-b border-mid-gray/15 flex items-start gap-2">
        <span className="text-[10px] text-mid-gray w-[92px] pt-1.5 shrink-0">
          o que está diferente hoje
        </span>
        <textarea
          value={mudancas}
          onChange={(e) => setMudancas(e.target.value)}
          onFocus={() => setOndeDitar("mudancas")}
          rows={2}
          placeholder="o nódulo do lobo superior direito agora tem 12 mm · o derrame sumiu · apareceu uma opacidade na base esquerda"
          className="flex-1 resize-none rounded-lg border border-mid-gray/25 bg-background px-2.5 py-1.5 text-[12px]"
        />
      </div>

      <div className="flex-1 min-h-0 flex gap-0">
        {/* anterior — travado */}
        <div className="flex-1 min-w-0 flex flex-col border-e border-mid-gray/20">
          <div className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] text-mid-gray border-b border-mid-gray/15">
            <Lock size={12} /> exame anterior — travado, não se dita nem se edita aqui
          </div>
          <textarea
            value={anterior}
            onChange={(e) => setAnterior(e.target.value)}
            placeholder="cole aqui o laudo do exame anterior"
            className="flex-1 min-h-0 w-full resize-none bg-white text-black px-6 py-5 text-[12px] leading-[1.6] outline-none"
          />
        </div>

        {/* atual — editável */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="px-3 py-1.5 text-[11px] text-mid-gray border-b border-mid-gray/15">
            exame atual — o ditado cai aqui
          </div>
          <textarea
            ref={atual}
            onFocus={() => setOndeDitar("atual")}
            placeholder="dite ou escreva o laudo de agora — ou aperte Gerar o atual"
            className="flex-1 min-h-0 w-full resize-none bg-white text-black px-6 py-5 text-[12px] leading-[1.6] outline-none"
          />
        </div>
      </div>

      {revisao && (
        <div className="max-h-[38%] overflow-y-auto border-t border-mid-gray/20 p-3 space-y-1">
          <div className="text-[11px] text-mid-gray pb-1">
            conferência do que saiu · <b className="text-amber-300">amarelo</b> = veio do exame
            anterior sem mudança
          </div>
          {revisao.linhas.map((l, i) =>
            !l.trim() ? null : (
              <div
                key={i}
                className={`text-[11.5px] px-2 py-1 rounded ${
                  revisao.mantidas.includes(i)
                    ? "bg-amber-200/10 text-amber-200/90"
                    : "text-text"
                }`}
              >
                {l.replace(/\*\*/g, "")}
              </div>
            ),
          )}
        </div>
      )}

      {linhas && (
        <div className="max-h-[38%] overflow-y-auto border-t border-mid-gray/20 p-3 space-y-1.5">
          <div className="flex items-center gap-2 pb-1">
            {resumo && <span className="text-[11.5px] text-mid-gray">{resumo}</span>}
            <button
              type="button"
              onClick={() => setSoMudou((v) => !v)}
              className="ms-auto text-[10.5px] px-2 py-0.5 rounded border border-mid-gray/30 cursor-pointer hover:bg-mid-gray/20"
            >
              {soMudou ? "mostrar tudo" : "só o que mudou"}
            </button>
          </div>
          {linhas.length === 0 && (
            <div className="text-[11.5px] text-mid-gray">
              a IA não achou par entre os dois textos
            </div>
          )}
          {linhas
            .filter((l) => !soMudou || l.situacao !== "estavel")
            .map((l, i) => (
            <div
              key={`${l.achado}-${i}`}
              className={`rounded-lg border px-2.5 py-2 text-[11.5px] ${CORES[l.situacao]}`}
            >
              <div className="flex items-center gap-2">
                <b className="text-text">{l.achado || "—"}</b>
                <span className="text-[10px] uppercase tracking-wide">{NOMES[l.situacao]}</span>
                {l.frase && (
                  <button
                    type="button"
                    onClick={() => porNaDireita(l.frase)}
                    className="ms-auto text-[10.5px] px-2 py-0.5 rounded border border-mid-gray/30 cursor-pointer hover:bg-mid-gray/20 text-text"
                  >
                    pôr no atual
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 mt-1 text-text/85">
                <div>
                  <span className="text-mid-gray text-[10px]">anterior: </span>
                  {l.anterior || "—"}
                </div>
                <div>
                  <span className="text-mid-gray text-[10px]">atual: </span>
                  {l.atual || (l.situacao === "pendente" ? "não mencionado" : "—")}
                </div>
              </div>
              {l.situacao === "pendente" && (
                <div className="mt-1 text-[10.5px]">
                  o atual não fala deste achado. Não menciona ≠ não existe: olhe as imagens e
                  escreva você. A IA não escreve esta frase — ela não viu o exame de hoje.
                </div>
              )}
            </div>
            ))}
          {soMudou && linhas.some((l) => l.situacao === "estavel") && (
            <div className="text-[10.5px] text-mid-gray pt-1">
              {linhas.filter((l) => l.situacao === "estavel").length} achado(s) estável(is)
              escondido(s) — "mostrar tudo" traz de volta
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 px-3 py-2 border-t border-mid-gray/20">
        <Button variant="primary" size="sm" onClick={() => void colar()}>
          <span className="flex items-center gap-1.5">
            <CornerDownLeft size={14} /> Colar no RIS
          </span>
        </Button>
        <Button variant="secondary" size="sm" onClick={() => void copiar()}>
          <span className="flex items-center gap-1.5">
            <Copy size={14} /> Copiar
          </span>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setLinhas(null);
            setRevisao(null);
            setResumo("");
            setAviso("");
          }}
        >
          <span className="flex items-center gap-1.5">
            <ListChecks size={14} /> Limpar a tabela
          </span>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setAnterior("");
            setMudancas("");
            if (atual.current) atual.current.value = "";
            setLinhas(null);
            setRevisao(null);
            setErro("");
            setAviso("");
          }}
        >
          <span className="flex items-center gap-1.5">
            <Trash2 size={14} /> Recomeçar
          </span>
        </Button>
      </div>
    </div>
  );
};

export default ComparativoPage;
