/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Adendos.
//
// O laudo já foi assinado e alguém pediu revisão, ou você viu um achado que
// não estava lá. Cola o laudo, diz o que quer, e sai o texto do adendo —
// carimbado com a data e a hora de agora, no seu tom.
//
// O laudo colado passa pela mesma triagem do resto: se tiver identificador de
// paciente, nada é enviado e a tela diz o que tirar.
import React, { useCallback, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Mic, Sparkles, Copy, CornerDownLeft, Trash2, FileDown } from "lucide-react";
import { Button } from "../ui/Button";
import { Dica } from "./Dica";
import { useDitado } from "./useDitado";
import { TextoDeLaudo } from "./TextoDeLaudo";
import { htmlDeTexto, semMarcas, copiarRico } from "./formatar";

type Tipo = "achado_adicional" | "resposta_pedido" | "retificacao" | "complemento" | "livre";

const TIPOS: { id: Tipo; nome: string; dica: string; exemplo: string }[] = [
  {
    id: "achado_adicional",
    nome: "Achado adicional",
    dica: "Vi algo que não estava descrito e quero registrar.",
    exemplo:
      "revi as imagens e há um nódulo sólido de 6 mm no lobo inferior esquerdo, " +
      "que não constava no laudo anterior",
  },
  {
    id: "resposta_pedido",
    nome: "Resposta a pedido de revisão",
    dica: "Pediram revisão e eu mantenho o laudo.",
    exemplo:
      "o solicitante pede que eu descreva fratura no escafoide; revi as imagens e " +
      "mantenho o laudo: não há traço de fratura nas incidências disponíveis",
  },
  {
    id: "retificacao",
    nome: "Retificação",
    dica: "Erro material: lado, medida, termo.",
    exemplo: "onde está joelho direito, leia-se joelho esquerdo",
  },
  {
    id: "complemento",
    nome: "Complemento",
    dica: "Comparação, medida ou seguimento.",
    exemplo:
      "acrescenta a comparação com a TC de 12/03/2026: o nódulo mantém o mesmo tamanho",
  },
  { id: "livre", nome: "Livre", dica: "Escrevo o pedido do meu jeito.", exemplo: "" },
];

const motivoEmPortugues = (m?: string): string => {
  if (!m) return "não deu certo";
  if (m === "laudo_vazio") return "cole o laudo primeiro";
  if (m === "pedido_vazio") return "diga o que você quer no adendo";
  if (m === "nuvem_desligada") return "a IA está desligada nas configurações";
  if (m === "nuvem_sem_chave") return "falta a chave da IA nas configurações";
  if (m === "nuvem_ausente") return "o roteador está sem o módulo da IA";
  if (m === "nuvem_bloqueada") return "a IA recusou o envio (veja o aviso acima)";
  if (m.startsWith("limite")) return "o limite de gasto do mês foi atingido";
  return m;
};

interface Resposta {
  ok?: boolean;
  texto?: string;
  quando?: string;
  modelo?: string;
  motivo?: string;
  achados?: string[];
}

export const AdendoPage: React.FC<{
  modelos?: { id: string; nome: string }[];
  idModelo?: string;
  aoTrocarModelo?: (id: string) => void;
}> = ({ modelos = [], idModelo = "", aoTrocarModelo }) => {
  const [laudo, setLaudo] = useState("");
  const [pedido, setPedido] = useState("");
  const [tipo, setTipo] = useState<Tipo>("achado_adicional");
  const [saida, setSaida] = useState<Resposta | null>(null);
  const [ocupado, setOcupado] = useState<"" | "ia" | "colar">("");
  const [aviso, setAviso] = useState("");
  const caixaPedido = useRef<HTMLTextAreaElement>(null);

  const ditado = useDitado("transcribe", (t) => {
    if (!t) return;
    setPedido((p) => (p ? p + " " + t : t));
    caixaPedido.current?.focus();
  });

  const gerar = useCallback(async () => {
    if (!laudo.trim()) {
      setAviso("cole o laudo primeiro");
      return;
    }
    if (!pedido.trim()) {
      setAviso("diga o que você quer no adendo");
      return;
    }
    setOcupado("ia");
    setAviso("");
    setSaida(null);
    try {
      const bruto = await invoke<string>("rotrix_adendo", {
        laudo,
        pedido,
        tipo,
        modelo: idModelo,
      });
      const r = JSON.parse(bruto || "{}") as Resposta;
      setSaida(r);
      if (!r.ok) {
        setAviso(
          r.motivo === "tem_identificador"
            ? `o laudo tem ${(r.achados || []).join(", ")} — tire isso antes: nada com identificador de paciente sai do computador`
            : motivoEmPortugues(r.motivo),
        );
      }
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupado("");
    }
  }, [laudo, pedido, tipo, idModelo]);

  const copiar = async () => {
    if (!saida?.texto) return;
    try {
      const rico = await copiarRico(htmlDeTexto(saida.texto), semMarcas(saida.texto));
      setAviso(
        rico
          ? "adendo copiado, com a formatação"
          : "adendo copiado (sem formatação: o campo não aceita texto rico)",
      );
    } catch {
      setAviso("não consegui copiar");
    }
  };

  const colarNoRis = async () => {
    if (!saida?.texto) return;
    setOcupado("colar");
    try {
      await invoke("rotrix_colar", { texto: saida.texto });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupado("");
    }
  };

  const juntarAoLaudo = () => {
    if (!saida?.texto) return;
    setLaudo((l) => `${l.trim()}\n\n${saida.texto}`);
    setAviso("adendo juntado ao laudo aqui do lado");
  };

  const oTipo = TIPOS.find((t) => t.id === tipo) || TIPOS[0];

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* barra */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <h2 className="text-base font-semibold">Adendos</h2>
        <span className="text-[11px] text-mid-gray">
          laudo já assinado + o que você quer = o texto do adendo, carimbado com
          a hora de agora
        </span>
        <div className="ms-auto flex items-center gap-1.5">
          {modelos.length > 1 && (
            <Dica texto="Qual IA escreve o adendo. Para pedido de revisão, prefira o modelo mais forte.">
              <select
                value={idModelo}
                onChange={(e) => aoTrocarModelo?.(e.target.value)}
                className="h-7 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
              >
                {modelos.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome}
                  </option>
                ))}
              </select>
            </Dica>
          )}
          <Button
            variant="primary"
            size="sm"
            disabled={ocupado === "ia"}
            onClick={() => void gerar()}
          >
            <span className="flex items-center gap-1.5">
              <Sparkles size={14} />
              {ocupado === "ia" ? "escrevendo…" : "Escrever o adendo"}
            </span>
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden flex gap-3 p-3">
        {/* esquerda: laudo + pedido */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          <div className="rounded-lg border border-mid-gray/20 bg-background flex-1 min-h-0 flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold">Laudo já assinado</span>
              <span className="text-[10px] text-mid-gray">
                {laudo.trim() ? `${laudo.trim().length} caracteres` : "cole aqui"}
              </span>
              {laudo && (
                <button
                  type="button"
                  className="ms-auto text-mid-gray hover:text-text cursor-pointer"
                  title="limpar"
                  onClick={() => setLaudo("")}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
            <textarea
              value={laudo}
              onChange={(e) => setLaudo(e.target.value)}
              placeholder="cole aqui o laudo inteiro, sem o cabeçalho com o nome do paciente"
              className="flex-1 min-h-40 w-full resize-none bg-white text-black px-4 py-3 text-[12px] leading-relaxed outline-none rounded-b-lg"
            />
          </div>

          <div className="rounded-lg border border-mid-gray/20 bg-background">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold">O que você quer</span>
              <Button
                variant={ditado.gravando ? "danger" : "primary-soft"}
                size="sm"
                className="ms-auto"
                onPointerDown={ditado.apertou}
                onPointerUp={ditado.soltou}
                onPointerLeave={ditado.soltou}
              >
                <span className="flex items-center gap-1.5">
                  <Mic size={13} />
                  {ditado.gravando ? "gravando — clique para parar" : "Falar"}
                </span>
              </Button>
            </div>
            <div className="p-3 flex flex-col gap-2">
              <div className="flex flex-wrap gap-1.5">
                {TIPOS.map((t) => (
                  <Dica key={t.id} texto={t.dica}>
                    <button
                      type="button"
                      onClick={() => {
                        setTipo(t.id);
                        if (!pedido.trim() && t.exemplo) setPedido(t.exemplo);
                      }}
                      className={`text-[11px] rounded-lg border px-2 py-1 cursor-pointer ${
                        tipo === t.id
                          ? "bg-logo-primary/20 border-logo-primary/40 font-semibold"
                          : "border-mid-gray/25 hover:bg-mid-gray/10"
                      }`}
                    >
                      {t.nome}
                    </button>
                  </Dica>
                ))}
              </div>
              <textarea
                ref={caixaPedido}
                value={pedido}
                onChange={(e) => setPedido(e.target.value)}
                rows={4}
                placeholder={oTipo.exemplo || "escreva ou dite o que o adendo precisa dizer"}
                className="w-full resize-y rounded-lg border border-mid-gray/25 bg-background px-2.5 py-2 text-[12.5px] leading-relaxed outline-none focus:border-logo-primary/50"
              />
              <p className="text-[11px] text-mid-gray">
                a IA não inventa achado: ela escreve com o que está no laudo e no
                seu pedido. Se faltar informação, ela diz o que falta.
              </p>
            </div>
          </div>
        </div>

        {/* direita: o adendo */}
        <div className="w-[420px] shrink-0 flex flex-col gap-3">
          <div className="rounded-lg border border-mid-gray/20 bg-background flex-1 min-h-0 flex flex-col">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20 bg-mid-gray/5">
              <span className="text-xs font-semibold">O adendo</span>
              {saida?.quando && (
                <span className="text-[10px] text-mid-gray">
                  {saida.quando} · {saida.modelo}
                </span>
              )}
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-3">
              {saida?.ok && saida.texto ? (
                <TextoDeLaudo
                  texto={saida.texto}
                  className="text-[12px] leading-relaxed rounded-lg border border-mid-gray/20 bg-white text-black p-4"
                />
              ) : (
                <p className="text-xs text-mid-gray">
                  o texto do adendo aparece aqui, começando pelo carimbo com a
                  data e a hora.
                </p>
              )}
            </div>
            {saida?.ok && saida.texto && (
              <div className="flex flex-wrap gap-1.5 p-3 border-t border-mid-gray/20">
                <Button
                  variant="primary"
                  size="sm"
                  disabled={ocupado === "colar"}
                  onClick={() => void colarNoRis()}
                >
                  <span className="flex items-center gap-1.5">
                    <CornerDownLeft size={13} /> Colar no RIS
                  </span>
                </Button>
                <Button variant="secondary" size="sm" onClick={() => void copiar()}>
                  <span className="flex items-center gap-1.5">
                    <Copy size={13} /> Copiar
                  </span>
                </Button>
                <Dica texto="Cola o adendo no fim do laudo aqui do lado, para você conferir o conjunto.">
                  <Button variant="secondary" size="sm" onClick={juntarAoLaudo}>
                    <span className="flex items-center gap-1.5">
                      <FileDown size={13} /> Juntar ao laudo
                    </span>
                  </Button>
                </Dica>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="px-3 py-2 bg-background border-t border-mid-gray/20 text-[11px] text-mid-gray">
        {aviso ||
          "laudo com identificador de paciente não é enviado — o app avisa o que tirar"}
      </div>
    </div>
  );
};

export default AdendoPage;
