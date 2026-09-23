/* eslint-disable i18next/no-literal-string */
// Rotrix L-1000 v2 — balão de dica.
//
// O `title` do HTML não aparece de forma confiável dentro do WebView2 (o motor
// que o app usa no Windows): você deixa o mouse parado em cima do botão e não
// vem nada. Então o balão é desenhado por nós.
import React, { useRef, useState } from "react";

export const Dica: React.FC<{
  texto: string;
  atalho?: string;
  lado?: "baixo" | "cima";
  children: React.ReactNode;
}> = ({ texto, atalho, lado = "baixo", children }) => {
  const [aberto, setAberto] = useState(false);
  const espera = useRef<number | null>(null);

  const entrou = () => {
    if (espera.current) window.clearTimeout(espera.current);
    espera.current = window.setTimeout(() => setAberto(true), 350);
  };
  const saiu = () => {
    if (espera.current) window.clearTimeout(espera.current);
    setAberto(false);
  };

  return (
    <span
      className="relative inline-flex"
      onPointerEnter={entrou}
      onPointerLeave={saiu}
      onPointerDown={saiu}
    >
      {children}
      {aberto && texto && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute z-50 start-1/2 -translate-x-1/2 w-max max-w-[260px] rounded-lg border border-mid-gray/30 bg-background px-2 py-1.5 text-[11px] leading-snug shadow-lg ${
            lado === "cima" ? "bottom-full mb-1.5" : "top-full mt-1.5"
          }`}
        >
          {texto}
          {atalho && (
            <span className="ms-1.5 rounded bg-mid-gray/20 px-1 py-0.5 text-[10px] font-semibold">
              {atalho}
            </span>
          )}
        </span>
      )}
    </span>
  );
};

export default Dica;
