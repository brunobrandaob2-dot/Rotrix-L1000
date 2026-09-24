/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Laudo.
//
// A folha é o centro: o laudo é montado aqui e sai daqui. Três botões de
// ditado (microfone cru, modelo leve, modelo completo), barra de edição no
// formato da do LeoRad e, no rodapé, o destino da colagem.
//
// Cada botão de ditado funciona como o atalho: clique curto liga e o clique
// seguinte desliga; segurar grava enquanto estiver segurado. Menos cliques.
//
// O texto nunca sai do computador por conta própria: o ditado vai para o
// roteador local e a IA só roda quando você aperta o botão dela.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  Mic,
  Sparkles,
  Trash2,
  RotateCw,
  History,
  Paperclip,
  Info,
  Undo2,
  Redo2,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  List,
  ListOrdered,
  Table,
  Brush,
  Copy,
  CornerDownLeft,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Dica } from "./Dica";
import { textoEmHtml, htmlEmTexto, htmlEmMarcado, htmlDaFolha } from "./formatar";
import { BotoesDaFolha } from "./BotoesDaFolha";
import { ImagemNaFolha } from "./ImagemNaFolha";

type Modo = "simples" | "leve" | "completo";

interface Props {
  /** nome do modelo de cada botão, vindo das configurações */
  modeloLeve?: string;
  /** identificador do modelo leve, e como trocá-lo (fica guardado) */
  idModeloLeve?: string;
  aoTrocarModeloLeve?: (id: string) => void;
  modeloCompleto?: string;
  /** identificador do modelo completo para a chamada da IA */
  idModeloCompleto?: string;
  /** texto vindo de outra aba (Histórico → "Abrir no Laudo"); `n` muda a cada envio */
  textoEntrando?: { texto: string; n: number };
  /** modelos que o botão forte pode usar */
  modelos?: { id: string; nome: string }[];
  /** troca o modelo do botão forte (fica guardado para as próximas vezes) */
  aoTrocarModelo?: (id: string) => void;
}

// Qual atalho cada botão dispara. O "completo" grava igual ao "leve" e, quando
// o texto volta, passa pela IA grande.
const BINDING: Record<Modo, string> = {
  simples: "transcribe",
  leve: "transcribe_with_post_process",
  completo: "transcribe_with_post_process",
};

const SEGURAR_MS = 300; // igual ao hold_threshold_ms do Handy

const Fer: React.FC<{
  titulo: string;
  atalho?: string;
  ativo?: boolean;
  tom?: "normal" | "vermelho" | "ciano" | "azul";
  onClick?: () => void;
  onPointerDown?: () => void;
  onPointerUp?: () => void;
  children: React.ReactNode;
}> = ({ titulo, atalho, ativo, tom = "normal", children, ...ev }) => {
  const cor =
    tom === "vermelho"
      ? "bg-red-500 border-red-500 text-white hover:bg-red-600"
      : tom === "ciano"
        ? "bg-logo-primary border-logo-primary text-white hover:opacity-90"
        : tom === "azul"
          ? "bg-background-ui border-background-ui text-white hover:opacity-90"
          : ativo
            ? "bg-logo-primary/25 border-logo-primary/40"
            : "bg-background border-mid-gray/25 hover:bg-mid-gray/10";
  return (
    <Dica texto={titulo} atalho={atalho}>
      <button
        type="button"
        aria-label={titulo}
        className={`h-8 w-8 shrink-0 rounded-lg border flex items-center justify-center transition-colors cursor-pointer ${cor}`}
        {...ev}
      >
        {children}
      </button>
    </Dica>
  );
};

const Sep = () => <span className="h-5 w-px bg-mid-gray/25 mx-1 shrink-0" />;

export const LaudoPage: React.FC<Props> = ({
  modeloLeve = "IA rápida",
  idModeloLeve = "",
  aoTrocarModeloLeve,
  modeloCompleto = "IA completa",
  idModeloCompleto = "",
  textoEntrando,
  modelos = [],
  aoTrocarModelo,
}) => {
  const folha = useRef<HTMLDivElement>(null);
  const [gravando, setGravando] = useState<Modo | null>(null);
  const [ocupado, setOcupado] = useState<"" | "ia" | "colar">("");
  const [aviso, setAviso] = useState("");
  const [marcas, setMarcas] = useState(true);
  const [ultimoIA, setUltimoIA] = useState<string>("");
  const apertadoEm = useRef(0);
  const soltouCedo = useRef(false);
  const esperandoIA = useRef(false); // o ditado atual termina na IA grande?

  const textoDaFolha = useCallback(() => htmlEmTexto(folha.current), []);

  // ---------- IA sobre o texto que está na folha ----------
  const rodarIA = useCallback(
    async (instrucao = "") => {
      const texto = textoDaFolha();
      if (!texto) {
        setAviso("a folha está vazia");
        return;
      }
      setOcupado("ia");
      setAviso("");
      try {
        const bruto = await invoke<string>("rotrix_ia_texto", {
          texto,
          instrucao,
          modelo: idModeloCompleto,
        });
        const r = JSON.parse(bruto || "{}");
        if (r.ok && r.texto) {
          setUltimoIA(texto);
          if (folha.current) folha.current.innerHTML = textoEmHtml(r.texto);
        } else {
          setAviso(motivoEmPortugues(r.motivo));
        }
      } catch (e) {
        setAviso(motivoEmPortugues(String(e)));
      } finally {
        setOcupado("");
      }
    },
    [idModeloCompleto, textoDaFolha],
  );

  // ---------- o texto do ditado volta para a folha ----------
  useEffect(() => {
    const p = listen<string>("rotrix-ditado", (ev) => {
      const texto = ev.payload || "";
      setGravando(null);
      if (!texto.trim()) return;
      const el = folha.current;
      if (el) {
        el.focus();
        const sel = window.getSelection();
        const noCursor = Boolean(sel && sel.rangeCount && el.contains(sel.anchorNode));
        // máscara (várias linhas) entra formatada, com os títulos em negrito;
        // frase solta entra como texto, no lugar onde o cursor está
        if (texto.includes("\n")) {
          const html = textoEmHtml(texto);
          if (noCursor) document.execCommand("insertHTML", false, html);
          else el.innerHTML = (el.innerHTML || "") + html;
        } else if (noCursor) {
          document.execCommand("insertText", false, texto);
        } else {
          el.innerHTML = (el.innerHTML || "") + textoEmHtml(texto);
        }
      }
      if (esperandoIA.current) {
        esperandoIA.current = false;
        void rodarIA();
      }
    });
    return () => {
      p.then((fn) => fn());
    };
  }, [rodarIA]);

  // ---------- texto trazido de outra aba (Histórico) ----------
  useEffect(() => {
    if (!textoEntrando || !textoEntrando.texto) return;
    const el = folha.current;
    if (!el) return;
    setUltimoIA(el.innerText || "");
    el.innerHTML = textoEmHtml(textoEntrando.texto);
    el.focus();
    setAviso("texto trazido do histórico");
  }, [textoEntrando]);

  // ---------- ditado: clique curto liga/desliga, segurar grava ----------
  const acao = async (modo: Modo, comeco: boolean) => {
    try {
      await invoke("rotrix_acao", {
        binding: BINDING[modo],
        comeco,
        paraFolha: true,
      });
      setGravando(comeco ? modo : null);
      if (comeco) setAviso("");
    } catch (e) {
      setGravando(null);
      setAviso(String(e));
    }
  };

  const apertou = (modo: Modo) => {
    if (gravando === modo) {
      // já estava ligado por clique curto: este clique desliga
      soltouCedo.current = false;
      void acao(modo, false);
      return;
    }
    apertadoEm.current = Date.now();
    soltouCedo.current = true;
    esperandoIA.current = modo === "completo";
    void acao(modo, true);
  };

  const soltou = (modo: Modo) => {
    if (!soltouCedo.current) return;
    soltouCedo.current = false;
    if (Date.now() - apertadoEm.current < SEGURAR_MS) return; // fica gravando
    void acao(modo, false);
  };

  const desfazerIA = () => {
    if (!ultimoIA || !folha.current) return;
    // o guardado pode ser HTML (apagar, histórico) ou texto (antes da IA)
    if (/<[a-z][\s\S]*>/i.test(ultimoIA)) folha.current.innerHTML = ultimoIA;
    else folha.current.innerHTML = textoEmHtml(ultimoIA);
    setUltimoIA("");
    setAviso("voltou ao texto anterior");
  };

  // ---------- saída ----------
  // Copiar com formatação: vai HTML (para quem aceita texto rico) e texto puro
  // junto, para o campo simples receber o laudo limpo.
  const copiar = async () => {
    const texto = textoDaFolha();
    if (!texto) return;
    const html = htmlDaFolha(folha.current);
    try {
      const Item = (window as unknown as { ClipboardItem?: typeof ClipboardItem })
        .ClipboardItem;
      if (Item && navigator.clipboard.write) {
        await navigator.clipboard.write([
          new Item({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([texto], { type: "text/plain" }),
          }),
        ]);
        setAviso("copiado com a formatação");
        return;
      }
      await navigator.clipboard.writeText(texto);
      setAviso("copiado (sem formatação: o campo não aceita texto rico)");
    } catch {
      setAviso("não consegui copiar");
    }
  };

  const colarNoRis = useCallback(async () => {
    // o colador espera os cabeçalhos marcados com ** e uma linha por parágrafo;
    // é isso que vira negrito e espaçamento no RIS
    const texto = htmlEmMarcado(folha.current);
    if (!texto) {
      setAviso("a folha está vazia");
      return;
    }
    setOcupado("colar");
    try {
      await invoke("rotrix_colar", { texto });
      setAviso("colado na janela de antes");
    } catch (e) {
      setAviso(String(e));
    } finally {
      setOcupado("");
    }
  }, []);

  // Apaga na hora, sem perguntar nada: o laudo fica guardado no botão de
  // voltar (Ctrl+Z também funciona, porque a folha é um campo editável).
  const limpar = () => {
    const el = folha.current;
    if (!el || !textoDaFolha()) return;
    setUltimoIA(el.innerHTML);
    el.innerHTML = "";
    el.focus();
    setAviso("laudo apagado · o botão ⏱ traz de volta");
  };

  const cmd = (nome: string, valor?: string) => {
    folha.current?.focus();
    document.execCommand(nome, false, valor);
  };

  // A folha é um contentEditable: o texto mora no DOM. Guardar aqui é o que
  // faz o laudo sobreviver a fechar o app — e, junto com as abas que ficam
  // montadas (Casca.tsx), a trocar de aba.
  const GUARDADO_FOLHA = "rotrix2.folha";
  useEffect(() => {
    const el = folha.current;
    if (!el || el.innerHTML.trim()) return;
    try {
      const salvo = localStorage.getItem(GUARDADO_FOLHA);
      if (salvo) el.innerHTML = salvo;
    } catch {
      /* navegador sem armazenamento: começa em branco, e tudo bem */
    }
  }, []);
  useEffect(() => {
    const el = folha.current;
    if (!el) return;
    let tarefa: ReturnType<typeof setTimeout> | undefined;
    const guardar = () => {
      clearTimeout(tarefa);
      tarefa = setTimeout(() => {
        try {
          localStorage.setItem(GUARDADO_FOLHA, el.innerHTML);
        } catch {
          /* sem espaço ou sem permissão: o laudo na tela continua intacto */
        }
      }, 800);
    };
    const obs = new MutationObserver(guardar);
    obs.observe(el, { childList: true, subtree: true, characterData: true });
    el.addEventListener("input", guardar);
    return () => {
      clearTimeout(tarefa);
      obs.disconnect();
      el.removeEventListener("input", guardar);
    };
  }, []);

  const [imagemAberta, setImagemAberta] = useState(false);

  const inserirImagem = useCallback((dataUrl: string) => {
    const el = folha.current;
    if (!el) return;
    el.focus();
    const img = `<div><img src="${dataUrl}" style="max-width:100%;height:auto" /></div>`;
    const sel = window.getSelection();
    if (sel && sel.rangeCount && el.contains(sel.anchorNode)) {
      document.execCommand("insertHTML", false, img);
    } else {
      el.innerHTML += img;
    }
    setAviso("imagem recortada e limpa, posta na folha");
  }, []);

  // Põe um texto do banco (máscara de medida, prescrição, idade óssea) no
  // ponto do cursor, sem atropelar o que já está escrito.
  const inserirNaFolha = useCallback((texto: string) => {
    const el = folha.current;
    if (!el) return;
    el.focus();
    const html = textoEmHtml(texto);
    const sel = window.getSelection();
    if (sel && sel.rangeCount && el.contains(sel.anchorNode)) {
      document.execCommand("insertHTML", false, html);
    } else {
      el.innerHTML = el.innerHTML.trim() ? el.innerHTML + "<br>" + html : html;
    }
    setAviso("texto posto na folha · Tab pula de campo em campo");
  }, []);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        void colarNoRis();
      }
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [colarNoRis]);

  const rotulo = (modo: Modo) =>
    gravando === modo ? "gravando · clique para parar" : "";

  return (
    <div className="flex flex-col h-full min-h-0 bg-mid-gray/5">
      {/* ---------- fileira 1: ações ---------- */}
      <div className="flex items-center gap-1.5 px-3 py-2 bg-background border-b border-mid-gray/20 flex-wrap">
        <Fer
          titulo="Ditado simples: texto cru, sem IA. Clique liga e o próximo clique desliga; segurando, grava enquanto segura."
          atalho="Ctrl+Espaço"
          tom={gravando === "simples" ? "vermelho" : "normal"}
          onPointerDown={() => apertou("simples")}
          onPointerUp={() => soltou("simples")}
        >
          <Mic size={15} />
        </Fer>

        <Fer
          titulo={`Ditado com ${modeloLeve}: monta a máscara e arruma a escrita. Clique liga e o próximo clique desliga.`}
          atalho="Ctrl+Alt+Espaço"
          tom={gravando === "leve" ? "vermelho" : "ciano"}
          onPointerDown={() => apertou("leve")}
          onPointerUp={() => soltou("leve")}
        >
          <Sparkles size={15} />
        </Fer>
        {modelos.length > 1 ? (
          <Dica texto="Qual IA o botão leve usa. Escolha guardada para as próximas vezes.">
            <select
              value={idModeloLeve}
              onChange={(e) => aoTrocarModeloLeve?.(e.target.value)}
              className="h-7 me-1 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
            >
              {modelos.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </select>
          </Dica>
        ) : (
          <span className="text-xs text-mid-gray me-1">{modeloLeve}</span>
        )}

        <Fer
          titulo={`Ditado e ${modeloCompleto}: monta o laudo inteiro. Clique liga e o próximo clique desliga.`}
          atalho="Ctrl+Alt+A"
          tom={gravando === "completo" ? "vermelho" : "azul"}
          onPointerDown={() => apertou("completo")}
          onPointerUp={() => soltou("completo")}
        >
          <Sparkles size={15} />
        </Fer>
        {modelos.length > 1 ? (
          <Dica texto="Qual IA o botão forte usa. Vale também para o botão de reprocessar.">
            <select
              value={idModeloCompleto}
              onChange={(e) => aoTrocarModelo?.(e.target.value)}
              className="h-7 me-1 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
            >
              {modelos.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </select>
          </Dica>
        ) : (
          <span className="text-xs text-mid-gray me-1">{modeloCompleto}</span>
        )}

        <Sep />
        <Fer
          titulo="Apaga o laudo da folha na hora. O botão ao lado (⏱) traz de volta."
          tom="vermelho"
          onClick={limpar}
        >
          <Trash2 size={15} />
        </Fer>
        <Fer
          titulo={`Reprocessar o texto da folha com ${modeloCompleto}`}
          onClick={() => void rodarIA()}
        >
          <RotateCw size={15} />
        </Fer>
        <Fer
          titulo="Traz de volta o texto anterior: o de antes da IA, ou o que você acabou de apagar."
          ativo={Boolean(ultimoIA)}
          onClick={desfazerIA}
        >
          <History size={15} />
        </Fer>
        <Fer
          titulo="Anexar imagem: colar o print, escolher arquivo ou arrastar"
          onClick={() => setImagemAberta(true)}
        >
          <Paperclip size={15} />
        </Fer>
        <Fer
          titulo="Marcas do que a IA mudou"
          ativo={marcas}
          onClick={() => setMarcas((v) => !v)}
        >
          <Info size={15} />
        </Fer>

        <div className="ms-auto flex items-center gap-1.5">
          <Button variant="secondary" size="sm" onClick={copiar}>
            <span className="flex items-center gap-1.5">
              <Copy size={14} /> Copiar
            </span>
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void colarNoRis()}
            disabled={ocupado === "colar"}
          >
            <span className="flex items-center gap-1.5">
              <CornerDownLeft size={14} />
              {ocupado === "colar" ? "colando…" : "Colar no RIS"}
            </span>
          </Button>
        </div>
      </div>

      {/* ---------- fileira 2: formatação ---------- */}
      <div className="flex items-center gap-1 px-3 py-1.5 bg-background border-b border-mid-gray/20 flex-wrap">
        <Fer titulo="Desfazer (Ctrl+Z)" onClick={() => cmd("undo")}>
          <Undo2 size={14} />
        </Fer>
        <Fer titulo="Refazer (Ctrl+Y)" onClick={() => cmd("redo")}>
          <Redo2 size={14} />
        </Fer>
        <Sep />
        <select
          className="h-7 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
          defaultValue="Arial"
          title="Fonte"
          onChange={(e) => cmd("fontName", e.target.value)}
        >
          <option>Arial</option>
          <option>Calibri</option>
          <option>Georgia</option>
          <option>Times New Roman</option>
        </select>
        <select
          className="h-7 rounded-lg border border-mid-gray/25 bg-background text-xs px-1 cursor-pointer"
          defaultValue="3"
          title="Tamanho"
          onChange={(e) => cmd("fontSize", e.target.value)}
        >
          <option value="2">9 pt</option>
          <option value="3">11 pt</option>
          <option value="4">13 pt</option>
          <option value="5">16 pt</option>
        </select>
        <Fer titulo="Limpar formatação" onClick={() => cmd("removeFormat")}>
          <span className="text-[11px] font-semibold">Tx</span>
        </Fer>
        <Sep />
        <Fer titulo="Negrito" onClick={() => cmd("bold")}>
          <Bold size={14} />
        </Fer>
        <Fer titulo="Itálico" onClick={() => cmd("italic")}>
          <Italic size={14} />
        </Fer>
        <Fer titulo="Sublinhado" onClick={() => cmd("underline")}>
          <Underline size={14} />
        </Fer>
        <Sep />
        <Fer titulo="Alinhar à esquerda" onClick={() => cmd("justifyLeft")}>
          <AlignLeft size={14} />
        </Fer>
        <Fer
          titulo="Lista com marcador"
          onClick={() => cmd("insertUnorderedList")}
        >
          <List size={14} />
        </Fer>
        <Fer titulo="Lista numerada" onClick={() => cmd("insertOrderedList")}>
          <ListOrdered size={14} />
        </Fer>
        <Fer
          titulo="Tabela (próxima etapa)"
          onClick={() => setAviso("tabela entra na próxima etapa")}
        >
          <Table size={14} />
        </Fer>
        <Fer titulo="Copiar formato" onClick={() => cmd("removeFormat")}>
          <Brush size={14} />
        </Fer>
        <BotoesDaFolha aoInserir={inserirNaFolha} aoAvisar={setAviso} />
        {(ocupado === "ia" || gravando) && (
          <span className="text-xs text-mid-gray ms-2">
            {gravando ? rotulo(gravando) : "a IA está lendo o laudo…"}
          </span>
        )}
      </div>

      {/* ---------- a folha ---------- */}
      {/* a folha ocupa a janela inteira: sem moldura escura em volta dela */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden bg-white">
        <div
          ref={folha}
          contentEditable
          suppressContentEditableWarning
          spellCheck
          data-rotrix="folha"
          style={{
            overflowWrap: "anywhere",
            // a folha cresce com o texto e marca onde termina cada página,
            // como no Word: a linha tracejada aparece a cada 720 px de texto
            backgroundImage:
              "repeating-linear-gradient(to bottom, transparent 0 716px, rgba(0,0,0,.10) 716px 717px, transparent 717px 720px)",
          }}
          className="w-full min-h-full h-auto bg-white text-black px-10 py-8 text-[12px] leading-[1.6] outline-none select-text cursor-text break-words [&_*]:max-w-full"
        />
      </div>

      <ImagemNaFolha
        aberto={imagemAberta}
        aoFechar={() => setImagemAberta(false)}
        aoConfirmar={inserirImagem}
      />

      {/* ---------- rodapé ---------- */}
      <div className="flex items-center gap-2 px-3 py-2 bg-background border-t border-mid-gray/20">
        <span className="text-[11px] rounded-lg border border-amber-300/50 bg-amber-100/40 text-amber-800 px-2 py-1">
          colar na janela que estava na frente
        </span>
        <Button variant="secondary" size="sm" onClick={() => void colarNoRis()}>
          Colar lá · Ctrl+Enter
        </Button>
        <span className="ms-auto text-[11px] text-mid-gray">
          {aviso ||
            "clique curto liga e desliga · segurar grava enquanto segura"}
        </span>
      </div>
    </div>
  );
};

function motivoEmPortugues(motivo?: string): string {
  const m = (motivo || "").toLowerCase();
  if (m.includes("texto_vazio")) return "a folha está vazia";
  if (m.includes("nuvem_desligada"))
    return "a IA está desligada nas configurações";
  if (m.includes("nuvem_ausente") || m.includes("sem_chave"))
    return "falta a chave da IA nas configurações";
  if (m.includes("roteador parado")) return "o roteador está parado";
  return motivo ? `a IA não respondeu (${motivo})` : "a IA não respondeu";
}

export default LaudoPage;
