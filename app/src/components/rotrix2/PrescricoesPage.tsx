/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — aba Prescrições.
//
// A árvore por modalidade à esquerda, a prescrição à direita. Dose e volume saem
// EM BRANCO, sempre: prescrição pré-preenchida é prescrição assinada sem olhar.
// As lacunas ficam destacadas e o Tab pula de uma para a outra.
//
// Nada aqui passa por IA e nada sai do computador: é texto do banco, colado.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Search, Copy, CornerDownLeft, Printer, FileText } from "lucide-react";
import { Button } from "../ui/Button";
import { htmlDaFolha, copiarRico } from "./formatar";

interface Item {
  titulo: string;
  nome: string;
  modalidade: string;
  regiao: string;
  gatilhos: string[];
  lacunas: string[];
}

interface Grupo {
  grupo: string;
  modalidade: string;
  itens: Item[];
}

const bonito = (nome: string) =>
  nome.charAt(0).toUpperCase() + nome.slice(1).replace(/\s+/g, " ");

export const PrescricoesPage: React.FC = () => {
  const [grupos, setGrupos] = useState<Grupo[]>([]);
  const [busca, setBusca] = useState("");
  const [escolhida, setEscolhida] = useState("");
  const [texto, setTexto] = useState("");
  const [aviso, setAviso] = useState("");
  const folha = useRef<HTMLDivElement>(null);

  useEffect(() => {
    invoke<string>("rotrix_prescricoes", { titulo: "", busca: "" })
      .then((b) => {
        const d = JSON.parse(b || "{}") as { ok?: boolean; grupos?: Grupo[] };
        setGrupos(d.grupos || []);
      })
      .catch(() => setGrupos([]));
  }, []);

  const abrir = useCallback((titulo: string) => {
    setEscolhida(titulo);
    setAviso("");
    invoke<string>("rotrix_prescricoes", { titulo, busca: "" })
      .then((b) => {
        const d = JSON.parse(b || "{}") as { texto?: string };
        setTexto(d.texto || "");
      })
      .catch(() => setTexto(""));
  }, []);

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return grupos;
    return grupos
      .map((g) => ({
        ...g,
        itens: g.itens.filter(
          (i) =>
            i.nome.toLowerCase().includes(q) ||
            i.titulo.toLowerCase().includes(q) ||
            i.gatilhos.some((x) => x.includes(q)),
        ),
      }))
      .filter((g) => g.itens.length > 0);
  }, [grupos, busca]);

  // o texto do banco vira HTML com as lacunas destacadas e navegáveis por Tab
  const html = useMemo(() => {
    const esc = (s: string) =>
      s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return esc(texto)
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/\{([a-z_0-9]+)\|([^}]*)\}/g, (_m, _k, ops: string) => {
        const lista = ops.split("/").map((o) => `<option>${o}</option>`).join("");
        return `<select class="lacuna-op" tabindex="0">${lista}</select>`;
      })
      .replace(
        /\{([a-z_0-9]+)\}/g,
        (_m, k: string) =>
          `<span class="lacuna" contenteditable="true" tabindex="0" data-campo="${k}">&nbsp;&nbsp;&nbsp;&nbsp;</span>`,
      )
      .replace(/\n/g, "<br>");
  }, [texto]);

  const textoFinal = () => (folha.current?.innerText || "").replace(/ /g, " ").trim();

  const copiar = async () => {
    const t = textoFinal();
    if (!t) return;
    try {
      const rico = await copiarRico(htmlDaFolha(folha.current), t);
      setAviso(
        rico
          ? "prescrição copiada, com a formatação"
          : "prescrição copiada (sem formatação: o campo não aceita texto rico)",
      );
    } catch {
      setAviso("não consegui copiar");
    }
  };

  const colar = async () => {
    const t = textoFinal();
    if (!t) return;
    try {
      await invoke("rotrix_colar", { texto: t });
      setAviso("colado na janela que estava na frente");
    } catch (e) {
      setAviso(String(e));
    }
  };

  const imprimir = () => {
    const w = window.open("", "_blank", "width=800,height=900");
    if (!w) {
      setAviso("o navegador bloqueou a janela de impressão");
      return;
    }
    w.document.write(
      `<pre style="font:12pt/1.6 Arial,sans-serif;white-space:pre-wrap;padding:24px">${
        textoFinal().replace(/</g, "&lt;")
      }</pre>`,
    );
    w.document.close();
    w.print();
  };

  const vazias = (texto.match(/\{[a-z_0-9]+\}/g) || []).length;

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-mid-gray/20">
        <FileText size={15} />
        <span className="text-[13px] font-semibold">Prescrições</span>
        <span className="text-[11px] text-mid-gray">
          dose e volume saem em branco, de propósito
        </span>
        <div className="ms-auto relative">
          <Search size={13} className="absolute start-2 top-1/2 -translate-y-1/2 text-mid-gray" />
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="procurar"
            className="h-7 w-52 rounded-lg border border-mid-gray/25 bg-background ps-7 pe-2 text-[12px]"
          />
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        <div className="w-[250px] shrink-0 border-e border-mid-gray/20 overflow-y-auto p-2">
          {filtrados.map((g) => (
            <div key={g.grupo} className="mb-2">
              <div className="text-[9.5px] font-bold tracking-wider text-mid-gray px-1.5 pb-1">
                {g.grupo.toUpperCase()}
              </div>
              {g.itens.map((i) => (
                <button
                  key={i.titulo}
                  type="button"
                  onClick={() => abrir(i.titulo)}
                  className={`w-full text-start px-2 py-1.5 rounded-md text-[11.5px] cursor-pointer ${
                    escolhida === i.titulo
                      ? "bg-logo-primary/25 font-semibold"
                      : "hover:bg-mid-gray/15"
                  }`}
                >
                  {bonito(i.nome)}
                  {i.regiao && <span className="text-mid-gray"> · {i.regiao}</span>}
                </button>
              ))}
            </div>
          ))}
          {filtrados.length === 0 && (
            <div className="text-[11.5px] text-mid-gray p-2">
              nenhuma prescrição com esse nome
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-y-auto bg-white">
            {texto ? (
              <div
                ref={folha}
                className="min-h-full px-10 py-8 text-black text-[12.5px] leading-[1.7] outline-none [&_.lacuna]:bg-[#fdeef6] [&_.lacuna]:text-[#9d2168] [&_.lacuna]:rounded-sm [&_.lacuna]:px-1 [&_.lacuna]:font-semibold [&_.lacuna-op]:bg-[#fdeef6] [&_.lacuna-op]:text-[#9d2168] [&_.lacuna-op]:rounded-sm [&_.lacuna-op]:px-1 [&_.lacuna-op]:font-semibold [&_.lacuna-op]:border-0"
                dangerouslySetInnerHTML={{ __html: html }}
              />
            ) : (
              <div className="p-8 text-[12.5px] text-mid-gray">
                escolha uma prescrição à esquerda
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 px-3 py-2 border-t border-mid-gray/20 bg-background">
            <Button variant="primary" size="sm" disabled={!texto} onClick={() => void colar()}>
              <span className="flex items-center gap-1.5">
                <CornerDownLeft size={14} /> Colar no RIS
              </span>
            </Button>
            <Button variant="secondary" size="sm" disabled={!texto} onClick={() => void copiar()}>
              <span className="flex items-center gap-1.5">
                <Copy size={14} /> Copiar
              </span>
            </Button>
            <Button variant="secondary" size="sm" disabled={!texto} onClick={imprimir}>
              <span className="flex items-center gap-1.5">
                <Printer size={14} /> Imprimir
              </span>
            </Button>
            <span className="ms-auto text-[11px] text-mid-gray">
              {aviso ||
                (vazias
                  ? `${vazias} campo(s) para preencher · Tab pula de um para o outro`
                  : "clique no campo rosa para preencher")}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PrescricoesPage;
