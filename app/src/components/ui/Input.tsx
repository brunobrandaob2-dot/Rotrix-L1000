// Fase 6 (Astryx): o campo de texto é o TextInput do Astryx.
//
// Mesmas props de antes (as do <input>): value, onChange(evento), type,
// placeholder, disabled, className, onKeyDown, onBlur… O TextInput só aceita
// texto (text, password, email, search, tel, url); número e o resto continuam
// no <input> de antes. O nome acessível vem de aria-label ou do placeholder.
import React from "react";
import { TextInput } from "@astryxdesign/core/TextInput";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  variant?: "default" | "compact";
}

const TIPOS = new Set(["text", "password", "email", "search", "tel", "url"]);

export const Input: React.FC<InputProps> = ({
  className = "",
  variant = "default",
  disabled,
  type = "text",
  value,
  onChange,
  placeholder,
  "aria-label": ariaLabel,
  ...props
}) => {
  if (TIPOS.has(type) && (typeof value === "string" || value === undefined)) {
    return (
      <TextInput
        {...(props as Record<string, unknown>)}
        containerClassName={className}
        type={type as "text"}
        label={ariaLabel || placeholder || "campo"}
        isLabelHidden
        value={(value as string) ?? ""}
        onChange={(_v, e) => onChange?.(e)}
        placeholder={placeholder}
        isDisabled={Boolean(disabled)}
        size={variant === "compact" ? "sm" : "md"}
      />
    );
  }
  const baseClasses =
    "px-2 py-1 text-sm font-semibold bg-mid-gray/10 border border-mid-gray/80 rounded-md text-start transition-all duration-150";
  const interactiveClasses = disabled
    ? "opacity-60 cursor-not-allowed bg-mid-gray/10 border-mid-gray/40"
    : "hover:bg-logo-primary/10 hover:border-logo-primary focus:outline-none focus:bg-logo-primary/20 focus:border-logo-primary";
  const variantClasses = { default: "px-3 py-2", compact: "px-2 py-1" } as const;
  return (
    <input
      className={`${baseClasses} ${variantClasses[variant]} ${interactiveClasses} ${className}`}
      disabled={disabled}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      aria-label={ariaLabel}
      {...props}
    />
  );
};
