// Rotrix v2, fase 6: os botões das telas da v2 são o Button do Astryx.
//
// Mesmas props do botão antigo (../ui/Button), para as telas não precisarem
// mudar: variant, size, disabled, title, className e os eventos (o ditado de
// "segurar para gravar" usa onPointerDown/Up/Leave e continua funcionando).
// O texto do botão vira o `label` do Astryx (o nome que o leitor de tela lê);
// ícone + texto continuam aparecendo como estavam.
import React from "react";
import { Button as AxButton } from "@astryxdesign/core/Button";

type Variante =
  | "primary"
  | "primary-soft"
  | "secondary"
  | "warning"
  | "danger"
  | "danger-ghost"
  | "ghost";

const VARIANTE: Record<Variante, "primary" | "secondary" | "ghost" | "destructive"> = {
  primary: "primary",
  "primary-soft": "secondary",
  secondary: "secondary",
  warning: "secondary",
  danger: "destructive",
  "danger-ghost": "destructive", // apagar arquivos: o vermelho avisa
  ghost: "ghost",
};

/** O texto que está dentro do botão (para o nome acessível). */
export const textoDe = (no: React.ReactNode): string => {
  if (no == null || typeof no === "boolean") return "";
  if (typeof no === "string" || typeof no === "number") return String(no);
  if (Array.isArray(no)) return no.map(textoDe).join("").replace(/\s+/g, " ").trim();
  if (React.isValidElement(no)) return textoDe((no.props as { children?: React.ReactNode }).children);
  return "";
};

export interface BotaoProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  variant?: Variante;
  size?: "sm" | "md" | "lg";
  type?: "button" | "submit" | "reset";
}

export const Botao: React.FC<BotaoProps> = ({
  children,
  variant = "primary",
  size = "md",
  disabled,
  title,
  type = "button",
  "aria-label": ariaLabel,
  ...resto
}) => {
  const texto = textoDe(children);
  const soTexto = typeof children === "string" || typeof children === "number";
  return (
    <AxButton
      {...(resto as Record<string, unknown>)}
      type={type}
      label={ariaLabel || texto || title || "botão"}
      variant={VARIANTE[variant]}
      size={size}
      isDisabled={Boolean(disabled)}
      tooltip={title}
    >
      {soTexto ? undefined : children}
    </AxButton>
  );
};

export default Botao;
