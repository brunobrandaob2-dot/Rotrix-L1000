// Rotrix L-1000 v2 — ditado por botão, com o mesmo comportamento do atalho.
//
// Clique curto liga e o clique seguinte desliga (hold). Segurar grava enquanto
// o dedo estiver no botão e solta ao levantar. É o mesmo jeito do atalho do
// teclado, para que o botão não custe um clique a mais.
import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const SEGURAR_MS = 300; // igual ao hold_threshold_ms do Handy

export interface Ditado {
  /** está gravando por causa deste botão? */
  gravando: boolean;
  /** pointerdown do botão */
  apertou: () => void;
  /** pointerup / pointerleave do botão */
  soltou: () => void;
  erro: string;
}

/**
 * @param binding atalho equivalente ("transcribe" = ditado cru)
 * @param aoReceber chamado com o texto quando o ditado termina
 */
export function useDitado(
  binding: string,
  aoReceber: (texto: string) => void,
): Ditado {
  const [gravando, setGravando] = useState(false);
  const [erro, setErro] = useState("");
  const apertadoEm = useRef(0);
  const soltouCedo = useRef(false);
  const meu = useRef(false); // o ditado que está vindo é deste botão?
  const receber = useRef(aoReceber);
  receber.current = aoReceber;

  useEffect(() => {
    const p = listen<string>("rotrix-ditado", (e) => {
      setGravando(false);
      if (!meu.current) return;
      meu.current = false;
      receber.current(e.payload || "");
    });
    return () => {
      p.then((fn) => fn());
    };
  }, []);

  const parar = useCallback(async () => {
    setGravando(false);
    try {
      await invoke("rotrix_acao", { binding, comeco: false, paraFolha: true });
    } catch (e) {
      setErro(String(e));
    }
  }, [binding]);

  const apertou = useCallback(() => {
    if (gravando) {
      void parar();
      return;
    }
    apertadoEm.current = Date.now();
    soltouCedo.current = false;
    meu.current = true;
    setGravando(true);
    invoke("rotrix_acao", { binding, comeco: true, paraFolha: true }).catch(
      (e) => {
        setGravando(false);
        meu.current = false;
        setErro(String(e));
      },
    );
  }, [binding, gravando, parar]);

  const soltou = useCallback(() => {
    if (!apertadoEm.current) return;
    const tempo = Date.now() - apertadoEm.current;
    apertadoEm.current = 0;
    if (tempo < SEGURAR_MS) {
      soltouCedo.current = true; // clique curto: continua gravando (hold)
      return;
    }
    void parar();
  }, [parar]);

  return { gravando, apertou, soltou, erro };
}
