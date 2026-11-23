// Rotrix L-1000 v2 — balão de dica e o "?" de ajuda.
//
// O `title` do HTML não aparece de forma confiável dentro do WebView2 (o motor
// que o app usa no Windows): você deixa o mouse parado em cima do botão e não
// vem nada. 23/11 (fase 6): o balão agora é o Tooltip do Astryx — desenhado
// pelo app, como antes, mas com o tema, a posição que não sai da tela, o
// teclado (foco mostra o balão) e o Esc para fechar.
import React from "react";
import { CircleHelp } from "lucide-react";
import { Tooltip } from "@astryxdesign/core/Tooltip";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Kbd } from "@astryxdesign/core/Kbd";

export const Dica: React.FC<{
  texto: string;
  atalho?: string;
  lado?: "baixo" | "cima";
  children: React.ReactNode;
}> = ({ texto, atalho, lado = "baixo", children }) => {
  if (!texto) return <>{children}</>;
  return (
    <Tooltip
      content={
        atalho ? (
          <>
            {texto} <Kbd keys={atalho} />
          </>
        ) : (
          texto
        )
      }
      placement={lado === "cima" ? "above" : "below"}
      delay={350}
      hasHoverIndication={false}
    >
      {children}
    </Tooltip>
  );
};

// 22/11/2026 (v2): "essa informação não precisa estar escrita — um íconezinho de
// interrogação, passo o mouse e aparece a caixinha". Explicação fica atrás do ?,
// a tela fica só com o que importa. (O InfoTip do Astryx usa um "i"; ele pediu "?".)
export const Ajuda: React.FC<{ texto: string; lado?: "baixo" | "cima" }> = ({
  texto,
  lado = "baixo",
}) => (
  <Dica texto={texto} lado={lado}>
    <IconButton label={texto} icon={<CircleHelp size={14} />} variant="ghost" size="sm" />
  </Dica>
);

export default Dica;
