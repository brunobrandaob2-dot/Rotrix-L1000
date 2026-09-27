// Ctrl+C / Ctrl+X nas folhas copia o TEXTO, nunca a cor da tela.
//
// 27/09: no tema escuro a folha é cinza-chumbo com letra branca. Quando se
// seleciona e copia de um campo editável, o Chromium (WebView2) põe no clipboard
// o HTML com a cor CALCULADA de cada trecho — "color: rgb(255,255,255)". Colado
// no RIS ou no Word, o laudo sairia branco no branco: invisível. Aqui a cópia de
// qualquer folha (.papel ou a folha do Laudo) vai com o HTML que está no
// documento (negrito, parágrafos) e o texto puro — sem cor da tela.

import { htmlDaFolha } from "./formatar";

const DENTRO_DA_FOLHA = ".papel, [data-rotrix='folha']";

/** O HTML do que está selecionado, sem estilo calculado — só o que está no DOM. */
export const htmlDaSelecao = (sel: Selection): string => {
  const caixa = document.createElement("div");
  for (let i = 0; i < sel.rangeCount; i++) {
    caixa.appendChild(sel.getRangeAt(i).cloneContents());
  }
  return htmlDaFolha(caixa);
};

const aoCopiar = (e: ClipboardEvent) => {
  // textarea/input: o navegador já copia só texto
  const ativo = document.activeElement as HTMLElement | null;
  if (ativo && (ativo.tagName === "TEXTAREA" || ativo.tagName === "INPUT")) return;
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !e.clipboardData) return;
  const no = sel.getRangeAt(0).commonAncestorContainer;
  const el = no.nodeType === Node.ELEMENT_NODE ? (no as Element) : no.parentElement;
  if (!el || !el.closest(DENTRO_DA_FOLHA)) return;

  e.clipboardData.setData("text/html", htmlDaSelecao(sel));
  e.clipboardData.setData("text/plain", sel.toString());
  e.preventDefault();
  // recortar: apaga pelo próprio editor, para o Ctrl+Z continuar desfazendo
  if (e.type === "cut" && (el as HTMLElement).isContentEditable) {
    document.execCommand("delete");
  }
};

/** Liga a cópia limpa no documento inteiro. Devolve a função que desliga. */
export const ligarCopiaLimpa = (): (() => void) => {
  document.addEventListener("copy", aoCopiar);
  document.addEventListener("cut", aoCopiar);
  return () => {
    document.removeEventListener("copy", aoCopiar);
    document.removeEventListener("cut", aoCopiar);
  };
};
