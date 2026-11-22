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

// 22/11/2026 (v2): "essa informação não precisa estar escrita — um íconezinho de
// interrogação, passo o mouse e aparece a caixinha". Explicação fica atrás do ?,
// a tela fica só com o que importa.
export const Ajuda: React.FC<{ texto: string; lado?: "baixo" | "cima" }> = ({
  texto,
  lado = "baixo",
}) => (
  <Dica texto={texto} lado={lado}>
    <span
      tabIndex={0}
      role="img"
      aria-label={texto}
      className="ms-1.5 inline-grid h-4 w-4 place-items-center rounded-full border border-mid-gray/50 text-[10px] font-semibold leading-none text-mid-gray cursor-help hover:border-logo-primary hover:text-logo-primary align-middle"
    >
      ?
    </span>
  </Dica>
);

export default Dica;
