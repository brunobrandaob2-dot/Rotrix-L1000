// Fase 6 (Astryx): a lista de escolha é o Selector do Astryx.
//
// Mesmas props de antes. `onRefresh` (microfone, alto-falante) roda quando a
// lista vai abrir: o Selector não avisa que abriu, então é no clique/tecla.
import React from "react";
import { useTranslation } from "react-i18next";
import { Selector } from "@astryxdesign/core/Selector";

export interface DropdownOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface DropdownProps {
  options: DropdownOption[];
  className?: string;
  /** era a posição do menu antigo; o Selector se posiciona sozinho */
  menuClassName?: string;
  selectedValue: string | null;
  onSelect: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  onRefresh?: () => void;
}

export const Dropdown: React.FC<DropdownProps> = ({
  options,
  selectedValue,
  onSelect,
  className = "",
  placeholder = "Select an option...",
  disabled = false,
  onRefresh,
}) => {
  const { t } = useTranslation();
  return (
    <div
      className={`min-w-[200px] ${className}`}
      onPointerDownCapture={() => !disabled && onRefresh?.()}
      onKeyDownCapture={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) onRefresh?.();
      }}
    >
      <Selector
        label={placeholder}
        isLabelHidden
        options={options.map((o) => ({
          value: o.value,
          label: o.label,
          description: o.description,
          disabled: o.disabled,
        }))}
        value={selectedValue ?? undefined}
        onChange={(v) => {
          if (v != null) onSelect(v);
        }}
        placeholder={placeholder}
        isDisabled={disabled}
        emptyText={t("common.noOptionsFound")}
        width="100%"
        size="sm"
      />
    </div>
  );
};
