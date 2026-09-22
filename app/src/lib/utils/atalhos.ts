/**
 * Rotrix L-1000: atalho de teclado para os botões da tela.
 *
 * Uma letra por botão, sem combinação. Vale enquanto a janela do Rotrix está
 * na frente e o cursor não está dentro de um campo de texto. O texto do atalho
 * aparece quando você passa o mouse em cima do botão (`dica`).
 */
import { useEffect } from "react";

/** Texto do "title" do botão: o que ele faz e a tecla. */
export const dica = (texto: string, tecla?: string): string =>
  tecla ? `${texto} · tecla ${tecla.toUpperCase()}` : texto;

const digitando = (alvo: EventTarget | null): boolean => {
  const el = alvo as HTMLElement | null;
  if (!el || !el.tagName) return false;
  const t = el.tagName.toLowerCase();
  return t === "input" || t === "textarea" || t === "select" || el.isContentEditable === true;
};

/**
 * Liga uma tecla solta (sem Ctrl/Alt/Cmd) a uma ação da tela.
 * `ativo = false` desliga sem mudar a ordem dos hooks.
 */
export const useAtalho = (tecla: string, acao: () => void, ativo = true): void => {
  useEffect(() => {
    if (!ativo || !tecla) return;
    const alvo = tecla.toLowerCase();
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey || e.repeat) return;
      if (digitando(e.target)) return;
      if (e.key.toLowerCase() !== alvo) return;
      e.preventDefault();
      acao();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [tecla, acao, ativo]);
};
