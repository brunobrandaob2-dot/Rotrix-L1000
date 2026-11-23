// Fase 6 (Astryx): a caixa de texto é o TextArea do Astryx. Mesmas props de
// antes (value, onChange(evento), placeholder, rows, disabled, className).
import React from "react";
import { TextArea } from "@astryxdesign/core/TextArea";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  variant?: "default" | "compact";
}

export const Textarea: React.FC<TextareaProps> = ({
  className = "",
  variant = "default",
  value,
  onChange,
  placeholder,
  rows,
  disabled,
  "aria-label": ariaLabel,
  ...props
}) => (
  <TextArea
    {...(props as Record<string, unknown>)}
    containerClassName={className}
    label={ariaLabel || placeholder || "texto"}
    isLabelHidden
    value={String(value ?? "")}
    onChange={(_v, e) => onChange?.(e)}
    placeholder={placeholder}
    rows={rows ?? (variant === "compact" ? 3 : 4)}
    isDisabled={Boolean(disabled)}
    size={variant === "compact" ? "sm" : "md"}
  />
);
